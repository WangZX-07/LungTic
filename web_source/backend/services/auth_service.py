from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
import hmac
import hashlib
import json
import base64
import secrets
from sqlalchemy.orm import Session
from models.db_models import User, PasswordReset
from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES, CAPTCHA_SECRET, CAPTCHA_EXPIRE_SECONDS


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


# ---- Captcha helpers ----

def generate_captcha_token(code: str) -> str:
    """Create an encoded captcha token containing code and expiry."""
    payload = {
        "code": code.upper(),
        "exp": int((datetime.now(timezone.utc) + timedelta(seconds=CAPTCHA_EXPIRE_SECONDS)).timestamp()),
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = hmac.new(CAPTCHA_SECRET.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    token = base64.urlsafe_b64encode(payload_bytes + b"." + sig.encode("utf-8")).decode("utf-8")
    return token


def verify_captcha_token(token: str) -> dict | None:
    """Decode and verify captcha token. Returns payload dict or None if invalid."""
    try:
        raw = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        payload_str, sig = raw.rsplit(".", 1)
        expected_sig = hmac.new(CAPTCHA_SECRET.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, sig):
            return None
        payload = json.loads(payload_str)
        if int(datetime.now(timezone.utc).timestamp()) > payload["exp"]:
            return None
        return payload
    except Exception:
        return None


# ---- Password reset helpers ----

def generate_reset_token() -> str:
    """Generate a 6-digit numeric reset token."""
    return str(secrets.randbelow(900000) + 100000)


def create_password_reset(db: Session, user_id: int) -> str:
    """Create a password reset record and return the token."""
    token = generate_reset_token()
    reset = PasswordReset(
        user_id=user_id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.add(reset)
    db.commit()
    return token


def verify_reset_token(db: Session, token: str) -> User | None:
    """Verify a reset token. Returns the User if valid, None otherwise."""
    reset = db.query(PasswordReset).filter(
        PasswordReset.token == token,
        PasswordReset.used == 0,
    ).first()
    if not reset:
        return None
    if datetime.now(timezone.utc) > reset.expires_at:
        return None
    user = db.query(User).filter(User.id == reset.user_id).first()
    return user
