"""DICOM management API routes."""

import os
import io
import base64
import uuid
import sys
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from routers.auth import get_current_user
from models.db_models import User, Patient, Study, Series, Slice
from services.dicom_parser import parse_dicom, store_dicom, group_slices_by_phase, parse_nifti, study_storage_dir
from services.access_control import patient_for_upload, upload_department, visible_patients, require_patient, require_study, audit
from config import DICOM_DIR, TICI_DIR
from datetime import datetime

router = APIRouter(prefix="/api/dicom", tags=["dicom"])


def check_patient_access(patient: Patient, current_user: User, db: Session):
    return require_patient(db, current_user, patient.id)


def _create_tici_from_upload(study_id: int, study_uid: str, db: Session):
    """Create .tici file from uploaded DICOM files for a given study."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from tici import TiciWriter

        study = db.query(Study).filter(Study.id == study_id).first()
        if not study:
            return

        # Load DICOM dir for this study
        dicom_study_dir = os.path.join(DICOM_DIR, study_storage_dir(study_uid))
        if not os.path.isdir(dicom_study_dir):
            return

        dcm_files = [f for f in os.listdir(dicom_study_dir) if f.lower().endswith(".dcm")]
        if not dcm_files:
            return

        # Read first DICOM for metadata
        import pydicom
        first_path = os.path.join(dicom_study_dir, dcm_files[0])
        first_ds = pydicom.dcmread(first_path, force=True)

        # Patient metadata
        patient_obj = db.query(Patient).filter(Patient.id == study.patient_id).first()
        patient_dict = {
            "patient_id": str(getattr(first_ds, "PatientID", "UNKNOWN")),
            "patient_name": str(getattr(first_ds, "PatientName", "UNKNOWN")),
            "patient_sex": str(getattr(first_ds, "PatientSex", "")),
            "patient_age": str(getattr(first_ds, "PatientAge", "")),
        }

        rows = int(getattr(first_ds, "Rows", 512))
        cols = int(getattr(first_ds, "Columns", 512))

        import re
        ps_str = str(getattr(first_ds, "PixelSpacing", "[1, 1]"))
        nums = re.findall(r"[\d.]+", ps_str)
        pixel_spacing = [float(nums[0]) if len(nums) > 0 else 1.0,
                         float(nums[1]) if len(nums) > 1 else 1.0]

        slice_thickness = float(getattr(first_ds, "SliceThickness", 1.0))

        # Collect all slices grouped by phase
        all_slices = []
        for fname in dcm_files:
            try:
                ds = pydicom.dcmread(os.path.join(dicom_study_dir, fname), force=True)
                inst = int(getattr(ds, "InstanceNumber", 0))
                sloc = float(getattr(ds, "SliceLocation", 0))
                all_slices.append({
                    "path": os.path.join(dicom_study_dir, fname),
                    "instance": inst,
                    "phase": inst % 10,
                    "z": sloc,
                })
            except Exception:
                continue

        # Group by phase
        phases: dict[int, list] = {}
        for s in all_slices:
            p = s["phase"]
            if p not in phases:
                phases[p] = []
            phases[p].append(s)

        for p in phases:
            phases[p].sort(key=lambda x: x["z"])

        max_slices = max(len(v) for v in phases.values()) if phases else 0
        slice_locations = sorted(set(s["z"] for s in all_slices))

        # Normalize min/max across all files
        pmin, pmax = float("inf"), float("-inf")
        phase_pixel_data = {}
        for phase_idx, slist in phases.items():
            pixel_list = []
            for s in slist:
                ds = pydicom.dcmread(s["path"], force=True)
                pixels = ds.pixel_array.astype(np.float32)
                pmin = min(pmin, pixels.min())
                pmax = max(pmax, pixels.max())
                pixel_list.append(pixels)
            phase_pixel_data[phase_idx] = pixel_list

        # Study metadata
        study_dict = {
            "study_uid": study_uid,
            "study_date": str(getattr(first_ds, "StudyDate", "")),
            "modality": str(getattr(first_ds, "Modality", "CT")),
            "phase_count": len(phases),
            "rows": rows,
            "cols": cols,
            "slice_count": max_slices,
            "pixel_spacing": pixel_spacing,
            "slice_thickness": slice_thickness,
            "slice_locations": slice_locations,
        }

        # Write .tici
        tici_name = f"study_{study_id}.tici"
        tici_path = os.path.join(TICI_DIR, tici_name)
        os.makedirs(TICI_DIR, exist_ok=True)

        with TiciWriter(tici_path, "w") as w:
            w.write_metadata(patient_dict, study_dict)
            for phase_idx in sorted(phases.keys()):
                vol_pixels = phase_pixel_data[phase_idx]
                if pmax > pmin:
                    vol_pixels = [(p - pmin) / (pmax - pmin) for p in vol_pixels]
                vol = np.stack(vol_pixels, axis=0).astype(np.float32)
                w.write_phase_images(phase_idx, vol)
            w.write_provenance({
                "source_type": "dicom",
                "source_files_count": len(dcm_files),
                "converter_version": "LungTic-1.0.0",
                "conversion_date": datetime.now().isoformat(),
            })

        # Update study record
        study.tici_path = tici_path
        db.commit()

    except Exception:
        pass  # Silently skip .tici creation on failure; data is still in DB


@router.post("/upload")
def upload_dicom(
    files: list[UploadFile] = File(...),
    patient_id_override: str = Form(""),
    department_id: int | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload multiple DICOM files. Auto-parses metadata and stores slices."""
    if not files or len(files) > 512:
        raise HTTPException(400, "Upload 1-512 files")
    department_id = upload_department(db, current_user, department_id)

    # Separate DICOM and NIfTI files
    dicom_files = []
    nifti_files = []
    for file in files:
        fn = (file.filename or "").lower()
        if fn.endswith(".nii") or fn.endswith(".nii.gz"):
            nifti_files.append(file)
        else:
            dicom_files.append(file)

    written_paths = []
    if dicom_files and nifti_files:
        raise HTTPException(400, "Upload DICOM and NIfTI in separate requests")

    try:
        results = []

        # Process DICOM files
        if dicom_files:
            results.extend(_process_dicom(dicom_files, db, current_user, patient_id_override, department_id, written_paths))

        # Process NIfTI files
        if nifti_files:
            results.extend(_process_nifti(nifti_files, db, current_user, patient_id_override, department_id, written_paths))

        db.commit()
    except Exception:
        db.rollback()
        for stored in written_paths:
            try:
                os.remove(os.path.join(DICOM_DIR, stored))
            except FileNotFoundError:
                pass
        raise
    total = sum(r.get("slice_count", 0) for r in results)

    # Auto-create .tici files for each study
    for result_item in results:
        study_id = result_item.get("study_id")
        study_uid = result_item.get("study_uid")
        if study_id and study_uid:
            _create_tici_from_upload(study_id, study_uid, db)
        audit(db, current_user, "upload_imaging", "study", study_id, result_item.get("patient_id"), True)

    return {"status": "ok", "studies": results, "total_files": total}


