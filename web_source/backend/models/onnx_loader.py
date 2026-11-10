"""ONNX model loader for custom user models.

Supports loading .onnx files and running inference through ONNX Runtime.
"""

import numpy as np
from typing import Optional


class ONNXModel:
    """Wrapper around ONNX Runtime inference session.

    Usage:
        model = ONNXModel("path/to/model.onnx")
        output = model.run(input_array)
    """

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.session = None
        self.input_name: Optional[str] = None
        self.output_name: Optional[str] = None

    def load(self):
        """Load the ONNX model."""
        try:
            import onnxruntime as ort
            self.session = ort.InferenceSession(
                self.model_path,
                providers=["CPUExecutionProvider"],
            )
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            return True
        except ImportError:
            raise ImportError("onnxruntime not installed. Run: pip install onnxruntime")
        except Exception as e:
            raise RuntimeError(f"Failed to load ONNX model: {e}")

    def run(self, input_data: np.ndarray) -> np.ndarray:
        """Run inference.

        Args:
            input_data: numpy array matching model input shape
        Returns:
            numpy array of model output
        """
        if self.session is None:
            self.load()

        # Ensure float32 and correct shape
        if input_data.dtype != np.float32:
            input_data = input_data.astype(np.float32)

        # Add batch dimension if needed
        if input_data.ndim == 3:
            input_data = np.expand_dims(input_data, axis=0)

        outputs = self.session.run(
            [self.output_name],
            {self.input_name: input_data},
        )
        return outputs[0]


class PyTorchModel:
    """Wrapper around PyTorch .pth model (TorchScript or state_dict).

    Usage:
        model = PyTorchModel("path/to/model.pth", model_class=AttentionUNet)
        output = model.run(input_tensor)
    """

    def __init__(self, model_path: str, model_class=None):
        self.model_path = model_path
        self.model_class = model_class
        self.model = None
        self.device = "cpu"

    def load(self, device: str = "cpu"):
        """Load the PyTorch model."""
        import torch

        self.device = device

        # Try loading as TorchScript first
        try:
            self.model = torch.jit.load(self.model_path, map_location=device)
            self.model.eval()
            return True
        except Exception:
            pass

        # Fall back to state_dict loading
        if self.model_class is not None:
            self.model = self.model_class()
            checkpoint = torch.load(self.model_path, map_location=device, weights_only=False)
            if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
                state_dict = checkpoint["model_state_dict"]
            elif isinstance(checkpoint, dict) and "state_dict" in checkpoint:
                state_dict = checkpoint["state_dict"]
            else:
                state_dict = checkpoint
            self.model.load_state_dict(state_dict)
            self.model.to(device)
            self.model.eval()
            return True

        raise ValueError(
            "Cannot load .pth file. Provide model_class for state_dict, "
            "or save as TorchScript (torch.jit.script)."
        )

    def run(self, input_data):
        """Run inference.

        Args:
            input_data: numpy array or torch tensor
        Returns:
            numpy array of model output
        """
        import torch

        if self.model is None:
            self.load()

        if isinstance(input_data, np.ndarray):
            input_data = torch.from_numpy(input_data).float().to(self.device)

        if input_data.ndim == 3:
            input_data = input_data.unsqueeze(0)

        with torch.no_grad():
            output = self.model(input_data)

        if isinstance(output, torch.Tensor):
            output = output.cpu().numpy()

        return output