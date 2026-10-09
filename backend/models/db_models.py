from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Enum, Text, ForeignKey, Boolean, UniqueConstraint, BigInteger
from sqlalchemy.orm import relationship
from database import Base
import enum


class UserRole(str, enum.Enum):
    doctor = "doctor"
    admin = "admin"
    patient = "patient"


class ModelType(str, enum.Enum):
    pth = "pth"
    onnx = "onnx"


class TaskType(str, enum.Enum):
    segmentation = "segmentation"
    prediction = "prediction"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.doctor)
    patient_code = Column(String(32), nullable=True)
    email = Column(String(128), nullable=True)
    phone = Column(String(20), nullable=True)
    created_at = Column(DateTime)


class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_code = Column(String(32), unique=True, nullable=False)
    age_range = Column(String(16))
    gender = Column(String(1))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    primary_department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    created_at = Column(DateTime)
    studies = relationship("Study", back_populates="patient")
    user = relationship("User", foreign_keys=[user_id])


class Study(Base):
    __tablename__ = "studies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    study_uid = Column(String(128), unique=True, nullable=False)
    study_date = Column(Date)
    phase_count = Column(Integer, default=10)
    tici_path = Column(String(512), nullable=True)
    patient = relationship("Patient", back_populates="studies")


class Series(Base):
    __tablename__ = "series"
    id = Column(Integer, primary_key=True, autoincrement=True)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=False)
    series_uid = Column(String(128))
    phase_index = Column(Integer, nullable=False)
    slice_count = Column(Integer)


class Slice(Base):
    __tablename__ = "slices"
    id = Column(Integer, primary_key=True, autoincrement=True)
    series_id = Column(Integer, ForeignKey("series.id"), nullable=False)
    file_path = Column(String(512))
    slice_index = Column(Integer)
    z_position = Column(Float)


class Segmentation(Base):
    __tablename__ = "segmentations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    slice_id = Column(Integer, ForeignKey("slices.id"), unique=True, nullable=False)
    mask_path = Column(String(512))
    dice_score = Column(Float)
    model_version = Column(String(32))
    created_at = Column(DateTime)


class IgtvResult(Base):
    __tablename__ = "igtv_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    study_id = Column(Integer, ForeignKey("studies.id"), unique=True, nullable=False)
    volume_cc = Column(Float)
    mesh_path = Column(String(512))
    created_at = Column(DateTime)


class Trajectory(Base):
    __tablename__ = "trajectories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=False)
    phase_index = Column(Integer, nullable=False)
    x_pos = Column(Float)
    y_pos = Column(Float)
    z_pos = Column(Float)
    is_predicted = Column(Integer, default=0)


class UserModel(Base):
    __tablename__ = "user_models"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    model_name = Column(String(128), nullable=False)
    model_type = Column(Enum(ModelType), nullable=False)
    task_type = Column(Enum(TaskType), nullable=False)
    file_path = Column(String(512))
    is_active = Column(Integer, default=0)
    uploaded_at = Column(DateTime)


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String(32), nullable=False)
    access_token = Column(Text)
    refresh_token = Column(Text)
    expires_at = Column(DateTime)


class PasswordReset(Base):
    __tablename__ = "password_resets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(12), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Integer, default=0)



class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False)


class DepartmentMembership(Base):
    __tablename__ = "department_memberships"
    __table_args__ = (UniqueConstraint("user_id", "department_id"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    is_head = Column(Boolean, default=False, nullable=False)
    active = Column(Boolean, default=True, nullable=False)


class PatientCareAssignment(Base):
    __tablename__ = "patient_care_assignments"
    __table_args__ = (UniqueConstraint("patient_id", "user_id", "department_id"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    active = Column(Boolean, default=True, nullable=False)


class AccessGrant(Base):
    __tablename__ = "access_grants"
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    grantee_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    granted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    purpose = Column(String(256), nullable=False)
    can_write = Column(Boolean, default=False, nullable=False)
    starts_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)


class ClinicalRecord(Base):
    __tablename__ = "clinical_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=True)
    record_type = Column(String(32), nullable=False)
    title = Column(String(256), nullable=False)
    original_filename = Column(String(256), nullable=False)
    media_type = Column(String(128), nullable=False)
    storage_key = Column(String(128), unique=True, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False)
    ciphertext_sha256 = Column(String(64), nullable=True)
    encryption_version = Column(Integer, default=0, nullable=False)
    key_id = Column(String(32), nullable=True)
    wrapped_key = Column(String(128), nullable=True)
    wrap_nonce = Column(String(32), nullable=True)
    file_nonce = Column(String(32), nullable=True)
    file_tag = Column(String(32), nullable=True)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    patient_visible = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    action = Column(String(64), nullable=False)
    resource_type = Column(String(32), nullable=False)
    resource_id = Column(Integer, nullable=True)
    allowed = Column(Boolean, nullable=False)
    created_at = Column(DateTime, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    kind = Column(String(32), nullable=False)
    title = Column(String(128), nullable=False)
    message = Column(String(512), nullable=False)
    target_path = Column(String(256), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, index=True)
