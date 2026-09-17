"""TICI file format REST API routes."""

import os
import sys
import io
import base64
import uuid
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import get_current_user
from models.db_models import User, Patient, Study, Series, Slice, Segmentation, IgtvResult, Trajectory
from config import DICOM_DIR, TICI_DIR, TICI_VIEWER_DIR
from datetime import datetime

# Add ui/ to path so we can import tici package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tici import TiciWriter, TiciReader
from tici.converter import from_dicom_dir as _from_dicom_dir, from_study as _from_study

router = APIRouter(prefix="/api/tici", tags=["tici"])

VIEWER_UPLOAD_LIMIT = 2 * 1024 * 1024 * 1024
VIEWER_UPLOAD_CHUNK = 1024 * 1024


def _get_study_with_access(study_id: int, db: Session, current_user: User) -> Study:
    """Get study and verify access."""
    study = db.query(Study).filter(Study.id == study_id).first()
    if not study:
        raise HTTPException(404, "Study not found")

    patient = db.query(Patient).filter(Patient.id == study.patient_id).first()
    if patient:
        user_role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
        if user_role not in ("doctor", "admin"):
            if patient.user_id != current_user.id:
                if not (current_user.patient_code and patient.patient_code == current_user.patient_code):
                    raise HTTPException(403, "Access denied")
    return study


def _get_tici_path(study_id: int) -> str:
    """Get the .tici file path for a study."""
    tici_name = f"study_{study_id}.tici"
    return os.path.join(TICI_DIR, tici_name)


def _get_viewer_path(viewer_id: uuid.UUID, current_user: User) -> str:
    """Return an access-scoped path for a temporary viewer file."""
    return os.path.join(
        TICI_VIEWER_DIR,
        f"viewer_{current_user.id}_{viewer_id.hex}.tici",
    )


def _viewer_info(path: str, viewer_id: uuid.UUID) -> dict:
    """Read lightweight viewer metadata without loading phase volumes."""
    with TiciReader(path) as reader:
        meta = reader.get_metadata()
        format_version = reader.format_version
        phase_meta = reader.get_phase_meta()
        has_igtv = reader.has_igtv
        has_trajectory = reader.has_trajectory

    return {
        "viewer_id": str(viewer_id),
        "status": "ready",
        "format_version": format_version,
        "patient": {
            "patient_id": meta.patient.patient_id,
            "patient_name": meta.patient.patient_name,
            "patient_sex": meta.patient.patient_sex,
            "patient_age": meta.patient.patient_age,
        },
        "study": {
            "study_uid": meta.study.study_uid,
            "study_date": meta.study.study_date,
            "modality": meta.study.modality,
            "phase_count": meta.study.phase_count,
            "rows": meta.study.rows,
            "cols": meta.study.cols,
            "slice_count": meta.study.slice_count,
            "pixel_spacing": meta.study.pixel_spacing,
            "slice_thickness": meta.study.slice_thickness,
        },
        "phases": phase_meta,
        "has_igtv": has_igtv,
        "has_trajectory": has_trajectory,
        "provenance": {
            "source_type": meta.provenance.source_type,
            "source_files_count": meta.provenance.source_files_count,
            "converter_version": meta.provenance.converter_version,
            "conversion_date": meta.provenance.conversion_date,
            "model_version": meta.provenance.model_version,
        },
        "file_size_bytes": os.path.getsize(path),
    }


def _encode_png(array: np.ndarray) -> str:
    from PIL import Image

    image = Image.fromarray(array)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


# ---------------------------------------------------------------------------
# Viewer sessions: inspect a TICI file without importing it into the database
# ---------------------------------------------------------------------------

