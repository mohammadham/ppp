"""SOFTWARE TEST ONLY fixtures for thesis toolkit regression tests."""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import torch
torch.set_num_threads(1)
from scripts.training import train


def _write_png(path: Path, array: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(array.astype(np.uint8)).save(path)


def _tiny_sample(seed: int, size: int = 32):
    rng = np.random.default_rng(seed)
    mask = np.zeros((size, size), dtype=np.uint8)
    start = size//4 + (seed % 3)
    end = 3*size//4
    mask[start:end, start:end] = 255
    noise = rng.integers(0, 24, size=(size, size), dtype=np.uint8)
    image = np.clip(noise + (mask > 0) * 180, 0, 255).astype(np.uint8)
    return image, mask


@pytest.fixture
def stable_cfg():
    return {
        "profile": "software_test_only_stable",
        "system": "subathra_2025",
        "parameters": {"alpha": 40.0, "beta": 8.0, "gamma": 40.0, "delta": 1.0, "epsilon": -0.5, "rho": 25.5, "kappa": 0.05},
        "parameter_source": "SOFTWARE TEST ONLY stable fixture",
        "dt": 0.001,
        "transient": 10,
        "scale": 1e14,
        "hash_mapping": "mod_1e8",
        "dna_variant": "pseudocode_3_3",
        "saliency_quantile": 0.6,
        "saliency_filter": 3,
        "saliency_sigma": 2.5,
        "roi_coordinates": "permuted_union_original",
        "compression_level": 9,
        "seed": 2026,
        "correlation_pairs": 128,
        "differential_trials": 4,
        "training": {
            "epochs": 60,
            "batch_size": 1,
            "learning_rate": 0.01,
            "base_channels": 4,
            "size": 32,
            "patience": 20,
            "threshold": 0.5,
        },
    }


@pytest.fixture
def tiny_image_roi():
    h, w = 64, 96
    x = np.arange(h * w, dtype=np.uint8).reshape(h, w)
    roi = np.zeros((h, w), dtype=bool)
    roi[8:40, 16:72] = True
    return x, roi


@pytest.fixture
def trained_bundle(tmp_path, stable_cfg):
    base = tmp_path / "software_test_only_bundle"
    data_dir = base / "data"
    manifest = base / "manifest.jsonl"
    payload = base / "payload.bin"
    output = base / "weights"

    records = []
    for i, split in enumerate(("train", "val", "test"), start=1):
        sample_id = f"{i:02d}"
        image, mask = _tiny_sample(seed=100 + i, size=64)
        image_path = data_dir / f"{sample_id}_image.png"
        mask_path = data_dir / f"{sample_id}_mask.png"
        _write_png(image_path, image)
        _write_png(mask_path, mask)
        records.append(
            {
                "id": sample_id,
                "dataset": "DRIVE",
                "patient_id": sample_id,
                "group_id": f"retina:{sample_id}",
                "split": split,
                "image": str(image_path.resolve()),
                "mask": str(mask_path.resolve()),
                "source": "SOFTWARE TEST ONLY synthetic retinal fixtures",
                "mask_definition": "SOFTWARE TEST ONLY binary vessel-like mask",
            }
        )
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    payload.write_bytes(b'SOFTWARE TEST ONLY metadata\n'*300)

    result = train(str(manifest), "DRIVE", stable_cfg, str(output), device="cpu", resume=False)
    assert Path(result["best_checkpoint"]).is_file()

    return {
        "root": base,
        "manifest": manifest,
        "payload": payload,
        "weights_dir": output,
        "best_checkpoint": output / "best.pt",
        "last_checkpoint": output / "last.pt",
        "config": stable_cfg,
    }
