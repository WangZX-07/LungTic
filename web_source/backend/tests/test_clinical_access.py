"""End-to-end authorization checks using synthetic patients and a temporary SQLite database."""
import io
import os
import base64
import json
import hashlib
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

os.environ["LUNGTIC_DB_URL"] = "sqlite://"
os.environ["LUNGTIC_JWT_SECRET"] = "integration-test-secret-32-characters-minimum"
os.environ["LUNGTIC_CAPTCHA_SECRET"] = "integration-test-captcha-secret-32-characters-minimum"
os.environ["LUNGTIC_CORS_ORIGINS"] = "http://127.0.0.1:5173"
os.environ["LUNGTIC_DATA_DIR"] = tempfile.mkdtemp(prefix="lungtic-test-data-")
os.environ["LUNGTIC_LOCAL_VIEWER"] = "0"
os.environ["LUNGTIC_RECORD_ACTIVE_KEY_ID"] = "test-v1"
os.environ["LUNGTIC_RECORD_KEYS_JSON"] = json.dumps({
    "test-v1": base64.b64encode(b"K" * 32).decode("ascii"),
    "test-v2": base64.b64encode(b"L" * 32).decode("ascii"),
})

import pytest
from fastapi.testclient import TestClient
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db
from models.db_models import (
    AccessGrant, AuditEvent, ClinicalRecord, Department, DepartmentMembership, Notification, Patient,
    PatientCareAssignment, Series, Slice, Study, User, UserRole,
    SmtpSetting,
)
from services.auth_service import create_access_token
from routers import clinical_records, dicom
from services import dicom_parser
from services.record_crypto import IntegrityFailure, KeyUnavailable, load_keyring, rewrap_record, verify_record
from services.notification_service import create_notification
from services import email_service
from services.email_service import get_smtp_config
from encrypt_legacy_records import migrate_record


