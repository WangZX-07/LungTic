import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db
from routers.auth import get_current_user
from models.db_models import User, UserModel, ModelType, TaskType
from services.inference import get_engine
from config import MODEL_DIR

router = APIRouter(prefix="/api/models", tags=["models"])


class ModelOut(BaseModel):
    model_config = {'protected_namespaces': ()}
    model_config = {'protected_namespaces': ()}
    id: int
    model_name: str
    model_type: str
    task_type: str
    is_active: bool
    uploaded_at: datetime | None = None

    model_config = {'protected_namespaces': (), 'from_attributes': True}


@router.post("/upload")
def upload_model(
    file: UploadFile = File(...),
    model_name: str = Form(...),
    task_type: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.filename is None:
        raise HTTPException(400, "No file provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext == ".pth":
        mtype = ModelType.pth
    elif ext == ".onnx":
        mtype = ModelType.onnx
    else:
        raise HTTPException(400, "Only .pth and .onnx files are supported")

    if task_type not in ("segmentation", "prediction"):
        raise HTTPException(400, "task_type must be segmentation or prediction")
    ttype = TaskType(task_type)

    user_dir = os.path.join(MODEL_DIR, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(user_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(file.file.read())

    model = UserModel(
        user_id=current_user.id,
        model_name=model_name,
        model_type=mtype,
        task_type=ttype,
        file_path=file_path,
        is_active=0,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return ModelOut.model_validate(model)


@router.get("/", response_model=list[ModelOut])
def list_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    models = (
        db.query(UserModel)
        .filter(UserModel.user_id == current_user.id)
        .order_by(UserModel.uploaded_at.desc())
        .all()
    )
    return [ModelOut.model_validate(m) for m in models]


@router.put("/{model_id}/activate")
def activate_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = (
        db.query(UserModel)
        .filter(UserModel.id == model_id, UserModel.user_id == current_user.id)
        .first()
    )
    if not model:
        raise HTTPException(404, "Model not found")

    db.query(UserModel).filter(
        UserModel.user_id == current_user.id,
        UserModel.task_type == model.task_type,
    ).update({"is_active": 0})

    model.is_active = 1
    db.commit()

    # Load model into inference engine
    if model.file_path and os.path.exists(model.file_path):
        try:
            engine = get_engine()
            engine.load_custom_model(
                model.file_path,
                model.model_type.value,
                model.task_type.value,
            )
        except Exception as e:
            model.is_active = 0
            db.commit()
            raise HTTPException(500, f"Failed to load model: {str(e)}")

    return {"status": "ok", "message": f"Model '{model.model_name}' activated and loaded"}


@router.delete("/{model_id}")
def delete_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = (
        db.query(UserModel)
        .filter(UserModel.id == model_id, UserModel.user_id == current_user.id)
        .first()
    )
    if not model:
        raise HTTPException(404, "Model not found")

    if model.file_path and os.path.exists(model.file_path):
        os.remove(model.file_path)

    db.delete(model)
    db.commit()
    return {"status": "ok", "message": "Model deleted"}