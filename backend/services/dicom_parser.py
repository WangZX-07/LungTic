"""DICOM file parser using pydicom + SimpleITK."""

import os
import uuid
import pydicom
from typing import Optional
from config import DICOM_DIR


def parse_dicom(file_path: str) -> dict:
    """Parse a single DICOM file and extract key metadata."""
    ds = pydicom.dcmread(file_path, force=True)

    return {
        "patient_id": getattr(ds, "PatientID", "UNKNOWN"),
        "patient_name": str(getattr(ds, "PatientName", "UNKNOWN")),
        "patient_sex": getattr(ds, "PatientSex", ""),
        "patient_age": getattr(ds, "PatientAge", ""),
        "study_uid": getattr(ds, "StudyInstanceUID", uuid.uuid4().hex),
        "study_date": getattr(ds, "StudyDate", ""),
        "series_uid": getattr(ds, "SeriesInstanceUID", uuid.uuid4().hex),
        "series_description": getattr(ds, "SeriesDescription", ""),
        "modality": getattr(ds, "Modality", "CT"),
        "slice_location": float(getattr(ds, "SliceLocation", 0)),
        "instance_number": int(getattr(ds, "InstanceNumber", 0)),
        "rows": int(getattr(ds, "Rows", 512)),
        "cols": int(getattr(ds, "Columns", 512)),
        "pixel_spacing": str(getattr(ds, "PixelSpacing", [1, 1])),
        "slice_thickness": float(getattr(ds, "SliceThickness", 1)),
    }


def store_dicom(file_content: bytes, filename: str, study_uid: str) -> str:
    """Store DICOM file and return relative path."""
    study_dir = os.path.join(DICOM_DIR, study_uid)
    os.makedirs(study_dir, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}.dcm"
    file_path = os.path.join(study_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(file_content)

    return os.path.relpath(file_path, DICOM_DIR)


def group_slices_by_phase(slices: list[dict]) -> dict[int, list[dict]]:
    """Group slices by phase index (0-9). Uses instance_number mod 10 as phase."""
    phases: dict[int, list[dict]] = {}
    for s in slices:
        phase = s["instance_number"] % 10
        if phase not in phases:
            phases[phase] = []
        phases[phase].append(s)
    for p in phases:
        phases[p].sort(key=lambda x: x["slice_location"])
    return phases

def parse_nifti(file_path: str) -> list[dict]:
    """Parse a NIfTI (.nii/.nii.gz) file and extract slice metadata."""
    import nibabel as nib
    import numpy as np

    img = nib.load(file_path)
    data = img.get_fdata()
    header = img.header

    # Extract dimensions
    nx, ny, nz = data.shape[:3]
    nt = data.shape[3] if len(data.shape) > 3 else 1

    # Get voxel spacing
    zooms = header.get_zooms()
    sx, sy, sz = zooms[:3]

    slices = []
    for t in range(nt):
        for z in range(nz):
            slices.append({
                "patient_id": "NIFTI",
                "patient_name": os.path.basename(file_path),
                "patient_sex": "",
                "patient_age": "",
                "study_uid": f"nifti_{os.path.basename(file_path)}_{t}",
                "study_date": "",
                "series_uid": f"nifti_{os.path.basename(file_path)}_{t}",
                "series_description": "",
                "modality": "NIfTI",
                "slice_location": z * sz,
                "instance_number": z,
                "rows": nx,
                "cols": ny,
                "pixel_spacing": f"[{sx}, {sy}]",
                "slice_thickness": sz,
                "filename": os.path.basename(file_path),
                "nifti_data": data[:, :, z, t].astype(np.float32).tobytes() if nt > 1 else data[:, :, z].astype(np.float32).tobytes(),
                "nifti_shape": [nx, ny],
                "time_index": t,
            })
    return slices


def store_nifti(file_content: bytes, filename: str, study_uid: str) -> str:
    """Store NIfTI file and return relative path."""
    import uuid
    study_dir = os.path.join(DICOM_DIR, study_uid)
    os.makedirs(study_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}.nii.gz"
    file_path = os.path.join(study_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(file_content)
    return os.path.relpath(file_path, DICOM_DIR)