@pytest.fixture
def api(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    def override_db():
        with Session() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(clinical_records, "RECORD_DIR", str(tmp_path / "records"))
    monkeypatch.setattr(dicom, "DICOM_DIR", str(tmp_path / "dicom"))
    monkeypatch.setattr(dicom_parser, "DICOM_DIR", str(tmp_path / "dicom"))
    monkeypatch.setattr(dicom, "_create_tici_from_upload", lambda *args: None)

    with Session() as db:
        users = [
            User(username=name, password_hash="unused", role=role)
            for name, role in [
                ("admin", UserRole.admin), ("doctor_a", UserRole.doctor),
                ("doctor_b", UserRole.doctor), ("head_a", UserRole.doctor),
                ("patient_a", UserRole.patient),
            ]
        ]
        db.add_all(users)
        db.flush()
        dept_a, dept_b = Department(name="Dept A"), Department(name="Dept B")
        db.add_all([dept_a, dept_b])
        db.flush()
        db.add_all([
            DepartmentMembership(user_id=users[1].id, department_id=dept_a.id),
            DepartmentMembership(user_id=users[2].id, department_id=dept_b.id),
            DepartmentMembership(user_id=users[3].id, department_id=dept_a.id, is_head=True),
        ])
        patient_a = Patient(
            patient_code="SYN-A", primary_department_id=dept_a.id, user_id=users[4].id
        )
        patient_b = Patient(patient_code="SYN-B", primary_department_id=dept_b.id)
        db.add_all([patient_a, patient_b])
        db.flush()
        db.add_all([
            PatientCareAssignment(
                patient_id=patient_a.id, user_id=users[1].id, department_id=dept_a.id
            ),
            PatientCareAssignment(
                patient_id=patient_b.id, user_id=users[2].id, department_id=dept_b.id
            ),
        ])
        study = Study(patient_id=patient_a.id, study_uid="synthetic-study", phase_count=1)
        db.add(study)
        db.flush()
        series = Series(study_id=study.id, series_uid="synthetic-series", phase_index=0)
        db.add(series)
        db.flush()
        dcm_path = tmp_path / "dicom" / "sample.dcm"
        dcm_path.parent.mkdir()
        dcm_path.write_bytes(b"synthetic image")
        slc = Slice(series_id=series.id, file_path="sample.dcm", slice_index=0)
        db.add(slc)
        db.commit()
        ids = {
            "patient_a": patient_a.id, "patient_b": patient_b.id,
            "study": study.id, "series": series.id, "slice": slc.id,
            "dept_a": dept_a.id, "dept_b": dept_b.id,
            **{u.username: u.id for u in users if u.username != "patient_a"},
            "patient_user": users[4].id,
        }

    def headers(name):
        role = "admin" if name == "admin" else "patient" if name == "patient_a" else "doctor"
        token = create_access_token(ids["patient_user"] if name == "patient_a" else ids[name], name, role)
        return {"Authorization": f"Bearer {token}"}

    with TestClient(app) as client:
        yield client, Session, ids, headers, tmp_path
    app.dependency_overrides.clear()
    engine.dispose()


def test_patient_lists_and_direct_ids_are_scoped(api):
    client, Session, ids, headers, _ = api
    for name, expected in [
        ("doctor_a", ["SYN-A"]), ("doctor_b", ["SYN-B"]),
        ("head_a", ["SYN-A"]), ("patient_a", ["SYN-A"]), ("admin", []),
    ]:
        response = client.get("/api/dicom/patients", headers=headers(name))
        assert response.status_code == 200, response.text
        assert [row["patient_code"] for row in response.json()] == expected

    for name in ("doctor_b", "admin"):
        for path in [
            f"/api/dicom/patients/{ids['patient_a']}/studies",
            f"/api/dicom/studies/{ids['study']}/series",
            f"/api/dicom/series/{ids['series']}/slices",
            f"/api/dicom/slice/{ids['slice']}/dicom",
            f"/api/segmentation/{ids['study']}/result",
            f"/api/tici/info/{ids['study']}",
        ]:
            response = client.get(path, headers=headers(name))
            assert response.status_code == 404, (name, path, response.text)
    admin_patients = client.get("/api/organization/patients", headers=headers("admin"))
    assert admin_patients.status_code == 200
    assert [row["patient_code"] for row in admin_patients.json()] == ["SYN-A", "SYN-B"]
    assert client.post(
        f"/api/tici/export/{ids['study']}", headers=headers("head_a")
    ).status_code == 404
    assert client.get(
        f"/api/patients/{ids['patient_a']}/access", headers=headers("head_a")
    ).json()["can_write"] is False
    assert client.get(
        f"/api/patients/{ids['patient_a']}/access", headers=headers("doctor_a")
    ).json()["can_write"] is True
    with Session() as db:
        denied = db.query(AuditEvent).filter(
            AuditEvent.actor_user_id == ids["doctor_b"], AuditEvent.allowed.is_(False)
        ).count()
        assert denied >= 4


def test_internal_notifications_are_user_scoped_and_actionable(api):
    client, Session, ids, headers, _ = api
    with Session() as db:
        assert create_notification(
            db,
            user_id=ids["doctor_a"],
            kind="test",
            title="Synthetic notification",
            message="Open the patient list.",
            target_path="/dashboard/patients",
        ) is True

    listed = client.get("/api/notifications", headers=headers("doctor_a"))
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1
    notification_id = listed.json()[0]["id"]
    assert listed.json()[0]["is_read"] is False
    assert client.get(
        "/api/notifications/unread-count", headers=headers("doctor_a")
    ).json()["count"] == 1

    assert client.put(
        f"/api/notifications/{notification_id}/read", headers=headers("doctor_b")
    ).status_code == 404
    assert client.put(
        f"/api/notifications/{notification_id}/read", headers=headers("doctor_a")
    ).status_code == 200
    assert client.get(
        "/api/notifications/unread-count", headers=headers("doctor_a")
    ).json()["count"] == 0

    grant = client.post(
        f"/api/organization/patients/{ids['patient_a']}/grants",
        headers=headers("head_a"),
        json={"grantee_user_id": ids["doctor_b"], "purpose": "consultation", "hours": 1},
    )
    assert grant.status_code == 200, grant.text
    doctor_b_messages = client.get(
        "/api/notifications", headers=headers("doctor_b")
    ).json()
    assert doctor_b_messages[0]["kind"] == "access_grant_created"
    serialized = json.dumps(doctor_b_messages, ensure_ascii=False)
    assert "SYN-A" not in serialized
    assert "consultation" not in serialized
    with Session() as db:
        assert db.query(Notification).filter(
            Notification.user_id == ids["doctor_b"]
        ).count() == 1


def test_admin_can_manage_and_test_encrypted_smtp_settings(api, monkeypatch):
    client, Session, _, headers, _ = api
    sent = {}

    class FakeSmtp:
        def __init__(self, host, port, timeout, **_):
            sent.update(host=host, port=port, timeout=timeout)

        def login(self, username, password):
            sent.update(username=username, password=password)

        def sendmail(self, sender, recipient, message):
            sent.update(sender=sender, recipient=recipient, message=message)

        def quit(self):
            sent["quit"] = True

    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", FakeSmtp)
    payload = {
        "enabled": True,
        "host": "smtp.example.com",
        "port": 465,
        "security": "ssl",
        "username": "mailer@example.com",
        "from_address": "mailer@example.com",
        "password": "smtp-authorization-secret",
    }
    assert client.put(
        "/api/admin/settings/smtp", headers=headers("doctor_a"), json=payload
    ).status_code == 403

    saved = client.put(
        "/api/admin/settings/smtp", headers=headers("admin"), json=payload
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["password_configured"] is True
    assert "password" not in saved.json()

    with Session() as db:
        row = db.query(SmtpSetting).filter(SmtpSetting.id == 1).one()
        assert "smtp-authorization-secret" not in row.password_ciphertext
        assert get_smtp_config(db).password == "smtp-authorization-secret"

    payload["password"] = ""
    retained = client.put(
        "/api/admin/settings/smtp", headers=headers("admin"), json=payload
    )
    assert retained.status_code == 200, retained.text
    tested = client.post(
        "/api/admin/settings/smtp/test",
        headers=headers("admin"),
        json={"recipient": "receiver@example.com"},
    )
    assert tested.status_code == 200, tested.text
    assert sent["host"] == "smtp.example.com"
    assert sent["password"] == "smtp-authorization-secret"
    assert sent["recipient"] == "receiver@example.com"
    assert sent["quit"] is True


def test_record_upload_visibility_grant_and_revoke(api):
    client, Session, ids, headers, tmp_path = api
    path = f"/api/patients/{ids['patient_a']}/records"
    payload = {"title": "Synthetic report", "record_type": "report"}
    file_data = b"%PDF-1.4\nsynthetic\n%%EOF"
    response = client.post(
        path, headers=headers("doctor_a"), data=payload,
        files={"file": ("test.pdf", file_data, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    record_id = response.json()["id"]
    assert response.json()["sha256"]
    encrypted_paths = list((tmp_path / "records").glob("*.enc"))
    assert len(encrypted_paths) == 1
    assert encrypted_paths[0].read_bytes() != file_data
    assert not encrypted_paths[0].read_bytes().startswith(b"%PDF-")
    assert response.json()["ciphertext_sha256"] == hashlib.sha256(encrypted_paths[0].read_bytes()).hexdigest()
    assert response.json()["encryption"] == "AES-256-GCM"
    duplicate = client.post(
        path, headers=headers("doctor_a"), data=payload,
        files={"file": ("again.pdf", file_data, "application/pdf")},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == record_id
    assert len(list((tmp_path / "records").glob("*.enc"))) == 1

    assert client.get(
        f"/api/records/{record_id}/integrity", headers=headers("doctor_a")
    ).json()["valid"] is True
    download = f"/api/records/{record_id}/download"
    assert client.get(download, headers=headers("doctor_a")).content == file_data
    assert client.get(download, headers=headers("head_a")).status_code == 200
    assert client.get(download, headers=headers("doctor_b")).status_code == 404
    assert client.get(download, headers=headers("admin")).status_code == 404
    assert client.get(download, headers=headers("patient_a")).status_code == 404
    assert client.post(
        path, headers=headers("head_a"), data=payload,
        files={"file": ("other.pdf", file_data + b"1", "application/pdf")},
    ).status_code == 404

    grant_response = client.post(
        f"/api/organization/patients/{ids['patient_a']}/grants",
        headers=headers("head_a"),
        json={"grantee_user_id": ids["doctor_b"], "purpose": "consultation", "hours": 1},
    )
    assert grant_response.status_code == 200, grant_response.text
    grant_id = grant_response.json()["id"]
    assert client.get(download, headers=headers("doctor_b")).status_code == 200
    assert client.post(
        path, headers=headers("doctor_b"), data=payload,
        files={"file": ("new.pdf", file_data + b"2", "application/pdf")},
    ).status_code == 404
    assert client.delete(
        f"/api/organization/grants/{grant_id}", headers=headers("head_a")
    ).status_code == 200
    assert client.get(download, headers=headers("doctor_b")).status_code == 404

    visibility = client.put(
        f"/api/records/{record_id}/visibility",
        headers=headers("doctor_a"), json={"patient_visible": True},
    )
    assert visibility.status_code == 200
    assert client.get(download, headers=headers("patient_a")).content == file_data
    assert [r["id"] for r in client.get(path, headers=headers("patient_a")).json()] == [record_id]

    invalid = client.post(
        path, headers=headers("doctor_a"), data=payload,
        files={"file": ("bad.pdf", b"bad content", "application/pdf")},
    )
    assert invalid.status_code == 400
    assert list((tmp_path / "records").glob("*.part")) == []


def test_assignment_and_expired_grant_take_effect_immediately(api):
    client, Session, ids, headers, _ = api
    path = f"/api/dicom/patients/{ids['patient_a']}/studies"
    assert client.get(path, headers=headers("doctor_a")).status_code == 200
    response = client.put(
        f"/api/organization/patients/{ids['patient_a']}/care-team/{ids['doctor_a']}",
        headers=headers("admin"),
        json={"department_id": ids["dept_a"], "active": False},
    )
    assert response.status_code == 200, response.text
    assert client.get(path, headers=headers("doctor_a")).status_code == 404
    assert client.get(path, headers=headers("head_a")).status_code == 200
    with Session() as db:
        db.add(AccessGrant(
            patient_id=ids["patient_a"], grantee_user_id=ids["doctor_b"],
            granted_by_user_id=ids["head_a"], purpose="expired",
            can_write=True, starts_at=datetime.utcnow()-timedelta(hours=2),
            expires_at=datetime.utcnow()-timedelta(hours=1),
        ))
        db.commit()
    assert client.get(path, headers=headers("doctor_b")).status_code == 404


def make_dicom(patient_code: str, study_uid: str) -> bytes:
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.PatientID = patient_code
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = generate_uid()
    ds.StudyDate = "20260917"
    ds.Modality = "CT"
    ds.PatientSex = "O"
    ds.InstanceNumber = 1
    ds.SliceLocation = 0
    ds.Rows = 2
    ds.Columns = 2
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.PixelData = b"\0" * 8
    buffer = io.BytesIO()
    ds.save_as(buffer, enforce_file_format=True)
    return buffer.getvalue()


def test_dicom_upload_keeps_real_bytes_and_cannot_claim_other_patient(api):
    client, Session, ids, headers, tmp_path = api
    source = make_dicom("SYN-B", generate_uid())
    response = client.post(
        "/api/dicom/upload", headers=headers("doctor_a"),
        data={"patient_id_override": "SYN-B"},
        files={"files": ("image.dcm", source, "application/dicom")},
    )
    assert response.status_code == 404, response.text
    assert list((tmp_path / "dicom").rglob("*.dcm")) == [tmp_path / "dicom" / "sample.dcm"]

    mixed = client.post(
        "/api/dicom/upload", headers=headers("doctor_a"),
        files=[
            ("files", ("first.dcm", make_dicom("SYN-TEMP", generate_uid()), "application/dicom")),
            ("files", ("second.dcm", make_dicom("SYN-B", generate_uid()), "application/dicom")),
        ],
    )
    assert mixed.status_code == 404
    assert list((tmp_path / "dicom").rglob("*.dcm")) == [tmp_path / "dicom" / "sample.dcm"]
    with Session() as db:
        assert db.query(Patient).filter(Patient.patient_code == "SYN-TEMP").count() == 0

    own = make_dicom("SYN-C", generate_uid())
    response = client.post(
        "/api/dicom/upload", headers=headers("doctor_a"),
        files={"files": ("image.dcm", own, "application/dicom")},
    )
    assert response.status_code == 200, response.text
    study_id = response.json()["studies"][0]["study_id"]
    with Session() as db:
        stored = db.query(Slice).join(Series, Slice.series_id == Series.id).filter(
            Series.study_id == study_id
        ).one()
        assert (tmp_path / "dicom" / stored.file_path).read_bytes() == own



def test_admin_can_bind_existing_patient_account(api):
    client, Session, ids, headers, _ = api
    weak = client.post(
        "/api/auth/users", headers=headers("admin"),
        json={"username": "new_patient", "password": "short", "role": "patient", "patient_code": "SYN-B"},
    )
    assert weak.status_code == 400
    created = client.post(
        "/api/auth/users", headers=headers("admin"),
        json={
            "username": "new_patient", "password": "long-synthetic-password-123",
            "role": "patient", "patient_code": "SYN-B",
        },
    )
    assert created.status_code == 200, created.text
    with Session() as db:
        patient = db.query(Patient).filter(Patient.id == ids["patient_b"]).one()
        assert patient.user_id == created.json()["id"]
        assert db.query(Patient).count() == 2



def test_uncompressed_nifti_upload(api):
    import nibabel as nib
    import numpy as np

    client, Session, ids, headers, tmp_path = api
    source_path = tmp_path / "source.nii"
    nib.save(nib.Nifti1Image(np.zeros((2, 2, 2), dtype=np.float32), np.eye(4)), source_path)
    response = client.post(
        "/api/dicom/upload", headers=headers("doctor_a"),
        data={"patient_id_override": "SYN-NIFTI"},
        files={"files": ("source.nii", source_path.read_bytes(), "application/octet-stream")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["studies"][0]["slice_count"] == 2



def test_tampering_blocks_plaintext_and_is_audited(api):
    client, Session, ids, headers, tmp_path = api
    response = client.post(
        f"/api/patients/{ids['patient_a']}/records",
        headers=headers("doctor_a"),
        data={"title": "Integrity test", "record_type": "report"},
        files={"file": ("safe.pdf", b"%PDF-1.4\nnot real patient data", "application/pdf")},
    )
    assert response.status_code == 200, response.text
    record_id = response.json()["id"]
    encrypted_path = next((tmp_path / "records").glob("*.enc"))
    damaged = bytearray(encrypted_path.read_bytes())
    damaged[0] ^= 1
    encrypted_path.write_bytes(damaged)
    for path in (f"/api/records/{record_id}/integrity", f"/api/records/{record_id}/download"):
        result = client.get(path, headers=headers("doctor_a"))
        assert result.status_code == 409, result.text
        assert b"%PDF-" not in result.content
    with Session() as db:
        assert db.query(AuditEvent).filter(
            AuditEvent.action == "record_integrity_failed",
            AuditEvent.resource_id == record_id,
            AuditEvent.allowed.is_(False),
        ).count() == 2


def test_master_key_rewrap_preserves_file_and_old_key_can_be_removed(api, monkeypatch):
    client, Session, ids, headers, tmp_path = api
    response = client.post(
        f"/api/patients/{ids['patient_a']}/records",
        headers=headers("doctor_a"),
        data={"title": "Rotation test"},
        files={"file": ("rotation.pdf", b"%PDF-1.4\nrotation", "application/pdf")},
    )
    assert response.status_code == 200, response.text
    record_id = response.json()["id"]
    encrypted_path = next((tmp_path / "records").glob("*.enc"))
    before = encrypted_path.read_bytes()
    with Session() as db:
        record = db.query(ClinicalRecord).filter(ClinicalRecord.id == record_id).one()
        _, keys = load_keyring()
        rewrap_record(record, "test-v2", keys)
        db.commit()
    assert encrypted_path.read_bytes() == before
    monkeypatch.setenv("LUNGTIC_RECORD_ACTIVE_KEY_ID", "test-v2")
    monkeypatch.setenv("LUNGTIC_RECORD_KEYS_JSON", json.dumps({
        "test-v2": base64.b64encode(b"L" * 32).decode("ascii"),
    }))
    download = client.get(f"/api/records/{record_id}/download", headers=headers("doctor_a"))
    assert download.status_code == 200
    assert download.content == b"%PDF-1.4\nrotation"



def test_offline_legacy_migration_checks_hash_and_removes_plaintext(api):
    client, Session, ids, headers, tmp_path = api
    record_dir = tmp_path / "records"
    record_dir.mkdir(exist_ok=True)
    old_key = "a" * 32 + ".pdf"
    plaintext = b"%PDF-1.4\nlegacy synthetic"
    old_path = record_dir / old_key
    old_path.write_bytes(plaintext)
    with Session() as db:
        record = ClinicalRecord(
            patient_id=ids["patient_a"], record_type="report",
            title="Legacy", original_filename="legacy.pdf",
            media_type="application/pdf", storage_key=old_key,
            size_bytes=len(plaintext), sha256=hashlib.sha256(plaintext).hexdigest(),
            encryption_version=0, uploaded_by_user_id=ids["doctor_a"],
            version=1, patient_visible=False, created_at=datetime.utcnow(),
        )
        db.add(record)
        db.commit()
        record_id = record.id
    blocked = client.get(f"/api/records/{record_id}/download", headers=headers("doctor_a"))
    assert blocked.status_code == 409
    assert plaintext not in blocked.content
    with Session() as db:
        record = db.query(ClinicalRecord).filter(ClinicalRecord.id == record_id).one()
        assert migrate_record(db, record, record_dir) is True
    assert not old_path.exists()
    assert len(list(record_dir.glob("*.enc"))) == 1
    result = client.get(f"/api/records/{record_id}/download", headers=headers("doctor_a"))
    assert result.status_code == 200
    assert result.content == plaintext


def test_missing_or_malformed_master_key_fails_closed(monkeypatch):
    monkeypatch.setenv("LUNGTIC_RECORD_KEYS_JSON", json.dumps({
        "test-v1": base64.b64encode(b"too short").decode("ascii")
    }))
    with pytest.raises(KeyUnavailable):
        load_keyring()



def test_ciphertext_is_bound_to_patient_and_storage_key(api):
    client, Session, ids, headers, tmp_path = api
    response = client.post(
        f"/api/patients/{ids['patient_a']}/records",
        headers=headers("doctor_a"),
        data={"title": "Binding test"},
        files={"file": ("binding.pdf", b"%PDF-1.4\nbinding", "application/pdf")},
    )
    assert response.status_code == 200
    with Session() as db:
        record = db.query(ClinicalRecord).filter(
            ClinicalRecord.id == response.json()["id"]
        ).one()
        path = tmp_path / "records" / record.storage_key
        record.patient_id = ids["patient_b"]
        with pytest.raises(IntegrityFailure):
            verify_record(record, path)
        db.rollback()


def test_segmentation_writes_saved_masks_to_tici(api, monkeypatch):
    import numpy as np
    from routers import segmentation
    from tici import TiciReader, TiciWriter

    client, _, ids, headers, tmp_path = api
    dcm_dir = tmp_path / "dicom"
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(str(dcm_dir / "sample.dcm"), {}, file_meta=meta, preamble=b"\0" * 128)
    ds.Rows, ds.Columns = 2, 2
    ds.BitsAllocated, ds.BitsStored, ds.HighBit = 16, 16, 15
    ds.PixelRepresentation, ds.SamplesPerPixel = 0, 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = np.array([[0, 1], [2, 3]], dtype=np.uint16).tobytes()
    ds.save_as(str(dcm_dir / "sample.dcm"))

    class Engine:
        def ensure_segmentation_loaded(self):
            pass
        def segment_slice(self, image):
            return np.ones(image.shape, dtype=np.uint8)

    monkeypatch.setattr(segmentation, "DICOM_DIR", str(dcm_dir))
    monkeypatch.setattr(segmentation, "TICI_DIR", str(tmp_path))
    monkeypatch.setattr(segmentation, "get_engine", lambda: Engine())
    tici_path = tmp_path / f"study_{ids['study']}.tici"
    with TiciWriter(str(tici_path), "w") as writer:
        writer.write_metadata({}, {"phase_count": 1})
        writer.write_phase_images(0, np.zeros((1, 2, 2), dtype=np.float32))

    response = client.post(
        "/api/segmentation/run", headers=headers("doctor_a"),
        json={"study_id": ids["study"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["slices_processed"] == 1
    with TiciReader(str(tici_path)) as reader:
        np.testing.assert_array_equal(reader.get_phase_masks(0), np.ones((1, 2, 2), dtype=np.uint8))


def test_admin_management_lists_are_role_guarded(api):
    client, _, ids, headers, _ = api
    paths = [
        f"/api/organization/departments/{ids['dept_a']}/members",
        f"/api/organization/patients/{ids['patient_a']}/care-team",
        f"/api/organization/patients/{ids['patient_a']}/grants",
    ]
    for path in paths:
        assert client.get(path, headers=headers("doctor_a")).status_code == 403
        assert client.get(path, headers=headers("patient_a")).status_code == 403
        response = client.get(path, headers=headers("admin"))
        assert response.status_code == 200, response.text
    members = client.get(paths[0], headers=headers("admin")).json()
    assert any(row["username"] == "head_a" and row["is_head"] for row in members)
    care = client.get(paths[1], headers=headers("admin")).json()
    assert any(row["username"] == "doctor_a" and row["active"] for row in care)
    grant = client.post(
        f"/api/organization/patients/{ids['patient_a']}/grants",
        headers=headers("admin"),
        json={"grantee_user_id": ids["doctor_b"], "purpose": "Review", "hours": 2},
    )
    assert grant.status_code == 200
    listed = client.get(paths[2], headers=headers("admin")).json()
    assert listed[0]["grantee_username"] == "doctor_b"
    assert listed[0]["revoked_at"] is None
