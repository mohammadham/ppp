"""Regression: build_delivery.py must run from package root as a script."""

import subprocess
import sys
from pathlib import Path


def test_build_delivery_entrypoint_runs_without_import_error():
    project_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "scripts/build_delivery.py"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "build_delivery.py should succeed when executed as a script from package root.\n"
        f"returncode={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