def _process_dicom(files, db, current_user, patient_id_override="", department_id=0, written_paths=None):
    parsed = []
    total_bytes = 0
    for file in files:
        if not (file.filename or "").lower().endswith(".dcm"):
            raise HTTPException(400, "Only .dcm and NIfTI files are accepted")
        file_data = file.file.read(64 * 1024 * 1024 + 1)
        total_bytes += len(file_data)
        if len(file_data) > 64 * 1024 * 1024 or total_bytes > 512 * 1024 * 1024:
            raise HTTPException(413, "DICOM upload exceeds size limit")
        try:
            meta = parse_dicom(io.BytesIO(file_data))
            if str(meta["patient_id"]).upper() == "UNKNOWN":
                raise ValueError("DICOM PatientID is missing")
            meta["filename"] = file.filename
            meta["_content"] = file_data
            parsed.append(meta)
        except Exception:
            raise HTTPException(400, "Invalid DICOM file")

    if not parsed:
        raise HTTPException(400, "No valid DICOM files")

    # Group by study
    study_groups: dict[str, list[dict]] = {}
    for p in parsed:
        uid = p["study_uid"]
        if uid not in study_groups:
            study_groups[uid] = []
        study_groups[uid].append(p)

    results = []
    for study_uid, slices in study_groups.items():
        first = slices[0]

        # Find or create patient
        search_code = patient_id_override if patient_id_override else first["patient_id"]

        patient = patient_for_upload(
            db, current_user, search_code, department_id, first["patient_sex"]
        )

        # Find or create study
        study = db.query(Study).filter(Study.study_uid == study_uid).first()
        if study and study.patient_id != patient.id:
            raise HTTPException(409, "Study UID belongs to another patient")
        if not study:
            study_date = None
            if first["study_date"] and len(first["study_date"]) >= 8:
                try:
                    study_date = datetime.strptime(first["study_date"][:8], "%Y%m%d").date()
                except ValueError:
                    pass
            study = Study(
                patient_id=patient.id,
                study_uid=study_uid,
                study_date=study_date,
                phase_count=10,
            )
            db.add(study)
            db.flush()

        # Group by phase
        phases = group_slices_by_phase(slices)

        for phase_idx in sorted(phases.keys()):
            phase_slices = phases[phase_idx]

            series_uid = f"{study_uid}_{phase_idx}"
            series = (
                db.query(Series)
                .filter(Series.series_uid == series_uid)
                .first()
            )
            if not series:
                series = Series(
                    study_id=study.id,
                    series_uid=series_uid,
                    phase_index=phase_idx,
                    slice_count=0,
                )
                db.add(series)
                db.flush()

            series_slice_count = 0
            for s in phase_slices:
                file_path = store_dicom(
                    file_content=s["_content"],
                    filename=s["filename"],
                    study_uid=study_uid,
                )
                if written_paths is not None:
                    written_paths.append(file_path)
                slc = Slice(
                    series_id=series.id,
                    file_path=file_path,
                    slice_index=s["instance_number"],
                    z_position=s["slice_location"],
                )
                db.add(slc)
                series_slice_count += 1

            series.slice_count = series_slice_count

        results.append({
            "study_uid": study_uid,
            "study_id": study.id,
            "patient_id": patient.id,
            "phase_count": len(phases),
            "slice_count": len(slices),
        })

    return results


