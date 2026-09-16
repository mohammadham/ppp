# -*- coding: utf-8 -*-
"""Repair cells 8/9/10 from pristine git HEAD content, then apply clean skip-guards."""
import json
import ast
import subprocess
from pathlib import Path

nb_path = Path('published/scripts/medsec_colab/Thesis_Colab.ipynb')
nb = json.loads(nb_path.read_text(encoding='utf-8'))
cells = nb['cells']

raw = subprocess.run(
    ['git', 'show', 'HEAD:./published/scripts/medsec_colab/Thesis_Colab.ipynb'],
    capture_output=True, check=True
).stdout.decode('utf-8')
head_nb = json.loads(raw)
head_cells = head_nb['cells']
print('HEAD notebook cells:', len(head_cells))

def cell_src(c):
    return ''.join(c['source']) if isinstance(c['source'], list) else c['source']

# ---- cell 8: unique by docstring ----
hits8 = [cell_src(c) for c in head_cells if 'Downloads a pinned public REDISTRIBUTION' in cell_src(c)]
assert len(hits8) == 1, f'cell 8: {len(hits8)} hits'
pristine8 = hits8[0]

# ---- cells 9/10: two kagglehub cells, take them in document order ----
khits = [cell_src(c) for c in head_cells if 'selected_datasets = ["CHASE_DB1", "STARE"]' in cell_src(c)]
assert len(khits) == 2, f'kagglehub cells: {len(khits)}'
pristine9, pristine10 = khits[0], khits[1]
print('cell 9 FIVES line:', [l.strip() for l in pristine9.splitlines() if 'fundus-image' in l])
print('cell 10 FIVES line:', [l.strip() for l in pristine10.splitlines() if 'fundus-image' in l])

# ---- cell 11 / 13 ----
hits11 = [cell_src(c) for c in head_cells if 'fives_root = (' in cell_src(c)]
hits13 = [cell_src(c) for c in head_cells if 'specs = [' in cell_src(c)]
assert len(hits11) == 1 and len(hits13) == 1
pristine11, pristine13 = hits11[0], hits13[0]

for name, v in (('8', pristine8), ('9', pristine9), ('10', pristine10), ('11', pristine11), ('13', pristine13)):
    assert '_dataset_present' not in v and 'Conditional skip' not in v, f'cell {name} pristine contaminated'
print('pristine cells 8/9/10/11/13 extracted clean')

def set_src(i, text):
    cells[i]['source'] = text.splitlines(keepends=True)
    cells[i]['outputs'] = []
    cells[i]['execution_count'] = None

# ---- CELL 8: clean guard around download+unpack ----
old8 = """    archive = downloads / 'DRIVE-kaggle-v1.zip'
    download_archive(archive)
    unpack_verified(archive, source)"""
new8 = """    archive = downloads / 'DRIVE-kaggle-v1.zip'
    if archive.is_file() and source.is_dir():
        print('DRIVE از قبل موجود و کامل است؛ دانلود و استخراج تکراری انجام نشد.')
    else:
        print('DRIVE یافت نشد؛ دانلود و استخراج آغاز می‌شود.')
        download_archive(archive)
        unpack_verified(archive, source)"""
assert old8 in pristine8, 'cell 8 target block not found'
set_src(8, pristine8.replace(old8, new8, 1))
print('cell 8: clean guard applied')

# ---- CELLS 9/10: helper + guard, indent download loop under else ----
def guard_kagglehub(src):
    lines = src.splitlines(keepends=True)
    loop_idx = next(i for i, l in enumerate(lines) if l.startswith('for name in selected_datasets:'))
    end_idx = next(i for i, l in enumerate(lines) if 'دانلود پایان یافت' in l)
    assert loop_idx < end_idx
    indented = [('    ' + l) if l.strip() else l for l in lines[loop_idx:end_idx]]
    guard = [
        'def _dataset_present(name):\n',
        '    root = cache_root / catalog[name]\n',
        "    return root.is_dir() and any(root.rglob('*'))\n",
        '\n',
        '# اگر همهٔ مجموعه‌های انتخاب‌شده از قبل در کش ماندگار موجود باشند،\n',
        '# دانلود/استخراج/پردازش تکراری انجام نمی‌شود؛ فقط مسیرها بازخوانی می‌شوند.\n',
        'if all(_dataset_present(n) for n in selected_datasets):\n',
        "    print('همهٔ مجموعه‌ها از قبل در کش موجودند؛ دانلود و پردازش تکراری انجام نشد.')\n",
        '    for n in selected_datasets:\n',
        '        EXTRA_DATA_ROOTS[n] = (cache_root / catalog[n]).resolve()\n',
        "        print(f'{n}: از قبل موجود است.')\n",
        'else:\n',
    ]
    return ''.join(lines[:loop_idx] + guard + indented + lines[end_idx:])

set_src(9, guard_kagglehub(pristine9))
set_src(10, guard_kagglehub(pristine10))
print('cells 9, 10: clean guard applied')

# ---- CELL 11: pristine + missing-data guard ----
old11 = '/ "fundus-image-dataset-for-vessel-segmentation'
assert old11 in pristine11
guard11 = """

# این سلول چیزی دانلود نمی‌کند؛ اگر FIVES در کش نباشد با پیام روشن متوقف می‌شود
# و هیچ داده‌ای حذف یا دوباره دانلود نمی‌شود.
if not fives_root.is_dir():
    raise FileNotFoundError(
        'FIVES هنوز در کش kagglehub موجود نیست؛ ابتدا سلول دانلود kagglehub را اجرا کنید. '
        'هیچ داده‌ای حذف یا دوباره دانلود نمی‌شود.'
    )"""
# insert right after the closing paren of fives_root assignment
anchor = '\n)'
idx = pristine11.index('fives_root = (')
close_idx = pristine11.index('\n)', idx)
src11 = pristine11[:close_idx] + guard11 + pristine11[close_idx:]
set_src(11, src11)
print('cell 11: rebuilt from pristine + guard')

# ---- CELL 13: pristine + skip instead of hard failure ----
old13 = """    if not root.is_dir():
        raise FileNotFoundError(f"پوشهٔ دریافت‌شده پیدا نشد: {root}")"""
new13 = """    if not root.is_dir():
        print(f'{name} در کش موجود نیست؛ ابتدا سلول دانلود kagglehub را اجرا کنید. از این مجموعه عبور می‌شود.')
        continue"""
assert old13 in pristine13, 'cell 13 target not found'
set_src(13, pristine13.replace(old13, new13, 1))
print('cell 13: rebuilt from pristine + skip-guard')

# ---- CELL 33: default True (re-apply if missing) ----
src33 = cell_src(cells[33])
if 'USE_APPENDIX_PROFILE = False' in src33:
    src33 = src33.replace('USE_APPENDIX_PROFILE = False', 'USE_APPENDIX_PROFILE = True', 1)
    cells[33]['source'] = src33.splitlines(keepends=True)
    print('cell 33: default=True set')
else:
    print('cell 33: default already True')

# ---- validate all code cells ----
bad = []
for i, c in enumerate(cells):
    if c['cell_type'] != 'code':
        continue
    try:
        ast.parse(cell_src(c))
    except SyntaxError as e:
        bad.append((i, str(e)))
real_bad = [b for b in bad if b[0] != 1]  # cell 1 = %pip magic (expected)
print('syntax check:', 'OK' if not real_bad else real_bad)

nb_path.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('notebook saved')
