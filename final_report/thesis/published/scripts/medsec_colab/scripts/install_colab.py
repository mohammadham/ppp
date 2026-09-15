"""Install missing dependencies without replacing an existing CUDA-enabled torch."""
import subprocess
import sys
from pathlib import Path

PACKAGES = ['numpy', 'scipy', 'scikit-image', 'pillow', 'numba', 'nibabel',
            'cryptography', 'torch', 'matplotlib', 'pytest', 'nbformat']

if __name__ == '__main__':
    subprocess.run([sys.executable, '-m', 'pip', 'install', *PACKAGES], check=True)
    result = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], check=True, capture_output=True, text=True)
    Path('installed_environment.txt').write_text(result.stdout, encoding='utf-8')
    print('نصب انجام شد. نسخه‌ها در installed_environment.txt ثبت شدند؛ CUDA موجود با نسخهٔ CPU جایگزین نشد.')