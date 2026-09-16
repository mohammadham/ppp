"""Counterexample probes, not a CPA/KPA security proof."""
import numpy as np
from .chaos import roi_digest
from .cipher import encrypt
from .metrics import differential

def fixed_mask_probes(image, roi, cfg):
    baseline, digest = encrypt(image, roi, cfg); rows = []
    for name in ('outside_pixel', 'swap_two_roi_pixels'):
        changed = image.copy()
        positions = np.flatnonzero((~roi if name == 'outside_pixel' else roi).ravel())
        if (name == 'outside_pixel' and not len(positions)) or (name != 'outside_pixel' and len(positions) < 2):
            rows.append({'probe': name, 'status': 'not_applicable'}); continue
        if name == 'outside_pixel': changed.ravel()[positions[0]] = (int(changed.ravel()[positions[0]])+1)%256
        else:
            a = int(positions[0]); different = positions[image.ravel()[positions] != image.ravel()[a]]
            if not len(different): rows.append({'probe': name, 'status': 'not_applicable'}); continue
            b = int(different[0]); changed.ravel()[a], changed.ravel()[b] = int(image.ravel()[b]), int(image.ravel()[a])
        cipher, second = encrypt(changed, roi, cfg)
        rows.append({'probe': name, 'status': 'ok', 'mask_held_fixed': True, 'same_digest': second == digest,
                     'plaintext_changed_pixels': int(np.count_nonzero(changed != image)), **differential(baseline, cipher)})
    return {'protocol': 'diagnostic_fixed_mask_NOT_end_to_end_UNet', 'proof_of_CPA_KPA_resistance': False, 'probes': rows}