def _process_nifti(files, db, current_user, patient_id_override="", department_id=0, written_paths=None):
    if not patient_id_override.strip():
        raise HTTPException(400, "NIfTI upload requires patient_id_override")
    parsed = []
    total_bytes = 0
    for file in files:
        file_data = file.file.read(512 * 1024 * 1024 + 1)
        total_bytes += len(file_data)
        if len(file_data) > 512 * 1024 * 1024 or total_bytes > 512 * 1024 * 1024:
            raise HTTPException(413, "NIfTI upload exceeds size limit")
        suffix = ".nii" if (file.filename or "").lower().endswith(".nii") else ".nii.gz"
        tmp_path = os.path.join(DICOM_DIR, f"_nifti_{uuid.uuid4().hex}{suffix}")
        os.makedirs(DICOM_DIR, exist_ok=True)
        try:
            with open(tmp_path, "wb") as target:
                target.write(file_data)
            parsed.extend(parse_nifti(tmp_path))
        except Exception:
            raise HTTPException(400, "Invalid NIfTI file")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    if not parsed:
        raise HTTPException(400, "No valid NIfTI data")

    # Group by study_uid, but also consider time_index
    study_slices: dict[str, list[dict]] = {}
    for p in parsed:
        uid = p["study_uid"]
        if uid not in study_slices:
            study_slices[uid] = []
        study_slices[uid].append(p)

    results = []
    for study_uid, slices in study_slices.items():
        first = slices[0]
        search_code = patient_id_override if patient_id_override else first["patient_id"]

        patient = patient_for_upload(
            db, current_user, search_code, department_id, first["patient_sex"]
        )

        study = db.query(Study).filter(Study.study_uid == study_uid).first()
        if study and study.patient_id != patient.id:
            raise HTTPException(409, "Study UID belongs to another patient")
        if not study:
            study = Study(
                patient_id=patient.id,
                study_uid=study_uid,
                phase_count=10,
            )
            db.add(study)
            db.flush()

        # Group by time_index
        time_groups: dict[int, list[dict]] = {}
        for s in slices:
            t = s.get("time_index", 0)
            if t not in time_groups:
                time_groups[t] = []
            time_groups[t].append(s)

        for time_idx in sorted(time_groups.keys()):
            t_slices = time_groups[time_idx]

            series_uid = f"{study_uid}_{time_idx}"
            series = (
                db.query(Series)
                .filter(Series.series_uid == series_uid)
                .first()
            )
            if not series:
                series = Series(
                    study_id=study.id,
                    series_uid=series_uid,
                    phase_index=time_idx,
                    slice_count=0,
                )
                db.add(series)
                db.flush()

            series_slice_count = 0
            for s in t_slices:
                file_path = store_dicom(
                    file_content=s.get("nifti_data", b""),
                    filename=f"nifti_slice_{s['instance_number']}.raw",
                    study_uid=study_uid,
                )
                if written_paths is not None:
                    written_paths.append(file_path)
                slc = Slice(
                    series_id=series.id,
                    file_path=file_path,
                    slice_index=s["instance_number"],
                    z_position=s["slice_location"],
                )
                db.add(slc)
                series_slice_count += 1

            series.slice_count = series_slice_count

        results.append({
            "study_uid": study_uid,
            "study_id": study.id,
            "patient_id": patient.id,
            "phase_count": len(time_groups),
            "slice_count": len(slices),
        })

    return results


