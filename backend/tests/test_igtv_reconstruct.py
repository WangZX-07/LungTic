"""IGTV accumulation should preserve results without holding every phase volume."""

import numpy as np
import pytest

from models.igtv_reconstruct import fuse_phase_masks


def test_fuse_one_shot_phase_stream_with_different_shapes():
    a = np.array([[[1, 0], [0, 0]]], dtype=np.uint8)
    b = np.array([[[0, 1, 0], [0, 0, 1]]], dtype=np.uint8)
    expected = np.array([[[1, 1, 0], [0, 0, 1]]], dtype=np.uint8)
    np.testing.assert_array_equal(fuse_phase_masks(iter((a, b))), expected)
    np.testing.assert_array_equal(fuse_phase_masks(iter((a, b)), "majority"), np.zeros_like(expected))


def test_empty_phase_stream_is_rejected():
    with pytest.raises(ValueError, match="No masks"):
        fuse_phase_masks(iter(()))
