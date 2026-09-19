"""High-performance Medical Image Cipher based on 5D Hyperchaos and DNA Computing.

Strictly aligned with Subathra & Thanikaiselvan (Scientific Reports 2025):
  1. Zig-zag Scan Scrambling (Algorithm 4)
  2. Chaotic Dynamic Permutation using state variable z (Eq. 13)
  3. Dynamic Rule-Based DNA Encoding (Rules 1-8, Table 5)
  4. Dynamic 4-Base DNA Circular Permutation / Flip using state variable v (Eq. 16-17)
  5. DNA XOR Diffusion with Chaotic Key Stream using state variable v (Table 6, Eq. 18-19)
"""
from functools import lru_cache
import numpy as np
from .chaos import roi_digest, stream

# DNA Encoding Rules (Table 5 of Subathra et al. 2025 / Watson-Crick Complementary)
RULES = np.array([
    [0, 1, 2, 3],  # Rule 1
    [0, 2, 1, 3],  # Rule 2
    [1, 0, 3, 2],  # Rule 3
    [1, 3, 0, 2],  # Rule 4
    [2, 0, 3, 1],  # Rule 5
    [2, 3, 0, 1],  # Rule 6
    [3, 1, 2, 0],  # Rule 7
    [3, 2, 1, 0]   # Rule 8
], dtype=np.uint8)

INVERSE = np.argsort(RULES, axis=1).astype(np.uint8)


@lru_cache(maxsize=16)
def zigzag_indices(h: int, w: int) -> np.ndarray:
    """Generate 2D zig-zag scrambling order coordinates for arbitrary rectangular images."""
    indices = []
    for diagonal in range(h + w - 1):
        rows = range(max(0, diagonal - w + 1), min(h - 1, diagonal) + 1)
        if diagonal % 2 == 0:
            rows = reversed(rows)
        indices.extend(r * w + diagonal - r for r in rows)
    out = np.array(indices, dtype=np.int64)
    out.flags.writeable = False
    return out


def encode_dna(values: np.ndarray, rules: np.ndarray) -> np.ndarray:
    """Vectorized DNA encoding: maps uint8 pixels to (N, 4) nucleotide bases."""
    v = np.asarray(values, dtype=np.uint8)[:, None]
    pairs = (v >> np.array([6, 4, 2, 0], dtype=np.uint8)) & 3
    r = np.asarray(rules, dtype=np.int64)[:, None]
    return RULES[r, pairs]


def decode_dna(bases: np.ndarray, rules: np.ndarray) -> np.ndarray:
    """Vectorized DNA decoding: reconstructs uint8 pixels from (N, 4) bases."""
    r = np.asarray(rules, dtype=np.int64)[:, None]
    pairs = INVERSE[r, bases]
    return np.sum(pairs.astype(np.uint16) << np.array([6, 4, 2, 0], dtype=np.uint16), axis=1).astype(np.uint8)


def apply_dna_circular_flip(bases: np.ndarray, p_positions: np.ndarray, inverse: bool = False) -> np.ndarray:
    """Dynamic 4-base DNA circular permutation according to Eq. 17 in Subathra et al. (2025)."""
    out = np.empty_like(bases)
    b0, b1, b2, b3 = bases[:, 0], bases[:, 1], bases[:, 2], bases[:, 3]

    m0 = (p_positions == 0)
    m1 = (p_positions == 1)
    m2 = (p_positions == 2)
    m3 = (p_positions == 3)

    if not inverse:
        out[m0, 0] = b1[m0]; out[m0, 1] = b2[m0]; out[m0, 2] = b3[m0]; out[m0, 3] = b0[m0]
        out[m1, 0] = b2[m1]; out[m1, 1] = b3[m1]; out[m1, 2] = b1[m1]; out[m1, 3] = b0[m1]
        out[m2, 0] = b3[m2]; out[m2, 1] = b2[m2]; out[m2, 2] = b0[m2]; out[m2, 3] = b1[m2]
        out[m3, 0] = b3[m3]; out[m3, 1] = b0[m3]; out[m3, 2] = b1[m3]; out[m3, 3] = b2[m3]
    else:
        out[m0, 0] = b3[m0]; out[m0, 1] = b0[m0]; out[m0, 2] = b1[m0]; out[m0, 3] = b2[m0]
        out[m1, 0] = b3[m1]; out[m1, 1] = b2[m1]; out[m1, 2] = b0[m1]; out[m1, 3] = b1[m1]
        out[m2, 0] = b2[m2]; out[m2, 1] = b3[m2]; out[m2, 2] = b1[m2]; out[m2, 3] = b0[m2]
        out[m3, 0] = b1[m3]; out[m3, 1] = b2[m3]; out[m3, 2] = b3[m3]; out[m3, 3] = b0[m3]

    return out


