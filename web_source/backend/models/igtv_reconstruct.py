"""IGTV (Internal Gross Tumor Volume) reconstruction.

Fuses segmentation masks from all 10 respiratory phases into a single
ITV volume, then generates a 3D mesh via Marching Cubes.
"""

import numpy as np
from typing import Iterable, Optional


def fuse_phase_masks(
    masks: Iterable[np.ndarray],
    method: str = "union",
) -> np.ndarray:
    """Fuse phase volumes one at a time, padding only the accumulator if needed."""
    if method not in {"union", "majority"}:
        raise ValueError(f"Unknown fusion method: {method}")

    result = None
    count = 0
    for mask in masks:
        if mask.ndim != 3:
            raise ValueError("Phase mask must be a 3D volume")
        if result is None:
            result = np.zeros(mask.shape, dtype=bool if method == "union" else np.uint16)
        elif any(mask.shape[i] > result.shape[i] for i in range(3)):
            padding = [(0, max(0, mask.shape[i] - result.shape[i])) for i in range(3)]
            result = np.pad(result, padding)
        region = result[tuple(slice(0, size) for size in mask.shape)]
        if method == "union":
            np.logical_or(region, mask > 0, out=region)
        else:
            region += mask > 0
        count += 1

    if result is None:
        raise ValueError("No masks provided")
    if method == "majority":
        result = result > count / 2
    return result.astype(np.uint8)


def marching_cubes_mesh(
    volume: np.ndarray,
    spacing: tuple[float, float, float] = (1.0, 1.0, 1.0),
    level: float = 0.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate 3D mesh from binary volume using Marching Cubes.

    Args:
        volume: (D, H, W) binary volume
        spacing: voxel spacing in mm (z, y, x)
        level: isosurface level

    Returns:
        vertices: (N, 3) vertex positions
        faces: (M, 3) triangle indices
    """
    try:
        from skimage import measure

        verts, faces, _, _ = measure.marching_cubes(
            volume.astype(np.float32),
            level=level,
            spacing=spacing,
            method="lewiner",
        )
        return verts, faces
    except ImportError:
        # Fallback: simple bounding box mesh
        return _bbox_mesh(volume, spacing)


def _bbox_mesh(
    volume: np.ndarray,
    spacing: tuple[float, float, float],
) -> tuple[np.ndarray, np.ndarray]:
    """Fallback: generate bounding box mesh from non-zero voxels."""
    indices = np.argwhere(volume > 0)
    if len(indices) == 0:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=int)

    z_min, y_min, x_min = indices.min(axis=0).astype(float)
    z_max, y_max, x_max = (indices.max(axis=0) + 1).astype(float)

    z_min *= spacing[0]; z_max *= spacing[0]
    y_min *= spacing[1]; y_max *= spacing[1]
    x_min *= spacing[2]; x_max *= spacing[2]

    vertices = np.array([
        [x_min, y_min, z_min], [x_max, y_min, z_min],
        [x_max, y_max, z_min], [x_min, y_max, z_min],
        [x_min, y_min, z_max], [x_max, y_min, z_max],
        [x_max, y_max, z_max], [x_min, y_max, z_max],
    ])

    faces = np.array([
        [0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
        [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7],
    ])

    return vertices, faces


def compute_igtv_volume(
    mask: np.ndarray,
    spacing: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> float:
    """Compute volume in cc (cubic centimeters) from binary mask.

    Args:
        mask: (D, H, W) binary mask
        spacing: voxel spacing in mm (z, y, x)

    Returns:
        volume in cc
    """
    voxel_volume_mm3 = spacing[0] * spacing[1] * spacing[2]
    total_mm3 = mask.sum() * voxel_volume_mm3
    return total_mm3 / 1000.0  # mm^3 -> cc


def save_mesh_obj(
    vertices: np.ndarray,
    faces: np.ndarray,
    filepath: str,
) -> str:
    """Save mesh as Wavefront OBJ file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        for v in vertices:
            f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
        for face in faces:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")
    return filepath


import os  # noqa: E402