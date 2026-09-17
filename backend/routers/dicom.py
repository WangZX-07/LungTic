"""DICOM management API routes."""

import os
import io
import base64
import sys
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from routers.auth import get_current_user
from models.db_models import User, Patient, Study, Series, Slice
from services.dicom_parser import parse_dicom, store_dicom, group_slices_by_phase, parse_nifti, store_nifti
from config import DICOM_DIR, TICI_DIR
from datetime import datetime

router = APIRouter(prefix="/api/dicom", tags=["dicom"])


def check_patient_access(patient: Patient, current_user: User):
    """Check if current user has access to this patient. Raises 403 if not."""
    user_role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    if user_role in ("doctor", "admin"):
        return True
    # patient role: double matching
    if patient.user_id == current_user.id:
        return True
    if current_user.patient_code and patient.patient_code == current_user.patient_code:
        return True
    raise HTTPException(status_code=403, detail="Access denied")


def _create_tici_from_upload(study_id: int, study_uid: str, db: Session):
    """Create .tici file from uploaded DICOM files for a given study."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from tici import TiciWriter

        study = db.query(Study).filter(Study.id == study_id).first()
        if not study:
            return

        # Load DICOM dir for this study
        dicom_study_dir = os.path.join(DICOM_DIR, study_uid)
        if not os.path.isdir(dicom_study_dir):
            return

        dcm_files = [f for f in os.listdir(dicom_study_dir) if f.lower().endswith(".dcm")]
        if not dcm_files:
            return

        # Read first DICOM for metadata
        import pydicom
        first_path = os.path.join(dicom_study_dir, dcm_files[0])
        first_ds = pydicom.dcmread(first_path, force=True)

        # Patient metadata
        patient_obj = db.query(Patient).filter(Patient.id == study.patient_id).first()
        patient_dict = {
            "patient_id": str(getattr(first_ds, "PatientID", "UNKNOWN")),
            "patient_name": str(getattr(first_ds, "PatientName", "UNKNOWN")),
            "patient_sex": str(getattr(first_ds, "PatientSex", "")),
            "patient_age": str(getattr(first_ds, "PatientAge", "")),
        }

        rows = int(getattr(first_ds, "Rows", 512))
        cols = int(getattr(first_ds, "Columns", 512))

        import re
        ps_str = str(getattr(first_ds, "PixelSpacing", "[1, 1]"))
        nums = re.findall(r"[\d.]+", ps_str)
        pixel_spacing = [float(nums[0]) if len(nums) > 0 else 1.0,
                         float(nums[1]) if len(nums) > 1 else 1.0]

        slice_thickness = float(getattr(first_ds, "SliceThickness", 1.0))

        # Collect all slices grouped by phase
        all_slices = []
        for fname in dcm_files:
            try:
                ds = pydicom.dcmread(os.path.join(dicom_study_dir, fname), force=True)
                inst = int(getattr(ds, "InstanceNumber", 0))
                sloc = float(getattr(ds, "SliceLocation", 0))
                all_slices.append({
                    "path": os.path.join(dicom_study_dir, fname),
                    "instance": inst,
                    "phase": inst % 10,
                    "z": sloc,
                })
            except Exception:
                continue

        # Group by phase
        phases: dict[int, list] = {}
        for s in all_slices:
            p = s["phase"]
            if p not in phases:
                phases[p] = []
            phases[p].append(s)

        for p in phases:
            phases[p].sort(key=lambda x: x["z"])

        max_slices = max(len(v) for v in phases.values()) if phases else 0
        slice_locations = sorted(set(s["z"] for s in all_slices))

        # Normalize min/max across all files
        pmin, pmax = float("inf"), float("-inf")
        phase_pixel_data = {}
        for phase_idx, slist in phases.items():
            pixel_list = []
            for s in slist:
                ds = pydicom.dcmread(s["path"], force=True)
                pixels = ds.pixel_array.astype(np.float32)
                pmin = min(pmin, pixels.min())
                pmax = max(pmax, pixels.max())
                pixel_list.append(pixels)
            phase_pixel_data[phase_idx] = pixel_list

        # Study metadata
        study_dict = {
            "study_uid": study_uid,
            "study_date": str(getattr(first_ds, "StudyDate", "")),
            "modality": str(getattr(first_ds, "Modality", "CT")),
            "phase_count": len(phases),
            "rows": rows,
            "cols": cols,
            "slice_count": max_slices,
            "pixel_spacing": pixel_spacing,
            "slice_thickness": slice_thickness,
            "slice_locations": slice_locations,
        }

        # Write .tici
        tici_name = f"study_{study_id}.tici"
        tici_path = os.path.join(TICI_DIR, tici_name)
        os.makedirs(TICI_DIR, exist_ok=True)

        with TiciWriter(tici_path, "w") as w:
            w.write_metadata(patient_dict, study_dict)
            for phase_idx in sorted(phases.keys()):
                vol_pixels = phase_pixel_data[phase_idx]
                if pmax > pmin:
                    vol_pixels = [(p - pmin) / (pmax - pmin) for p in vol_pixels]
                vol = np.stack(vol_pixels, axis=0).astype(np.float32)
                w.write_phase_images(phase_idx, vol)
            w.write_provenance({
                "source_type": "dicom",
                "source_files_count": len(dcm_files),
                "converter_version": "LungTic-1.0.0",
                "conversion_date": datetime.now().isoformat(),
            })

        # Update study record
        study.tici_path = tici_path
        db.commit()

    except Exception:
        pass  # Silently skip .tici creation on failure; data is still in DB


@router.post("/upload")
def upload_dicom(
    files: list[UploadFile] = File(...),
    patient_id_override: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload multiple DICOM files. Auto-parses metadata and stores slices."""
    if not files:
        raise HTTPException(400, "No files provided")

    # Separate DICOM and NIfTI files
    dicom_files = []
    nifti_files = []
    for file in files:
        fn = (file.filename or "").lower()
        if fn.endswith(".nii") or fn.endswith(".nii.gz"):
            nifti_files.append(file)
        else:
            dicom_files.append(file)

    results = []

    # Process DICOM files
    if dicom_files:
        results.extend(_process_dicom(dicom_files, db, current_user, patient_id_override))

    # Process NIfTI files
    if nifti_files:
        results.extend(_process_nifti(nifti_files, db, current_user, patient_id_override))

    db.commit()
    total = sum(r.get("slice_count", 0) for r in results)

    # Auto-create .tici files for each study
    for result_item in results:
        study_id = result_item.get("study_id")
        study_uid = result_item.get("study_uid")
        if study_id and study_uid:
            _create_tici_from_upload(study_id, study_uid, db)

    return {"status": "ok", "studies": results, "total_files": total}


