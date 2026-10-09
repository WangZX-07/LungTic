"""Internal notification inbox helpers."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.db_models import Notification

logger = logging.getLogger(__name__)
MAX_NOTIFICATIONS_PER_USER = 200


def create_notification(
    db: Session,
    *,
    user_id: int | None,
    kind: str,
    title: str,
    message: str,
    target_path: str | None = None,
) -> bool:
    """Persist a notification after the business transaction has committed.

    Notification delivery is best-effort: a missing migration or transient
    database failure must not roll back a completed clinical operation.
    """
    if not user_id:
        return False
    try:
        db.add(Notification(
            user_id=user_id,
            kind=kind[:32],
            title=title[:128],
            message=message[:512],
            target_path=target_path[:256] if target_path else None,
            is_read=False,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ))
        db.commit()

        stale_ids = [row[0] for row in db.query(Notification.id).filter(
            Notification.user_id == user_id
        ).order_by(Notification.id.desc()).offset(MAX_NOTIFICATIONS_PER_USER).all()]
        if stale_ids:
            db.query(Notification).filter(Notification.id.in_(stale_ids)).delete(
                synchronize_session=False
            )
            db.commit()
        return True
    except Exception:
        db.rollback()
        logger.exception("Failed to create internal notification for user %s", user_id)
        return False
