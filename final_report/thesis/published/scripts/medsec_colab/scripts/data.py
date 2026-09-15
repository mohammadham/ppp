"""Explicit, subject-split manifests. Never synthesize missing research data."""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from .artifacts import sha256_file

DATASETS = ('DRIVE', 'RITE', 'BraTS2020', 'COVID19_CXR')
REQUIRED = ('id', 'dataset', 'patient_id', 'group_id', 'split', 'image', 'mask', 'source', 'mask_definition')

def load_manifest(path, verify_files=True):
    path = Path(path).resolve()
    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if not records: raise ValueError('Empty manifest; real image/mask files required')
    ids, groups, images, file_hashes = set(), {}, {}, {}
    for r in records:
        if any(not r.get(k) for k in REQUIRED): raise ValueError(f'Missing required fields: {REQUIRED}')
        if r['dataset'] not in DATASETS or r['split'] not in ('train', 'val', 'test'):
            raise ValueError('Unknown dataset/split')
        uid = (r['dataset'], r['id'])
        if uid in ids: raise ValueError(f'Duplicate sample: {uid}')
        ids.add(uid)
        # Both patient and shared cross-dataset groups must stay in one split.
        for key in [('patient', r['dataset'], r['patient_id']), ('group', r['group_id'])]:
            if key in groups and groups[key] != r['split']: raise ValueError(f'Patient/group leakage: {key}')
            groups[key] = r['split']
        if r['dataset'] in ('DRIVE', 'RITE') and not r['group_id'].startswith('retina:'):
            raise ValueError('DRIVE/RITE require common retina:<original-image-id> group IDs')
        for kind in ('image', 'mask'):
            p = Path(r[kind]); p = p if p.is_absolute() else path.parent / p
            r[kind] = str(p.resolve())
            if verify_files:
                if not p.is_file(): raise FileNotFoundError(p)
                key = str(p.resolve())
                if key not in file_hashes: file_hashes[key] = sha256_file(p)
                actual = file_hashes[key]
                if r.get(kind + '_sha256') and r[kind + '_sha256'] != actual:
                    raise ValueError(f'Changed file checksum: {p}')
                r[kind + '_sha256'] = actual
        if verify_files:
            # Entire volumes/images cannot appear across different splits, even with renamed IDs.
            digest = r['image_sha256']
            if digest in images and images[digest] != r['split']: raise ValueError('Image-content leakage across splits')
            images[digest] = r['split']
    return records

def _load_raw(record):
    image_path, mask_path = Path(record['image']), Path(record['mask'])
    if image_path.name.endswith(('.nii', '.nii.gz')):
        import nibabel as nib
        image, mask = nib.load(image_path), nib.load(mask_path)
        if image.shape != mask.shape or not np.allclose(image.affine, mask.affine):
            raise ValueError('NIfTI mask/image geometry mismatch')
        axis, index = int(record['axis']), int(record['slice'])
        if len(image.shape) != 3 or axis not in (0, 1, 2) or not 0 <= index < image.shape[axis]:
            raise ValueError('Explicit valid 3D axis/slice required')
        sel = [slice(None)] * 3; sel[axis] = index
        a, m = np.asarray(image.dataobj[tuple(sel)]), np.asarray(mask.dataobj[tuple(sel)])
        if not np.isfinite(a).all() or not np.isfinite(m).all(): raise ValueError('Nonfinite medical intensities')
        lo, hi = float(a.min()), float(a.max())
        a = np.rint((a-lo)/(hi-lo)*255).astype(np.uint8) if hi > lo else np.zeros(a.shape, np.uint8)
        prep = {'conversion': 'per-slice minmax uint8 (lossy to source)', 'min': lo, 'max': hi}
    else:
        with Image.open(image_path) as im:
            if im.mode not in ('L', 'RGB', 'RGBA', 'P'):
                raise ValueError('Non-8-bit raster: provide documented NIfTI or explicit external conversion')
            a = np.array(im.convert('L'))
        with Image.open(mask_path) as im:
            m = np.array(im.convert('RGB')) if im.mode in ('RGB', 'RGBA', 'P') else np.array(im)
        if m.ndim == 3: m = np.any(m != 0, axis=-1)
        prep = {'conversion': 'Pillow luminance uint8; original color not recoverable'}
    if a.shape != m.shape: raise ValueError('Image/mask pixel dimensions differ')
    return a, m > 0, prep

def load_sample(record, size=None):
    a, m, prep = _load_raw(record)
    prep['original_shape'] = list(a.shape)
    if size:
        if size < 16: raise ValueError('Size must be at least 16')
        a = np.array(Image.fromarray(a).resize((size, size), Image.Resampling.BILINEAR))
        m = np.array(Image.fromarray(m).resize((size, size), Image.Resampling.NEAREST))
    return a, m.astype(bool), {**prep, 'processed_shape': list(a.shape), 'resize': 'bilinear image / nearest mask' if size else None}