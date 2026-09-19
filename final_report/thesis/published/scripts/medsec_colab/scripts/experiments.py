"""One shared pipeline; sample-level failures remain in the denominator."""
import json
import hashlib
import secrets
import time
from pathlib import Path
import numpy as np
from PIL import Image
from .artifacts import append_jsonl, environment, sha256_file, write_json
from .attacks import channel_experiments, corrupt, key_experiments, one_pixel_trial
from .chaos import roi_digest, stream
from .cipher import encrypt
from .config import validate
from .data import load_manifest, load_sample
from .metrics import quality, security
from .model import Predictor, segmentation_scores
from .transport import send, send_prepared, receive
from .stego import CapacityError

def sync(device):
    if str(device).startswith('cuda'):
        import torch
        torch.cuda.synchronize()

def ensure_held_out(predictor, records, dataset):
    ckpt = predictor.checkpoint
    if ckpt['dataset'] != dataset: raise ValueError('Checkpoint dataset mismatch; cross-dataset inference must be a separate study')
    seen_groups, seen_images = set(ckpt['seen_groups']), set(ckpt['seen_image_sha256'])
    for r in records:
        if r['group_id'] in seen_groups or r['image_sha256'] in seen_images:
            raise ValueError('Test sample appeared in training/validation checkpoint provenance')

def evaluate_segmentation(manifest, dataset, checkpoint, output, device='cpu'):
    records = [r for r in load_manifest(manifest) if r['dataset'] == dataset and r['split'] == 'test']
    if not records: raise ValueError('No held-out test samples')
    predictor = Predictor(checkpoint, device); ensure_held_out(predictor, records, dataset)
    rows = []
    for r in records:
        image, target, preprocessing = load_sample(r)
        prediction = predictor(image)
        rows.append({'id': r['id'], 'group_id': r['group_id'], 'preprocessing': preprocessing,
                     **segmentation_scores(prediction, target)})
    result = {'dataset': dataset, 'checkpoint_sha256': sha256_file(checkpoint), 'records': rows,
              'mean_dice': float(np.mean([r['dice'] for r in rows])), 'mean_iou': float(np.mean([r['iou'] for r in rows])),
              'empty_target_count': sum(r['target_empty'] for r in rows), 'environment': environment()}
    write_json(output, result); return result

