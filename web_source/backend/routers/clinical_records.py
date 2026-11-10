"""Patient-scoped clinical attachment upload and retrieval."""

import os
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import RECORD_DIR
from database import get_db
from models.db_models import ClinicalRecord, Patient, Study, User
from routers.auth import get_current_user
from services.access_control import audit, can_access_patient, require_patient, upload_department, patient_for_upload
from services.record_crypto import (
    CHUNK_BYTES, IntegrityFailure, KeyUnavailable, seal_upload, verify_record,
)
from services.notification_service import create_notification

router = APIRouter(prefix="/api", tags=["clinical-records"])

CONTENT_TYPES = {
    ".pdf": ("application/pdf", b"%PDF-"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".jpg": ("image/jpeg", b"\xff\xd8"),
    ".jpeg": ("image/jpeg", b"\xff\xd8"),
    ".tici": ("application/x-tici", b"\x89HDF\r\n\x1a\n"),
    ".dcm": ("application/dicom", None),
}
RECORD_TYPES = {"report", "note", "image", "tici", "dicom", "other"}


def _record_metadata(record: ClinicalRecord) -> dict:
    return {
        "id": record.id,
        "patient_id": record.patient_id,
        "study_id": record.study_id,
        "record_type": record.record_type,
        "title": record.title,
        "original_filename": record.original_filename,
        "media_type": record.media_type,
        "size_bytes": record.size_bytes,
        "sha256": record.sha256,
        "ciphertext_sha256": record.ciphertext_sha256,
        "encryption": "AES-256-GCM" if record.encryption_version == 1 else "legacy",
        "uploaded_by_user_id": record.uploaded_by_user_id,
        "version": record.version,
        "patient_visible": record.patient_visible,
        "created_at": record.created_at,
    }


def _record_for_user(db: Session, user: User, record_id: int, action: str) -> ClinicalRecord:
    record = db.query(ClinicalRecord).filter(ClinicalRecord.id == record_id).first()
    if not record:
        raise HTTPException(404, "Record not found")
    require_patient(db, user, record.patient_id, action=action)
    role = user.role.value if hasattr(user.role, "value") else user.role
    if role == "patient" and not record.patient_visible:
        audit(db, user, action, "record", record_id, record.patient_id, False)
        raise HTTPException(404, "Record not found")
    audit(db, user, action, "record", record_id, record.patient_id, True)
    return record


def _storage_path(key: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}\.enc", key):
        raise HTTPException(500, "Invalid stored record key")
    return Path(RECORD_DIR) / key




class PatientCreate(BaseModel):
    patient_code: str = Field(min_length=1, max_length=32)
    department_id: int | None = None
    gender: str | None = Field(default=None, max_length=1)
    age_range: str | None = Field(default=None, max_length=16)


@router.post("/patients")
def create_patient(
    req: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    department_id = upload_department(db, current_user, req.department_id)
    patient = patient_for_upload(
        db, current_user, req.patient_code, department_id, req.gender
    )
    if req.age_range and patient.age_range is None:
        patient.age_range = req.age_range
    db.commit()
    audit(db, current_user, "create_or_open_patient", "patient", patient.id, patient.id, True)
    return {"id": patient.id, "patient_code": patient.patient_code}


@router.get("/patients/{patient_id}/access")
def patient_access(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_patient(db, current_user, patient_id, action="view_patient_access")
    return {"can_read": True, "can_write": can_access_patient(db, current_user, patient_id, write=True)}


@router.get("/patients/{patient_id}/records")
def list_records(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_patient(db, current_user, patient_id, action="list_records")
    query = db.query(ClinicalRecord).filter(ClinicalRecord.patient_id == patient_id)
    role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    if role == "patient":
        query = query.filter(ClinicalRecord.patient_visible.is_(True))
    return [_record_metadata(r) for r in query.order_by(ClinicalRecord.created_at.desc()).all()]


@router.post("/patients/{patient_id}/records")
def upload_record(
    patient_id: int,
    file: UploadFile = File(...),
    title: str = Form(...),
    record_type: str = Form("other"),
    study_id: int | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_patient(db, current_user, patient_id, write=True, action="upload_record")
    title = title.strip()
    if not title or len(title) > 256:
        raise HTTPException(400, "Title must be 1-256 characters")
    if record_type not in RECORD_TYPES:
        raise HTTPException(400, "Unsupported record type")
    if study_id is not None:
        study = db.query(Study).filter(Study.id == study_id, Study.patient_id == patient_id).first()
        if not study:
            raise HTTPException(404, "Study not found")
    filename = Path(file.filename or "").name[:256]
    ext = Path(filename).suffix.lower()
    if ext not in CONTENT_TYPES:
        raise HTTPException(400, "Unsupported file type")
    media_type, signature = CONTENT_TYPES[ext]
    os.makedirs(RECORD_DIR, exist_ok=True)
    key = f"{uuid.uuid4().hex}.enc"
    temp_path = Path(RECORD_DIR) / f"{key}.part"
    final_path = _storage_path(key)
    committed = False
    try:
        sealed = seal_upload(
            file.file, temp_path, patient_id=patient_id, storage_key=key
        )
        if sealed.size_bytes == 0:
            raise HTTPException(400, "Empty file")
        if ext == ".dcm":
            valid = len(sealed.head) >= 132 and sealed.head[128:132] == b"DICM"
        else:
            valid = sealed.head.startswith(signature)
        if not valid:
            raise HTTPException(400, "File content does not match extension")

        duplicate = db.query(ClinicalRecord).filter(
            ClinicalRecord.patient_id == patient_id,
            ClinicalRecord.sha256 == sealed.sha256,
            ClinicalRecord.size_bytes == sealed.size_bytes,
            ClinicalRecord.encryption_version == 1,
        ).first()
        if duplicate:
            verify_record(duplicate, _storage_path(duplicate.storage_key))
            audit(db, current_user, "duplicate_record_upload", "record", duplicate.id, patient_id, True)
            return _record_metadata(duplicate)

        record = ClinicalRecord(
            patient_id=patient_id, study_id=study_id,
            record_type=record_type, title=title,
            original_filename=filename,
            media_type=media_type, storage_key=key,
            size_bytes=sealed.size_bytes, sha256=sealed.sha256,
            ciphertext_sha256=sealed.ciphertext_sha256,
            encryption_version=1, key_id=sealed.key_id,
            wrapped_key=sealed.wrapped_key, wrap_nonce=sealed.wrap_nonce,
            file_nonce=sealed.file_nonce, file_tag=sealed.file_tag,
            uploaded_by_user_id=current_user.id,
            version=1, patient_visible=False,
            created_at=datetime.utcnow(),
        )
        db.add(record)
        db.flush()
        if final_path.exists():
            raise HTTPException(409, "Record storage key collision")
        os.replace(temp_path, final_path)
        verify_record(record, final_path)
        db.commit()
        committed = True
        db.refresh(record)
        audit(db, current_user, "upload_record", "record", record.id, patient_id, True)
        return _record_metadata(record)
    except Exception as exc:
        db.rollback()
        if not committed and final_path.exists():
            final_path.unlink()
        if isinstance(exc, ValueError) and str(exc) == "Record exceeds 512 MB":
            raise HTTPException(413, str(exc)) from exc
        if isinstance(exc, KeyUnavailable):
            raise HTTPException(503, "Record encryption key is unavailable") from exc
        if isinstance(exc, IntegrityFailure):
            raise HTTPException(409, "Stored record failed integrity verification") from exc
        raise
    finally:
        if temp_path.exists():
            temp_path.unlink()


class RecordVisibilityChange(BaseModel):
    patient_visible: bool


@router.put("/records/{record_id}/visibility")
def set_record_visibility(
    record_id: int,
    req: RecordVisibilityChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.query(ClinicalRecord).filter(ClinicalRecord.id == record_id).first()
    if not record:
        raise HTTPException(404, "Record not found")
    require_patient(db, current_user, record.patient_id, write=True, action="set_record_visibility")
    became_visible = req.patient_visible and not record.patient_visible
    record.patient_visible = req.patient_visible
    db.commit()
    audit(db, current_user, "set_record_visibility", "record", record_id, record.patient_id, True)
    if became_visible:
        patient = db.query(Patient).filter(Patient.id == record.patient_id).first()
        create_notification(
            db,
            user_id=patient.user_id if patient else None,
            kind="record_visible",
            title="新的病历资料",
            message="医师向您开放了一份新的病历资料，点击查看病例列表。",
            target_path="/dashboard/patients",
        )
    return _record_metadata(record)


@router.get("/records/{record_id}")
def get_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _record_metadata(_record_for_user(db, current_user, record_id, "view_record"))


def _verify_for_response(
    db: Session, user: User, record: ClinicalRecord, *, sink: BinaryIO | None = None
) -> None:
    if record.encryption_version != 1:
        audit(db, user, "legacy_record_blocked", "record", record.id, record.patient_id, False)
        raise HTTPException(409, "Legacy record requires encryption migration")
    try:
        verify_record(record, _storage_path(record.storage_key), sink=sink)
    except KeyUnavailable as exc:
        audit(db, user, "record_key_unavailable", "record", record.id, record.patient_id, False)
        raise HTTPException(503, "Record encryption key is unavailable") from exc
    except IntegrityFailure as exc:
        audit(db, user, "record_integrity_failed", "record", record.id, record.patient_id, False)
        raise HTTPException(409, "Stored record failed integrity verification") from exc
    audit(db, user, "verify_record", "record", record.id, record.patient_id, True)


@router.get("/records/{record_id}/integrity")
def check_record_integrity(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = _record_for_user(db, current_user, record_id, "check_record_integrity")
    _verify_for_response(db, current_user, record)
    return {
        "id": record.id, "valid": True,
        "algorithm": "AES-256-GCM",
        "sha256": record.sha256,
        "ciphertext_sha256": record.ciphertext_sha256,
    }


@router.get("/records/{record_id}/download")
def download_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = _record_for_user(db, current_user, record_id, "download_record")
    # Authenticate the full file before the first response byte is sent.
    plaintext = tempfile.TemporaryFile(mode="w+b", dir=RECORD_DIR)
    try:
        _verify_for_response(db, current_user, record, sink=plaintext)
        plaintext.seek(0)
    except Exception:
        plaintext.close()
        raise

    def chunks():
        try:
            while chunk := plaintext.read(CHUNK_BYTES):
                yield chunk
        finally:
            plaintext.close()

    return StreamingResponse(
        chunks(),
        media_type=record.media_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(record.original_filename)}",
            "Content-Length": str(record.size_bytes),
        },
    )
