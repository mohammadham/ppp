"""Transport/stego integrity tests (SOFTWARE TEST ONLY)."""

import numpy as np
import pytest

from scripts.cipher import protected_mask
from scripts.stego import embedding_mask, extract
from scripts.transport import receive, send


def _image_roi_for_capacity():
    image = np.tile(np.arange(256, dtype=np.uint8), (256, 1))
    roi = np.zeros_like(image, dtype=bool)
    roi[100:156, 100:156] = True
    return image, roi


@pytest.mark.parametrize("payload", [b"", bytes([i % 251 for i in range(5000)])])
def test_send_receive_uint8_exact_for_empty_and_large_payload(stable_cfg, payload):
    image, roi = _image_roi_for_capacity()
    cfg = dict(stable_cfg)
    cfg["no_saliency"] = True
    secret = b"K" * 32
    outcome = send(image, roi, payload, cfg, secret)
    plain, recovered_payload = receive(outcome["stego"], outcome["sidecar"], secret)
    np.testing.assert_array_equal(plain, image)
    assert recovered_payload == payload


def test_overflow_payload_rejected(stable_cfg):
    image, roi = _image_roi_for_capacity()
    cfg = dict(stable_cfg)
    cfg["no_saliency"] = True
    rng = np.random.default_rng(2026)
    payload = rng.integers(0, 256, size=80_000, dtype=np.uint8).tobytes()
    with pytest.raises(ValueError, match="Insufficient capacity"):
        send(image, roi, payload, cfg, b"S" * 32)


def test_compressed_packet_above_4096_bytes_roundtrip(stable_cfg):
    import zlib
    image, roi = _image_roi_for_capacity()
    cfg = dict(stable_cfg); cfg['no_saliency'] = True
    payload = np.random.default_rng(55).integers(0, 256, 7000, dtype=np.uint8).tobytes()
    assert len(zlib.compress(payload)) > 4096
    outcome = send(image, roi, payload, cfg, b'L'*32)
    plain, extracted = receive(outcome['stego'], outcome['sidecar'], b'L'*32)
    assert extracted == payload
    np.testing.assert_array_equal(plain, image)


def test_roi_protection_excludes_protected_positions(stable_cfg):
    image, roi = _image_roi_for_capacity()
    cfg = dict(stable_cfg)
    protected = protected_mask(roi, cfg)
    eligible = embedding_mask(image, protected, cfg)
    assert np.count_nonzero(eligible & protected) == 0


def test_tampering_sidecar_stego_wrong_secret_rejected(stable_cfg):
    image, roi = _image_roi_for_capacity()
    cfg = dict(stable_cfg)
    cfg["no_saliency"] = True
    secret = b"A" * 32
    outcome = send(image, roi, b"metadata", cfg, secret)

    stego_bad = outcome["stego"].copy()
    stego_bad[0, 0] ^= np.uint8(1)
    with pytest.raises(ValueError):
        receive(stego_bad, outcome["sidecar"], secret)

    sidecar_bad = bytearray(outcome["sidecar"])
    sidecar_bad[-1] ^= 0x01
    with pytest.raises(Exception):
        receive(outcome["stego"], bytes(sidecar_bad), secret)

    with pytest.raises(Exception):
        receive(outcome["stego"], outcome["sidecar"], b"B" * 32)


def test_extract_rejects_bad_header_and_invalid_mask_inputs():
    stego = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(ValueError, match="Invalid extraction positions"):
        extract(stego, np.array([-1, 2], dtype=np.int64))
    with pytest.raises(ValueError, match="Invalid extraction positions"):
        extract(stego, np.array([999], dtype=np.int64))
    with pytest.raises(ValueError, match="Truncated header"):
        extract(stego, np.array([0, 1], dtype=np.int64))
