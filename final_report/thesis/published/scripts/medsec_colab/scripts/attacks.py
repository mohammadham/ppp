"""Destructive-channel experiments are NOT authenticated receiver acceptance."""
import numpy as np
from .cipher import decrypt, encrypt
from .metrics import differential, quality

ATTACKS = [('salt_pepper', x) for x in (.01, .05, .10)] + [('gaussian', x) for x in (.01, .05)] + [('crop', x) for x in (.125, .25, .5)]

def corrupt(image, kind, strength, rng):
    if not 0 <= strength <= 1: raise ValueError('Invalid attack strength')
    out = image.copy()
    if kind == 'gaussian':
        out = np.rint(np.clip(out.astype(float)/255+rng.normal(0, np.sqrt(strength), out.shape), 0, 1)*255).astype(np.uint8)
    elif kind == 'salt_pepper':
        count = round(out.size*strength); pos = rng.choice(out.size, count, replace=False)
        out.ravel()[pos] = rng.integers(0, 2, count).astype(np.uint8)*255
    elif kind == 'crop':
        # Exact zeroed area: top-left rectangle plus at most one partial row.
        count = round(out.size*strength); width = max(1, min(out.shape[1], round(out.shape[1]*np.sqrt(strength))))
        rows, extra = divmod(count, width)
        out[:rows, :width] = 0
        if extra: out[rows, :extra] = 0
    else: raise ValueError('Unknown attack')
    return out

def channel_experiments(image, roi, cipher, digest, cfg, seed):
    rng = np.random.default_rng(seed)
    for kind, strength in ATTACKS:
        damaged = corrupt(cipher, kind, strength, rng)
        recovered = decrypt(damaged, digest, cfg)
        yield {'attack': kind, 'strength': strength, 'mode': 'core_decryption_with_sender_digest_NOT_authenticated_receive',
               'changed_cipher_pixels': int(np.count_nonzero(damaged != cipher)), **quality(image, recovered, roi)}

def one_pixel_trial(image, roi, cipher, predictor, cfg, rng, region):
    candidates = np.flatnonzero((roi if region == 'inside' else ~roi).ravel())
    if not len(candidates): raise ValueError(f'No pixels {region} predicted ROI')
    position = int(rng.choice(candidates)); changed = image.copy()
    changed.ravel()[position] = (int(changed.ravel()[position])+1) % 256
    changed_roi = predictor(changed)
    second, digest = encrypt(changed, changed_roi, cfg)
    return {'position': position, 'region': region, 'roi_changed_pixels': int(np.count_nonzero(roi != changed_roi)),
            'changed_digest': digest, 'protocol': 'reinfer_ROI_and_rehash', **differential(cipher, second)}

def key_experiments(image, roi, cipher, digest, cfg):
    altered = (int(digest, 16) ^ (1 << 255)).to_bytes(32, 'big').hex()
    second, _ = encrypt(image, roi, cfg, digest=altered)
    recovered = decrypt(cipher, altered, cfg)
    return {'protocol': 'flip_most_significant_digest_bit_no_plaintext_change',
            'cipher_sensitivity': differential(cipher, second), 'wrong_digest_decryption': quality(image, recovered, roi)}