def _process_dicom(files, db, current_user, patient_id_override=""):
    parsed = []
    for file in files:
        file_data = file.file.read()
        tmp_path = os.path.join(DICOM_DIR, "_tmp.dcm")
        os.makedirs(DICOM_DIR, exist_ok=True)
        with open(tmp_path, "wb") as f:
            f.write(file_data)

        try:
            meta = parse_dicom(tmp_path)
            meta["filename"] = file.filename or "unknown.dcm"
            meta["size"] = len(file_data)
            parsed.append(meta)
        except Exception as e:
            os.remove(tmp_path)
            raise HTTPException(400, f"Failed to parse {file.filename}: {str(e)}")

    if not parsed:
        raise HTTPException(400, "No valid DICOM files")

    # Group by study
    study_groups: dict[str, list[dict]] = {}
    for p in parsed:
        uid = p["study_uid"]
        if uid not in study_groups:
            study_groups[uid] = []
        study_groups[uid].append(p)

    results = []
    for study_uid, slices in study_groups.items():
        first = slices[0]

        # Find or create patient
        search_code = patient_id_override if patient_id_override else first["patient_id"]

        patient = db.query(Patient).filter(
            Patient.patient_code == search_code
        ).first()
        if not patient:
            patient = Patient(
                patient_code=first["patient_id"],
                gender=first["patient_sex"][:1] if first["patient_sex"] else None,
                user_id=current_user.id,
            )
            db.add(patient)
            db.flush()
        elif patient.user_id is None:
            patient.user_id = current_user.id

        # Find or create study
        study = db.query(Study).filter(Study.study_uid == study_uid).first()
        if not study:
            study_date = None
            if first["study_date"] and len(first["study_date"]) >= 8:
                try:
                    study_date = datetime.strptime(first["study_date"][:8], "%Y%m%d").date()
                except ValueError:
                    pass
            study = Study(
                patient_id=patient.id,
                study_uid=study_uid,
                study_date=study_date,
                phase_count=10,
            )
            db.add(study)
            db.flush()

        # Group by phase
        phases = group_slices_by_phase(slices)

        for phase_idx in sorted(phases.keys()):
            phase_slices = phases[phase_idx]

            series_uid = f"{study_uid}_{phase_idx}"
            series = (
                db.query(Series)
                .filter(Series.series_uid == series_uid)
                .first()
            )
            if not series:
                series = Series(
                    study_id=study.id,
                    series_uid=series_uid,
                    phase_index=phase_idx,
                    slice_count=0,
                )
                db.add(series)
                db.flush()

            series_slice_count = 0
            for s in phase_slices:
                file_path = store_dicom(
                    file_content=open(s.get("_tmp_path", ""), "rb").read() if s.get("_tmp_path") else b"",
                    filename=s["filename"],
                    study_uid=study_uid,
                )
                slc = Slice(
                    series_id=series.id,
                    file_path=file_path,
                    slice_index=s["instance_number"],
                    z_position=s["slice_location"],
                )
                db.add(slc)
                series_slice_count += 1

            series.slice_count = series_slice_count

        results.append({
            "study_uid": study_uid,
            "study_id": study.id,
            "phase_count": len(phases),
            "slice_count": len(slices),
        })

    return results