def ablations(image, reference, predicted, payload, cfg, secret):
    for name in ('no_saliency', 'no_zigzag', 'no_dna', 'ground_truth_roi_oracle'):
        alternative = dict(cfg)
        if name != 'ground_truth_roi_oracle': alternative[name] = True
        try:
            outcome = send(image, reference if name == 'ground_truth_roi_oracle' else predicted, payload, alternative, secret)
            recovered, message = receive(outcome['stego'], outcome['sidecar'], secret)
            yield {'ablation': name, 'status': 'ok', 'security': security(outcome['cipher']),
                   'stego_quality': quality(outcome['cipher'], outcome['stego'], outcome['protected']),
                   'recovered': quality(image, recovered), 'message_exact': message == payload, 'info': outcome['info']}
        except Exception as exc:
            yield {'ablation': name, 'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}

def run(manifest, dataset, checkpoint, cfg, payload_path, output, device='cpu', limit=None,
        evaluation_size=None, include_ablations=False):
    output = Path(output)
    if output.exists(): raise FileExistsError('Use a new run directory to avoid mixing results')
    output.mkdir(parents=True)
    provenance = {'environment': environment(), 'config': cfg, 'dataset': dataset,
                  'schema_version': 2,
                  'code_sha256': {p.name: sha256_file(p) for p in sorted(Path(__file__).parent.glob('*.py'))},
                  'profile_warning': 'No claim of reproducing thesis numbers or proving cryptographic/clinical security',
                  'evaluation_size': evaluation_size, 'limit': limit}
    write_json(output/'run.json', provenance)
    try:
        validate(cfg)
        records = [r for r in load_manifest(manifest) if r['dataset'] == dataset and r['split'] == 'test']
        if limit is not None:
            if limit < 1: raise ValueError('Limit must be positive')
            records = records[:limit]
        if not records: raise ValueError('No held-out test samples')
        predictor = Predictor(checkpoint, device); ensure_held_out(predictor, records, dataset)
        payload = Path(payload_path).read_bytes()
        provenance.update({'manifest_sha256': sha256_file(manifest), 'checkpoint_sha256': sha256_file(checkpoint),
                           'payload_sha256': sha256_file(payload_path), 'records': records})
        # Explicit JIT/model warm-up; excluded from sample timings, separately recorded.
        start = time.perf_counter(); stream('12'*32, 1, cfg)
        warm_image, _, _ = load_sample(records[0], evaluation_size); predictor(warm_image); sync(device)
        provenance['warmup_seconds'] = time.perf_counter()-start
        write_json(output/'run.json', provenance)
    except Exception as exc:
        write_json(output/'status.json', {'status': 'blocked', 'error': f'{type(exc).__name__}: {exc}'})
        raise
    secret = secrets.token_bytes(32)  # Ephemeral test secret; not a research key or saved artifact.
    successful, cipher_references, failed, optional_failed = [], [], 0, 0
    for index, r in enumerate(records):
        folder = output/f'sample_{index:05d}'; folder.mkdir()
        row = {'id': r['id'], 'dataset': dataset, 'group_id': r['group_id'], 'folder': folder.name,
               'origin_dataset': r.get('origin_dataset', dataset), 'cipher_status': 'not_run',
               'stage': 'load_preprocess', 'message_exact': None}
        try:
            start = time.perf_counter(); image, target, prep = load_sample(r, evaluation_size)
            row['load_preprocess_seconds'] = time.perf_counter()-start
            row['stage'] = 'segmentation'
            start = time.perf_counter(); roi = predictor(image); sync(device)
            row['inference_seconds'] = time.perf_counter()-start
            row.update({'segmentation': segmentation_scores(roi, target), 'preprocessing': prep})
            Image.fromarray(image).save(folder/'processed.png'); np.save(folder/'roi.npy', roi)
            row['stage'] = 'encryption'
            start = time.perf_counter(); cipher, digest = encrypt(image, roi, cfg)
            cipher_seconds = time.perf_counter()-start
            np.save(folder/'cipher.npy', cipher)
            row.update({'cipher_status': 'ok', 'cipher_seconds': cipher_seconds,
                        'security': security(cipher, cfg['correlation_pairs'], cfg['seed']),
                        'plaintext_security': security(image, cfg['correlation_pairs'], cfg['seed']),
                        'processed_sha256': sha256_file(folder/'processed.png')})
            cipher_references.append((r, folder, digest))
            row['stage'] = 'embedding'
            start = time.perf_counter(); outcome = send_prepared(image, roi, payload, cfg, secret, cipher, digest, cipher_seconds)
            row['sender_seconds_excluding_io'] = time.perf_counter()-start + cipher_seconds + row['inference_seconds']
            row['stage'] = 'receiving'
            start = time.perf_counter(); recovered, message = receive(outcome['stego'], outcome['sidecar'], secret)
            row['receiver_seconds'] = time.perf_counter()-start
            if not np.array_equal(image, recovered) or message != payload: raise AssertionError('Roundtrip mismatch')
            Image.fromarray(outcome['stego']).save(folder/'stego.png')
            Image.fromarray(recovered).save(folder/'recovered.png')
            (folder/'recovered_payload.bin').write_bytes(message)
            row.update({'status': 'ok', 'stage': 'complete',
                        'stego_quality': quality(cipher, outcome['stego'], outcome['protected']),
                        'recovery_quality': quality(image, recovered, roi), 'message_exact': message == payload,
                        'payload_sha256': hashlib.sha256(payload).hexdigest(),
                        'recovered_payload_sha256': hashlib.sha256(message).hexdigest(),
                        'payload_ber': float(np.count_nonzero(np.unpackbits(np.frombuffer(payload, np.uint8)) !=
                                                            np.unpackbits(np.frombuffer(message, np.uint8))) / (8*len(payload))) if payload else 0.,
                        'transport': outcome['info'], 'processed_sha256': sha256_file(folder/'processed.png')})
            # Save success immediately: later optional experiments cannot erase successful evidence.
            write_json(folder/'result.json', row)
            successful.append((r, folder, digest))
            damaged = corrupt(outcome['stego'], 'salt_pepper', .1, np.random.default_rng(cfg['seed']+index))
            try:
                receive(damaged, outcome['sidecar'], secret); rejection = False
            except Exception: rejection = True
            write_json(folder/'authenticated_channel.json', {'tampered_rejected': rejection})
        except Exception as exc:
            failed += 1; row.update({'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'})
            if isinstance(exc, CapacityError): row['capacity'] = exc.details
            write_json(folder/'result.json', row)
        # Security experiments are independent of steganographic payload capacity.
        if row['cipher_status'] == 'ok':
            try:
                write_json(folder/'key_sensitivity.json', key_experiments(image, roi, cipher, digest, cfg))
                from .diagnostics import fixed_mask_probes
                write_json(folder/'fixed_mask_diagnostics.json', fixed_mask_probes(image, roi, cfg))
                write_json(folder/'channel.json', list(channel_experiments(image, roi, cipher, digest, cfg, cfg['seed']+index)))
                if include_ablations:
                    results = list(ablations(image, target, roi, payload, cfg, secret))
                    optional_failed += sum(r['status'] == 'failed' for r in results)
                    write_json(folder/'ablations.json', results)
            except Exception as exc:
                optional_failed += 1
                write_json(folder/'optional_failure.json', {'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'})
        append_jsonl(output/'samples.jsonl', row)
    rng = np.random.default_rng(cfg['seed']); trials_ok = 0
    # Exactly configured trials per DATASET, not silently 100 per image.
    for trial in range(cfg['differential_trials']):
        result = {'trial': trial, 'dataset': dataset, 'region': 'inside' if trial % 2 == 0 else 'outside'}
        try:
            if not cipher_references: raise ValueError('No successful reference cipher available')
            # Advance once per inside/outside pair; both regions cover all reference images.
            r, folder, digest = cipher_references[(trial // 2) % len(cipher_references)]
            image = np.array(Image.open(folder/'processed.png')); roi = np.load(folder/'roi.npy', allow_pickle=False)
            cipher = np.load(folder/'cipher.npy', allow_pickle=False)
            result.update({'id': r['id'], **one_pixel_trial(image, roi, cipher, predictor, cfg, rng, result['region'])})
            result['digest_changed'] = result.pop('changed_digest') != digest
            result['status'] = 'ok'; trials_ok += 1
        except Exception as exc: result.update({'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'})
        append_jsonl(output/'differential.jsonl', result)
    status = {'status': 'completed_with_failures' if failed or optional_failed or trials_ok < cfg['differential_trials'] else 'completed',
              'attempted_samples': len(records), 'successful_samples': len(successful), 'failed_samples': failed,
              'successful_ciphers': len(cipher_references),
              'differential_attempted': cfg['differential_trials'], 'differential_successful': trials_ok,
              'optional_failures': optional_failed,
              'full_thesis_reproduction': False}
    write_json(output/'status.json', status)
    return status