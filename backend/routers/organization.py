"""Administrative organization and time-limited consultation access APIs."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import (
    AccessGrant, AuditEvent, Department, DepartmentMembership,
    Patient, PatientCareAssignment, User,
)
from routers.auth import get_current_user, require_admin
from services.access_control import audit

router = APIRouter(prefix="/api/organization", tags=["organization"])


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class MembershipChange(BaseModel):
    is_head: bool = False
    active: bool = True


class AssignmentChange(BaseModel):
    department_id: int
    active: bool = True
    set_primary: bool = False


class GrantCreate(BaseModel):
    grantee_user_id: int
    purpose: str = Field(min_length=1, max_length=256)
    hours: int = Field(ge=1, le=720)
    can_write: bool = False


def _doctor(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    role = user.role.value if user and hasattr(user.role, "value") else (user.role if user else None)
    if role != "doctor":
        raise HTTPException(400, "Active doctor account required")
    return user


def _head_of_patient(db: Session, user: User, patient: Patient) -> bool:
    if patient.primary_department_id is None:
        return False
    return db.query(DepartmentMembership).filter(
        DepartmentMembership.user_id == user.id,
        DepartmentMembership.department_id == patient.primary_department_id,
        DepartmentMembership.is_head.is_(True),
        DepartmentMembership.active.is_(True),
    ).first() is not None


def _can_manage_grants(db: Session, user: User, patient: Patient) -> bool:
    role = user.role.value if hasattr(user.role, "value") else user.role
    return role == "admin" or (role == "doctor" and _head_of_patient(db, user, patient))


@router.get("/departments")
def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return [
        {"id": department.id, "name": department.name}
        for department in db.query(Department).order_by(Department.name).all()
    ]


@router.post("/departments")
def create_department(
    req: DepartmentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "Department name required")
    if db.query(Department).filter(Department.name == name).first():
        raise HTTPException(409, "Department already exists")
    department = Department(name=name)
    db.add(department)
    db.commit()
    db.refresh(department)
    audit(db, admin, "create_department", "department", department.id, None, True)
    return {"id": department.id, "name": department.name}


@router.get("/departments/{department_id}/members")
def list_members(
    department_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if not db.query(Department).filter(Department.id == department_id).first():
        raise HTTPException(404, "Department not found")
    rows = db.query(DepartmentMembership, User).join(
        User, User.id == DepartmentMembership.user_id
    ).filter(DepartmentMembership.department_id == department_id).order_by(User.username).all()
    return [
        {"user_id": user.id, "username": user.username, "is_head": member.is_head,
         "active": member.active}
        for member, user in rows
    ]


@router.put("/departments/{department_id}/members/{user_id}")
def set_membership(
    department_id: int,
    user_id: int,
    req: MembershipChange,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if not db.query(Department).filter(Department.id == department_id).first():
        raise HTTPException(404, "Department not found")
    _doctor(db, user_id)
    member = db.query(DepartmentMembership).filter(
        DepartmentMembership.department_id == department_id,
        DepartmentMembership.user_id == user_id,
    ).first()
    if member is None:
        member = DepartmentMembership(department_id=department_id, user_id=user_id)
        db.add(member)
    member.is_head = req.is_head
    member.active = req.active
    db.commit()
    audit(db, admin, "set_membership", "department", department_id, None, True)
    return {"department_id": department_id, "user_id": user_id, "is_head": member.is_head, "active": member.active}


@router.get("/patients")
def list_patient_assignments(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    patients = db.query(Patient).order_by(Patient.id).offset(offset).limit(limit).all()
    audit(db, admin, "list_patient_assignments", "patient", None, None, True)
    return [
        {"id": patient.id, "patient_code": patient.patient_code,
         "primary_department_id": patient.primary_department_id}
        for patient in patients
    ]


@router.get("/patients/{patient_id}/care-team")
def list_care_team(
    patient_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if not db.query(Patient).filter(Patient.id == patient_id).first():
        raise HTTPException(404, "Patient not found")
    rows = db.query(PatientCareAssignment, User).join(
        User, User.id == PatientCareAssignment.user_id
    ).filter(PatientCareAssignment.patient_id == patient_id).order_by(User.username).all()
    return [
        {"user_id": user.id, "username": user.username,
         "department_id": assignment.department_id, "active": assignment.active}
        for assignment, user in rows
    ]


@router.put("/patients/{patient_id}/care-team/{user_id}")
def set_care_assignment(
    patient_id: int,
    user_id: int,
    req: AssignmentChange,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient not found")
    _doctor(db, user_id)
    membership = db.query(DepartmentMembership).filter(
        DepartmentMembership.user_id == user_id,
        DepartmentMembership.department_id == req.department_id,
        DepartmentMembership.active.is_(True),
    ).first()
    if not membership:
        raise HTTPException(400, "Doctor has no active membership in department")
    assignment = db.query(PatientCareAssignment).filter(
        PatientCareAssignment.patient_id == patient_id,
        PatientCareAssignment.user_id == user_id,
        PatientCareAssignment.department_id == req.department_id,
    ).first()
    if assignment is None:
        assignment = PatientCareAssignment(
            patient_id=patient_id, user_id=user_id,
            department_id=req.department_id,
        )
        db.add(assignment)
    assignment.active = req.active
    if req.set_primary:
        if not req.active:
            raise HTTPException(400, "Primary department requires active assignment")
        patient.primary_department_id = req.department_id
    db.commit()
    audit(db, admin, "set_care_assignment", "patient", patient_id, patient_id, True)
    return {"patient_id": patient_id, "user_id": user_id, "department_id": req.department_id, "active": assignment.active}


@router.get("/patients/{patient_id}/grants")
def list_grants(
    patient_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if not db.query(Patient).filter(Patient.id == patient_id).first():
        raise HTTPException(404, "Patient not found")
    rows = db.query(AccessGrant, User).join(
        User, User.id == AccessGrant.grantee_user_id
    ).filter(AccessGrant.patient_id == patient_id).order_by(AccessGrant.id.desc()).all()
    return [
        {"id": grant.id, "grantee_user_id": user.id, "grantee_username": user.username,
         "purpose": grant.purpose, "can_write": grant.can_write,
         "starts_at": grant.starts_at, "expires_at": grant.expires_at,
         "revoked_at": grant.revoked_at}
        for grant, user in rows
    ]


@router.post("/patients/{patient_id}/grants")
def create_grant(
    patient_id: int,
    req: GrantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient not found")
    if not _can_manage_grants(db, current_user, patient):
        raise HTTPException(403, "Grant manager required")
    _doctor(db, req.grantee_user_id)
    now = datetime.utcnow()
    grant = AccessGrant(
        patient_id=patient_id,
        grantee_user_id=req.grantee_user_id,
        granted_by_user_id=current_user.id,
        purpose=req.purpose.strip(),
        can_write=req.can_write,
        starts_at=now,
        expires_at=now + timedelta(hours=req.hours),
    )
    db.add(grant)
    db.commit()
    db.refresh(grant)
    audit(db, current_user, "create_grant", "grant", grant.id, patient_id, True)
    return {"id": grant.id, "patient_id": patient_id, "expires_at": grant.expires_at, "can_write": grant.can_write}


@router.delete("/grants/{grant_id}")
def revoke_grant(
    grant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    grant = db.query(AccessGrant).filter(AccessGrant.id == grant_id).first()
    patient = db.query(Patient).filter(Patient.id == grant.patient_id).first() if grant else None
    if not grant or not patient:
        raise HTTPException(404, "Grant not found")
    if not _can_manage_grants(db, current_user, patient):
        raise HTTPException(403, "Grant manager required")
    grant.revoked_at = datetime.utcnow()
    db.commit()
    audit(db, current_user, "revoke_grant", "grant", grant_id, patient.id, True)
    return {"id": grant_id, "revoked": True}


@router.get("/audit-events")
def list_audit_events(
    patient_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    limit = max(1, min(limit, 100))
    query = db.query(AuditEvent)
    if patient_id is not None:
        query = query.filter(AuditEvent.patient_id == patient_id)
    events = query.order_by(AuditEvent.id.desc()).limit(limit).all()
    return [
        {
            "id": event.id, "actor_user_id": event.actor_user_id,
            "patient_id": event.patient_id, "action": event.action,
            "resource_type": event.resource_type, "resource_id": event.resource_id,
            "allowed": event.allowed, "created_at": event.created_at,
        }
        for event in events
    ]
