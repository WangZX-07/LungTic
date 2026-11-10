"""LSTM-based tumor motion trajectory prediction.

Predicts future tumor centroid positions (x, y, z) based on
observed positions from previous respiratory phases.
"""

import torch
import torch.nn as nn


class TrajectoryLSTM(nn.Module):
    """BiLSTM encoder-decoder for 3D trajectory prediction.

    Input:  (B, seq_len, 3)  xyz centroid sequence from observed phases
    Output: (B, pred_len, 3)  predicted xyz for future phases

    Args:
        input_size: input features per time step (3 for xyz)
        hidden_size: LSTM hidden dimension
        num_layers: number of LSTM layers
        pred_len: number of future time steps to predict
    """

    def __init__(
        self,
        input_size: int = 3,
        hidden_size: int = 64,
        num_layers: int = 2,
        pred_len: int = 3,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.pred_len = pred_len

        # Encoder: BiLSTM
        self.encoder = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        # Decoder: unidirectional LSTM
        self.decoder = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size * 2,  # bidirectional encoder output
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        # Output projection
        self.fc = nn.Linear(hidden_size * 2, input_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: (B, seq_len, 3) observed trajectory
        Returns:
            (B, pred_len, 3) predicted trajectory
        """
        batch_size = x.size(0)

        # Encode
        encoder_out, (h_n, c_n) = self.encoder(x)  # encoder_out: (B, seq_len, hidden*2)

        # Initialize decoder with last encoder state
        # Convert bidirectional states to unidirectional
        h_dec = self._reshape_hidden(h_n, batch_size)
        c_dec = self._reshape_hidden(c_n, batch_size)

        # Start token: last observed position
        decoder_input = x[:, -1:, :]  # (B, 1, 3)

        outputs = []
        for _ in range(self.pred_len):
            out, (h_dec, c_dec) = self.decoder(decoder_input, (h_dec, c_dec))
            pred = self.fc(out)  # (B, 1, 3)
            outputs.append(pred)
            decoder_input = pred  # autoregressive

        return torch.cat(outputs, dim=1)  # (B, pred_len, 3)

    def _reshape_hidden(self, h: torch.Tensor, batch_size: int) -> torch.Tensor:
        """Reshape bidirectional hidden state (layers*2, B, hidden) -> (layers, B, hidden*2)."""
        # h: (num_layers * 2, B, hidden)
        h = h.view(self.num_layers, 2, batch_size, self.hidden_size)
        h = torch.cat([h[:, 0, :, :], h[:, 1, :, :]], dim=-1)  # (layers, B, hidden*2)
        return h


class SimpleTCN(nn.Module):
    """Lightweight Temporal Convolutional Network as alternative predictor.

    Faster than LSTM, suitable for real-time prediction.
    """

    def __init__(
        self,
        input_size: int = 3,
        hidden_size: int = 64,
        pred_len: int = 3,
    ):
        super().__init__()
        self.pred_len = pred_len

        self.conv1 = nn.Conv1d(input_size, hidden_size, 3, padding=1)
        self.conv2 = nn.Conv1d(hidden_size, hidden_size, 3, padding=1)
        self.conv3 = nn.Conv1d(hidden_size, hidden_size, 3, padding=1)
        self.fc = nn.Linear(hidden_size, input_size * pred_len)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, seq_len, 3) -> (B, pred_len, 3)"""
        x = x.transpose(1, 2)  # (B, 3, seq_len)
        x = self.relu(self.conv1(x))
        x = self.relu(self.conv2(x))
        x = self.relu(self.conv3(x))
        x = x.mean(dim=-1)  # global average pooling -> (B, hidden)
        out = self.fc(x)  # (B, 3 * pred_len)
        return out.view(-1, self.pred_len, 3)


def mse_loss(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Mean squared error for trajectory prediction."""
    return nn.functional.mse_loss(pred, target)