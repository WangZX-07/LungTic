"""Convert DICOM directories and NIfTI files to .tiCi format."""

import os
import uuid
import pydicom
import numpy as np
from datetime import datetime
from typing import Optional

from .tici_io import TiciWriter, CONVERTER_VERSION


def from_dicom_dir(dicom_dir: str, output_path: str) -> str:
    """Convert a directory of DICOM files into a single .tici file.

    Args:
        dicom_dir: Directory containing .dcm files.
        output_path: Destination .tici file path.

    Returns:
        The output_path.
    """
    # Collect all DICOM files
    dcm_files = []
    for root, dirs, files in os.walk(dicom_dir):
        for f in files:
            if f.lower().endswith(".dcm"):
                dcm_files.append(os.path.join(root, f))

    if not dcm_files:
        raise ValueError(f"No .dcm files found in {dicom_dir}")

    # Parse metadata from first file
    first_ds = pydicom.dcmread(dcm_files[0], force=True, stop_before_pixels=True)

    patient = {
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

    # Keep only paths and metadata; scan one image at a time for the global range.
    slices_info = []
    pmin, pmax = float("inf"), float("-inf")
    for path in dcm_files:
        ds = pydicom.dcmread(path, force=True)
        inst = int(getattr(ds, "InstanceNumber", 0))
        sloc = float(getattr(ds, "SliceLocation", 0))
        pixels = ds.pixel_array
        pmin = min(pmin, float(pixels.min()))
        pmax = max(pmax, float(pixels.max()))
        slices_info.append({
            "path": path,
            "phase": inst % 10,
            "z": sloc,
        })

    phases: dict[int, list[dict]] = {}
    for item in slices_info:
        phases.setdefault(item["phase"], []).append(item)
    for phase_slices in phases.values():
        phase_slices.sort(key=lambda item: item["z"])

    max_slices = max(len(items) for items in phases.values())
    slice_locations = sorted(set(item["z"] for item in slices_info))

    def normalized_pixels(path: str) -> np.ndarray:
        pixels = pydicom.dcmread(path, force=True).pixel_array.astype(np.float32)
        if pmax > pmin:
            pixels -= pmin
            pixels /= pmax - pmin
        return pixels

    study = {
        "study_uid": str(getattr(first_ds, "StudyInstanceUID", uuid.uuid4().hex)),
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

    provenance = {
        "source_type": "dicom",
        "source_files_count": len(dcm_files),
        "converter_version": CONVERTER_VERSION,
        "conversion_date": datetime.now().isoformat(),
    }

    # Write
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with TiciWriter(output_path, "w") as w:
        w.write_metadata(patient, study)
        for phase_idx in sorted(phases.keys()):
            phase_slices = phases[phase_idx]
            # Build 3D volume (Z, H, W)
            volume = np.stack([normalized_pixels(item["path"]) for item in phase_slices], axis=0)
            w.write_phase_images(phase_idx, volume)
        w.write_provenance(provenance)

    return output_path


def from_nifti(nifti_path: str, output_path: str) -> str:
    """Convert a 4D NIfTI (.nii/.nii.gz) file to .tici format.

    The 4th dimension (time) becomes phases in the .tici file.
    """
    import nibabel as nib

    img = nib.load(nifti_path)
    header = img.header

    nx, ny, nz = img.shape[:3]
    has_time_axis = len(img.shape) > 3
    nt = img.shape[3] if has_time_axis else 1

    zooms = header.get_zooms()
    sx, sy, sz = zooms[:3]

    patient = {
        "patient_id": "NIFTI",
        "patient_name": os.path.basename(nifti_path),
        "patient_sex": "",
        "patient_age": "",
    }

    study = {
        "study_uid": f"nifti_{os.path.basename(nifti_path)}",
        "study_date": "",
        "modality": "NIfTI",
        "phase_count": nt,
        "rows": ny,
        "cols": nx,
        "slice_count": nz,
        "pixel_spacing": [float(sy), float(sx)],
        "slice_thickness": float(sz),
        "slice_locations": [float(i * sz) for i in range(nz)],
    }

    # ArrayProxy slicing reads one phase at a time, including compressed NIfTI.
    def read_phase(t: int) -> np.ndarray:
        volume = img.dataobj[:, :, :, t] if has_time_axis else img.dataobj[:, :, :]
        return np.array(volume, dtype=np.float32, copy=True)

    dmin, dmax = float("inf"), float("-inf")
    for t in range(nt):
        phase = read_phase(t)
        dmin = min(dmin, float(phase.min()))
        dmax = max(dmax, float(phase.max()))

    provenance = {
        "source_type": "nifti",
        "source_files_count": 1,
        "converter_version": CONVERTER_VERSION,
        "conversion_date": datetime.now().isoformat(),
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with TiciWriter(output_path, "w") as w:
        w.write_metadata(patient, study)
        for t in range(nt):
            volume = read_phase(t)
            if dmax > dmin:
                volume -= dmin
                volume /= dmax - dmin
            # NIfTI uses (X, Y, Z); TICI uses (Z, Y, X).
            w.write_phase_images(t, np.transpose(volume, (2, 1, 0)))
        w.write_provenance(provenance)

    return output_path


def from_study(study_id: int, db_session) -> TiciWriter:
    """Create a TiciWriter pre-populated with metadata from DB study.

    Returns the opened TiciWriter 锟?caller must use as context manager.

    Args:
        study_id: Database study ID.
        db_session: SQLAlchemy session.

    Returns:
        TiciWriter instance (must be used with `with`).
    """
    from ..backend.models.db_models import Study, Patient, Series, Slice
    from ..backend.config import TICI_DIR
    import os as _os

    study = db_session.query(Study).filter(Study.id == study_id).first()
    if not study:
        raise ValueError(f"Study {study_id} not found")

    patient = db_session.query(Patient).filter(Patient.id == study.patient_id).first()

    # Determine output path
    tici_name = f"study_{study_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tici"
    output_path = _os.path.join(TICI_DIR, tici_name)

    _os.makedirs(TICI_DIR, exist_ok=True)

    writer = TiciWriter(output_path, "w")
    writer.__enter__()

    patient_dict = {
        "patient_id": patient.patient_code if patient else f"DB-{study_id}",
        "patient_name": patient.patient_code if patient else "",
        "patient_sex": patient.gender if patient else "",
        "patient_age": patient.age_range if patient else "",
    }

    # Count slices and get locations from first series
    slice_count = 0
    slice_locations = []
    first_series = db_session.query(Series).filter(Series.study_id == study_id).first()
    if first_series:
        slices = db_session.query(Slice).filter(Slice.series_id == first_series.id).order_by(Slice.z_position).all()
        slice_count = len(slices)
        slice_locations = [s.z_position for s in slices if s.z_position is not None]

    study_dict = {
        "study_uid": study.study_uid,
        "study_date": str(study.study_date) if study.study_date else "",
        "modality": "CT",
        "phase_count": study.phase_count or 10,
        "rows": 512,
        "cols": 512,
        "slice_count": slice_count,
        "pixel_spacing": [1.0, 1.0],
        "slice_thickness": 1.0,
        "slice_locations": slice_locations,
    }

    writer.write_metadata(patient_dict, study_dict)
    writer.write_provenance({
        "source_type": "dicom",
        "converter_version": CONVERTER_VERSION,
        "conversion_date": datetime.now().isoformat(),
    })

    return writer
