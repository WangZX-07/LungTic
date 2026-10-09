"""Administrator-only runtime configuration endpoints."""

import re
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from config import SMTP_PASSWORD
from database import get_db
from models.db_models import SmtpSetting, User
from routers.auth import require_admin
from services.access_control import audit
from services.email_service import EmailDeliveryError, get_smtp_config, send_email
from services.settings_crypto import encrypt_smtp_password

router = APIRouter(prefix="/api/admin/settings", tags=["admin-settings"])


def _email_address(value: str) -> str:
    value = value.strip()
    _, parsed = parseaddr(value)
    if parsed != value or "@" not in parsed or any(ch in value for ch in "\r\n"):
        raise ValueError("请输入有效的邮箱地址")
    return value


class SmtpSettingsUpdate(BaseModel):
    enabled: bool = True
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    security: Literal["ssl", "starttls"]
    username: str = Field(min_length=1, max_length=255)
    from_address: str
    password: str | None = Field(default=None, max_length=512)

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9.-]+", value):
            raise ValueError("SMTP 服务器地址格式无效")
        return value

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ch in value for ch in "\r\n"):
            raise ValueError("SMTP 用户名格式无效")
        return value

    @field_validator("from_address")
    @classmethod
    def validate_from_address(cls, value: str) -> str:
        return _email_address(value)


class SmtpTestRequest(BaseModel):
    recipient: str

    @field_validator("recipient")
    @classmethod
    def validate_recipient(cls, value: str) -> str:
        return _email_address(value)


def _smtp_payload(db: Session) -> dict:
    config = get_smtp_config(db)
    row = db.query(SmtpSetting).filter(SmtpSetting.id == 1).first()
    return {
        "enabled": config.enabled,
        "host": config.host,
        "port": config.port,
        "security": config.security,
        "username": config.username,
        "from_address": config.from_address,
        "password_configured": bool(config.password),
        "source": config.source,
        "updated_at": row.updated_at if row else None,
    }


@router.get("/smtp")
def get_smtp_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return _smtp_payload(db)


@router.put("/smtp")
def update_smtp_settings(
    req: SmtpSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    row = db.query(SmtpSetting).filter(SmtpSetting.id == 1).first()
    password = req.password if req.password else None
    if password is None and row is None:
        password = SMTP_PASSWORD or ""
    if req.enabled and row is not None and password is None and not get_smtp_config(db).password:
        raise HTTPException(400, "启用前必须填写 SMTP 授权码或密码")
    if req.enabled and row is None and not password:
        raise HTTPException(400, "首次启用时必须填写 SMTP 授权码或密码")

    if row is None:
        row = SmtpSetting(id=1)
        db.add(row)
    if password is not None:
        row.key_id, row.password_nonce, row.password_ciphertext = encrypt_smtp_password(password)

    row.enabled = req.enabled
    row.host = req.host
    row.port = req.port
    row.security = req.security
    row.username = req.username
    row.from_address = req.from_address
    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    row.updated_by_user_id = admin.id
    db.commit()
    audit(db, admin, "update_smtp_settings", "settings", 1, None, True)
    return _smtp_payload(db)


@router.post("/smtp/test")
def test_smtp_settings(
    req: SmtpTestRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        send_email(
            req.recipient,
            "LungTic SMTP 测试邮件",
            "这是一封来自 LungTic 管理后台的 SMTP 测试邮件。\n\n如果您收到此邮件，说明密码重置邮件通道配置正确。",
            db=db,
            raise_on_error=True,
        )
    except EmailDeliveryError as exc:
        audit(db, admin, "test_smtp_settings", "settings", 1, None, False)
        raise HTTPException(502, f"SMTP 测试失败：{exc}") from exc
    audit(db, admin, "test_smtp_settings", "settings", 1, None, True)
    return {"message": "测试邮件已发送"}
