"""IGTV Reconstruction API 鈥?connected to real reconstruction."""

import os
import sys
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import get_current_user
from services.access_control import require_study
from models.db_models import User, Study, Series, Slice, Segmentation, IgtvResult
from models.igtv_reconstruct import (
    fuse_phase_masks, marching_cubes_mesh,
    compute_igtv_volume, save_mesh_obj,
)
from config import DICOM_DIR, TICI_DIR
from datetime import datetime

router = APIRouter(prefix="/api/igtv", tags=["igtv"])


class ReconstructRequest(BaseModel):
    study_id: int


def _get_tici_path(study_id: int) -> str:
    return os.path.join(TICI_DIR, f"study_{study_id}.tici")


@router.post("/reconstruct")
def reconstruct_igtv(
    req: ReconstructRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reconstruct IGTV from all phase segmentation masks."""
    study = require_study(db, current_user, req.study_id, write=True, action="run_ai")

    # Get all segmentation masks grouped by phase
    series_list = (
        db.query(Series)
        .filter(Series.study_id == req.study_id)
        .order_by(Series.phase_index)
        .all()
    )

    phase_masks = []
    for series in series_list:
        segs = (
            db.query(Segmentation)
            .join(Slice, Segmentation.slice_id == Slice.id)
            .filter(Slice.series_id == series.id)
            .order_by(Slice.z_position)
            .all()
        )

        if not segs:
            continue

        # Stack slices into 3D volume
        slices_3d = []
        for seg in segs:
            mask_path = os.path.join(DICOM_DIR, seg.mask_path) if seg.mask_path else ""
            if os.path.exists(mask_path):
                mask = np.load(mask_path)
                slices_3d.append(mask)

        if slices_3d:
            volume = np.stack(slices_3d, axis=0)  # (D, H, W)
            phase_masks.append(volume)

    if not phase_masks:
        raise HTTPException(400, "No segmentation masks found. Run segmentation first.")

    # Fuse all phase masks into ITV
    itv_mask = fuse_phase_masks(phase_masks, method="union")

    # Compute volume
    spacing = (1.0, 1.0, 1.0)  # mm, default 鈥?can be extracted from DICOM
    volume_cc = compute_igtv_volume(itv_mask, spacing)

    # Generate mesh
    verts, faces = marching_cubes_mesh(itv_mask, spacing)

    # Save mesh and mask
    mesh_dir = os.path.join(DICOM_DIR, f"igtv/{req.study_id}")
    os.makedirs(mesh_dir, exist_ok=True)
    mesh_path = os.path.join(mesh_dir, "igtv.obj")
    save_mesh_obj(verts, faces, mesh_path)
    rel_mesh_path = os.path.relpath(mesh_path, DICOM_DIR)

    mask_path = os.path.join(mesh_dir, "itv_mask.npy")
    np.save(mask_path, itv_mask)
    rel_mask_path = os.path.relpath(mask_path, DICOM_DIR)

    # Store result
    existing = db.query(IgtvResult).filter(IgtvResult.study_id == req.study_id).first()
    if existing:
        existing.volume_cc = volume_cc
        existing.mesh_path = rel_mesh_path
        existing.created_at = datetime.now()
    else:
        result = IgtvResult(
            study_id=req.study_id,
            volume_cc=volume_cc,
            mesh_path=rel_mesh_path,
        )
        db.add(result)

    db.commit()

    # Read mesh text for .tici
    mesh_text = ""
    if os.path.exists(mesh_path):
        try:
            with open(mesh_path, "r", encoding="utf-8") as f:
                mesh_text = f.read()
        except Exception:
            pass

    # Append IGTV to .tici file if it exists
    tici_path = _get_tici_path(req.study_id)
    if os.path.exists(tici_path):
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from tici import TiciWriter
            with TiciWriter(tici_path, "a") as w:
                w.write_igtv(itv_mask, mesh_text, volume_cc, method="union")
        except Exception:
            pass  # Silently skip tici append on failure

    return {
        "status": "completed",
        "study_id": req.study_id,
        "volume_cc": round(volume_cc, 2),
        "phases_used": len(phase_masks),
        "mesh_path": rel_mesh_path,
        "mask_path": rel_mask_path,
    }


@router.get("/{study_id}")
def get_igtv(
    study_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get IGTV result for a study."""
    require_study(db, current_user, study_id, action="view_ai_result")
    igtv = db.query(IgtvResult).filter(IgtvResult.study_id == study_id).first()
    if not igtv:
        return {"study_id": study_id, "status": "not_run"}

    return {
        "study_id": study_id,
        "status": "completed",
        "volume_cc": igtv.volume_cc,
        "mesh_path": igtv.mesh_path,
    }
