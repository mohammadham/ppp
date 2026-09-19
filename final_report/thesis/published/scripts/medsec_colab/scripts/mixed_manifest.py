"""Strict CHASE/STARE pairing and deterministic subject-level splits.

Never discover STARE images with *.ppm: that includes .ah/.vk ground truths.
CHASE left/right eyes share a patient. Splits are fixed before model training.
"""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from PIL import Image
import numpy as np
from .artifacts import sha256_file, write_json
from .data import load_manifest


def _index(root, pattern):
    result = {}
    for path in sorted(Path(root).rglob('*')):
        if path.is_file() and re.fullmatch(pattern, path.name, re.IGNORECASE):
            key = path.stem.lower()
            if key in result: raise ValueError(f'Ambiguous duplicate candidate {key}: {result[key]} / {path}')
            result[key] = path.resolve()
    return result


def _record(image, mask, origin):
    with Image.open(image) as im: a = np.array(im.convert('RGB'))
    with Image.open(mask) as im: m = np.array(im.convert('L'))
    if a.shape[:2] != m.shape: raise ValueError(f'Image/mask geometry mismatch: {image}')
    if image == mask or sha256_file(image) == sha256_file(mask): raise ValueError(f'Image is its own mask: {image}')
    if np.unique(a).size <= 2: raise ValueError(f'Binary mask-like input is not a fundus photograph: {image}')
    if not (m > 0).any() or (m > 0).all(): raise ValueError(f'Degenerate vessel mask: {mask}')
    stem = image.stem
    patient = re.sub(r'[LR]$', '', stem, flags=re.IGNORECASE) if origin == 'CHASE_DB1' else stem
    prefix = 'chase' if origin == 'CHASE_DB1' else 'stare'
    return {'id': f'{prefix}_{stem}', 'dataset': 'CHASE_STARE_Merged', 'origin_dataset': origin,
            'patient_id': f'{prefix}_{patient}', 'group_id': f'retina:{prefix}_{patient}',
            'image': str(image), 'mask': str(mask), 'source': f'Kaggle {origin}; exact paths and hashes recorded',
            'mask_definition': 'first-observer vessels (_1stHO)' if origin == 'CHASE_DB1' else 'AH observer vessels (.ah)',
            'image_sha256': sha256_file(image), 'mask_sha256': sha256_file(mask),
            'original_shape': list(m.shape), 'split_policy': 'subject_hash_rank_70_15_15_v1',
            'identity_limitation': 'STARE image ID used as subject proxy; verify external patient metadata' if origin == 'STARE' else 'left/right eyes share subject'}


def build_mixed_manifest(chase_root, stare_root, output, seed=2026):
    records = []
    for root, origin, pattern, suffix in [
        (chase_root, 'CHASE_DB1', r'Image_\d+[LR]\.(jpg|jpeg|png|tif|tiff)', '_1stHO.png'),
        (stare_root, 'STARE', r'im\d+\.(ppm|png|jpg|jpeg|tif|tiff)', '.ah.ppm'),
    ]:
        images = _index(root, pattern)
        if not images: raise ValueError(f'No real fundus images found for {origin} at {root}')
        for image in images.values():
            names = {image.stem.lower()+suffix.lower()}
            if origin == 'STARE': names.add(image.stem.lower()+'.ah.png')
            candidates = [p.resolve() for p in Path(root).rglob('*') if p.is_file() and p.name.lower() in names]
            if len(candidates) != 1: raise ValueError(f'Expected exactly one primary mask for {image}; found {candidates}')
            records.append(_record(image, candidates[0], origin))
    # Stratify by source, but assign all eyes of a subject together; never move single images.
    for origin in ('CHASE_DB1', 'STARE'):
        groups = sorted({r['group_id'] for r in records if r['origin_dataset'] == origin},
                        key=lambda g: hashlib.sha256(f'{seed}:{g}'.encode()).hexdigest())
        if len(groups) < 3: raise ValueError(f'At least three subjects needed for {origin}')
        n_val = max(1, round(len(groups)*.15)); n_test = max(1, round(len(groups)*.15))
        assigned = {g: ('val' if i < n_val else 'test' if i < n_val+n_test else 'train') for i, g in enumerate(groups)}
        for r in records:
            if r['origin_dataset'] == origin: r['split'] = assigned[r['group_id']]
    records.sort(key=lambda r: r['id'])
    text = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True)+'\n' for r in records)
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.read_text(encoding='utf-8') != text:
        raise FileExistsError('Manifest differs; use a new filename and retrain, never silently overwrite splits')
    # Validate in the same directory before publishing an atomic manifest.
    temporary = output.with_suffix(output.suffix+'.tmp')
    try:
        temporary.write_text(text, encoding='utf-8'); load_manifest(temporary); temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    summary = {'samples': len(records), 'subjects': len({r['group_id'] for r in records}),
               'split_counts': dict(Counter(r['split'] for r in records)),
               'source_split_counts': dict(Counter(f"{r['origin_dataset']}:{r['split']}" for r in records)),
               'manifest_sha256': sha256_file(output), 'seed': seed, 'policy': 'subject_hash_rank_70_15_15_v1'}
    write_json(output.with_suffix('.summary.json'), summary)
    return summary