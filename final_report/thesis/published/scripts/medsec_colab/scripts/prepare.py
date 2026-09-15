"""Native DRIVE/RITE, BraTS2020 import; explicit CSV for ambiguous CXR source."""
import csv
import hashlib
import json
from pathlib import Path
from .data import load_manifest

def group_split(group, seed):
    value = int(hashlib.sha256(f'{seed}:{group}'.encode()).hexdigest()[:8], 16) / 2**32
    return 'train' if value < .7 else 'val' if value < .85 else 'test'

def retinal(root, dataset, source):
    records = []
    for official in ('training', 'test'):
        folder = root / official
        images = sorted((folder / 'images').glob('*'))
        images = [p for p in images if p.suffix.lower() in ('.tif', '.tiff', '.png', '.jpg')]
        for image in images:
            ident = image.stem.split('_')[0]
            if not ident.isdigit(): raise ValueError(f'Cannot infer original DRIVE/RITE ID: {image}')
            ident = f'{int(ident):02d}'
            masks = [p for p in folder.rglob('*') if p.is_file() and p.stem.split('_')[0] == ident
                     and (('1st_manual' in str(p)) if dataset == 'DRIVE' else ('av' in p.parent.name.lower()))]
            if len(masks) != 1: raise ValueError(f'Need exactly one first-observer/AV mask for {image}: {masks}')
            # Official test untouched; same four train IDs held out in both retinal datasets.
            split = 'test' if official == 'test' else 'val' if int(ident) in (21, 26, 31, 36) else 'train'
            records.append(dict(id=ident, dataset=dataset, patient_id=ident, group_id=f'retina:{ident}',
                                split=split, image=str(image.resolve()), mask=str(masks[0].resolve()),
                                source=source, mask_definition='first-observer vessels' if dataset == 'DRIVE' else 'AV nonzero union'))
    return records

def brats(root, source, seed, modalities, stride):
    import nibabel as nib
    records = []
    if stride < 1: raise ValueError('Slice stride must be positive')
    if not set(modalities) <= {'t1', 't1ce', 't2', 'flair'}: raise ValueError('Unknown BraTS modality')
    for seg in sorted(root.rglob('*_seg.nii*')):
        patient = seg.name.split('_seg.nii')[0]; group = f'brats2020:{patient}'
        shape = nib.load(seg).shape
        for modality in modalities:
            image = seg.with_name(seg.name.replace('_seg.nii', f'_{modality}.nii'))
            if not image.is_file(): raise FileNotFoundError(image)
            for index in range(0, shape[2], stride):
                records.append(dict(id=f'{patient}_{modality}_{index:03d}', dataset='BraTS2020', patient_id=patient,
                                    group_id=group, split=group_split(group, seed), image=str(image.resolve()),
                                    mask=str(seg.resolve()), axis=2, slice=index, source=source,
                                    mask_definition='whole tumor: segmentation > 0', modality=modality))
    return records

def prepare(dataset, root, output, source, seed=2026, csv_path=None, modalities=('flair',), stride=1):
    root = Path(root).resolve(); output = Path(output)
    if not root.is_dir() or not source.strip(): raise ValueError('Existing root and documented source required')
    if dataset in ('DRIVE', 'RITE'): rows = retinal(root, dataset, source)
    elif dataset == 'BraTS2020': rows = brats(root, source, seed, modalities, stride)
    else:
        if not csv_path: raise ValueError('CXR source is ambiguous: explicit CSV and masks required')
        with open(csv_path, encoding='utf-8-sig') as f: rows = list(csv.DictReader(f))
        for r in rows:
            r['dataset'] = dataset; r['source'] = source
            r['group_id'] = r.get('group_id') or f'cxr:{r["patient_id"]}'
            r['split'] = r.get('split') or group_split(r['group_id'], seed)
            for k in ('image', 'mask'): r[k] = str((root / r[k]).resolve())
    if not rows: raise ValueError('No real samples found; check native folder layout')
    if output.exists(): raise FileExistsError('Refusing to overwrite a manifest')
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.with_suffix('.staging.jsonl')
    staging.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
    try: verified = load_manifest(staging)
    finally: staging.unlink(missing_ok=True)
    output.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in verified), encoding='utf-8')
    return {'samples': len(rows), 'manifest': str(output), 'split_policy': 'documented implementation choice'}