"""High-performance reversible steganography engine for medical cipher metadata embedding.

Implements:
  1. Spectral residual saliency detection in the frequency domain.
  2. Strict ROI-exclusion embedding masks.
  3. High-throughput bit-pair packing and unpacking via vectorized numpy bitwise operations.
  4. Framed zlib payload packaging with SHA-256 integrity verification.
"""
import hashlib
import struct
import zlib
import numpy as np
from scipy.ndimage import uniform_filter, gaussian_filter

# Framing structure: Magic (4B), Compressed Length (8B), Payload Length (8B), SHA-256 (32B)
HEADER = struct.Struct('>4sQQ32s')


class CapacityError(ValueError):
    """Structured exception indicating insufficient background embedding capacity."""

    def __init__(self, required_bits: int, available_bits: int):
        self.details = {
            'error_code': 'NO_ELIGIBLE_PIXELS' if available_bits == 0 else 'INSUFFICIENT_CAPACITY',
            'required_bits': int(required_bits),
            'available_bits': int(available_bits),
            'embedded_bits': 0,
            'roi_protection_relaxed': False,
        }
        guidance = (
            'No eligible background remains: inspect segmentation and mask conventions; do not bypass ROI protection.'
            if available_bits == 0
            else 'Packet including framing does not fit; choose a documented smaller payload or report failure.'
        )
        super().__init__(
            f'Insufficient capacity: need {required_bits} bits; available {available_bits}; nothing embedded. {guidance}'
        )


def saliency(image: np.ndarray, cfg: dict) -> np.ndarray:
    """Computes Hou & Zhang spectral residual visual saliency map in the 2D frequency domain."""
    if image.ndim != 2:
        raise ValueError('2D array required for saliency computation')

    # Convert to contiguous float64 for high-precision FFT
    img_float = np.ascontiguousarray(image, dtype=np.float64)
    freq = np.fft.fft2(img_float)
    amplitude = np.abs(freq)
    np.maximum(amplitude, np.finfo(np.float64).eps, out=amplitude)
    logamp = np.log(amplitude)

    filter_size = int(cfg.get('saliency_filter', 3))
    sigma = float(cfg.get('saliency_sigma', 2.5))

    residual = logamp - uniform_filter(logamp, size=filter_size, mode='reflect')
    phase = np.angle(freq)

    # Reconstruction of spatial saliency
    spectral_representation = np.exp(residual + 1j * phase)
    spatial = np.abs(np.fft.ifft2(spectral_representation)) ** 2
    return gaussian_filter(spatial, sigma=sigma)


def embedding_mask(cipher: np.ndarray, protected: np.ndarray, cfg: dict) -> np.ndarray:
    """Derives a boolean mask indicating pixels eligible for 2-bit LSB substitution."""
    if protected.dtype != bool or protected.shape != cipher.shape:
        raise ValueError('Boolean aligned protected mask required')

    if cfg.get('no_saliency'):
        return ~protected

    s_map = saliency(cipher, cfg)
    quantile_val = float(cfg.get('saliency_quantile', 0.6))
    threshold = np.quantile(s_map, quantile_val)
    return (s_map < threshold) & (~protected)


def pack_pairs(values: np.ndarray) -> bytes:
    """Vectorized conversion of 2-bit values (0-3) into packed 8-bit bytes."""
    v = np.asarray(values, dtype=np.uint8).ravel()
    # Mask to ensure only the lower 2 bits are considered
    v_clean = v & 3
    # Two bits per pixel means 4 pixels per byte
    pad_len = (-len(v_clean)) % 4
    if pad_len:
        v_clean = np.pad(v_clean, (0, pad_len), mode='constant')

    reshaped = v_clean.reshape(-1, 4)
    packed = (
        (reshaped[:, 0] << 6)
        | (reshaped[:, 1] << 4)
        | (reshaped[:, 2] << 2)
        | reshaped[:, 3]
    )
    return packed.tobytes()


def unpack_pairs(data: bytes, count: int) -> np.ndarray:
    """Vectorized unpacking of packed bytes back into an array of 2-bit integers."""
    raw = np.frombuffer(data, dtype=np.uint8)
    # Extract four 2-bit pairs per byte
    b0 = (raw >> 6) & 3
    b1 = (raw >> 4) & 3
    b2 = (raw >> 2) & 3
    b3 = raw & 3

    unpacked = np.column_stack((b0, b1, b2, b3)).ravel()
    return unpacked[:count]


