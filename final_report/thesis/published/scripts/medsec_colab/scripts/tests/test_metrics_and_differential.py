"""Metrics and differential behavior tests (SOFTWARE TEST ONLY)."""

import numpy as np

from scripts.attacks import one_pixel_trial
from scripts.diagnostics import fixed_mask_probes
from scripts.metrics import differential, quality, security


def test_differential_known_one_pixel_values():
    a = np.zeros((10, 10), dtype=np.uint8)
    b = a.copy()
    b[0, 0] = 255
    out = differential(a, b)
    assert out["npcr"] == 1.0  # 100 / N where N=100
    assert out["uaci"] == 1.0


def test_psnr_inf_and_undefined_correlations_none_and_roi_ssim_separate():
    a = np.full((8, 8), 10, dtype=np.uint8)
    b = a.copy()
    roi = np.zeros_like(a, dtype=bool)
    roi[2:6, 2:6] = True

    q = quality(a, b, roi)
    s = security(a)

    assert q["psnr"] == float("inf")
    assert q["roi_ssim_local_mean"] is not None
    assert s["correlation_horizontal"] is None
    assert s["correlation_vertical"] is None
    assert s["correlation_diagonal"] is None


def test_one_pixel_trial_reencrypts_after_predictor_step(stable_cfg):
    image = np.arange(64, dtype=np.uint8).reshape(8, 8)
    roi = np.ones_like(image, dtype=bool)

    class FixedPredictor:
        def __call__(self, _):
            return roi

    from scripts.cipher import encrypt

    cipher, digest = encrypt(image, roi, stable_cfg)
    result = one_pixel_trial(image, roi, cipher, FixedPredictor(), stable_cfg, np.random.default_rng(2026), "inside")
    assert result["protocol"] == "reinfer_ROI_and_rehash"
    assert result["changed_digest"] != digest


def test_fixed_mask_diagnostic_keeps_same_digest_outside_roi(stable_cfg):
    image = np.arange(256, dtype=np.uint8).reshape(16, 16)
    roi = np.zeros_like(image, dtype=bool)
    roi[4:12, 4:12] = True
    rows = fixed_mask_probes(image, roi, stable_cfg)
    outside = [r for r in rows["probes"] if r["probe"] == "outside_pixel"][0]
    assert outside["status"] == "ok"
    assert outside["same_digest"] is True