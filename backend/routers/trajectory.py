"""Tumor Trajectory Prediction API 鈥?connected to LSTM model."""

import os
import sys
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import get_current_user
from models.db_models import User, Study, Series, Slice, Segmentation, Trajectory, UserModel
from services.inference import get_engine
from config import DICOM_DIR, TICI_DIR

router = APIRouter(prefix="/api/trajectory", tags=["trajectory"])


class PredictRequest(BaseModel):
    model_config = {'protected_namespaces': ()}
    model_config = {'protected_namespaces': ()}
    study_id: int
    model_id: int | None = None


def _get_tici_path(study_id: int) -> str:
    return os.path.join(TICI_DIR, f"study_{study_id}.tici")


@router.post("/predict")
def predict_trajectory(
    req: PredictRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Predict tumor motion trajectory using LSTM."""
    study = db.query(Study).filter(Study.id == req.study_id).first()
    if not study:
        raise HTTPException(404, "Study not found")

    engine = get_engine()
    model_version = "builtin-lstm-v0.1"

    if req.model_id:
        model = (
            db.query(UserModel)
            .filter(UserModel.id == req.model_id, UserModel.user_id == current_user.id)
            .first()
        )
        if not model:
            raise HTTPException(404, "Model not found")
        engine.load_custom_model(model.file_path, model.model_type.value, "prediction")
        model_version = model.model_name
    else:
        engine.ensure_prediction_loaded()

    # Collect centroids from each phase
    series_list = (
        db.query(Series)
        .filter(Series.study_id == req.study_id)
        .order_by(Series.phase_index)
        .all()
    )

    centroids = []
    for series in series_list:
        # Get slices with segmentations for this phase
        segs = (
            db.query(Segmentation)
            .join(Slice, Segmentation.slice_id == Slice.id)
            .filter(Slice.series_id == series.id)
            .order_by(Slice.z_position)
            .all()
        )

        if not segs:
            centroids.append((0.0, 0.0, 0.0))
            continue

        xs, ys, zs = [], [], []
        for seg in segs:
            mask_path = os.path.join(DICOM_DIR, seg.mask_path) if seg.mask_path else ""
            if os.path.exists(mask_path):
                mask = np.load(mask_path)
                cy, cx = engine.get_centroid(mask)
                xs.append(cx)
                ys.append(cy)
                # z from slice position
                slc = db.query(Slice).filter(Slice.id == seg.slice_id).first()
                zs.append(slc.z_position if slc and slc.z_position else 0.0)

        centroids.append((np.mean(xs), np.mean(ys), np.mean(zs)))

    # Prepare observed trajectory
    observed = np.array(centroids[:7], dtype=np.float32)  # First 7 phases
    if len(observed) < 3:
        raise HTTPException(400, "Need at least 3 phases with segmentations")

    # Predict remaining phases
    pred_len = max(1, len(series_list) - len(observed))
    predicted = engine.predict_trajectory(observed, pred_len=pred_len)

    # Store trajectories
    db.query(Trajectory).filter(Trajectory.study_id == req.study_id).delete()

    for i, (x, y, z) in enumerate(centroids):
        db.add(Trajectory(
            study_id=req.study_id,
            phase_index=i,
            x_pos=float(x),
            y_pos=float(y),
            z_pos=float(z),
            is_predicted=0,
        ))

    for i in range(pred_len):
        if i < len(predicted):
            db.add(Trajectory(
                study_id=req.study_id,
                phase_index=len(observed) + i,
                x_pos=float(predicted[i][0]),
                y_pos=float(predicted[i][1]),
                z_pos=float(predicted[i][2]),
                is_predicted=1,
            ))

    db.commit()

    # Collect predicted points for .tici
    predicted_pts = []
    for i in range(pred_len):
        if i < len(predicted):
            predicted_pts.append([float(predicted[i][0]), float(predicted[i][1]), float(predicted[i][2])])

    # Append trajectory to .tici file if it exists
    tici_path = _get_tici_path(req.study_id)
    if os.path.exists(tici_path):
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from tici import TiciWriter
            with TiciWriter(tici_path, "a") as w:
                w.write_trajectory(
                    centroids=np.array(centroids, dtype=np.float32),
                    observed=observed,
                    predicted=np.array(predicted_pts, dtype=np.float32) if predicted_pts else np.zeros((0, 3), dtype=np.float32),
                    model_name=model_version,
                )
        except Exception:
            pass  # Silently skip tici append on failure

    return {
        "status": "completed",
        "study_id": req.study_id,
        "model_version": model_version,
        "observed_phases": len(observed),
        "predicted_phases": pred_len,
    }


@router.get("/{study_id}")
def get_trajectory(
    study_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get trajectory data (real + predicted) for a study."""
    trajectories = (
        db.query(Trajectory)
        .filter(Trajectory.study_id == study_id)
        .order_by(Trajectory.phase_index)
        .all()
    )

    if not trajectories:
        return {"study_id": study_id, "status": "not_run", "trajectories": []}

    return {
        "study_id": study_id,
        "status": "completed",
        "trajectories": [
            {
                "phase": t.phase_index,
                "x": t.x_pos,
                "y": t.y_pos,
                "z": t.z_pos,
                "is_predicted": bool(t.is_predicted),
            }
            for t in trajectories
        ],
    }
