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
from scripts.dynamics import lyapunov, variational_steps
from scripts.nist import FAMILIES, export_streams, run_official
from scripts.chaos import jacobian, rhs, rhs_5d

SCRIPTS = Path(__file__).resolve().parents[1]


def test_jacobian_matches_subathra_2025_5d_hyperchaos():
    """Test Jacobian against finite difference for Subathra & Thanikaiselvan (2025) 5D hyperchaos."""
    s = np.array([0.3, -0.2, 0.5, 0.1, -0.4], dtype=np.float64)
    p = np.array([40.0, 8.0, 40.0, 1.0, -0.5, 25.5, 0.05], dtype=np.float64)
    eps = 1e-6

    j = jacobian(s, p, 2)
    fd = np.zeros_like(j)
    for i in range(5):
        ds = np.zeros(5, dtype=np.float64)
        ds[i] = eps
        fd[:, i] = (rhs(s + ds, p, 2) - rhs(s - ds, p, 2)) / (2.0 * eps)

    np.testing.assert_allclose(j, fd, rtol=1e-4, atol=1e-4)

def test_finite_time_qr_linear_case_near_expected_eigenvalues(stable_cfg):
    """Retain expansion in R; orthogonality alone cannot test Lyapunov exponents.

    Appendix at equilibrium with a=2,b=3,c=0,d=-4,e=.2 has triangular
    tangent flow and eigenvalues -2,-4,-3,.2,-.2 in this coordinate order.
    """
    p = np.array([2., 3., 0., -4., .2])
    s = np.zeros(5, dtype=np.float64)
    q = np.eye(5, dtype=np.float64)
    dt = .001; sums = np.zeros(5); steps = 2000
    for _ in range(steps//20):
        s, q = variational_steps(s, q, 20, dt, p, 1)
        q, r = np.linalg.qr(q)
        sums += np.log(np.abs(np.diag(r)))
    np.testing.assert_allclose(sums/(steps*dt), [-2., -4., -3., .2, -.2], atol=1e-7)
    np.testing.assert_allclose(q.T @ q, np.eye(5), atol=1e-5)

def test_lyapunov_failure_logging_on_divergence():
    cfg = json.loads((SCRIPTS / 'appendix_experiment.json').read_text())
    cfg["dt"] = 10.0
    cfg["transient"] = 1
    out = lyapunov("12" * 32, cfg, steps=2000, qr_interval=10)
    assert out["status"] == "failed"
    assert "diverged" in out["error"]


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