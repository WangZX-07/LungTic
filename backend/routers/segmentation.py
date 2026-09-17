"""AI Segmentation API routes 鈥?connected to real InferenceEngine."""

import os
import sys
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import get_current_user
from models.db_models import User, Study, Series, Slice, Segmentation, UserModel
from services.inference import get_engine
from datetime import datetime
from sqlalchemy import func
from config import DICOM_DIR, TICI_DIR

router = APIRouter(prefix="/api/segmentation", tags=["segmentation"])


class RunRequest(BaseModel):
    model_config = {'protected_namespaces': ()}
    model_config = {'protected_namespaces': ()}
    study_id: int
    model_id: int | None = None


def _get_tici_path(study_id: int) -> str:
    return os.path.join(TICI_DIR, f"study_{study_id}.tici")


@router.post("/run")
def run_segmentation(
    req: RunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run Attention U-Net segmentation on a study."""
    study = db.query(Study).filter(Study.id == req.study_id).first()
    if not study:
        raise HTTPException(404, "Study not found")

    engine = get_engine()
    model_version = "builtin-v0.1"

    if req.model_id:
        model = (
            db.query(UserModel)
            .filter(UserModel.id == req.model_id, UserModel.user_id == current_user.id)
            .first()
        )
        if not model:
            raise HTTPException(404, "Model not found")
        engine.load_custom_model(model.file_path, model.model_type.value, "segmentation")
        model_version = model.model_name
    else:
        engine.ensure_segmentation_loaded()

    # Get all slices for this study
    series_list = db.query(Series).filter(Series.study_id == req.study_id).all()
    total_processed = 0
    dice_sum = 0.0

    # Per-phase mask storage for .tici append
    phase_masks_dict: dict[int, list[np.ndarray]] = {}

    for series in series_list:
        slices = db.query(Slice).filter(Slice.series_id == series.id).order_by(Slice.z_position).all()
        phase_masks = []

        for slc in slices:
            # Load DICOM image
            import pydicom

            full_path = os.path.join(DICOM_DIR, slc.file_path) if slc.file_path else ""
            if not os.path.exists(full_path):
                continue

            ds = pydicom.dcmread(full_path)
            pixel_array = ds.pixel_array.astype(np.float32)
            if pixel_array.max() > pixel_array.min():
                pixel_array = (pixel_array - pixel_array.min()) / (pixel_array.max() - pixel_array.min())

            # Run segmentation
            mask = engine.segment_slice(pixel_array)

            # Save mask
            mask_dir = os.path.join(DICOM_DIR, f"masks/{req.study_id}")
            os.makedirs(mask_dir, exist_ok=True)
            mask_path = os.path.join(mask_dir, f"mask_{slc.id}.npy")
            np.save(mask_path, mask)

            rel_mask_path = os.path.relpath(mask_path, DICOM_DIR)

            # Compute approximate Dice (without ground truth, use 0 as placeholder)
            dice = 0.0  # Will be meaningful when ground truth is available

            # Store segmentation result
            existing = db.query(Segmentation).filter(Segmentation.slice_id == slc.id).first()
            if existing:
                existing.mask_path = rel_mask_path
                existing.dice_score = dice
                existing.model_version = model_version
                existing.created_at = datetime.now()
            else:
                seg = Segmentation(
                    slice_id=slc.id,
                    mask_path=rel_mask_path,
                    dice_score=dice,
                    model_version=model_version,
                )
                db.add(seg)

            total_processed += 1
            dice_sum += dice
            phase_masks.append(mask)

        if phase_masks:
            phase_masks_dict[series.phase_index] = phase_masks

    db.commit()

    # Append masks to .tici file if it exists
    tici_path = _get_tici_path(req.study_id)
    if os.path.exists(tici_path) and phase_masks_dict:
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from tici import TiciWriter
            with TiciWriter(tici_path, "a") as w:
                for phase_idx, masks_list in phase_masks_dict.items():
                    masks_vol = np.stack(masks_list, axis=0).astype(np.uint8)
                    w.append_phase_masks(phase_idx, masks_vol)
        except Exception:
            pass  # Silently skip tici append on failure

    return {
        "status": "completed",
        "study_id": req.study_id,
        "model_version": model_version,
        "slices_processed": total_processed,
        "mean_dice": round(dice_sum / total_processed, 4) if total_processed > 0 else 0,
    }


@router.get("/{study_id}/result")
def get_segmentation_result(
    study_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get segmentation results for a study."""
    study = db.query(Study).filter(Study.id == study_id).first()
    if not study:
        raise HTTPException(404, "Study not found")

    segs = (
        db.query(Segmentation, Slice)
        .join(Slice, Segmentation.slice_id == Slice.id)
        .join(Series, Slice.series_id == Series.id)
        .filter(Series.study_id == study_id)
        .all()
    )

    if not segs:
        return {"study_id": study_id, "status": "not_run", "segmentations": []}

    scores = [s[0].dice_score for s in segs if s[0].dice_score is not None]
    return {
        "study_id": study_id,
        "status": "completed",
        "mean_dice": round(sum(scores) / len(scores), 4) if scores else 0,
        "model_version": segs[0][0].model_version if segs else "",
        "segmentations": [
            {
                "slice_id": s[0].slice_id,
                "dice_score": s[0].dice_score,
                "mask_path": s[0].mask_path,
            }
            for s in segs
        ],
    }
