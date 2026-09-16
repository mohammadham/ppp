# Google Colab pytest Fix
## Issue: CalledProcessError with exit status 2
## Colab: https://colab.research.google.com/drive/1Y6wC2egkRu6SkTWq-ua42FyB5zHg9JjM

### Root Cause
pytest is installed (shown in Cell 2 output "✅ pytest Already installed"), but the test path is wrong. The tests are located at `medsec_colab/scripts/tests/`, not `scripts/tests/`.

### Solution: Run These Three Cells in Order

#### Cell 1: Setup Directory
```python
import os, sys
from pathlib import Path

# Change to the thesis toolkit directory
os.chdir('/content/thesis_toolkit')
sys.path.insert(0, '/content/thesis_toolkit')

# Verify structure
print("Working directory:", os.getcwd())
print("medsec_colab exists:", os.path.exists('medsec_colab'))
if os.path.exists('medsec_colab'):
    print("scripts/ contents:", os.listdir('medsec_colab/scripts/')[:10])
else:
    print("❌ medsec_colab not found - did you upload the zip?")
```

#### Cell 2: Verify pytest (already installed)
```python
# This cell was already executed and shows: ✅ pytest Already installed
import pytest
print('pytest version:', pytest.__version__)
print('pytest is ready to use')
```

#### Cell 3: Run Tests with Correct Path
```python
# THE FIX: Use medsec_colab/scripts/tests instead of scripts/tests
import subprocess

# Option A: Quiet mode (like your original attempt, but fixed path)
result = subprocess.run(
    [sys.executable, '-m', 'pytest', 'medsec_colab/scripts/tests', '-q'],
    capture_output=True, text=True
)
print("Return code:", result.returncode)
if result.returncode == 0:
    print("✅ All tests passed!")
else:
    print("stdout:", result.stdout)
    print("stderr (first 500 chars):", result.stderr[:500] if result.stderr else "None")

# Option B: Verbose mode - shows which tests pass/fail
result2 = subprocess.run(
    [sys.executable, '-m', 'pytest', 'medsec_colab/scripts/tests', '-v'],
    capture_output=True, text=True
)
print(result2.stdout[-2000:] if len(result2.stdout) > 2000 else result2.stdout)
```

### Expected Output
```
Working directory: /content/thesis_toolkit
medsec_colab exists: True
scripts/ contents: ['__init__.py', 'artifacts.py', 'chaos.py', ...]
Return code: 0
✅ All tests passed!
```

OR with -v:
```
... (test names).PASSED
= = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
24 passed in 12.34s
```

### If Tests Still Fail
Run with even more detail:
```python
subprocess.run(
    [sys.executable, '-m', 'pytest', 'medsec_colab/scripts/tests', '--tb=long'],
    capture_output=True, text=True
)
```
This will show exactly which test has the issue and the full error trace.

### After Tests Pass
You can now proceed to run sections 6-11 of the notebook. The core fixes are:
- `scripts/chaos.py`: Subathra 2025 parameters + RK4 integration + -e·u damping
- `scripts/config.py`: 3 system types + exact missing param names  
- `scripts/appendix_experiment.json`: subathra_2025 profile
- `scripts/training.py`: class weights + soft Dice + no Dice=0
