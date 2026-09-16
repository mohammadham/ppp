"""Core cipher/chaos software tests (SOFTWARE TEST ONLY)."""

import json
from pathlib import Path

import numpy as np
import pytest

from scripts import chaos
from scripts.cipher import decode_dna, dna_transform, encode_dna, encrypt, decrypt, zigzag_indices
from scripts.config import validate

SCRIPTS = Path(__file__).resolve().parents[1]


def test_dna_tables_exhaustive_roundtrip_for_all_rules():
    values = np.arange(256, dtype=np.uint8)
    for rule in range(8):
        rules = np.full(values.shape, rule, dtype=np.uint8)
        decoded = decode_dna(encode_dna(values, rules), rules)
        np.testing.assert_array_equal(decoded, values)


@pytest.mark.parametrize("variant", ["pseudocode_3_3", "equation_3_3_feedback"])
def test_encrypt_decrypt_roundtrip_both_variants(variant, stable_cfg, tiny_image_roi):
    image, roi = tiny_image_roi
    cfg = dict(stable_cfg)
    cfg["dna_variant"] = variant
    cipher, digest = encrypt(image, roi, cfg)
    plain = decrypt(cipher, digest, cfg)
    np.testing.assert_array_equal(plain, image)


def test_dna_feedback_inverse_roundtrip(stable_cfg):
    values = np.arange(32, dtype=np.uint8)
    keys = np.tile(np.array([[3, 150, 201]], dtype=np.uint8), (values.size, 1))
    transformed = dna_transform(values, keys, "equation_3_3_feedback", inverse=False)
    restored = dna_transform(transformed, keys, "equation_3_3_feedback", inverse=True)
    np.testing.assert_array_equal(restored, values)


def test_rectangular_zigzag_known_order():
    idx = zigzag_indices(2, 3)
    assert idx.tolist() == [0, 1, 3, 4, 2, 5]
    assert len(np.unique(idx)) == 6


@pytest.mark.parametrize("variant", [0, 1])
def test_rhs_matches_analytic_equations(variant):
    s = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    p = np.array([1.5, 0.8, -2.0, 0.5, 0.25, 0.75, 1.2])
    out = chaos.rhs(s, p, variant)
    expected = np.array([
        p[0] * (s[1] - s[0]) + s[3],
        p[2] * s[0] - s[0] * s[2] + p[3] * s[1] + s[4],
        s[0] * s[1] - p[1] * s[2],
        (-p[4] * s[0]) if variant == 0 else (-s[1] * s[2] + p[4] * s[3]),
        (p[5] * s[1] - p[6] * s[4]) if variant == 0 else (s[0] * s[2] - p[4] * s[4]),
    ])
    np.testing.assert_allclose(out, expected, rtol=1e-12, atol=1e-12)


def test_stream_determinism_and_no_rng_fallback(stable_cfg):
    digest = "ab" * 32
    first = chaos.stream(digest, 128, stable_cfg)
    second = chaos.stream(digest, 128, stable_cfg)
    np.testing.assert_array_equal(first, second)

    diverging = dict(stable_cfg)
    diverging["dt"] = 5.0
    diverging["transient"] = 1
    with pytest.raises(ValueError, match="no RNG substitution"):
        chaos.stream(digest, 32, diverging, raw=True)


def test_thesis_reference_rejects_missing_seven_parameters():
    cfg = json.loads((SCRIPTS / 'thesis_reference.json').read_text())
    with pytest.raises(ValueError, match="پارامترهای رابطه ۳-۲"):
        validate(cfg)


def test_appendix_n65536_known_divergence_remains_reported():
    cfg = json.loads((SCRIPTS / 'appendix_experiment.json').read_text())
    with pytest.raises(ValueError, match="ODE diverged"):
        chaos.stream("12" * 32, 65536, cfg, raw=True)
