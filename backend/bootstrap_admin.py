"""Create or rotate the central server administrator without a default password."""

import os
from datetime import datetime

from database import SessionLocal
from models.db_models import User, UserRole
from services.auth_service import hash_password


def main() -> None:
    username = os.getenv("LUNGTIC_BOOTSTRAP_USERNAME", "admin").strip()
    password = os.getenv("LUNGTIC_BOOTSTRAP_PASSWORD", "")
    if not username or len(password) < 12:
        raise SystemExit("Set LUNGTIC_BOOTSTRAP_USERNAME and a 12+ character LUNGTIC_BOOTSTRAP_PASSWORD")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            user = User(username=username, role=UserRole.admin, created_at=datetime.utcnow())
            db.add(user)
        else:
            role = user.role.value if hasattr(user.role, "value") else user.role
            if role != "admin":
                raise SystemExit("Existing username is not an administrator")
        user.password_hash = hash_password(password)
        db.commit()
        print(f"Administrator {username} is ready")
    finally:
        db.close()


if __name__ == "__main__":
    main()
