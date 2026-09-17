from datetime import datetime, timezone
import io
import csv
import random
import base64
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from services.auth_service import (
    authenticate_user, create_access_token, decode_token, hash_password, verify_password,
    generate_captcha_token, verify_captcha_token, create_password_reset, verify_reset_token,
)
from services.email_service import send_email
from models.db_models import User, PasswordReset, Patient
from config import SERVER_MODE
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from PIL import Image, ImageDraw

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()


# ---- Pydantic models ----

class LoginRequest(BaseModel):
    username: str
    password: str
    role: str = "doctor"
    captcha_token: str = ""
    captcha_code: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class CaptchaVerifyRequest(BaseModel):
    token: str
    code: str = ""


class ResetPasswordRequest(BaseModel):
    email: str


class ResetPasswordConfirmRequest(BaseModel):
    token: str
    new_password: str


class ProfileUpdateRequest(BaseModel):
    email: str | None = None
    phone: str | None = None


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "doctor"
    patient_code: str | None = None
    email: str | None = None
    phone: str | None = None
class UserUpdateRequest(BaseModel):
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    patient_code: str | None = None

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


# ---- Auth helpers ----

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        payload = decode_token(credentials.credentials)
        user_id = int(payload["sub"])
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_admin(user: User = Depends(get_current_user)):
    if user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


# ---- Captcha endpoints ----

@router.post("/captcha/generate")
def captcha_generate():
    """Generate text captcha image."""
    import random
    import string
    import io
    import base64
    from PIL import Image, ImageDraw, ImageFont

    # Generate 4-character alphanumeric code
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace("O", "").replace("0", "").replace("I", "").replace("1", "").replace("L", "")
    code = "".join(random.choice(chars) for _ in range(4))

    # Create image
    width, height = 120, 48
    img = Image.new("RGB", (width, height), color=(245, 245, 250))
    draw = ImageDraw.Draw(img)

    # Draw noise lines
    for _ in range(6):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line([x1, y1, x2, y2], fill=(random.randint(180, 220), random.randint(180, 220), random.randint(200, 230)), width=1)

    # Draw noise dots
    for _ in range(80):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        draw.point((x, y), fill=(random.randint(150, 200), random.randint(150, 200), random.randint(170, 210)))

    # Draw characters with random offset and rotation
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font = ImageFont.load_default()

    for i, ch in enumerate(code):
        x = 15 + i * 25 + random.randint(-3, 3)
        y = random.randint(2, 10)
        color = (random.randint(30, 100), random.randint(50, 130), random.randint(160, 220))
        draw.text((x, y), ch, fill=color, font=font)

    # Convert to base64
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    # Store code in token
    token = generate_captcha_token(code)

    return {"image_base64": img_base64, "token": token}


@router.post("/captcha/verify")
def captcha_verify(req: CaptchaVerifyRequest):
    """Verify text captcha code (case-insensitive)."""
    payload = verify_captcha_token(req.token)
    if payload is None:
        return {"valid": False, "message": "Invalid or expired token"}
    code = payload.get("code")
    if code and code.upper() == req.code.upper():
        return {"valid": True}
    return {"valid": False, "message": "Code mismatch"}


def captcha_verify(req: CaptchaVerifyRequest):
    """Verify slider captcha position."""
    payload = verify_captcha_token(req.token)
    if payload is None:
        return {"valid": False, "message": "Invalid or expired token"}

    expected_x = payload["x"]
    diff = abs(req.slider_x - expected_x)

    from config import CAPTCHA_TOLERANCE
    if diff <= CAPTCHA_TOLERANCE:
        return {"valid": True}
    return {"valid": False, "message": "Position mismatch"}


