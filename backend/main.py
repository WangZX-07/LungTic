import os
os.environ["LUNGTIC_LOCAL_VIEWER"] = "0"
os.environ["LUNGTIC_SERVER_MODE"] = "1"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.auth import router as auth_router
from routers.models_router import router as models_router
from routers.dicom import router as dicom_router
from routers.segmentation import router as segmentation_router
from routers.igtv import router as igtv_router
from routers.trajectory import router as trajectory_router
from routers.tici import router as tici_router
from routers.organization import router as organization_router
from routers.clinical_records import router as clinical_records_router
from config import CORS_ORIGINS, SERVER_MODE, JWT_SECRET, CAPTCHA_SECRET

if SERVER_MODE and (not os.getenv("LUNGTIC_DB_URL") or not os.getenv("LUNGTIC_CORS_ORIGINS") or len(JWT_SECRET) < 32 or JWT_SECRET == "lungtic-dev-secret-change-in-prod" or "*" in CORS_ORIGINS or len(CAPTCHA_SECRET) < 32 or CAPTCHA_SECRET == "lungtic-captcha-secret"):
    raise RuntimeError("Set LUNGTIC_DB_URL, 32+ character LUNGTIC_JWT_SECRET and LUNGTIC_CAPTCHA_SECRET, and explicit LUNGTIC_CORS_ORIGINS before server deployment")

app = FastAPI(title="LungTic API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(models_router)
app.include_router(dicom_router)
app.include_router(segmentation_router)
app.include_router(igtv_router)
app.include_router(trajectory_router)
app.include_router(tici_router)
app.include_router(organization_router)
app.include_router(clinical_records_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "LungTic"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
