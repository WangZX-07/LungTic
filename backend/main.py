from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.auth import router as auth_router
from routers.models_router import router as models_router
from routers.dicom import router as dicom_router
from routers.segmentation import router as segmentation_router
from routers.igtv import router as igtv_router
from routers.trajectory import router as trajectory_router
from routers.tici import router as tici_router

app = FastAPI(title="LungTic API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "LungTic"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