def dna_transform(values: np.ndarray, keys: np.ndarray, variant: str, inverse: bool = False) -> np.ndarray:
    """Unified DNA Transformation handling Subathra 2025 circular dynamic flip."""
    rules = keys[:, 0] % 8

    if variant == 'subathra_2025':
        # Using keys[:, 4] (state variable v) for diffusion key stream as per Subathra 2025 reference[cite: 2]
        key_bases = encode_dna(keys[:, 4], rules)
        # Using keys[:, 4] (state variable v) for dynamic flip positions p_positions as per reference[cite: 2]
        p_positions = keys[:, 4] % 4

        if not inverse:
            bases = encode_dna(values, rules)
            flipped = apply_dna_circular_flip(bases, p_positions, inverse=False)
            diffused = flipped ^ key_bases
            return decode_dna(diffused, rules)
        else:
            diffused = encode_dna(values, rules)
            flipped = diffused ^ key_bases
            bases = apply_dna_circular_flip(flipped, p_positions, inverse=True)
            return decode_dna(bases, rules)

    elif variant == 'pseudocode_3_3':
        bases = encode_dna(values, rules)
        key = encode_dna(keys[:, 1], rules)
        flip = (keys[:, 2] % 2 == 1)
        result = bases ^ key ^ (flip[:, None].astype(np.uint8) * 3)
        return decode_dna(result, rules)

    elif variant == 'equation_3_3_feedback':
        key = encode_dna(keys[:, 1], rules)
        flip = (keys[:, 2] > 128)
        if inverse:
            bases = encode_dna(values, rules)
            previous = np.vstack((np.zeros((1, 4), dtype=np.uint8), bases[:-1]))
            bases = bases ^ previous
            result = bases ^ key ^ (flip[:, None].astype(np.uint8) * 3)
            return decode_dna(result, rules)
        else:
            bases = encode_dna(values, rules)
            result = bases ^ key ^ (flip[:, None].astype(np.uint8) * 3)
            result = np.bitwise_xor.accumulate(result, axis=0)
            return decode_dna(result, rules)

    else:
        raise ValueError(f'Unknown DNA interpretation variant: {variant}')


def encrypt(image: np.ndarray, roi: np.ndarray, cfg: dict, digest: str = None):
    """Encrypts a 2D uint8 image following the full permutation-diffusion pipeline."""
    if image.ndim != 2 or image.dtype != np.uint8:
        raise ValueError('2D uint8 only')
    if roi.shape != image.shape or roi.dtype != bool:
        raise ValueError('Boolean aligned ROI required')

    digest = digest or roi_digest(image, roi)[0]
    keys = stream(digest, image.size, cfg)

    # 1. Iterative Zig-zag scan permutation (Confusion)
    permuted = image.ravel()
    iterations = cfg.get('zigzag_rounds', 1)
    idx = zigzag_indices(*image.shape) if not cfg.get('no_zigzag') else np.arange(image.size)
    for _ in range(iterations):
        permuted = permuted[idx]

    # 2. Chaos-Sorted dynamic permutation strictly using state variable z (keys[:, 2])[cite: 2]
    sort_idx = None
    if cfg.get('system') == 'subathra_2025' and not cfg.get('no_chaos_sort'):
        sort_idx = np.argsort(keys[:, 2], kind='stable')
        permuted = permuted[sort_idx]

    # 3. Dynamic DNA encoding, circular flip, and XOR diffusion
    dna_var = 'subathra_2025' if cfg.get('system') == 'subathra_2025' and cfg.get('dna_variant') == 'subathra_2025' else cfg['dna_variant']
    cipher = permuted if cfg.get('no_dna') else dna_transform(permuted, keys, dna_var, inverse=False)

    return cipher.reshape(image.shape), digest


def decrypt(cipher: np.ndarray, digest: str, cfg: dict):
    """Decrypts a 2D uint8 cipher image with strict inverse permutation and diffusion."""
    if cipher.ndim != 2 or cipher.dtype != np.uint8:
        raise ValueError('2D uint8 cipher required')

    keys = stream(digest, cipher.size, cfg)

    # 1. Inverse DNA diffusion and circular un-flip
    dna_var = 'subathra_2025' if cfg.get('system') == 'subathra_2025' and cfg.get('dna_variant') == 'subathra_2025' else cfg['dna_variant']
    diffused = cipher.ravel() if cfg.get('no_dna') else dna_transform(cipher.ravel(), keys, dna_var, inverse=True)

    # 2. Inverse Chaos-Sorted dynamic permutation using state variable z (keys[:, 2])[cite: 2]
    if cfg.get('system') == 'subathra_2025' and not cfg.get('no_chaos_sort'):
        sort_idx = np.argsort(keys[:, 2], kind='stable')
        inv_sort_idx = np.empty_like(sort_idx)
        inv_sort_idx[sort_idx] = np.arange(len(sort_idx))
        diffused = diffused[inv_sort_idx]

    # 3. Inverse Iterative Zig-zag scan permutation
    flat = diffused
    if not cfg.get('no_zigzag'):
        idx = zigzag_indices(*cipher.shape)
        inv_idx = np.empty_like(idx)
        inv_idx[idx] = np.arange(idx.size)
        iterations = cfg.get('zigzag_rounds', 1)
        for _ in range(iterations):
            flat = flat[inv_idx]

    return flat.reshape(cipher.shape)


def protected_mask(roi: np.ndarray, cfg: dict) -> np.ndarray:
    """Computes the protected ROI mask transformed into cipher space."""
    idx = zigzag_indices(*roi.shape) if not cfg.get('no_zigzag') else np.arange(roi.size)
    moved = roi.ravel()[idx].reshape(roi.shape)
    if cfg['roi_coordinates'] == 'permuted_union_original':
        return moved | roi
    if cfg['roi_coordinates'] == 'original':
        return roi.copy()
    raise ValueError('Unknown ROI coordinate convention')