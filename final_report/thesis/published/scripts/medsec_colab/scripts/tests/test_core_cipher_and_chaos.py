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


@pytest.mark.parametrize("variant", [2])
def test_rhs_matches_subathra_2025_5d_hyperchaos(variant):
    """Test that rhs matches the Subathra & Thanikaiselvan (2025) 5D hyperchaotic system.

    System equations:
      dx/dt = alpha*(y - x) + u
      dy/dt = gamma*x - x*z + rho*y + v
      dz/dt = x*y - beta*z
      du/dt = delta*u - x*z
      dv/dt = epsilon*v + kappa*x + theta*y   (theta = epsilon)
    """
    s = np.array([1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64)
    p = np.array([40.0, 8.0, 40.0, 1.0, -0.5, 25.5, 0.05], dtype=np.float64)  # alpha, beta, gamma, delta, epsilon, rho, kappa

    out = chaos.rhs(s, p, variant)

    x, y, z, u, v = s
    alpha, beta, gamma, delta, epsilon, rho, kappa = p
    theta = epsilon  # theta == epsilon in reference

    expected = np.array([
        alpha * (y - x) + u,          # dx/dt = 40*(1-1) + 1 = 1.0
        gamma * x - x * z + rho * y + v,  # dy/dt = 40*1 - 1*1 + 25.5*1 + 1 = 65.5
        x * y - beta * z,             # dz/dt = 1*1 - 8*1 = -7.0
        delta * u - x * z,            # du/dt = 1*1 - 1*1 = 0.0
        epsilon * v + kappa * x + theta * y,  # dv/dt = -0.5*1 + 0.05*1 + (-0.5)*1 = -0.95
    ])

    np.testing.assert_allclose(out, expected, rtol=1e-10, atol=1e-10)


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


def test_subathra_config_valid():
    """Test that subathra_diagnostic.json loads with valid parameters."""
    cfg = json.loads((SCRIPTS / 'subathra_diagnostic.json').read_text())
    validate(cfg)
    assert cfg['system'] == 'subathra_2025'
    assert cfg['parameters']['alpha'] == 40.0
    assert cfg['parameters']['beta'] == 8.0
    assert cfg['parameters']['gamma'] == 40.0
    assert cfg['parameters']['delta'] == 1.0
    assert cfg['parameters']['epsilon'] == -0.5
    assert cfg['parameters']['rho'] == 25.5
    assert cfg['parameters']['kappa'] == 0.05


def test_appendix_n65536_known_divergence_remains_reported():
    cfg = json.loads((SCRIPTS / 'appendix_experiment.json').read_text())
    with pytest.raises(ValueError, match="ODE diverged"):
        chaos.stream("12" * 32, 65536, cfg, raw=True)


def test_subathra_initial_conditions_derivatives():
    """Verify derivatives at (1,1,1,1,1) match reference values."""
    cfg = json.loads((SCRIPTS / 'subathra_diagnostic.json').read_text())
    p = chaos.ode_parameters(cfg)
    s = np.array([1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64)
    deriv = chaos.rhs(s, p, 2)
    expected = np.array([1.0, 65.5, -7.0, 0.0, -0.95])
    np.testing.assert_allclose(deriv, expected, rtol=1e-10, atol=1e-10)