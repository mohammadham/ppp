"""Data, training, run/report and CLI tests (SOFTWARE TEST ONLY)."""

import csv
import json
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from scripts.artifacts import sha256_file
from scripts.data import load_manifest, load_sample
from scripts.experiments import evaluate_segmentation, run
from scripts.prepare import prepare
from scripts.reporting import make_report
from scripts.training import train


def _write_manifest(path: Path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_manifest_leakage_and_hash_mismatch_rejected(tmp_path):
    image = np.zeros((16, 16), dtype=np.uint8)
    mask = np.zeros((16, 16), dtype=np.uint8)
    mask[2:8, 2:8] = 255
    img1 = tmp_path / "img1.png"
    msk1 = tmp_path / "mask1.png"
    img2 = tmp_path / "img2.png"
    msk2 = tmp_path / "mask2.png"
    from PIL import Image

    Image.fromarray(image).save(img1)
    Image.fromarray(mask).save(msk1)
    Image.fromarray(image).save(img2)  # identical content triggers leakage across split
    Image.fromarray(mask).save(msk2)

    rows = [
        {
            "id": "01",
            "dataset": "DRIVE",
            "patient_id": "01",
            "group_id": "retina:01",
            "split": "train",
            "image": str(img1),
            "mask": str(msk1),
            "source": "SOFTWARE TEST ONLY",
            "mask_definition": "SOFTWARE TEST ONLY",
        },
        {
            "id": "02",
            "dataset": "DRIVE",
            "patient_id": "02",
            "group_id": "retina:02",
            "split": "test",
            "image": str(img2),
            "mask": str(msk2),
            "source": "SOFTWARE TEST ONLY",
            "mask_definition": "SOFTWARE TEST ONLY",
        },
    ]
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(manifest, rows)
    with pytest.raises(ValueError, match="Image-content leakage"):
        load_manifest(manifest)

    rows[1]["split"] = "train"
    rows[1]["image_sha256"] = "deadbeef"
    _write_manifest(manifest, rows)
    with pytest.raises(ValueError, match="Changed file checksum"):
        load_manifest(manifest)


def test_nifti_affine_shape_validation_and_positive_labels(tmp_path):
    img_data = np.zeros((8, 8, 3), dtype=np.float32)
    img_data[..., 1] = 10
    mask_data = np.zeros((8, 8, 3), dtype=np.float32)
    mask_data[2:4, 2:4, 1] = 2
    affine = np.eye(4)
    img_path = tmp_path / "case_flair.nii.gz"
    mask_path = tmp_path / "case_seg.nii.gz"
    nib.save(nib.Nifti1Image(img_data, affine), img_path)
    nib.save(nib.Nifti1Image(mask_data, affine), mask_path)

    record = {
        "id": "case_001",
        "dataset": "BraTS2020",
        "patient_id": "case",
        "group_id": "brats2020:case",
        "split": "test",
        "image": str(img_path),
        "mask": str(mask_path),
        "axis": 2,
        "slice": 1,
        "source": "SOFTWARE TEST ONLY",
        "mask_definition": "SOFTWARE TEST ONLY labels > 0",
    }
    image, mask, _ = load_sample(record)
    assert image.dtype == np.uint8
    assert mask.any()

    bad_mask = tmp_path / "case_bad_seg.nii.gz"
    bad_affine = np.eye(4)
    bad_affine[0, 0] = 2
    nib.save(nib.Nifti1Image(mask_data, bad_affine), bad_mask)
    record["mask"] = str(bad_mask)
    with pytest.raises(ValueError, match="geometry mismatch"):
        load_sample(record)


def test_prepare_cxr_missing_mask_definition_rejected(tmp_path):
    root = tmp_path / "cxr"
    root.mkdir()
    from PIL import Image

    image = np.zeros((16, 16), dtype=np.uint8)
    mask = np.zeros((16, 16), dtype=np.uint8)
    (root / "images").mkdir()
    (root / "masks").mkdir()
    Image.fromarray(image).save(root / "images" / "a.png")
    Image.fromarray(mask).save(root / "masks" / "a.png")

    csv_path = tmp_path / "cxr.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "patient_id", "image", "mask", "split"])
        writer.writeheader()
        writer.writerow({"id": "a", "patient_id": "p1", "image": "images/a.png", "mask": "masks/a.png", "split": "train"})

    with pytest.raises(ValueError, match="Missing required fields"):
        prepare("COVID19_CXR", root, tmp_path / "cxr.jsonl", "SOFTWARE TEST ONLY", csv_path=csv_path)


def test_training_eval_resume_and_changed_manifest_rejected(trained_bundle):
    bundle = trained_bundle
    assert bundle["best_checkpoint"].is_file()
    assert bundle["last_checkpoint"].is_file()
    assert (bundle["weights_dir"] / "history.json").is_file()
    assert (bundle["weights_dir"] / "provenance.json").is_file()

    eval_out = bundle["root"] / "eval.json"
    result = evaluate_segmentation(bundle["manifest"], "DRIVE", bundle["best_checkpoint"], eval_out, device="cpu")
    assert result["dataset"] == "DRIVE"
    assert eval_out.is_file()

    resumed = train(str(bundle["manifest"]), "DRIVE", bundle["config"], str(bundle["weights_dir"]), device="cpu", resume=True)
    assert resumed["epochs"] >= 1

    changed_manifest = bundle["root"] / "manifest_changed.jsonl"
    rows = [json.loads(x) for x in bundle["manifest"].read_text().splitlines()]
    rows[2]["source"] = "SOFTWARE TEST ONLY changed manifest provenance"
    _write_manifest(changed_manifest, rows)
    with pytest.raises(ValueError, match="Resume requires identical"):
        train(str(changed_manifest), "DRIVE", bundle["config"], str(bundle["weights_dir"]), device="cpu", resume=True)


def test_run_blocked_writes_status_json(trained_bundle):
    bundle = trained_bundle
    invalid = dict(bundle["config"])
    invalid["parameters"] = {k: None for k in ("a", "b", "c", "d", "k", "h", "w")}
    out = bundle["root"] / "blocked_run"
    with pytest.raises(Exception):
        run(bundle["manifest"], "DRIVE", bundle["best_checkpoint"], invalid, bundle["payload"], out, "cpu", limit=1)
    status = json.loads((out / "status.json").read_text())
    assert status["status"] == "blocked"


def test_resume_rejects_changed_file_content_even_without_manifest_hashes(trained_bundle):
    from PIL import Image
    bundle = trained_bundle
    first = json.loads(bundle['manifest'].read_text().splitlines()[0])
    image = np.array(Image.open(first['image'])); image[0,0] ^= np.uint8(1)
    Image.fromarray(image).save(first['image'])
    with pytest.raises(ValueError, match='identical source image/mask contents'):
        train(bundle['manifest'], 'DRIVE', bundle['config'], bundle['weights_dir'], 'cpu', resume=True)


def test_run_and_report_emit_csv_json_png_with_recorded_values(trained_bundle):
    bundle = trained_bundle
    cfg = dict(bundle["config"])
    cfg["differential_trials"] = 2
    run_dir = bundle["root"] / "run_ok"
    status = run(bundle["manifest"], "DRIVE", bundle["best_checkpoint"], cfg, bundle["payload"], run_dir, "cpu", limit=1)
    assert status["status"] == "completed", (run_dir / 'samples.jsonl').read_text()
    assert status['successful_samples'] == 1
    make_report(run_dir)

    for p in (run_dir / "reports" / "samples.csv", run_dir / "reports" / "summary.json"):
        assert p.is_file()
    if status["successful_samples"] > 0:
        assert (run_dir / "reports" / "observed_images_histograms.png").is_file()
    text = (run_dir / "samples.jsonl").read_text()
    if status["successful_samples"] > 0:
        assert "Infinity" in text


def test_cli_train_evaluate_run_send_receive_paths_feasible(trained_bundle):
    bundle = trained_bundle
    scripts_root = Path(__file__).resolve().parents[2]
    cfg_path = bundle["root"] / "stable_cfg.json"
    cfg_path.write_text(json.dumps(bundle["config"]), encoding="utf-8")
    key = bundle["root"] / "secret.key"
    send_out = bundle["root"] / "sent_cli"
    recv_out = bundle["root"] / "recv_cli"
    run_out = bundle["root"] / "run_cli"

    py = sys.executable
    subprocess.run([py, "-m", "scripts", "keygen", "--output", str(key)], check=True, cwd=scripts_root)
    subprocess.run(
        [
            py,
            "-m",
            "scripts",
            "run",
            "--manifest",
            str(bundle["manifest"]),
            "--dataset",
            "DRIVE",
            "--checkpoint",
            str(bundle["best_checkpoint"]),
            "--config",
            str(cfg_path),
            "--payload",
            str(bundle["payload"]),
            "--output",
            str(run_out),
            "--device",
            "cpu",
            "--limit",
            "1",
        ],
        check=False,
        cwd=scripts_root,
    )

    sent = subprocess.run(
        [
            py,
            "-m",
            "scripts",
            "send",
            "--manifest",
            str(bundle["manifest"]),
            "--dataset",
            "DRIVE",
            "--id",
            "03",
            "--checkpoint",
            str(bundle["best_checkpoint"]),
            "--config",
            str(cfg_path),
            "--payload",
            str(bundle["payload"]),
            "--keyfile",
            str(key),
            "--output",
            str(send_out),
            "--device",
            "cpu",
        ],
        check=False,
        cwd=scripts_root,
        capture_output=True,
        text=True,
    )
    assert sent.returncode == 0, sent.stderr

    subprocess.run(
        [
            py,
            "-m",
            "scripts",
            "receive",
            "--stego",
            str(send_out / "stego.png"),
            "--sidecar",
            str(send_out / "recovery.msr"),
            "--keyfile",
            str(key),
            "--output",
            str(recv_out),
        ],
        check=True,
        cwd=scripts_root,
    )
    assert (recv_out / "recovered.png").is_file()
    assert sha256_file(recv_out / "metadata.bin") == sha256_file(bundle["payload"])
    from PIL import Image
    records = load_manifest(bundle['manifest'])
    image, _, _ = load_sample(next(r for r in records if r['id'] == '03'))
    np.testing.assert_array_equal(np.array(Image.open(recv_out/'recovered.png')), image)