def embed(cipher: np.ndarray, payload: bytes, eligible: np.ndarray, cfg: dict):
    """Embeds framed, compressed payload into 2-bit LSBs of eligible cipher pixels."""
    if cipher.shape != eligible.shape:
        raise ValueError('Mask shape mismatch')
    if cipher.dtype != np.uint8 or cipher.ndim != 2 or eligible.dtype != bool:
        raise ValueError('2D uint8 and boolean mask required')
    if not isinstance(payload, bytes):
        raise ValueError('Payload must be bytes')

    compression_level = int(cfg.get('compression_level', 9))
    compressed = zlib.compress(payload, level=compression_level)
    payload_hash = hashlib.sha256(payload).digest()

    packet = HEADER.pack(b'MST1', len(compressed), len(payload), payload_hash) + compressed
    positions = np.flatnonzero(eligible.ravel())

    # Each byte of packet requires 4 pixels (2 bits each)
    needed_pixels = len(packet) * 4
    if needed_pixels > positions.size:
        raise CapacityError(needed_pixels * 2, int(positions.size) * 2)

    positions = positions[:needed_pixels]
    flat = cipher.ravel().copy()

    # Extract original 2-bit LSBs for exact lossless sidecar restoration
    original_bits = pack_pairs(flat[positions] & 3)

    # Embed new 2-bit pairs
    new_pairs = unpack_pairs(packet, needed_pixels)
    flat[positions] = (flat[positions] & 252) | new_pairs

    info = {
        'compressed_bytes': len(compressed),
        'payload_bytes': len(payload),
        'framing_bytes': HEADER.size,
        'embedded_bits': len(packet) * 8,
        'available_bits': int(np.count_nonzero(eligible)) * 2,
        'payload_bpp': len(payload) * 8 / cipher.size,
        'compressed_bpp': len(compressed) * 8 / cipher.size,
        'gross_embedded_bpp': len(packet) * 8 / cipher.size,
        'available_bpp': int(np.count_nonzero(eligible)) * 2 / cipher.size,
        'compression_saving_pct': 100.0 * (1.0 - len(compressed) / len(payload)) if payload else None,
    }
    return flat.reshape(cipher.shape), positions, original_bits, info


def extract(stego: np.ndarray, positions: np.ndarray, max_payload_bytes: int = 64 * 1024 * 1024) -> bytes:
    """Extracts and verifies embedded payload from specified stego pixel coordinates."""
    positions = np.asarray(positions)
    if stego.dtype != np.uint8 or stego.ndim != 2:
        raise ValueError('2D uint8 stego required')
    if positions.ndim != 1 or positions.dtype.kind not in 'iu' or (positions < 0).any() or (positions >= stego.size).any():
        raise ValueError('Invalid extraction positions')

    packet = pack_pairs(stego.ravel()[positions] & 3)
    if len(packet) < HEADER.size:
        raise ValueError('Truncated header')

    magic, n, raw_size, expected_hash = HEADER.unpack(packet[:HEADER.size])
    if magic != b'MST1' or n != len(packet) - HEADER.size or raw_size > max_payload_bytes:
        raise ValueError('Corrupt length/magic or payload exceeds receiver limit')

    decomp = zlib.decompressobj()
    out = decomp.decompress(packet[HEADER.size:], raw_size + 1)
    if not decomp.eof or decomp.unused_data or len(out) != raw_size or hashlib.sha256(out).digest() != expected_hash:
        raise ValueError('Corrupt compressed payload/checksum')

    return out


def restore_cipher(stego: np.ndarray, positions: np.ndarray, original_lsb: bytes) -> np.ndarray:
    """Exact bit-level restoration of cipher image prior to LSB modification."""
    expected_bytes = (len(positions) * 2 + 7) // 8
    if len(original_lsb) != expected_bytes:
        raise ValueError('Recovery bit length mismatch')

    out = stego.ravel().copy()
    values = unpack_pairs(original_lsb, len(positions))
    if len(values) != len(positions):
        raise ValueError('Missing recovery bits')

    out[positions] = (out[positions] & 252) | values
    return out.reshape(stego.shape)