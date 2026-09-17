"""Patient-scoped authorization shared by imaging and record routes."""

import os
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import and_, false, or_
from sqlalchemy.orm import Session

from models.db_models import (
    AccessGrant, AuditEvent, DepartmentMembership, Patient,
    PatientCareAssignment, Study, User,
)


def _role(user: User) -> str:
    return user.role.value if hasattr(user.role, "value") else user.role


def local_viewer_mode() -> bool:
    return os.getenv("LUNGTIC_LOCAL_VIEWER") == "1"


def visible_patients(db: Session, user: User, write: bool = False):
    """Return a SQL query so list and direct-ID routes use the same policy."""
    query = db.query(Patient)
    if local_viewer_mode() and _role(user) == "admin":
        return query
    if _role(user) == "patient" and not write:
        return query.filter(Patient.user_id == user.id)
    if _role(user) != "doctor":
        return query.filter(false())

    assignments = (
        db.query(PatientCareAssignment.patient_id)
        .join(
            DepartmentMembership,
            and_(
                DepartmentMembership.user_id == PatientCareAssignment.user_id,
                DepartmentMembership.department_id == PatientCareAssignment.department_id,
                DepartmentMembership.active.is_(True),
            ),
        )
        .filter(
            PatientCareAssignment.user_id == user.id,
            PatientCareAssignment.active.is_(True),
        )
    )
    now = datetime.utcnow()
    grants = (
        db.query(AccessGrant.patient_id)
        .filter(
            AccessGrant.grantee_user_id == user.id,
            AccessGrant.starts_at <= now,
            AccessGrant.expires_at > now,
            AccessGrant.revoked_at.is_(None),
            *([AccessGrant.can_write.is_(True)] if write else []),
        )
    )
    allowed = [Patient.id.in_(assignments), Patient.id.in_(grants)]
    if not write:
        headed_departments = (
            db.query(DepartmentMembership.department_id)
            .filter(
                DepartmentMembership.user_id == user.id,
                DepartmentMembership.active.is_(True),
                DepartmentMembership.is_head.is_(True),
            )
        )
        allowed.append(Patient.primary_department_id.in_(headed_departments))
    return query.filter(or_(*allowed))


def can_access_patient(db: Session, user: User, patient_id: int, write: bool = False) -> bool:
    return visible_patients(db, user, write).filter(Patient.id == patient_id).first() is not None


def audit(
    db: Session, user: User, action: str, resource_type: str,
    resource_id: int | None, patient_id: int | None, allowed: bool,
) -> None:
    db.add(AuditEvent(
        actor_user_id=user.id,
        patient_id=patient_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        allowed=allowed,
        created_at=datetime.utcnow(),
    ))
    db.commit()


def require_patient(
    db: Session, user: User, patient_id: int, *, write: bool = False,
    action: str = "view_patient",
) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    allowed = patient is not None and can_access_patient(db, user, patient_id, write)
    audit(db, user, action, "patient", patient_id, patient_id if patient else None, allowed)
    if not allowed:
        raise HTTPException(404, "Patient not found")
    return patient


def require_study(
    db: Session, user: User, study_id: int, *, write: bool = False,
    action: str = "view_study",
) -> Study:
    study = db.query(Study).filter(Study.id == study_id).first()
    if not study:
        audit(db, user, action, "study", study_id, None, False)
        raise HTTPException(404, "Study not found")
    if not can_access_patient(db, user, study.patient_id, write):
        audit(db, user, action, "study", study_id, study.patient_id, False)
        raise HTTPException(404, "Study not found")
    audit(db, user, action, "study", study_id, study.patient_id, True)
    return study


def upload_department(db: Session, user: User, requested_id: int | None = None) -> int:
    if local_viewer_mode() and _role(user) == "admin":
        return 0
    if _role(user) != "doctor":
        raise HTTPException(403, "Doctor account required")
    memberships = db.query(DepartmentMembership).filter(
        DepartmentMembership.user_id == user.id,
        DepartmentMembership.active.is_(True),
    ).all()
    if requested_id is not None:
        if any(m.department_id == requested_id for m in memberships):
            return requested_id
        raise HTTPException(403, "No active membership in this department")
    if len(memberships) != 1:
        raise HTTPException(400, "Specify an active department_id")
    return memberships[0].department_id


def assign_uploader(db: Session, patient: Patient, user: User, department_id: int) -> None:
    if local_viewer_mode() and _role(user) == "admin":
        return
    assignment = db.query(PatientCareAssignment).filter(
        PatientCareAssignment.patient_id == patient.id,
        PatientCareAssignment.user_id == user.id,
        PatientCareAssignment.department_id == department_id,
    ).first()
    if assignment is None:
        db.add(PatientCareAssignment(
            patient_id=patient.id, user_id=user.id,
            department_id=department_id, active=True,
        ))
    else:
        assignment.active = True



def patient_for_upload(
    db: Session, user: User, code: str, department_id: int,
    gender: str | None = None,
) -> Patient:
    code = str(code or "").strip()
    if not code or code.upper() in {"UNKNOWN", "NIFTI"} or len(code) > 32:
        raise HTTPException(400, "A valid patient code is required")
    patient = db.query(Patient).filter(Patient.patient_code == code).first()
    if patient is not None:
        if not can_access_patient(db, user, patient.id, write=True):
            raise HTTPException(404, "Patient not found")
        return patient
    patient = Patient(
        patient_code=code,
        gender=(gender or "")[:1] or None,
        user_id=user.id if local_viewer_mode() else None,
        primary_department_id=department_id or None,
    )
    db.add(patient)
    db.flush()
    assign_uploader(db, patient, user, department_id)
    db.flush()
    return patient
