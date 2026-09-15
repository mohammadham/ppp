"""Dynamics, NIST, notebook/package and API endpoint tests (SOFTWARE TEST ONLY)."""

import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path

import nbformat
import numpy as np
import pytest

from scripts.artifacts import write_json
from scripts.dynamics import jacobian, lyapunov, variational_steps
from scripts.nist import FAMILIES, export_streams, run_official

SCRIPTS = Path(__file__).resolve().parents[1]


def test_jacobian_matches_finite_difference_both_variants():
    s = np.array([0.3, -0.2, 0.5, 0.1, -0.4], dtype=np.float64)
    p = np.array([1.0, 1.0, 0.0, -1.0, 0.0, 0.0, 1.0], dtype=np.float64)
    eps = 1e-6
    from scripts.chaos import rhs

    for variant in (0, 1):
        j = jacobian(s, p, variant)
        fd = np.zeros_like(j)
        for i in range(5):
            ds = np.zeros(5)
            ds[i] = eps
            fd[:, i] = (rhs(s + ds, p, variant) - rhs(s - ds, p, variant)) / (2 * eps)
        np.testing.assert_allclose(j, fd, atol=1e-5, rtol=1e-5)


def test_finite_time_qr_linear_case_near_expected_eigenvalues(stable_cfg):
    p = np.array([stable_cfg["parameters"][k] for k in ("a", "b", "c", "d", "k", "h", "w")], dtype=np.float64)
    s = np.zeros(5, dtype=np.float64)
    q = np.eye(5, dtype=np.float64)
    dt = stable_cfg["dt"]

    steps = 2000
    sums = np.zeros(5)
    done = 0
    while done < steps:
        s, q = variational_steps(s, q, 20, dt, p, 0)
        q, r = np.linalg.qr(q)
        sums += np.log(np.abs(np.diag(r)))
        done += 20
    spectrum = np.sort(sums / (steps * dt))

    expected = np.sort(np.real(np.linalg.eigvals(jacobian(np.zeros(5), p, 0))))
    np.testing.assert_allclose(spectrum, expected, atol=5e-2, rtol=5e-2)


def test_lyapunov_failure_logging_on_divergence():
    cfg = json.loads((SCRIPTS/'appendix_experiment.json').read_text())
    cfg["dt"] = 10.0
    cfg["transient"] = 1
    out = lyapunov("12" * 32, cfg, steps=2000, qr_interval=10)
    assert out["status"] == "failed"
    assert "diverged" in out["error"]


