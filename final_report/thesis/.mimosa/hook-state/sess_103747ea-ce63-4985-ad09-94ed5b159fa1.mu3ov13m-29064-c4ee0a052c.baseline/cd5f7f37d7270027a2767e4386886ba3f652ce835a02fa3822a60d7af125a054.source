"""Research provenance and strict JSON (Infinity is serialized as a string)."""
import hashlib
import importlib.metadata
import json
import math
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def clean(value):
    if isinstance(value, dict): return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    if isinstance(value, np.ndarray): return clean(value.tolist())
    if isinstance(value, np.generic): return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return 'Infinity' if value == math.inf else '-Infinity' if value == -math.inf else None
    if isinstance(value, Path): return str(value)
    return value

def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    tmp.replace(path)

def append_jsonl(path, value):
    with Path(path).open('a', encoding='utf-8') as f:
        f.write(json.dumps(clean(value), ensure_ascii=False, allow_nan=False) + '\n')

def environment():
    packages = {}
    for name in ['numpy', 'scipy', 'torch', 'numba', 'scikit-image', 'Pillow', 'nibabel', 'cryptography']:
        try: packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: packages[name] = None
    try:
        gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'],
                             capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired): gpu = None
    source = {p.name: sha256_file(p) for p in sorted(Path(__file__).parent.glob('*.py')) if p.name != 'untitled1.py'}
    return {'utc': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
            'platform': platform.platform(), 'processor': platform.processor(), 'gpu': gpu,
            'packages': packages, 'source_sha256': source}