@router.get("/patients")
def list_patients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all patients accessible to the current user."""
    patients = visible_patients(db, current_user).order_by(Patient.id).all()
    audit(db, current_user, "list_patients", "patient", None, None, True)

    result = []
    for p in patients:
        study_count = db.query(Study).filter(Study.patient_id == p.id).count()
        result.append({
            "id": p.id,
            "patient_code": p.patient_code,
            "gender": p.gender,
            "age_range": p.age_range,
            "study_count": study_count,
            "created_at": str(p.created_at) if p.created_at else "",
        })
    return result


@router.get("/patients/{patient_id}/studies")
def list_studies(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List studies for a patient."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient not found")
    check_patient_access(patient, current_user, db)

    studies = db.query(Study).filter(Study.patient_id == patient_id).all()
    return [
        {
            "id": s.id,
            "study_uid": s.study_uid,
            "study_date": str(s.study_date) if s.study_date else "",
            "phase_count": s.phase_count,
            "has_tici": bool(s.tici_path and os.path.isfile(s.tici_path)),
        }
        for s in studies
    ]


@router.get("/studies/{study_id}/series")
def list_series(
    study_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List series (phases) for a study."""
    require_study(db, current_user, study_id)

    series_list = (
        db.query(Series)
        .filter(Series.study_id == study_id)
        .order_by(Series.phase_index)
        .all()
    )
    return [
        {
            "id": s.id,
            "phase_index": s.phase_index,
            "slice_count": s.slice_count,
            "series_uid": s.series_uid,
        }
        for s in series_list
    ]


