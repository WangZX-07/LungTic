"""Inference engine: orchestrates model loading and prediction.

Supports:
- Built-in PyTorch models (Attention U-Net, LSTM, TCN)
- User-uploaded .pth models (TorchScript or state_dict)
- User-uploaded .onnx models (ONNX Runtime)
"""

import os
import numpy as np
from typing import Optional
from models.unet import AttentionUNet
from models.lstm import TrajectoryLSTM


class InferenceEngine:
    """Central inference engine for LungTic.

    Manages model registry, loading, and prediction dispatch.
    """

    def __init__(self):
        self._seg_model = None    # current segmentation model
        self._pred_model = None   # current prediction model
        self._seg_is_onnx = False
        self._pred_is_onnx = False
        self._seg_loaded_from = ""
        self._pred_loaded_from = ""
        self._device = "cpu"

    # ---- Model Loading ----

    def load_builtin_segmentation(self):
        """Load built-in Attention U-Net."""
        import torch
        self._seg_model = AttentionUNet(in_channels=1, out_channels=1)
        self._seg_model.to(self._device)
        self._seg_model.eval()
        self._seg_is_onnx = False
        self._seg_loaded_from = "builtin"
        return True

    def load_builtin_prediction(self):
        """Load built-in Trajectory LSTM."""
        import torch
        self._pred_model = TrajectoryLSTM(input_size=3, hidden_size=64, pred_len=3)
        self._pred_model.to(self._device)
        self._pred_model.eval()
        self._pred_is_onnx = False
        self._pred_loaded_from = "builtin"
        return True

    def load_custom_model(self, file_path: str, model_type: str, task_type: str) -> bool:
        """Load a user-uploaded custom model.

        Args:
            file_path: path to .pth or .onnx file
            model_type: "pth" or "onnx"
            task_type: "segmentation" or "prediction"
        """
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".onnx":
            from models.onnx_loader import ONNXModel
            model = ONNXModel(file_path)
            model.load()
            is_onnx = True
        elif ext == ".pth":
            from models.onnx_loader import PyTorchModel
            model_class = AttentionUNet if task_type == "segmentation" else TrajectoryLSTM
            model = PyTorchModel(file_path, model_class=model_class)
            model.load(device=self._device)
            is_onnx = False
        else:
            raise ValueError(f"Unsupported model format: {ext}")

        if task_type == "segmentation":
            self._seg_model = model
            self._seg_is_onnx = is_onnx
            self._seg_loaded_from = file_path
        else:
            self._pred_model = model
            self._pred_is_onnx = is_onnx
            self._pred_loaded_from = file_path

        return True

    def ensure_segmentation_loaded(self):
        """Ensure a segmentation model is loaded (builtin fallback)."""
        if self._seg_model is None:
            self.load_builtin_segmentation()

    def ensure_prediction_loaded(self):
        """Ensure a prediction model is loaded (builtin fallback)."""
        if self._pred_model is None:
            self.load_builtin_prediction()

    # ---- Inference Methods ----

    def segment_slice(self, ct_slice: np.ndarray) -> np.ndarray:
        """Run segmentation on a single CT slice.

        Args:
            ct_slice: (H, W) float32 array, normalized 0-1
        Returns:
            (H, W) binary mask uint8
        """
        self.ensure_segmentation_loaded()

        # Prepare input
        if ct_slice.ndim == 2:
            input_data = ct_slice[np.newaxis, np.newaxis, ...]  # (1, 1, H, W)
        else:
            input_data = ct_slice

        if self._seg_is_onnx:
            output = self._seg_model.run(input_data.astype(np.float32))
        else:
            import torch
            tensor = torch.from_numpy(input_data).float().to(self._device)
            with torch.no_grad():
                output = self._seg_model(tensor).cpu().numpy()

        mask = (output[0, 0] > 0.5).astype(np.uint8)
        return mask

    def predict_trajectory(
        self,
        observed: np.ndarray,
        pred_len: int = 3,
    ) -> np.ndarray:
        """Predict future tumor positions.

        Args:
            observed: (N_phases, 3) xyz centroid positions
            pred_len: number of future phases to predict
        Returns:
            (pred_len, 3) predicted positions
        """
        self.ensure_prediction_loaded()

        input_data = observed[np.newaxis, ...].astype(np.float32)  # (1, N, 3)

        if self._pred_is_onnx:
            output = self._pred_model.run(input_data)
        else:
            import torch
            tensor = torch.from_numpy(input_data).float().to(self._device)
            with torch.no_grad():
                output = self._pred_model(tensor).cpu().numpy()

        return output[0]  # (pred_len, 3)

    def get_centroid(self, mask: np.ndarray, spacing: tuple = (1, 1, 1)) -> np.ndarray:
        """Compute centroid of binary mask.

        Args:
            mask: (H, W) binary mask
            spacing: pixel spacing (dx, dy)
        Returns:
            (2,) centroid (x, y) in world coordinates
        """
        if mask.sum() == 0:
            return np.array([0.0, 0.0])

        ys, xs = np.where(mask > 0)
        cx = xs.mean() * spacing[0]
        cy = ys.mean() * spacing[1]
        return np.array([cx, cy])

    @property
    def seg_model_info(self) -> dict:
        return {
            "loaded": self._seg_model is not None,
            "source": self._seg_loaded_from or "none",
            "is_onnx": self._seg_is_onnx,
            "device": self._device,
        }

    @property
    def pred_model_info(self) -> dict:
        return {
            "loaded": self._pred_model is not None,
            "source": self._pred_loaded_from or "none",
            "is_onnx": self._pred_is_onnx,
            "device": self._device,
        }


# Global singleton
_engine: Optional[InferenceEngine] = None


def get_engine() -> InferenceEngine:
    global _engine
    if _engine is None:
        _engine = InferenceEngine()
    return _engine