def _process_nifti(files, db, current_user, patient_id_override=""):
    parsed = []
    for file in files:
        file_data = file.file.read()
        safe_name = file.filename or "upload.nii.gz"
        tmp_path = os.path.join(DICOM_DIR, safe_name)
        os.makedirs(DICOM_DIR, exist_ok=True)
        with open(tmp_path, "wb") as f:
            f.write(file_data)

        try:
            slices = parse_nifti(tmp_path)
            for s in slices:
                s["filename"] = safe_name
                s["_tmp_path"] = tmp_path
            parsed.extend(slices)
        except Exception as e:
            raise HTTPException(400, f"Failed to parse {file.filename}: {str(e)}")

    if not parsed:
        raise HTTPException(400, "No valid NIfTI data")

    # Group by study_uid, but also consider time_index
    study_slices: dict[str, list[dict]] = {}
    for p in parsed:
        uid = p["study_uid"]
        if uid not in study_slices:
            study_slices[uid] = []
        study_slices[uid].append(p)

    results = []
    for study_uid, slices in study_slices.items():
        first = slices[0]
        search_code = patient_id_override if patient_id_override else first["patient_id"]

        patient = db.query(Patient).filter(
            Patient.patient_code == search_code
        ).first()
        if not patient:
            patient = Patient(
                patient_code=first["patient_id"],
                gender=first["patient_sex"][:1] if first["patient_sex"] else "",
                user_id=current_user.id,
            )
            db.add(patient)
            db.flush()
        elif patient.user_id is None:
            patient.user_id = current_user.id

        study = db.query(Study).filter(Study.study_uid == study_uid).first()
        if not study:
            study = Study(
                patient_id=patient.id,
                study_uid=study_uid,
                phase_count=10,
            )
            db.add(study)
            db.flush()

        # Group by time_index
        time_groups: dict[int, list[dict]] = {}
        for s in slices:
            t = s.get("time_index", 0)
            if t not in time_groups:
                time_groups[t] = []
            time_groups[t].append(s)

        for time_idx in sorted(time_groups.keys()):
            t_slices = time_groups[time_idx]

            series_uid = f"{study_uid}_{time_idx}"
            series = (
                db.query(Series)
                .filter(Series.series_uid == series_uid)
                .first()
            )
            if not series:
                series = Series(
                    study_id=study.id,
                    series_uid=series_uid,
                    phase_index=time_idx,
                    slice_count=0,
                )
                db.add(series)
                db.flush()

            series_slice_count = 0
            for s in t_slices:
                file_path = store_dicom(
                    file_content=s.get("nifti_data", b""),
                    filename=f"nifti_slice_{s['instance_number']}.raw",
                    study_uid=study_uid,
                )
                slc = Slice(
                    series_id=series.id,
                    file_path=file_path,
                    slice_index=s["instance_number"],
                    z_position=s["slice_location"],
                )
                db.add(slc)
                series_slice_count += 1

            series.slice_count = series_slice_count

        results.append({
            "study_uid": study_uid,
            "study_id": study.id,
            "phase_count": len(time_groups),
            "slice_count": len(slices),
        })

    return results