@router.get("/series/{series_id}/slices")
def list_slices(
    series_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List slices for a series (phase)."""
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(404, "Series not found")
    require_study(db, current_user, series.study_id)

    slices = (
        db.query(Slice)
        .filter(Slice.series_id == series_id)
        .order_by(Slice.z_position)
        .all()
    )
    return [
        {
            "id": s.id,
            "slice_index": s.slice_index,
            "z_position": s.z_position,
        }
        for s in slices
    ]


@router.get("/slice/{slice_id}/image")
def get_slice_image(
    slice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the DICOM slice as base64 PNG image."""
    slc = db.query(Slice).filter(Slice.id == slice_id).first()
    if not slc:
        raise HTTPException(404, "Slice not found")

    series = db.query(Series).filter(Series.id == slc.series_id).first()
    if not series:
        raise HTTPException(404, "Slice not found")
    require_study(db, current_user, series.study_id, action="view_slice")

    full_path = os.path.join(DICOM_DIR, slc.file_path) if slc.file_path else ""
    if not os.path.exists(full_path):
        raise HTTPException(404, "File not found on disk")

    import numpy as np

    if full_path.endswith(".raw"):
        with open(full_path, "rb") as f:
            raw = f.read()
        side = int(np.sqrt(len(raw) // 4))
        pixel_array = np.frombuffer(raw, dtype=np.float32).reshape((side, side))
    else:
        import pydicom
        ds = pydicom.dcmread(full_path)
        pixel_array = ds.pixel_array.astype(np.float32)

    if pixel_array.max() > pixel_array.min():
        pixel_array = (pixel_array - pixel_array.min()) / (pixel_array.max() - pixel_array.min())
    pixel_array = (pixel_array * 255).astype(np.uint8)

    from PIL import Image
    img = Image.fromarray(pixel_array)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return {
        "slice_id": slice_id,
        "width": pixel_array.shape[1],
        "height": pixel_array.shape[0],
        "image_base64": base64.b64encode(buf.read()).decode("utf-8"),
    }


# ---- WADO-URI endpoint for Cornerstone.js ----

@router.get("/slice/{slice_id}/dicom")
def get_slice_dicom_raw(
    slice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return raw DICOM bytes for Cornerstone.js WADO-URI loader."""
    slc = db.query(Slice).filter(Slice.id == slice_id).first()
    if not slc:
        raise HTTPException(404, "Slice not found")

    series = db.query(Series).filter(Series.id == slc.series_id).first()
    if not series:
        raise HTTPException(404, "Slice not found")
    require_study(db, current_user, series.study_id, action="view_slice")

    full_path = os.path.join(DICOM_DIR, slc.file_path) if slc.file_path else ""
    if not os.path.exists(full_path):
        raise HTTPException(404, "File not found on disk")

    # For .dcm files, return raw bytes
    if full_path.endswith(".dcm"):
        with open(full_path, "rb") as f:
            return Response(content=f.read(), media_type="application/dicom")

    # For .raw files (NIfTI), wrap in a minimal DICOM
    import numpy as np
    import pydicom
    from pydicom.dataset import Dataset, FileDataset

    with open(full_path, "rb") as f:
        raw = f.read()
    side = int(np.sqrt(len(raw) // 4))
    pixel_array = np.frombuffer(raw, dtype=np.float32).reshape((side, side))

    # Normalize to uint16 for DICOM
    if pixel_array.max() > pixel_array.min():
        pixel_array = (pixel_array - pixel_array.min()) / (pixel_array.max() - pixel_array.min())
    pixel_array = (pixel_array * 4095).astype(np.uint16)

    ds = Dataset()
    ds.PatientName = "NIFTI"
    ds.PatientID = "NIFTI"
    ds.Modality = "CT"
    ds.Rows = side
    ds.Columns = side
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.HighBit = 11
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = pixel_array.tobytes()

    buf = io.BytesIO()
    ds.save_as(buf)
    buf.seek(0)
    return Response(content=buf.read(), media_type="application/dicom")


# ---- Delete patient ----

@router.delete("/patients/{patient_id}")
def delete_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a patient and all related data. Admin only."""
    user_role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    if user_role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient not found")
    raise HTTPException(403, "Patient deletion requires a reviewed retention workflow")
