"""Unified Colab/CLI entry point. python -m scripts --help"""
import argparse
import json
import os
import secrets
import sys
from pathlib import Path
from .artifacts import clean, environment, write_json
from .data import DATASETS

def parser():
    p = argparse.ArgumentParser(description='Thesis research toolkit / ابزار پژوهشی پایان‌نامه')
    commands = p.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor')
    q = commands.add_parser('prepare')
    q.add_argument('--dataset', required=True, choices=DATASETS); q.add_argument('--root', required=True)
    q.add_argument('--output', required=True); q.add_argument('--source', required=True); q.add_argument('--csv')
    q.add_argument('--seed', type=int, default=2026); q.add_argument('--modalities', nargs='+', default=['flair']); q.add_argument('--stride', type=int, default=1)
    q = commands.add_parser('validate-data'); q.add_argument('--manifest', required=True)
    for name in ('train', 'evaluate', 'run'):
        q = commands.add_parser(name)
        q.add_argument('--manifest', required=True); q.add_argument('--dataset', required=True, choices=DATASETS)
        q.add_argument('--output', required=True); q.add_argument('--device', default='cpu')
        if name != 'evaluate': q.add_argument('--config', required=True)
        if name == 'train': q.add_argument('--resume', action='store_true')
        else: q.add_argument('--checkpoint', required=True)
        if name == 'run':
            q.add_argument('--payload', required=True); q.add_argument('--limit', type=int)
            q.add_argument('--evaluation-size', type=int); q.add_argument('--ablations', action='store_true')
    q = commands.add_parser('lyapunov')
    q.add_argument('--config', required=True); q.add_argument('--digest', required=True); q.add_argument('--output', required=True)
    q.add_argument('--steps', type=int, default=100000); q.add_argument('--qr-interval', type=int, default=10)
    q = commands.add_parser('nist-export'); q.add_argument('--runs', nargs='+', required=True); q.add_argument('--output', required=True)
    q.add_argument('--sequences', type=int, default=100); q.add_argument('--bits', type=int, default=1000000)
    q = commands.add_parser('nist-build'); q.add_argument('--archive', required=True); q.add_argument('--output', required=True)
    q = commands.add_parser('nist-run'); q.add_argument('--sts-root', required=True); q.add_argument('--input', required=True); q.add_argument('--output', required=True)
    q.add_argument('--timeout', type=int, default=7200); q.add_argument('--allow-small', action='store_true')
    q = commands.add_parser('report'); q.add_argument('--run', required=True)
    q = commands.add_parser('keygen'); q.add_argument('--output', required=True)
    q = commands.add_parser('send')
    for field in ('manifest', 'dataset', 'id', 'checkpoint', 'config', 'payload', 'keyfile', 'output'): q.add_argument('--'+field, required=True)
    q.add_argument('--device', default='cpu')
    q = commands.add_parser('receive')
    for field in ('stego', 'sidecar', 'keyfile', 'output'): q.add_argument('--'+field, required=True)
    return p

def delivery(a):
    import numpy as np
    from PIL import Image
    from .transport import send, receive
    out = Path(a.output)
    if out.exists(): raise FileExistsError('Use a new delivery directory')
    secret = Path(a.keyfile).read_bytes()
    if len(secret) != 32: raise ValueError('Secret file must contain exactly 32 bytes')
    if a.command == 'receive':
        with Image.open(a.stego) as im:
            if im.mode != 'L': raise ValueError('Lossless 8-bit grayscale stego required')
            image = np.array(im)
        plain, payload = receive(image, Path(a.sidecar).read_bytes(), secret)
        out.mkdir(parents=True); Image.fromarray(plain).save(out/'recovered.png'); (out/'metadata.bin').write_bytes(payload)
        return {'image': str(out/'recovered.png'), 'metadata': str(out/'metadata.bin'), 'authenticated_recovery': True}
    from .data import load_manifest, load_sample
    from .model import Predictor
    from .config import load_config
    rows = [r for r in load_manifest(a.manifest) if r['dataset'] == a.dataset and r['id'] == a.id]
    if len(rows) != 1: raise ValueError('Sample ID must uniquely match selected dataset')
    predictor = Predictor(a.checkpoint, a.device)
    if predictor.checkpoint['dataset'] != a.dataset: raise ValueError('Checkpoint dataset mismatch')
    image, _, preprocessing = load_sample(rows[0]); cfg = load_config(a.config)
    outcome = send(image, predictor(image), Path(a.payload).read_bytes(), cfg, secret)
    out.mkdir(parents=True); Image.fromarray(outcome['stego']).save(out/'stego.png')
    (out/'recovery.msr').write_bytes(outcome['sidecar'])
    write_json(out/'receipt.json', {'info': outcome['info'], 'preprocessing': preprocessing,
                                   'warning': 'Research extension, NOT a clinically approved or proven-secure cipher'})
    return outcome['info']

def main(argv=None):
    a = parser().parse_args(argv)
    if a.command == 'doctor': return environment()
    if a.command == 'keygen':
        fd = os.open(a.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as f: f.write(secrets.token_bytes(32))
        return {'keyfile': a.output, 'warning': 'Keep separately from stego/sidecar; never upload into reports'}
    if a.command in ('send', 'receive'): return delivery(a)
    if a.command == 'prepare':
        from .prepare import prepare
        return prepare(a.dataset, a.root, a.output, a.source, a.seed, a.csv, a.modalities, a.stride)
    if a.command == 'validate-data':
        from .data import load_manifest, load_sample
        rows = load_manifest(a.manifest)
        for row in rows: load_sample(row)
        return {'validated_samples': len(rows), 'datasets': sorted({r['dataset'] for r in rows})}
    if a.command == 'train':
        from .training import train
        return train(a.manifest, a.dataset, json.loads(Path(a.config).read_text()), a.output, a.device, a.resume)
    if a.command == 'evaluate':
        from .experiments import evaluate_segmentation
        return evaluate_segmentation(a.manifest, a.dataset, a.checkpoint, a.output, a.device)
    if a.command == 'run':
        from .experiments import run
        return run(a.manifest, a.dataset, a.checkpoint, json.loads(Path(a.config).read_text()), a.payload, a.output,
                   a.device, a.limit, a.evaluation_size, a.ablations)
    if a.command == 'lyapunov':
        from .dynamics import lyapunov
        return lyapunov(a.digest, json.loads(Path(a.config).read_text()), a.steps, a.qr_interval, a.output)
    if a.command == 'nist-export':
        from .nist import export_streams
        return export_streams(a.runs, a.output, a.sequences, a.bits)
    if a.command == 'nist-build':
        from .nist import build_official
        return {'sts_root': str(build_official(a.archive, a.output))}
    if a.command == 'nist-run':
        from .nist import run_official
        return run_official(a.sts_root, a.input, a.output, a.timeout, a.allow_small)
    if a.command == 'report':
        from .reporting import make_report
        return make_report(a.run)

if __name__ == '__main__':
    try:
        result = main(); print(json.dumps(clean(result), ensure_ascii=False, indent=2, allow_nan=False))
        if result.get('status') in ('failed', 'blocked', 'completed_with_failures'): sys.exit(2)
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error': f'{type(exc).__name__}: {exc}',
                          **getattr(exc, 'details', {})}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)