@router.get("/patients")
def list_patients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all patients accessible to the current user."""
    user_role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    if user_role in ("doctor", "admin"):
        patients = db.query(Patient).all()
    else:
        patients = (
            db.query(Patient)
            .filter(
                (Patient.user_id == current_user.id) |
                (Patient.patient_code == current_user.patient_code)
                if current_user.patient_code
                else Patient.user_id == current_user.id
            )
            .all()
        )

    result = []
    for p in patients:
        study_count = db.query(Study).filter(Study.patient_id == p.id).count()
        result.append({
            "id": p.id,
            "patient_code": p.patient_code,
            "gender": p.gender,
            "age_range": p.age_range,
            "study_count": study_count,
            "created_at": str(p.created_at) if p.created_at else "",
        })
    return result


@router.get("/patients/{patient_id}/studies")
def list_studies(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List studies for a patient."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient not found")
    check_patient_access(patient, current_user)

    studies = db.query(Study).filter(Study.patient_id == patient_id).all()
    return [
        {
            "id": s.id,
            "study_uid": s.study_uid,
            "study_date": str(s.study_date) if s.study_date else "",
            "phase_count": s.phase_count,
            "tici_path": s.tici_path,
        }
        for s in studies
    ]


@router.get("/studies/{study_id}/series")
def list_series(
    study_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List series (phases) for a study."""
    study = db.query(Study).filter(Study.id == study_id).first()
    if not study:
        raise HTTPException(404, "Study not found")
    patient = db.query(Patient).filter(Patient.id == study.patient_id).first()
    if patient:
        check_patient_access(patient, current_user)

    series_list = (
        db.query(Series)
        .filter(Series.study_id == study_id)
        .order_by(Series.phase_index)
        .all()
    )
    return [
        {
            "id": s.id,
            "phase_index": s.phase_index,
            "slice_count": s.slice_count,
            "series_uid": s.series_uid,
        }
        for s in series_list
    ]


