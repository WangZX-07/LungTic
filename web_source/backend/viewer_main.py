"""Minimal local backend bundled with the TICI Viewer desktop app."""

import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ["LUNGTIC_LOCAL_VIEWER"] = "1"
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, SessionLocal, engine
from models.db_models import User, UserRole
from routers.auth import router as auth_router
from routers.tici import router as tici_router
from services.auth_service import hash_password


def initialize_local_database() -> None:
    """Create the local SQLite schema and a first-run administrator account."""
    Base.metadata.create_all(bind=engine)
    username = os.getenv("LUNGTIC_BOOTSTRAP_USERNAME", "admin")
    password = os.getenv("LUNGTIC_BOOTSTRAP_PASSWORD", "admin123")

    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first() is None:
            db.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    role=UserRole.admin,
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_local_database()
    yield


app = FastAPI(
    title="LungTic TICI Viewer API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(tici_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "LungTic TICI Viewer"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.getenv("LUNGTIC_PORT", "18765")),
        log_level="warning",
    )