def test_nist_official_all_families_one_sequence_allow_small(tmp_path):
    if not os.environ.get('NIST_STS_ROOT'):
        pytest.skip('Optional official STS integration: set NIST_STS_ROOT after building STS; not a research result')
    input_dir = tmp_path / "nist_input"
    output_dir = tmp_path / "nist_output"
    input_dir.mkdir(parents=True)

    bits = 1_000_000
    payload = bytes([i % 256 for i in range(bits // 8)])
    (input_dir / "bits.bin").write_bytes(payload)
    write_json(
        input_dir / "input.json",
        {
            "sequences": 1,
            "bits_per_sequence": bits,
            "input_sha256": hashlib.sha256(payload).hexdigest(),
            "membership": [{"sources": [{"id": "SOFTWARE_TEST_ONLY"}], "discarded_bytes": 0}],
        },
    )

    sts_root = Path(os.environ['NIST_STS_ROOT'])
    result = run_official(sts_root, input_dir, output_dir, timeout=2400, allow_small=True)
    assert result["families"] == 15
    assert set(FAMILIES) == {c["family"] for c in result["components"]}
    assert len(result["components"]) == 188
    assert sum(1 for c in result["components"] if c["family"] == "NonOverlappingTemplate") == 148
    assert all(c["raw_count"] == 1 for c in result["components"])


def test_nist_export_rejects_mixed_config_and_insufficient_and_no_padding(tmp_path):
    def make_run(root: Path, cfg_tag: str, group: str, image_bytes: bytes):
        run = root
        (run / "sample_00000").mkdir(parents=True)
        np.save(run / "sample_00000" / "cipher.npy", np.frombuffer(image_bytes, dtype=np.uint8).reshape(4, 4))
        write_json(run / "run.json", {"config": {"tag": cfg_tag}})
        write_json(
            run / "samples.jsonl",
            {"status": "ok", "id": "1", "dataset": "DRIVE", "group_id": group, "processed_sha256": group, "folder": "sample_00000"},
        )
        # normalize JSONL format
        (run / "samples.jsonl").write_text(
            json.dumps(
                {
                    "status": "ok",
                    "id": "1",
                    "dataset": "DRIVE",
                    "group_id": group,
                    "processed_sha256": group,
                    "folder": "sample_00000",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return run

    r1 = make_run(tmp_path / "run1", "A", "g1", bytes(range(16)))
    r2 = make_run(tmp_path / "run2", "B", "g2", bytes(range(16, 32)))

    with pytest.raises(ValueError, match="Do not pool different cipher configurations"):
        export_streams([r1, r2], tmp_path / "mix", sequences=1, bits=16)

    with pytest.raises(ValueError, match="Insufficient distinct-subject ciphertext"):
        export_streams([r1], tmp_path / "insufficient", sequences=2, bits=16)


def test_nist_export_exact_content_short_length(tmp_path):
    run = tmp_path / "run"
    (run / "sample_00000").mkdir(parents=True)
    cipher = np.array([[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]], dtype=np.uint8)
    np.save(run / "sample_00000" / "cipher.npy", cipher)
    write_json(run / "run.json", {"config": {"stable": True}})
    (run / "samples.jsonl").write_text(
        json.dumps(
            {
                "status": "ok",
                "id": "s1",
                "dataset": "DRIVE",
                "group_id": "retina:01",
                "processed_sha256": "abc123",
                "folder": "sample_00000",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = tmp_path / "export"
    meta = export_streams([run], out, sequences=1, bits=16)
    assert meta["sequences"] == 1
    assert (out / "bits.bin").read_bytes() == bytes([1, 2])


def test_notebook_valid_and_zip_excludes_legacy_scripts(tmp_path):
    from scripts.build_delivery import build
    zip_path = build(tmp_path/'delivery')
    nb_path = zip_path.parent/'Thesis_Colab.ipynb'
    nb = nbformat.read(nb_path, as_version=4)
    nbformat.validate(nb)
    for cell in nb.cells:
        if cell.cell_type == "code":
            compile(cell.source, "<colab_cell>", "exec")

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    assert "medsec_colab/scripts/Untitled1.ipynb" not in names
    assert "medsec_colab/scripts/untitled1.py" not in names
    assert all("__pycache__" not in n for n in names)


def test_public_download_endpoints_and_unknown_artifacts(tmp_path):
    if not os.environ.get('REACT_APP_BACKEND_URL'):
        pytest.skip('Optional website-download checks: not needed for offline Colab toolkit')
    base = os.environ['REACT_APP_BACKEND_URL']
    expected = {
        "download": "application/zip",
        "notebook": "application/x-ipynb+json",
        "guide": "text/markdown",
        "status": "text/markdown",
        "conformance": "text/markdown",
    }
    for artifact, content_type in expected.items():
        proc = subprocess.run(
            ["curl", "-sS", "-o", str(tmp_path/'artifact.bin'), "-w", "%{http_code} %{content_type}", f"{base}/api/research/{artifact}"],
            capture_output=True,
            text=True,
            check=True,
        )
        code, ctype = proc.stdout.strip().split(" ", 1)
        assert code == "200"
        assert content_type in ctype

    for bad in ("unknown", "..%2Fguide", "../guide"):
        proc = subprocess.run(
            ["curl", "-sS", "-o", str(tmp_path/'artifact_bad.bin'), "-w", "%{http_code}", f"{base}/api/research/{bad}"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert proc.stdout.strip() == "404"