@router.get("/series/{series_id}/slices")
def list_slices(
    series_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List slices for a series (phase)."""
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(404, "Series not found")
    study = db.query(Study).filter(Study.id == series.study_id).first()
    if study:
        patient = db.query(Patient).filter(Patient.id == study.patient_id).first()
        if patient:
            check_patient_access(patient, current_user)

    slices = (
        db.query(Slice)
        .filter(Slice.series_id == series_id)
        .order_by(Slice.z_position)
        .all()
    )
    return [
        {
            "id": s.id,
            "slice_index": s.slice_index,
            "z_position": s.z_position,
            "file_path": s.file_path,
        }
        for s in slices
    ]


@router.get("/slice/{slice_id}/image")
def get_slice_image(
    slice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the DICOM slice as base64 PNG image."""
    slc = db.query(Slice).filter(Slice.id == slice_id).first()
    if not slc:
        raise HTTPException(404, "Slice not found")

    # Access check
    series = db.query(Series).filter(Series.id == slc.series_id).first()
    if series:
        study = db.query(Study).filter(Study.id == series.study_id).first()
        if study:
            patient = db.query(Patient).filter(Patient.id == study.patient_id).first()
            if patient:
                check_patient_access(patient, current_user)

    full_path = os.path.join(DICOM_DIR, slc.file_path) if slc.file_path else ""
    if not os.path.exists(full_path):
        raise HTTPException(404, "File not found on disk")

    import numpy as np

    if full_path.endswith(".raw"):
        with open(full_path, "rb") as f:
            raw = f.read()
        side = int(np.sqrt(len(raw) // 4))
        pixel_array = np.frombuffer(raw, dtype=np.float32).reshape((side, side))
    else:
        import pydicom
        ds = pydicom.dcmread(full_path)
        pixel_array = ds.pixel_array.astype(np.float32)

    if pixel_array.max() > pixel_array.min():
        pixel_array = (pixel_array - pixel_array.min()) / (pixel_array.max() - pixel_array.min())
    pixel_array = (pixel_array * 255).astype(np.uint8)

    from PIL import Image
    img = Image.fromarray(pixel_array)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return {
        "slice_id": slice_id,
        "width": pixel_array.shape[1],
        "height": pixel_array.shape[0],
        "image_base64": base64.b64encode(buf.read()).decode("utf-8"),
    }


# ---- WADO-URI endpoint for Cornerstone.js ----

@router.get("/slice/{slice_id}/dicom")
def get_slice_dicom_raw(
    slice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return raw DICOM bytes for Cornerstone.js WADO-URI loader."""
    slc = db.query(Slice).filter(Slice.id == slice_id).first()
    if not slc:
        raise HTTPException(404, "Slice not found")

    # Access check
    series = db.query(Series).filter(Series.id == slc.series_id).first()
    if series:
        study = db.query(Study).filter(Study.id == series.study_id).first()
        if study:
            patient = db.query(Patient).filter(Patient.id == study.patient_id).first()
            if patient:
                check_patient_access(patient, current_user)

    full_path = os.path.join(DICOM_DIR, slc.file_path) if slc.file_path else ""
    if not os.path.exists(full_path):
        raise HTTPException(404, "File not found on disk")

    # For .dcm files, return raw bytes
    if full_path.endswith(".dcm"):
        with open(full_path, "rb") as f:
            return Response(content=f.read(), media_type="application/dicom")

    # For .raw files (NIfTI), wrap in a minimal DICOM
    import numpy as np
    import pydicom
    from pydicom.dataset import Dataset, FileDataset

    with open(full_path, "rb") as f:
        raw = f.read()
    side = int(np.sqrt(len(raw) // 4))
    pixel_array = np.frombuffer(raw, dtype=np.float32).reshape((side, side))

    # Normalize to uint16 for DICOM
    if pixel_array.max() > pixel_array.min():
        pixel_array = (pixel_array - pixel_array.min()) / (pixel_array.max() - pixel_array.min())
    pixel_array = (pixel_array * 4095).astype(np.uint16)

    ds = Dataset()
    ds.PatientName = "NIFTI"
    ds.PatientID = "NIFTI"
    ds.Modality = "CT"
    ds.Rows = side
    ds.Columns = side
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.HighBit = 11
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = pixel_array.tobytes()

    buf = io.BytesIO()
    ds.save_as(buf)
    buf.seek(0)
    return Response(content=buf.read(), media_type="application/dicom")


# ---- Delete patient ----

@router.delete("/patients/{patient_id}")
def delete_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a patient and all related data. Admin only."""
    user_role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    if user_role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient not found")
    db.delete(patient)
    db.commit()
    return {"status": "ok", "deleted": patient_id}