# ---- Login ----

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    # Require a fresh captcha on the shared server.
    if SERVER_MODE and not req.captcha_token:
        raise HTTPException(status_code=400, detail="验证码必填")
    if req.captcha_token:
        captcha_payload = verify_captcha_token(req.captcha_token)
        if captcha_payload is None:
            raise HTTPException(status_code=400, detail="验证码已过期或无效")
        from config import CAPTCHA_TOLERANCE
        if req.captcha_code.upper() != captcha_payload.get("code", ""):
            raise HTTPException(status_code=400, detail="验证码错误")

    user = authenticate_user(db, req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # Validate role selection
    user_role = user.role.value if hasattr(user.role, "value") else user.role
    if req.role and req.role != user_role:
        raise HTTPException(status_code=401, detail="角色不匹配")

    token = create_access_token(user.id, user.username, user_role)
    return TokenResponse(
        access_token=token,
        username=user.username,
        role=user_role,
    )


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    role = user.role.value if hasattr(user.role, "value") else user.role
    return {
        "id": user.id,
        "username": user.username,
        "role": role,
        "patient_code": user.patient_code,
        "email": user.email,
        "phone": user.phone,
    }


# ---- Password reset ----

@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Send password reset code to user's email."""
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        # Don't reveal whether email exists
        return {"message": "如果该邮箱已注册，验证码已发送"}

    token = create_password_reset(db, user.id)

    # Send email
    subject = "LungTic Password Reset"
    body = ("Hello " + user.username + ",\n\n"
            "Your password reset code is: " + token + "\n\n"
            "This code is valid for 15 minutes.\n\n"
            "If you did not request this, please ignore.\n\n"
            "LungTic Team")
    send_email(user.email, subject, body)

    return {"message": "验证码已发送至您的邮箱"}


@router.post("/reset-password/confirm")
def reset_password_confirm(req: ResetPasswordConfirmRequest, db: Session = Depends(get_db)):
    """Confirm password reset with token and set new password."""
    user = verify_reset_token(db, req.token)
    if not user:
        raise HTTPException(status_code=400, detail="验证码无效或已过期")

    if len(req.new_password) < (12 if SERVER_MODE else 6):
        raise HTTPException(status_code=400, detail="密码长度不足")

    user.password_hash = hash_password(req.new_password)

    # Mark all tokens for this user as used
    db.query(PasswordReset).filter(
        PasswordReset.user_id == user.id,
        PasswordReset.used == 0,
    ).update({"used": 1})

    db.commit()
    return {"message": "密码重置成功"}


# ---- Change password (logged in) ----

@router.put("/change-password")
def change_password(
    req: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(req.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="旧密码错误")
    if len(req.new_password) < (12 if SERVER_MODE else 6):
        raise HTTPException(status_code=400, detail="密码长度不足")

    current_user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"message": "密码修改成功"}



# ---- User management (admin only) ----

@router.get("/users")
def list_users(
    role: str = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List all users. Optionally filter by role."""
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    users = query.order_by(User.created_at.desc()).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role.value if hasattr(u.role, "value") else u.role,
            "patient_code": u.patient_code,
            "email": u.email,
            "phone": u.phone,
            "created_at": str(u.created_at) if u.created_at else None,
        }
        for u in users
    ]

# ---- Profile update ----

@router.put("/profile")
def update_profile(
    req: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update current user's profile (email, phone)."""
    if req.email is not None:
        current_user.email = req.email if req.email else None
    if req.phone is not None:
        current_user.phone = req.phone if req.phone else None
    db.commit()
    role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": role,
        "patient_code": current_user.patient_code,
        "email": current_user.email,
        "phone": current_user.phone,
    }



# ---- Create single user (admin) ----

@router.post("/users")
def create_user(
    req: CreateUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin creates a single user."""
    if req.role not in ("doctor", "admin", "patient"):
        raise HTTPException(status_code=400, detail="Invalid role")
    if SERVER_MODE and len(req.password) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters")
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        role=req.role,
        created_at=datetime.now(timezone.utc),
        patient_code=req.patient_code if req.role == "patient" else None,
        email=req.email if req.email else None,
        phone=req.phone if req.phone else None,
    )
    db.add(user)
    db.flush()

    if req.role == "patient":
        code = req.patient_code if req.patient_code else f"P{user.id:04d}"
        existing_pc = db.query(Patient).filter(Patient.patient_code == code).first()
        if existing_pc:
            if existing_pc.user_id is not None:
                raise HTTPException(status_code=400, detail="Patient code already has an account")
            existing_pc.user_id = user.id
        else:
            patient = Patient(patient_code=code, user_id=user.id)
            db.add(patient)

    db.commit()

    if req.email:
        subject = "LungTic \u8d26\u53f7\u5df2\u521b\u5efa"
        body_lines = []
        body_lines.append("\u60a8\u597d " + req.username + "\uff0c")
        body_lines.append("")
        body_lines.append("\u60a8\u7684 LungTic \u8d26\u53f7\u5df2\u521b\u5efa\u6210\u529f\uff01")
        body_lines.append("")
        body_lines.append("\u7528\u6237\u540d\uff1a" + req.username)
        body_lines.append("\u89d2\u8272\uff1a" + req.role)
        body_lines.append("")
        body_lines.append("\u8bf7\u767b\u5f55\u540e\u53ca\u65f6\u4fee\u6539\u5bc6\u7801\u3002")
        body_lines.append("")
        body_lines.append("LungTic Team")
        body = "\n".join(body_lines)
        send_email(req.email, subject, body)

    return {
        "id": user.id,
        "username": user.username,
        "role": req.role,
        "patient_code": user.patient_code,
        "email": user.email,
        "phone": user.phone,
    }

# ---- User management (admin) ----

@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    req: UserUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin updates a user's role, email, phone, or patient_code."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if req.role is not None:
        if req.role not in ("doctor", "admin", "patient"):
            raise HTTPException(status_code=400, detail="Invalid role")
        user.role = req.role
    if req.email is not None:
        user.email = req.email if req.email else None
    if req.phone is not None:
        user.phone = req.phone if req.phone else None
    if req.patient_code is not None:
        user.patient_code = req.patient_code if req.patient_code else None
    db.commit()
    role = user.role.value if hasattr(user.role, "value") else user.role
    return {
        "id": user.id,
        "username": user.username,
        "role": role,
        "patient_code": user.patient_code,
        "email": user.email,
        "phone": user.phone,
    }


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin deletes a user (cannot delete self)."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"status": "ok", "deleted": user_id}

# ---- Batch create users (admin only) ----

@router.post("/batch-create")
def batch_create(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Batch create users from CSV file. Columns: username,password,role,patient_code,email"""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="请上传 CSV 文件")

    content = file.file.read().decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    if len(rows) < 2:
        raise HTTPException(status_code=400, detail="CSV 文件至少需要表头和数据行")

    # First row is header
    headers = [h.strip().lower() for h in rows[0]]
    # Expected: username,password,role,patient_code,email

    created = []
    errors = []

    for i, row in enumerate(rows[1:], start=2):
        if len(row) < 2:
            errors.append(f"第{i}行: 列数不足")
            continue

        data = dict(zip(headers, row))
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        role = data.get("role", "doctor").strip().lower()
        patient_code = data.get("patient_code", "").strip()
        email = data.get("email", "").strip()

        if not username or not password:
            errors.append(f"第{i}行: 用户名或密码为空")
            continue
        if SERVER_MODE and len(password) < 12:
            errors.append(f"第{i}行: 密码至少12位")
            continue

        if role not in ("doctor", "admin", "patient"):
            errors.append(f"第{i}行: 无效的角色 {role}")
            continue

        # Check duplicate username
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            errors.append(f"第{i}行: 用户名 {username} 已存在")
            continue

        code = patient_code if patient_code else None
        existing_patient = db.query(Patient).filter(Patient.patient_code == code).first() if role == "patient" and code else None
        if existing_patient and existing_patient.user_id is not None:
            errors.append(f"第{i}行: 患者编码 {code} 已绑定账号")
            continue

        # Create user
        user = User(
            username=username,
            password_hash=hash_password(password),
            role=role,
            created_at=datetime.now(timezone.utc),
            patient_code=patient_code if role == "patient" else None,
            email=email if email else None,
        )
        db.add(user)
        db.flush()

        # Bind a reviewed existing record or create a new patient record.
        if role == "patient":
            code = patient_code if patient_code else f"P{user.id:04d}"
            if existing_patient:
                existing_patient.user_id = user.id
            else:
                db.add(Patient(patient_code=code, user_id=user.id))

        created.append({"username": username, "role": role, "email": email})

        # Send notification email
        if email:
            subject = "LungTic 账号已创建"
            body = f"您好 {username}，\n\n您的 LungTic 账号已创建成功！\n\n用户名：{username}\n角色：{role}\n\n请登录后及时修改密码。\n\nLungTic Team"
            send_email(email, subject, body)

    db.commit()

    return {
        "created": len(created),
        "errors": errors,
        "users": created,
    }
