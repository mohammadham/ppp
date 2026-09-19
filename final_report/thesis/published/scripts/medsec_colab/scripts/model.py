import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.nn import functional as F

def block(inputs, outputs):
    return nn.Sequential(nn.Conv2d(inputs, outputs, 3, padding=1), nn.ReLU(inplace=True),
                         nn.Conv2d(outputs, outputs, 3, padding=1), nn.ReLU(inplace=True))

class UNet(nn.Module):
    """Four encoder stages, skip connections; logits, no random inference fallback."""
    def __init__(self, base_channels=32):
        super().__init__()
        widths = [base_channels * 2**i for i in range(5)]
        self.encoders = nn.ModuleList([block(1 if i == 0 else widths[i-1], w) for i, w in enumerate(widths)])
        self.ups = nn.ModuleList([nn.ConvTranspose2d(widths[i+1], widths[i], 2, stride=2) for i in range(3, -1, -1)])
        self.decoders = nn.ModuleList([block(widths[i]*2, widths[i]) for i in range(3, -1, -1)])
        self.output = nn.Conv2d(widths[0], 1, 1)

    def forward(self, x):
        skips = []
        for i, encoder in enumerate(self.encoders):
            if i: x = F.max_pool2d(x, 2)
            x = encoder(x); skips.append(x)
        for up, decoder, skip in zip(self.ups, self.decoders, reversed(skips[:-1])):
            x = up(x)
            if x.shape[-2:] != skip.shape[-2:]: x = F.interpolate(x, skip.shape[-2:], mode='bilinear', align_corners=False)
            x = decoder(torch.cat([skip, x], dim=1))
        return self.output(x)

def segmentation_scores(pred, target):
    pred, target = np.asarray(pred, bool), np.asarray(target, bool)
    intersection = int(np.count_nonzero(pred & target)); union = int(np.count_nonzero(pred | target))
    total = int(pred.sum()+target.sum())
    return {'dice': 2*intersection/total if total else 1., 'iou': intersection/union if union else 1.,
            'target_empty': not bool(target.any()), 'prediction_empty': not bool(pred.any())}

class Predictor:
    def __init__(self, checkpoint, device='cpu'):
        # Only use checkpoints from trusted training runs.
        self.checkpoint = torch.load(checkpoint, map_location='cpu', weights_only=True)
        if self.checkpoint.get('trained_epochs', 0) < 1: raise ValueError('A trained checkpoint is required')
        self.device = torch.device(device)
        self.net = UNet(self.checkpoint['training']['base_channels']).to(self.device)
        self.net.load_state_dict(self.checkpoint['state_dict']); self.net.eval()
        self.size = self.checkpoint['training']['size']; self.threshold = self.checkpoint['training']['threshold']

    @torch.inference_mode()
    def __call__(self, image):
        if image.ndim != 2 or image.dtype != np.uint8: raise ValueError('Predictor expects 2D uint8 grayscale')
        shape = image.shape
        # Match training's Pillow resize exactly; avoid train/inference resampler drift.
        resized = np.array(Image.fromarray(image).resize((self.size, self.size), Image.Resampling.BILINEAR))
        tensor = torch.from_numpy(resized.astype(np.float32)/255)[None, None].to(self.device)
        probabilities = self.net(tensor).sigmoid()
        probabilities = F.interpolate(probabilities, shape, mode='bilinear', align_corners=False)
        return (probabilities[0, 0] >= self.threshold).cpu().numpy()