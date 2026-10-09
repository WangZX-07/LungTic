"""SMTP email delivery using encrypted administrator settings or environment fallback."""

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.utils import parseaddr
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

from config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USERNAME
from models.db_models import SmtpSetting
from services.settings_crypto import decrypt_smtp_password

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """SMTP configuration or delivery failed."""


@dataclass(frozen=True)
class SmtpConfig:
    enabled: bool
    host: str
    port: int
    security: str
    username: str
    password: str
    from_address: str
    source: str

    @property
    def configured(self) -> bool:
        return bool(self.host and self.username and self.password and self.from_address)


def get_smtp_config(db: Session | None = None) -> SmtpConfig:
    if db is not None:
        row = db.query(SmtpSetting).filter(SmtpSetting.id == 1).first()
        if row is not None:
            password = decrypt_smtp_password(
                key_id=row.key_id,
                nonce=row.password_nonce,
                ciphertext=row.password_ciphertext,
            )
            return SmtpConfig(
                enabled=row.enabled,
                host=row.host,
                port=row.port,
                security=row.security,
                username=row.username,
                password=password,
                from_address=row.from_address,
                source="database",
            )
    return SmtpConfig(
        enabled=True,
        host=SMTP_HOST,
        port=SMTP_PORT,
        security="ssl" if SMTP_PORT == 465 else "starttls",
        username=SMTP_USERNAME,
        password=SMTP_PASSWORD,
        from_address=SMTP_FROM,
        source="environment" if SMTP_USERNAME and SMTP_PASSWORD else "unconfigured",
    )


def send_email(
    to: str,
    subject: str,
    body: str,
    *,
    db: Session | None = None,
    raise_on_error: bool = False,
) -> bool:
    """Send a plain-text email without ever logging the SMTP password."""
    try:
        config = get_smtp_config(db)
        if not config.enabled:
            raise EmailDeliveryError("SMTP 邮件发送已停用")
        if not config.configured:
            raise EmailDeliveryError("SMTP 尚未配置完整")
        for address in (to, config.from_address):
            _, parsed = parseaddr(address)
            if parsed != address or "@" not in parsed or any(ch in address for ch in "\r\n"):
                raise EmailDeliveryError("邮件地址格式无效")

        msg = MIMEMultipart()
        msg["From"] = config.from_address
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        server = None
        try:
            tls_context = ssl.create_default_context()
            if config.security == "ssl":
                server = smtplib.SMTP_SSL(
                    config.host, config.port, timeout=10, context=tls_context
                )
            elif config.security == "starttls":
                server = smtplib.SMTP(config.host, config.port, timeout=10)
                server.ehlo()
                server.starttls(context=tls_context)
                server.ehlo()
            else:
                raise EmailDeliveryError("不支持的 SMTP 加密方式")
            server.login(config.username, config.password)
            server.sendmail(config.from_address, to, msg.as_string())
        finally:
            if server is not None:
                try:
                    server.quit()
                except Exception:
                    server.close()
        logger.info("Email sent via configured SMTP server")
        return True
    except Exception as exc:
        logger.error("Email delivery failed: %s", exc.__class__.__name__)
        if raise_on_error:
            if isinstance(exc, EmailDeliveryError):
                raise
            raise EmailDeliveryError(str(exc)) from exc
        return False
