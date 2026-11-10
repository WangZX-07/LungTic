"""Attention U-Net for 4D CT lung tumor segmentation.

Architecture:
- Encoder: 4 down-sampling blocks with double 3x3 conv + BN + ReLU
- Decoder: 4 up-sampling blocks with skip connections
- Attention Gates: at each skip connection to focus on tumor boundaries
- Bottleneck: double conv at deepest level
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class ConvBlock(nn.Module):
    """Double convolution block: Conv3x3 -> BN -> ReLU -> Conv3x3 -> BN -> ReLU."""

    def __init__(self, in_ch: int, out_ch: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class AttentionGate(nn.Module):
    """Attention gate: filters skip connection features using gating signal from decoder.

    g: gating signal (decoder features, up-sampled)
    x: skip connection (encoder features)
    Returns: attention-weighted skip features (same shape as x)
    """

    def __init__(self, F_g: int, F_l: int, F_int: int):
        super().__init__()
        self.W_g = nn.Sequential(
            nn.Conv2d(F_g, F_int, 1, bias=False),
            nn.BatchNorm2d(F_int),
        )
        self.W_x = nn.Sequential(
            nn.Conv2d(F_l, F_int, 1, bias=False),
            nn.BatchNorm2d(F_int),
        )
        self.psi = nn.Sequential(
            nn.Conv2d(F_int, 1, 1, bias=False),
            nn.BatchNorm2d(1),
            nn.Sigmoid(),
        )

    def forward(self, g: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
        g1 = self.W_g(g)
        x1 = self.W_x(x)

        # Align spatial dimensions
        if g1.shape[2:] != x1.shape[2:]:
            g1 = F.interpolate(g1, size=x1.shape[2:], mode="bilinear", align_corners=False)

        psi = self.psi(F.relu(g1 + x1))
        return x * psi


class UpConv(nn.Module):
    """Up-sampling block: upscale -> double conv."""

    def __init__(self, in_ch: int, out_ch: int):
        super().__init__()
        self.up = nn.ConvTranspose2d(in_ch, out_ch, 2, stride=2)
        self.conv = ConvBlock(out_ch * 2, out_ch)  # *2 for skip connection

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = self.up(x)
        # Pad if needed
        diff_y = skip.size(2) - x.size(2)
        diff_x = skip.size(3) - x.size(3)
        x = F.pad(x, [diff_x // 2, diff_x - diff_x // 2, diff_y // 2, diff_y - diff_y // 2])
        x = torch.cat([skip, x], dim=1)
        return self.conv(x)


class AttentionUNet(nn.Module):
    """Attention U-Net for medical image segmentation.

    Input:  (B, 1, H, W)  single-channel CT slice
    Output: (B, 1, H, W)  sigmoid probability map for tumor

    Args:
        in_channels: input channels (default 1 for grayscale CT)
        out_channels: output channels (default 1 for binary mask)
        base_filters: number of filters in first encoder block
    """

    def __init__(
        self,
        in_channels: int = 1,
        out_channels: int = 1,
        base_filters: int = 64,
    ):
        super().__init__()

        # Encoder
        self.enc1 = ConvBlock(in_channels, base_filters)
        self.enc2 = ConvBlock(base_filters, base_filters * 2)
        self.enc3 = ConvBlock(base_filters * 2, base_filters * 4)
        self.enc4 = ConvBlock(base_filters * 4, base_filters * 8)

        # Bottleneck
        self.bottleneck = ConvBlock(base_filters * 8, base_filters * 16)

        # Attention Gates
        self.att4 = AttentionGate(base_filters * 8, base_filters * 8, base_filters * 4)
        self.att3 = AttentionGate(base_filters * 4, base_filters * 4, base_filters * 2)
        self.att2 = AttentionGate(base_filters * 2, base_filters * 2, base_filters)
        self.att1 = AttentionGate(base_filters, base_filters, base_filters // 2)

        # Decoder
        self.up4 = UpConv(base_filters * 16, base_filters * 8)
        self.up3 = UpConv(base_filters * 8, base_filters * 4)
        self.up2 = UpConv(base_filters * 4, base_filters * 2)
        self.up1 = UpConv(base_filters * 2, base_filters)

        # Output
        self.out_conv = nn.Conv2d(base_filters, out_channels, 1)

        self.pool = nn.MaxPool2d(2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Encoder
        e1 = self.enc1(x)           # base_filters
        e2 = self.enc2(self.pool(e1))  # base_filters * 2
        e3 = self.enc3(self.pool(e2))  # base_filters * 4
        e4 = self.enc4(self.pool(e3))  # base_filters * 8

        # Bottleneck
        b = self.bottleneck(self.pool(e4))  # base_filters * 16

        # Decoder with attention
        d4 = self.up4(b, self.att4(b, e4))
        d3 = self.up3(d4, self.att3(d4, e3))
        d2 = self.up2(d3, self.att2(d3, e2))
        d1 = self.up1(d2, self.att1(d2, e1))

        return torch.sigmoid(self.out_conv(d1))

    def predict(self, x: torch.Tensor, threshold: float = 0.5) -> torch.Tensor:
        """Return binary mask."""
        return (self.forward(x) > threshold).float()


def dice_loss(pred: torch.Tensor, target: torch.Tensor, smooth: float = 1.0) -> torch.Tensor:
    """Dice loss for segmentation training."""
    pred_flat = pred.view(-1)
    target_flat = target.view(-1)
    intersection = (pred_flat * target_flat).sum()
    return 1 - (2.0 * intersection + smooth) / (pred_flat.sum() + target_flat.sum() + smooth)


def dice_coefficient(pred: torch.Tensor, target: torch.Tensor, smooth: float = 1.0) -> float:
    """Calculate Dice coefficient between prediction and ground truth."""
    pred_bin = (pred > 0.5).float()
    intersection = (pred_bin * target).sum().item()
    return float((2.0 * intersection + smooth) / (pred_bin.sum().item() + target.sum().item() + smooth))