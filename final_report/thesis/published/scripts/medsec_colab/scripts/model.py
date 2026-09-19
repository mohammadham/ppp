"""U-Net architecture and deterministic inference predictor for medical ROI segmentation.

Strictly aligned with Subathra & Thanikaiselvan (Scientific Reports 2025):
  - U-Net encoder-decoder with skip connections
  - Deterministic evaluation (no random fallback)
  - Seamless support for 2D grayscale and automatic conversion of 3D RGB fundus inputs
"""
import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.nn import functional as F


def block(inputs: int, outputs: int) -> nn.Sequential:
    """Standard double 3x3 convolution block with ReLU activation."""
    return nn.Sequential(
        nn.Conv2d(inputs, outputs, 3, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(outputs, outputs, 3, padding=1),
        nn.ReLU(inplace=True),
    )


class UNet(nn.Module):
    """Four encoder stages, skip connections, logits output."""

    def __init__(self, base_channels: int = 32, in_channels: int = 1, out_channels: int = 1):
        super().__init__()
        widths = [base_channels * (2**i) for i in range(5)]
        self.encoders = nn.ModuleList([
            block(in_channels if i == 0 else widths[i - 1], w)
            for i, w in enumerate(widths)
        ])
        self.ups = nn.ModuleList([
            nn.ConvTranspose2d(widths[i + 1], widths[i], 2, stride=2)
            for i in range(3, -1, -1)
        ])
        self.decoders = nn.ModuleList([
            block(widths[i] * 2, widths[i])
            for i in range(3, -1, -1)
        ])
        self.output = nn.Conv2d(widths[0], out_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        skips = []
        for i, encoder in enumerate(self.encoders):
            if i > 0:
                x = F.max_pool2d(x, 2)
            x = encoder(x)
            skips.append(x)

        for up, decoder, skip in zip(self.ups, self.decoders, reversed(skips[:-1])):
            x = up(x)
            if x.shape[-2:] != skip.shape[-2:]:
                x = F.interpolate(x, skip.shape[-2:], mode='bilinear', align_corners=False)
            x = decoder(torch.cat([skip, x], dim=1))

        return self.output(x)


def segmentation_scores(pred: np.ndarray, target: np.ndarray) -> dict:
    """Calculate Dice and IoU overlap metrics between boolean arrays."""
    pred_b = np.asarray(pred, dtype=bool)
    target_b = np.asarray(target, dtype=bool)

    intersection = int(np.count_nonzero(pred_b & target_b))
    union = int(np.count_nonzero(pred_b | target_b))
    total = int(pred_b.sum() + target_b.sum())

    return {
        'dice': float(2.0 * intersection / total) if total > 0 else 1.0,
        'iou': float(intersection / union) if union > 0 else 1.0,
        'target_empty': not bool(target_b.any()),
        'prediction_empty': not bool(pred_b.any()),
    }


class Predictor:
    """Deterministic inference wrapper around a trained U-Net checkpoint."""

    def __init__(self, checkpoint, device: str = 'cpu'):
        self.checkpoint = torch.load(checkpoint, map_location='cpu', weights_only=True)
        if self.checkpoint.get('trained_epochs', 0) < 1:
            raise ValueError('A trained checkpoint is required')

        self.device = torch.device(device)
        base_channels = self.checkpoint['training']['base_channels']
        in_channels = self.checkpoint.get('training', {}).get('in_channels', 1)
        out_channels = self.checkpoint.get('training', {}).get('out_channels', 1)

        self.net = UNet(
            base_channels=base_channels,
            in_channels=in_channels,
            out_channels=out_channels,
        ).to(self.device)

        self.net.load_state_dict(self.checkpoint['state_dict'])
        self.net.eval()
        self.size = int(self.checkpoint['training']['size'])
        self.threshold = float(self.checkpoint['training']['threshold'])

    @torch.inference_mode()
    def __call__(self, image: np.ndarray) -> np.ndarray:
        """Runs segmentation inference. Accepts 2D uint8 grayscale or 3D (H, W, 3) uint8."""
        if not isinstance(image, np.ndarray) or image.dtype != np.uint8:
            raise ValueError('Predictor expects uint8 numpy array')

        # Format input to 2D grayscale as required by the cipher pipeline and Subathra 2025
        if image.ndim == 3 and image.shape[2] == 3:
            # Standard luminance conversion: Y = 0.299 R + 0.587 G + 0.114 B
            working_image = np.array(Image.fromarray(image).convert('L'))
        elif image.ndim == 2:
            working_image = image
        else:
            raise ValueError('Predictor expects 2D uint8 grayscale or 3D RGB image')

        shape = working_image.shape
        # Match training's Pillow resize exactly
        resized = np.array(
            Image.fromarray(working_image).resize((self.size, self.size), Image.Resampling.BILINEAR)
        )
        tensor = torch.from_numpy(resized.astype(np.float32) / 255.0)[None, None].to(self.device)

        logits = self.net(tensor)
        probabilities = logits.sigmoid()
        probabilities = F.interpolate(probabilities, size=shape, mode='bilinear', align_corners=False)

        mask = (probabilities[0, 0] >= self.threshold).cpu().numpy()
        return mask