@router.post("/viewer/open")
def open_tici_viewer(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Open a TICI file in an access-scoped temporary viewer session."""
    if not file.filename or not file.filename.lower().endswith(".tici"):
        raise HTTPException(400, "请选择 .tici 文件")

    viewer_id = uuid.uuid4()
    path = _get_viewer_path(viewer_id, current_user)
    bytes_written = 0

    try:
        with open(path, "wb") as target:
            while True:
                chunk = file.file.read(VIEWER_UPLOAD_CHUNK)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > VIEWER_UPLOAD_LIMIT:
                    raise HTTPException(413, "TICI 文件超过 2 GB 查看上限")
                target.write(chunk)

        if bytes_written == 0:
            raise HTTPException(400, "TICI 文件为空")

        info = _viewer_info(path, viewer_id)
        if not info["phases"]:
            raise HTTPException(400, "TICI 文件不包含可查看的时相")
        info["filename"] = os.path.basename(file.filename)
        return info
    except HTTPException:
        if os.path.exists(path):
            os.remove(path)
        raise
    except ValueError as exc:
        if os.path.exists(path):
            os.remove(path)
        raise HTTPException(400, f"无效的 TICI 文件：{exc}")
    except OSError:
        if os.path.exists(path):
            os.remove(path)
        raise HTTPException(400, "TICI 文件损坏或无法读取")
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        raise HTTPException(500, "打开 TICI 文件失败")


@router.get("/viewer/{viewer_id}/info")
def get_tici_viewer_info(
    viewer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    """Return metadata for a viewer session."""
    path = _get_viewer_path(viewer_id, current_user)
    if not os.path.exists(path):
        raise HTTPException(404, "查看会话不存在或已关闭")
    return _viewer_info(path, viewer_id)


@router.get("/viewer/{viewer_id}/slice")
def get_tici_viewer_slice(
    viewer_id: uuid.UUID,
    phase: int = 0,
    slice: int = 0,
    window_center: float | None = None,
    window_width: float | None = None,
    include_mask: bool = True,
    current_user: User = Depends(get_current_user),
):
    """Render one lazily-read TICI slice and its optional mask."""
    path = _get_viewer_path(viewer_id, current_user)
    if not os.path.exists(path):
        raise HTTPException(404, "查看会话不存在或已关闭")
    if phase < 0 or slice < 0:
        raise HTTPException(400, "时相和层号不能为负数")
    if window_width is not None and window_width <= 0:
        raise HTTPException(400, "窗宽必须大于 0")

    try:
        with TiciReader(path) as reader:
            shape = reader.get_phase_shape(phase)
            image_slice = reader.get_phase_slice(phase, slice)
            mask_slice = (
                reader.get_phase_mask_slice(phase, slice)
                if include_mask
                else None
            )
    except KeyError:
        raise HTTPException(404, f"时相 {phase} 不存在")
    except IndexError:
        raise HTTPException(404, f"层 {slice} 超出范围")

    finite = image_slice[np.isfinite(image_slice)]
    if finite.size == 0:
        raw_min = raw_max = 0.0
        lower, upper = 0.0, 1.0
        window_center = 0.5
        window_width = 1.0
    else:
        raw_min = float(finite.min())
        raw_max = float(finite.max())
        if window_center is None or window_width is None:
            lower, upper = np.percentile(finite, [1.0, 99.0]).astype(float)
            if upper <= lower:
                lower, upper = raw_min, raw_max
            if upper <= lower:
                upper = lower + 1.0
            window_center = (lower + upper) / 2.0
            window_width = upper - lower
        else:
            lower = window_center - window_width / 2.0
            upper = window_center + window_width / 2.0

    normalized = np.nan_to_num(
        np.clip((image_slice - lower) / (upper - lower), 0.0, 1.0),
        nan=0.0,
        posinf=1.0,
        neginf=0.0,
    )
    image_u8 = (normalized * 255.0).astype(np.uint8)

    mask_base64 = None
    if mask_slice is not None:
        if mask_slice.shape != image_slice.shape:
            raise HTTPException(422, "当前层的图像与掩膜尺寸不一致")
        mask_pixels = mask_slice > 0
        mask_rgba = np.zeros((*mask_slice.shape, 4), dtype=np.uint8)
        mask_rgba[..., 0] = 255
        mask_rgba[..., 1] = 72
        mask_rgba[..., 2] = 72
        mask_rgba[..., 3] = mask_pixels.astype(np.uint8) * 255
        mask_base64 = _encode_png(mask_rgba)

    return {
        "viewer_id": str(viewer_id),
        "phase": phase,
        "slice": slice,
        "width": int(image_slice.shape[1]),
        "height": int(image_slice.shape[0]),
        "total_slices": int(shape[0]),
        "image_base64": _encode_png(image_u8),
        "mask_base64": mask_base64,
        "has_mask": mask_base64 is not None,
        "raw_min": raw_min,
        "raw_max": raw_max,
        "window_center": float(window_center),
        "window_width": float(window_width),
    }


@router.delete("/viewer/{viewer_id}")
def close_tici_viewer(
    viewer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    """Close a viewer session and remove its temporary copy."""
    path = _get_viewer_path(viewer_id, current_user)
    if os.path.exists(path):
        os.remove(path)
    return {"status": "closed", "viewer_id": str(viewer_id)}


# ---------------------------------------------------------------------------
# Import: import a .tici file into the system
# ---------------------------------------------------------------------------

@router.post("/import")
def import_tici(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import a .tici file. Reads metadata and images, creates DB records."""
    if not file.filename or not file.filename.lower().endswith(".tici"):
        raise HTTPException(400, "Only .tici files are accepted")

    # Save uploaded file temporarily
    os.makedirs(TICI_DIR, exist_ok=True)
    tmp_name = f"_import_{uuid.uuid4().hex}.tici"
    tmp_path = os.path.join(TICI_DIR, tmp_name)
    try:
        content = file.file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        with TiciReader(tmp_path) as reader:
            meta = reader.get_metadata()
            phase_count = reader.phase_count

        if phase_count == 0:
            raise HTTPException(400, "Empty .tici file (no phases)")

        # Create or find patient
        patient_code = meta.patient.patient_id or f"TICI-{uuid.uuid4().hex[:8]}"
        patient = db.query(Patient).filter(Patient.patient_code == patient_code).first()
        if not patient:
            patient = Patient(
                patient_code=patient_code,
                gender=meta.patient.patient_sex[:1] if meta.patient.patient_sex else None,
                age_range=meta.patient.patient_age or None,
                user_id=current_user.id,
            )
            db.add(patient)
            db.flush()

        # Create study
        study_date = None
        if meta.study.study_date and len(meta.study.study_date) >= 8:
            try:
                study_date = datetime.strptime(meta.study.study_date[:8], "%Y%m%d").date()
            except ValueError:
                pass

        study = Study(
            patient_id=patient.id,
            study_uid=meta.study.study_uid or f"tici-{uuid.uuid4().hex}",
            study_date=study_date,
            phase_count=phase_count,
        )
        db.add(study)
        db.flush()

        # Store .tici file permanently
        tici_name = f"study_{study.id}.tici"
        tici_path = os.path.join(TICI_DIR, tici_name)
        if tmp_path != tici_path:
            os.replace(tmp_path, tici_path)
            tmp_path = tici_path  # prevent double cleanup

        study.tici_path = tici_path

        # Extract images from .tici and create DICOM-style slices
        phase_info = reader.get_phase_meta()
        for pinfo in phase_info:
            phase_key = pinfo["phase"]  # e.g. "phase_0"
            phase_idx = int(phase_key.split("_")[1])
            shape = pinfo.get("shape", [])

            if not shape:
                continue

            series_uid = f"{study.study_uid}_{phase_idx}"
            series = Series(
                study_id=study.id,
                series_uid=series_uid,
                phase_index=phase_idx,
                slice_count=shape[0] if len(shape) > 0 else 0,
            )
            db.add(series)
            db.flush()

            # Load images for this phase
            images = reader.get_phase_images(phase_idx)
            masks = reader.get_phase_masks(phase_idx)

            mask_dir = os.path.join(DICOM_DIR, f"masks/{study.id}")
            os.makedirs(mask_dir, exist_ok=True)

            for z in range(images.shape[0]):
                slice_img = images[z]
                # Denormalize to uint16 for DICOM storage
                if slice_img.max() > slice_img.min():
                    dcm_pixels = ((slice_img - slice_img.min()) / (slice_img.max() - slice_img.min()) * 4095).astype(np.uint16)
                else:
                    dcm_pixels = np.zeros_like(slice_img, dtype=np.uint16)

                # Save as minimal DICOM
                slice_dcm_name = f"tici_p{phase_idx}_z{z:04d}.dcm"
                slice_dcm_path = os.path.join(DICOM_DIR, slice_dcm_name)
                os.makedirs(DICOM_DIR, exist_ok=True)

                try:
                    import pydicom
                    from pydicom.dataset import Dataset
                    ds = Dataset()
                    ds.PatientID = patient.patient_code
                    ds.StudyInstanceUID = study.study_uid
                    ds.Modality = "CT"
                    ds.Rows = images.shape[1]
                    ds.Columns = images.shape[2]
                    ds.BitsAllocated = 16
                    ds.BitsStored = 16
                    ds.HighBit = 15
                    ds.PixelRepresentation = 0
                    ds.SamplesPerPixel = 1
                    ds.PhotometricInterpretation = "MONOCHROME2"
                    ds.InstanceNumber = z
                    ds.SliceLocation = float(z)
                    ds.PixelData = dcm_pixels.tobytes()
                    ds.save_as(slice_dcm_path, write_like_original=False)
                except Exception:
                    # Fallback: raw save
                    slice_dcm_path = os.path.join(DICOM_DIR, f"tici_p{phase_idx}_z{z:04d}.raw")
                    slice_img.astype(np.float32).tobytes()
                    with open(slice_dcm_path, "wb") as sf:
                        sf.write(slice_img.astype(np.float32).tobytes())

                rel_path = os.path.relpath(slice_dcm_path, DICOM_DIR)
                slc = Slice(
                    series_id=series.id,
                    file_path=rel_path,
                    slice_index=z,
                    z_position=float(z),
                )
                db.add(slc)
                db.flush()

                # Save mask if available
                if masks is not None and z < masks.shape[0]:
                    mask_path = os.path.join(mask_dir, f"mask_{slc.id}.npy")
                    np.save(mask_path, masks[z])
                    rel_mask = os.path.relpath(mask_path, DICOM_DIR)
                    seg = Segmentation(
                        slice_id=slc.id,
                        mask_path=rel_mask,
                        dice_score=0.0,
                        model_version="imported-via-tici",
                    )
                    db.add(seg)

        # Import IGTV if present
        igtv_data = reader.get_igtv()
        if igtv_data is not None and igtv_data.mask is not None:
            mesh_dir = os.path.join(DICOM_DIR, f"igtv/{study.id}")
            os.makedirs(mesh_dir, exist_ok=True)

            # Save ITV mask
            mask_path = os.path.join(mesh_dir, "itv_mask.npy")
            np.save(mask_path, igtv_data.mask)
            rel_mask = os.path.relpath(mask_path, DICOM_DIR)

            # Save mesh
            mesh_path = os.path.join(mesh_dir, "igtv.obj")
            with open(mesh_path, "w", encoding="utf-8") as mf:
                mf.write(igtv_data.mesh)
            rel_mesh = os.path.relpath(mesh_path, DICOM_DIR)

            existing = db.query(IgtvResult).filter(IgtvResult.study_id == study.id).first()
            if not existing:
                igtv_result = IgtvResult(
                    study_id=study.id,
                    volume_cc=igtv_data.volume_cc,
                    mesh_path=rel_mesh,
                )
                db.add(igtv_result)

        # Import trajectory if present
        traj_data = reader.get_trajectory()
        if traj_data is not None and traj_data.centroids is not None:
            for i, c in enumerate(traj_data.centroids):
                db.add(Trajectory(
                    study_id=study.id,
                    phase_index=i,
                    x_pos=float(c[0]),
                    y_pos=float(c[1]),
                    z_pos=float(c[2]),
                    is_predicted=1 if i >= 7 else 0,
                ))

        db.commit()

        return {
            "status": "ok",
            "study_id": study.id,
            "study_uid": study.study_uid,
            "phase_count": phase_count,
            "patient_code": patient.patient_code,
            "has_igtv": igtv_data is not None and igtv_data.mask is not None,
            "has_trajectory": traj_data is not None and traj_data.centroids is not None,
            "tici_path": tici_path,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to import .tici file: {str(e)}")
    finally:
        if os.path.exists(tmp_path) and tmp_path != _get_tici_path(0):  # cleanup only if temp
            try:
                # Check if tmp_path was already moved
                if os.path.exists(tmp_path) and tmp_path.startswith(TICI_DIR) and "_import_" in tmp_path:
                    pass  # Already handled by os.replace
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Export: full export of a study to .tici
# ---------------------------------------------------------------------------

@router.post("/export/{study_id}")
def export_tici(
    study_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export all data for a study into a single .tici file."""
    study = _get_study_with_access(study_id, db, current_user)
    patient = db.query(Patient).filter(Patient.id == study.patient_id).first()

    tici_path = _get_tici_path(study_id)
    os.makedirs(TICI_DIR, exist_ok=True)

    with TiciWriter(tici_path, "w") as w:
        # Metadata
        w.write_metadata(
            patient={
                "patient_id": patient.patient_code if patient else "",
                "patient_name": patient.patient_code if patient else "",
                "patient_sex": patient.gender if patient else "",
                "patient_age": patient.age_range if patient else "",
            },
            study={
                "study_uid": study.study_uid,
                "study_date": str(study.study_date) if study.study_date else "",
                "modality": "CT",
                "phase_count": study.phase_count or 10,
                "rows": 512,
                "cols": 512,
                "slice_count": 0,
                "pixel_spacing": [1.0, 1.0],
                "slice_thickness": 1.0,
            },
        )

        # Load slices by phase and write images
        series_list = db.query(Series).filter(
            Series.study_id == study_id
        ).order_by(Series.phase_index).all()

        slice_count = 0
        for series in series_list:
            slices = db.query(Slice).filter(
                Slice.series_id == series.id
            ).order_by(Slice.z_position).all()

            if not slices:
                continue

            phase_images = []
            phase_masks = []
            for slc in slices:
                full_path = os.path.join(DICOM_DIR, slc.file_path) if slc.file_path else ""
                if not os.path.exists(full_path):
                    continue
                try:
                    import pydicom
                    ds = pydicom.dcmread(full_path)
                    img = ds.pixel_array.astype(np.float32)
                    if img.max() > img.min():
                        img = (img - img.min()) / (img.max() - img.min())
                    phase_images.append(img)
                except Exception:
                    continue

                # Check for mask
                seg = db.query(Segmentation).filter(Segmentation.slice_id == slc.id).first()
                if seg and seg.mask_path:
                    mask_full = os.path.join(DICOM_DIR, seg.mask_path)
                    if os.path.exists(mask_full):
                        try:
                            mask = np.load(mask_full)
                            phase_masks.append(mask.astype(np.uint8))
                        except Exception:
                            pass

            if phase_images:
                images_vol = np.stack(phase_images, axis=0)
                masks_vol = np.stack(phase_masks, axis=0) if phase_masks else None
                w.write_phase_images(series.phase_index, images_vol, masks=masks_vol)
                slice_count = max(slice_count, len(phase_images))

        # IGTV
        igtv = db.query(IgtvResult).filter(IgtvResult.study_id == study_id).first()
        if igtv:
            itv_mask = None
            mesh_text = ""
            if igtv.mesh_path:
                mesh_full = os.path.join(DICOM_DIR, igtv.mesh_path)
                if os.path.exists(mesh_full):
                    with open(mesh_full, "r", encoding="utf-8") as f:
                        mesh_text = f.read()
            # Try mask
            mask_dir = os.path.join(DICOM_DIR, f"igtv/{study_id}")
            mask_candidates = [
                os.path.join(mask_dir, "itv_mask.npy"),
                os.path.join(DICOM_DIR, f"masks/{study_id}/itv_mask.npy"),
            ]
            for mp in mask_candidates:
                if os.path.exists(mp):
                    itv_mask = np.load(mp).astype(np.uint8)
                    break
            if itv_mask is not None:
                w.write_igtv(itv_mask, mesh_text, igtv.volume_cc or 0.0, method="union")

        # Trajectory
        trajs = db.query(Trajectory).filter(
            Trajectory.study_id == study_id
        ).order_by(Trajectory.phase_index).all()
        if trajs:
            centroids = np.array([[t.x_pos, t.y_pos, t.z_pos] for t in trajs], dtype=np.float32)
            observed = centroids[:7] if len(centroids) >= 7 else centroids
            predicted_pts = [t for t in trajs if t.is_predicted]
            predicted = np.array([[t.x_pos, t.y_pos, t.z_pos] for t in predicted_pts], dtype=np.float32)
            if len(predicted) == 0:
                predicted = np.zeros((0, 3), dtype=np.float32)
            w.write_trajectory(centroids, observed, predicted, model_name="LungTic-builtin")

        # Provenance
        from datetime import datetime
        w.write_provenance({
            "source_type": "dicom",
            "source_files_count": slice_count,
            "converter_version": "LungTic-1.0.0",
            "conversion_date": datetime.now().isoformat(),
        })

    # Update study record with path
    study.tici_path = tici_path
    db.commit()

    return {
        "status": "ok",
        "study_id": study_id,
        "tici_path": tici_path,
        "phase_count": study.phase_count,
    }


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

@router.get("/download/{study_id}")
def download_tici(
    study_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the .tici file for a study."""
    _get_study_with_access(study_id, db, current_user)

    tici_path = _get_tici_path(study_id)
    if not os.path.exists(tici_path):
        raise HTTPException(404, "TICI file not found. Please export first via POST /api/tici/export/{study_id}")

    return FileResponse(
        path=tici_path,
        filename=f"study_{study_id}.tici",
        media_type="application/octet-stream",
    )


# ---------------------------------------------------------------------------
# Info (metadata without loading images)
# ---------------------------------------------------------------------------

@router.get("/info/{study_id}")
def get_tici_info(
    study_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get .tici metadata (does NOT load image data)."""
    _get_study_with_access(study_id, db, current_user)

    tici_path = _get_tici_path(study_id)
    if not os.path.exists(tici_path):
        return {
            "study_id": study_id,
            "status": "not_exported",
            "message": "TICI file not found. Please export first.",
        }

    with TiciReader(tici_path) as r:
        meta = r.get_metadata()
        phase_meta = r.get_phase_meta()

    return {
        "study_id": study_id,
        "status": "ready",
        "format_version": r.format_version,
        "patient": {
            "patient_id": meta.patient.patient_id,
            "patient_name": meta.patient.patient_name,
            "patient_sex": meta.patient.patient_sex,
            "patient_age": meta.patient.patient_age,
        },
        "study": {
            "study_uid": meta.study.study_uid,
            "study_date": meta.study.study_date,
            "modality": meta.study.modality,
            "phase_count": meta.study.phase_count,
            "rows": meta.study.rows,
            "cols": meta.study.cols,
            "slice_count": meta.study.slice_count,
            "pixel_spacing": meta.study.pixel_spacing,
            "slice_thickness": meta.study.slice_thickness,
        },
        "phases": phase_meta,
        "has_igtv": "igtv" in phase_meta if False else False,
        "has_trajectory": "trajectory" in phase_meta if False else False,
        "provenance": {
            "source_type": meta.provenance.source_type,
            "source_files_count": meta.provenance.source_files_count,
            "converter_version": meta.provenance.converter_version,
            "conversion_date": meta.provenance.conversion_date,
        },
        "file_size_bytes": os.path.getsize(tici_path) if os.path.exists(tici_path) else 0,
    }


# ---------------------------------------------------------------------------
# Preview: single slice image from a specific phase
# ---------------------------------------------------------------------------

@router.get("/preview/{study_id}")
def preview_tici_slice(
    study_id: int,
    phase: int = 0,
    slice: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview a specific slice from a specific phase as base64 PNG."""
    _get_study_with_access(study_id, db, current_user)

    tici_path = _get_tici_path(study_id)
    if not os.path.exists(tici_path):
        raise HTTPException(404, "TICI file not found. Please export first.")

    with TiciReader(tici_path) as r:
        try:
            images = r.get_phase_images(phase)
        except KeyError:
            raise HTTPException(404, f"Phase {phase} not found")
        except Exception as e:
            raise HTTPException(500, f"Error reading phase {phase}: {str(e)}")

        if slice < 0 or slice >= images.shape[0]:
            raise HTTPException(404, f"Slice {slice} out of range (0-{images.shape[0]-1})")

        img_slice = images[slice]

        # Normalize to uint8
        if img_slice.max() > img_slice.min():
            img_slice = (img_slice - img_slice.min()) / (img_slice.max() - img_slice.min())
        img_slice = (img_slice * 255).astype(np.uint8)

        from PIL import Image
        pil_img = Image.fromarray(img_slice)
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        buf.seek(0)

        return {
            "study_id": study_id,
            "phase": phase,
            "slice": slice,
            "width": img_slice.shape[1],
            "height": img_slice.shape[0],
            "image_base64": base64.b64encode(buf.read()).decode("utf-8"),
            "total_slices": images.shape[0],
        }
