# آرشیو سلول‌های دیباگ/تشخیصی نوت‌بوک

این سلول‌ها خروجی‌شان فقط برای عیب‌یابی بود و جزو جریان اصلی پایان‌نامه نیست.
آن‌ها از نوت‌بوک اصلی حذف شدند؛ این فایل نسخهٔ کامل هر سلول را همراه توضیح نگهداری می‌کند.
در صورت نیاز می‌توانید هر سلول را به نوت‌بوک برگردانید.
تاریخ: 1405/06/25 (2026-09-16)


================================================================================
## سلول 27 — code

**هدف:** گزارش منابع اسکریپت (خروجی txt دانلودی) — فقط برای بررسی کد؛ جزو جریان اصلی آموزشی نیست.

```python
from pathlib import Path
import sys
import uuid
from google.colab import files

package = Path(PACKAGE)
parts = [f'DEVICE={DEVICE}\ntorch={torch.__version__}\n']

for name in (
    'install_colab.py', 'training.py', 'model.py',
    'data.py', 'config.py', 'metrics.py', 'experiments.py'
):
    p = package / 'scripts' / name
    text = p.read_text(encoding='utf-8') if p.is_file() else 'MISSING'
    parts.append(f'\n===== scripts/{name} =====\n{text}\n')
    module = sys.modules.get('scripts.' + p.stem)
    if module is not None:
        print('Loaded module:', name, getattr(module, '__file__', None))

profile = Path(PROFILE)
parts.append('\n===== ACTIVE PROFILE =====\n' +
             (profile.read_text(encoding='utf-8')
              if profile.is_file() else 'MISSING'))

report = Path(WORK) / f'debug_sources_{uuid.uuid4().hex[:8]}.txt'
report.write_text('\n'.join(parts), encoding='utf-8')
print('Report saved:', report)
files.download(str(report))
```

================================================================================
## سلول 28 — code

**هدف:** گزارش runtime و نمونه‌های تشخیصی (فایل json دانلودی) — فقط برای عیب‌یابی.

```python
from pathlib import Path
from collections import Counter
import json, hashlib, uuid
import numpy as np
import torch
from google.colab import files
from scripts.data import load_manifest, load_sample
from scripts.model import UNet, segmentation_scores
from scripts.training import loss_function
from scripts.artifacts import sha256_file

report = {
    'device': str(DEVICE), 'torch': str(torch.__version__),
    'cuda_build': torch.version.cuda,
    'run_training': globals().get('RUN_TRAINING'),
    'resume_training': globals().get('RESUME_TRAINING'),
    'samples': [],
}
out = Path(WORK) / f'debug_runtime_{uuid.uuid4().hex[:8]}.json'

try:
    report['active_training'] = json.loads(
        Path(PROFILE).read_text(encoding='utf-8'))['training']
    rows = [r for r in load_manifest(MANIFEST)
            if r['dataset'] == DATASET]
    report['split_counts'] = dict(Counter(r['split'] for r in rows))
    history_path = Path(WEIGHTS) / 'history.json'
    report['history'] = (json.loads(history_path.read_text())
                         if history_path.is_file() else None)

    ckpt_path = next((Path(WEIGHTS) / name
                     for name in ('last.pt', 'best.pt')
                     if (Path(WEIGHTS) / name).is_file()), None)
    report['checkpoint_file'] = ckpt_path.name if ckpt_path else None

    if ckpt_path is None:
        report['status'] = 'no_checkpoint; prediction checks not run'
    else:
        # Only load checkpoints produced by your own trusted training.
        ckpt = torch.load(ckpt_path, map_location='cpu', weights_only=True)
        fingerprint = hashlib.sha256(
            json.dumps(rows, sort_keys=True).encode()).hexdigest()
        if (ckpt['dataset'] != DATASET
                or ckpt['manifest_sha256'] != sha256_file(MANIFEST)
                or ckpt.get('data_fingerprint') != fingerprint):
            raise ValueError('Checkpoint does not match current dataset/manifest')
        if ckpt.get('trained_epochs', 0) < 1:
            raise ValueError('Checkpoint has no completed training epoch')

        report['checkpoint'] = {k: ckpt.get(k) for k in (
            'trained_epochs', 'best', 'best_val_loss', 'stale', 'training')}
        t = ckpt['training']
        net_debug = UNet(t['base_channels']).to(DEVICE)
        net_debug.load_state_dict(ckpt['state_dict'])
        net_debug.eval()

        for split in ('train', 'val'):
            subset = [r for r in rows if r['split'] == split][:2]
            for i, record in enumerate(subset):
                image, mask, _ = load_sample(record, t['size'])
                x = torch.from_numpy(image.astype(np.float32) / 255)[None, None].to(DEVICE)
                y = torch.from_numpy(mask.astype(np.float32))[None, None].to(DEVICE)
                with torch.inference_mode():
                    z = net_debug(x)
                    if not torch.isfinite(z).all():
                        raise ValueError('Nonfinite model logits')
                    p = z.sigmoid()
                    loss = loss_function(z, y)
                    soft = (2 * (p*y).sum() + 1) / (p.sum() + y.sum() + 1)
                binary = (p[0, 0] >= t['threshold']).cpu().numpy()
                report['samples'].append({
                    'split': split, 'sample_index': i,
                    'image_min': float(x.min()), 'image_max': float(x.max()),
                    'target_fraction': float(mask.mean()),
                    'predicted_fraction': float(binary.mean()),
                    'prob_min': float(p.min()), 'prob_mean': float(p.mean()),
                    'prob_max': float(p.max()),
                    'loss': float(loss), 'soft_dice': float(soft),
                    **segmentation_scores(binary, mask),
                })
        del net_debug
        report['status'] = 'ok; limited sample diagnostic, not full evaluation'
except Exception as exc:
    report['status'] = 'error'
    report['error'] = f'{type(exc).__name__}: {exc}'
    raise
finally:
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('Report:', out)
    print('Status:', report.get('status'))
    files.download(str(out))
```

================================================================================
## سلول 30 — code

**هدف:** prediction probe — بارگذاری best/last و چاپ آمار پیش‌بینی روی validation — تشخیصی.

```python
from pathlib import Path
import json, hashlib, uuid
import numpy as np
import torch
from google.colab import files
from scripts.data import load_manifest, load_sample
from scripts.model import UNet, segmentation_scores
from scripts.artifacts import sha256_file

if 'DEBUG_WEIGHTS' not in globals():
    raise RuntimeError('Set DEBUG_WEIGHTS to the printed folder of the 3-epoch run')

folder = Path(DEBUG_WEIGHTS)
rows = [r for r in load_manifest(MANIFEST) if r['dataset'] == DATASET]
val_rows = [r for r in rows if r['split'] == 'val']
if not val_rows:
    raise ValueError('No validation records')
fingerprint = hashlib.sha256(
    json.dumps(rows, sort_keys=True).encode()).hexdigest()
report = {'device': str(DEVICE), 'validation_count': len(val_rows), 'results': []}

for name in ('best.pt', 'last.pt'):
    # Load only checkpoints from your own trusted training run.
    ckpt = torch.load(folder / name, map_location='cpu', weights_only=True)
    if (ckpt['dataset'] != DATASET
            or ckpt['manifest_sha256'] != sha256_file(MANIFEST)
            or ckpt.get('data_fingerprint') != fingerprint):
        raise ValueError('Checkpoint and current data do not match')

    t = ckpt['training']
    net_probe = UNet(t['base_channels']).to(DEVICE)
    net_probe.load_state_dict(ckpt['state_dict'])
    net_probe.eval()

    with torch.inference_mode():
        for i, record in enumerate(val_rows):
            image, mask, _ = load_sample(record, t['size'])
            x = torch.from_numpy(image.astype(np.float32) / 255)[None, None].to(DEVICE)
            logits = net_probe(x)
            if not torch.isfinite(logits).all():
                raise ValueError('Nonfinite logits')
            p = logits.sigmoid()[0, 0].cpu().numpy()
            pred = p >= t['threshold']
            row = {
                'checkpoint': name, 'epoch': ckpt['trained_epochs'],
                'validation_index': i, 'threshold': t['threshold'],
                'target_fraction': float(mask.mean()),
                'predicted_fraction': float(pred.mean()),
                'prob_min': float(p.min()), 'prob_mean': float(p.mean()),
                'prob_max': float(p.max()),
                'soft_dice': float((2*(p*mask).sum()+1) / (p.sum()+mask.sum()+1)),
                **segmentation_scores(pred, mask),
            }
            report['results'].append(row)
            print(json.dumps(row), flush=True)
    del net_probe, ckpt

out = folder / f'prediction_probe_{uuid.uuid4().hex[:8]}.json'
out.write_text(json.dumps(report, indent=2), encoding='utf-8')
files.download(str(out))
```

================================================================================
## سلول 31 — code

**هدف:** located_runs — جستجوی پوشه‌های training_runs در درایو و چاپ تاریخچه‌ها — تشخیصی.

```python
from pathlib import Path
import os, json, uuid
from google.colab import files

roots = {
    Path('/content/drive/MyDrive/Thesis_Research'),
    Path('/content/Thesis_Research'),
}
for value in (globals().get('WORK'), os.environ.get('THESIS_WORKDIR')):
    if isinstance(value, (str, os.PathLike)) and str(value):
        roots.add(Path(value))

report = {
    'drive_available': Path('/content/drive/MyDrive').is_dir(),
    'roots': {str(p): p.is_dir() for p in sorted(roots)},
    'path_variables': {}, 'runs': [], 'diagnostics': [], 'errors': [],
}
histories = set()

# Inspect known run areas, not the entire Drive or medical data folders.
for root in roots:
    for name in ('debug_training', 'training_runs', 'weights'):
        area = root / name
        if area.is_dir():
            histories.update(area.rglob('history.json'))

for name in ('WEIGHTS', 'DEBUG_WEIGHTS', 'NEXT_WEIGHTS', 'next_weights', 'RUN_DIR'):
    value = globals().get(name)
    if isinstance(value, (str, os.PathLike)) and str(value):
        folder = Path(value)
        report['path_variables'][name] = str(folder)
        for path in (folder / 'history.json', folder / 'weights/history.json'):
            if path.is_file():
                histories.add(path)

for history_path in sorted(histories):
    folder = history_path.parent
    try:
        history = json.loads(history_path.read_text(encoding='utf-8'))
        entry = {
            'weights_directory': str(folder),
            'history': history,
            'best_exists': (folder / 'best.pt').is_file(),
            'last_exists': (folder / 'last.pt').is_file(),
            'settings': [],
        }
        for path in (folder / 'provenance.json', folder / 'config.json',
                     folder.parent / 'config.json'):
            if path.is_file():
                try:
                    obj = json.loads(path.read_text(encoding='utf-8'))
                    cfg = obj.get('config', obj)
                    entry['settings'].append({
                        'source': str(path),
                        'training': cfg.get('training'),
                        'seed': cfg.get('seed'),
                        'dataset': obj.get('dataset', cfg.get('dataset')),
                    })
                except Exception as exc:
                    report['errors'].append(f'{path}: {exc}')
        report['runs'].append(entry)
    except Exception as exc:
        report['errors'].append(f'{history_path}: {exc}')

for root in sorted(roots):
    for path in sorted((root / 'checks').glob('DRIVE_diagnostic_*/diagnostic.json')):
        try:
            report['diagnostics'].append({
                'source': str(path),
                'report': json.loads(path.read_text(encoding='utf-8')),
            })
        except Exception as exc:
            report['errors'].append(f'{path}: {exc}')

out = Path('/content') / f'located_runs_{uuid.uuid4().hex[:8]}.json'
out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
print('Drive available:', report['drive_available'])
print('Runs found:', len(report['runs']))
for entry in report['runs']:
    print(entry['weights_directory'], '| history entries:', len(entry['history']))
files.download(str(out))
```

================================================================================
## سلول 36 — code

**هدف:** diagnose_drive (baseline) — پلاط history و محاسبهٔ Dice روی validation — تشخیصی/عیب‌یابی.

```python
import json, hashlib
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import numpy as np
import torch
import matplotlib.pyplot as plt
from scripts.data import load_manifest, load_sample
from scripts.model import UNet, segmentation_scores

# فقط تشخیص؛ وزن‌ها، آستانه، تقسیم داده و کد اصلی تغییر نمی‌کنند.
RUN_TRAINING = RUN_EXPERIMENTS = RUN_NIST = RUN_DELIVERY = False
METHOD_READY = False


def probability_summary(probability, target, threshold):
    if not np.isfinite(probability).all():
        raise ValueError('Nonfinite probabilities')
    if not target.any() or target.all():
        raise ValueError('Empty/full vessel reference mask')

    prediction = probability >= threshold
    return {
        **segmentation_scores(prediction, target),
        'reference_fraction': float(target.mean()),
        'predicted_fraction': float(prediction.mean()),
        'p_min': float(probability.min()),
        'p_max': float(probability.max()),
        'p_mean_vessel': float(probability[target].mean()),
        'p_mean_background': float(probability[~target].mean()),
        'all_foreground_dice': float(
            2 * target.mean() / (1 + target.mean())
        ),
    }


def diagnose_drive(work):
    work = Path(work)
    run = work / 'training_runs/DRIVE_baseline_v1'
    manifest = work / 'manifests/DRIVE_train_val_v1.jsonl'

    cfg = json.loads(
        (run / 'config.json').read_text(encoding='utf-8')
    )
    history = json.loads(
        (run / 'weights/history.json').read_text(encoding='utf-8')
    )
    rows = load_manifest(manifest)

    if (
        any(r['dataset'] != 'DRIVE' for r in rows)
        or Counter(r['split'] for r in rows) != Counter(train=16, val=4)
    ):
        raise ValueError('Expected DRIVE train/validation only')

    validation = [r for r in rows if r['split'] == 'val']
    if {r['id'] for r in validation} != {'21', '26', '31', '36'}:
        raise ValueError('Validation IDs changed')

    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    fingerprint = hashlib.sha256(
        json.dumps(rows, sort_keys=True).encode()
    ).hexdigest()

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print('Diagnostic device:', device, '| Training epochs:', len(history))
    print('Training settings:', cfg['training'])

    size = cfg['training']['size']
    threshold = cfg['training']['threshold']

    # دقیقاً همان پیش‌پردازش زمان آموزش؛ نه مسیر متفاوت Predictor.
    samples = [load_sample(r, size) for r in validation]
    images = np.stack([a for a, _, _ in samples])
    targets = np.stack([m for _, m, _ in samples])
    x = torch.from_numpy(
        images.astype(np.float32) / 255
    )[:, None].to(device)

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = work / 'checks' / f'DRIVE_diagnostic_{stamp}'
    out.mkdir(parents=True, exist_ok=False)

    report = dict(
        purpose='validation diagnostics only; NOT test evaluation',
        device=device,
        threshold=threshold,
        manifest_sha256=digest,
        checkpoints={}
    )

    for name in ('best', 'last'):
        path = run / 'weights' / f'{name}.pt'
        checkpoint = torch.load(
            path, map_location='cpu', weights_only=True
        )

        if (
            checkpoint['dataset'] != 'DRIVE'
            or checkpoint['manifest_sha256'] != digest
            or checkpoint['training'] != cfg['training']
            or checkpoint['data_fingerprint'] != fingerprint
        ):
            raise ValueError(f'Checkpoint/data/config mismatch: {name}')

        epoch = checkpoint['trained_epochs']
        if not 1 <= epoch <= len(history):
            raise ValueError('Checkpoint epoch/history mismatch')

        net = UNet(cfg['training']['base_channels']).to(device)
        net.load_state_dict(checkpoint['state_dict'], strict=True)
        net.eval()

        with torch.inference_mode():
            probabilities = net(x).sigmoid()[:, 0].cpu().numpy()

        if probabilities.shape != targets.shape:
            raise ValueError('Prediction shape mismatch')

        scores = [
            dict(
                id=r['id'],
                **probability_summary(p, m, threshold)
            )
            for r, p, m in zip(validation, probabilities, targets)
        ]

        summary = dict(
            epoch=epoch,
            stale=checkpoint['stale'],
            recorded_val_dice=history[epoch - 1]['val_dice'],
            recomputed_val_dice=float(
                np.mean([s['dice'] for s in scores])
            ),
            checkpoint_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            samples=scores
        )
        report['checkpoints'][name] = summary

        print('\nCHECKPOINT:', name)
        print(json.dumps(summary, ensure_ascii=False, indent=2))

        fig, axes = plt.subplots(4, 4, figsize=(12, 12))
        for i, (r, p, m) in enumerate(
            zip(validation, probabilities, targets)
        ):
            panels = [images[i] / 255.0, m, p, p >= threshold]
            titles = [
                f"Input {r['id']}",
                'Reference',
                'Probability [0,1]',
                f'Mask >= {threshold}'
            ]
            for ax, panel, title in zip(axes[i], panels, titles):
                ax.imshow(panel, cmap='gray', vmin=0, vmax=1)
                ax.set_title(title)
                ax.axis('off')

        fig.suptitle(
            f'{name}.pt | epoch {epoch} | validation at training resolution'
        )
        fig.tight_layout()
        fig.savefig(out / f'{name}_validation.png', dpi=140)
        plt.show()
        plt.close(fig)
        del net, checkpoint

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for phase in ('train', 'val'):
        for ax, metric in zip(axes, ('loss', 'dice')):
            ax.plot(
                [h['epoch'] for h in history],
                [h[f'{phase}_{metric}'] for h in history],
                label=phase
            )
            ax.set_xlabel('Epoch')
            ax.set_title(metric)
            ax.legend()
            ax.grid(alpha=.2)

    fig.tight_layout()
    fig.savefig(out / 'history.png', dpi=140)
    plt.show()
    plt.close(fig)

    (out / 'diagnostic.json').write_text(
        json.dumps(
            report, ensure_ascii=False, indent=2, allow_nan=False
        ),
        encoding='utf-8'
    )
    print('\nDiagnostic report:', out)
    print('آموزش یا تغییر وزن انجام نشد؛ مرحلهٔ ۶ همچنان اجرا نشود.')


if 'WORK' not in globals():
    raise RuntimeError('ابتدا اتصال Drive و تنظیم WORK را برقرار کنید.')

diagnose_drive(globals()['WORK'])
```

================================================================================
## سلول 37 — code

**هدف:** diagnose_drive (patience100) — پلاط history و محاسبهٔ Dice روی validation — تشخیصی/عیب‌یابی.

```python
import json, hashlib
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import numpy as np
import torch
import matplotlib.pyplot as plt
from scripts.data import load_manifest, load_sample
from scripts.model import UNet, segmentation_scores

# فقط تشخیص؛ وزن‌ها، آستانه، تقسیم داده و کد اصلی تغییر نمی‌کنند.
RUN_TRAINING = RUN_EXPERIMENTS = RUN_NIST = RUN_DELIVERY = False
METHOD_READY = False


def probability_summary(probability, target, threshold):
    if not np.isfinite(probability).all():
        raise ValueError('Nonfinite probabilities')
    if not target.any() or target.all():
        raise ValueError('Empty/full vessel reference mask')

    prediction = probability >= threshold
    return {
        **segmentation_scores(prediction, target),
        'reference_fraction': float(target.mean()),
        'predicted_fraction': float(prediction.mean()),
        'p_min': float(probability.min()),
        'p_max': float(probability.max()),
        'p_mean_vessel': float(probability[target].mean()),
        'p_mean_background': float(probability[~target].mean()),
        'all_foreground_dice': float(
            2 * target.mean() / (1 + target.mean())
        ),
    }


def diagnose_drive(work):
    work = Path(work)
    run = work / 'training_runs/DRIVE_patience100_v1'
    manifest = work / 'manifests/DRIVE_train_val_v1.jsonl'

    cfg = json.loads(
        (run / 'config.json').read_text(encoding='utf-8')
    )
    history = json.loads(
        (run / 'weights/history.json').read_text(encoding='utf-8')
    )
    rows = load_manifest(manifest)

    if (
        any(r['dataset'] != 'DRIVE' for r in rows)
        or Counter(r['split'] for r in rows) != Counter(train=16, val=4)
    ):
        raise ValueError('Expected DRIVE train/validation only')

    validation = [r for r in rows if r['split'] == 'val']
    if {r['id'] for r in validation} != {'21', '26', '31', '36'}:
        raise ValueError('Validation IDs changed')

    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    fingerprint = hashlib.sha256(
        json.dumps(rows, sort_keys=True).encode()
    ).hexdigest()

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print('Diagnostic device:', device, '| Training epochs:', len(history))
    print('Training settings:', cfg['training'])

    size = cfg['training']['size']
    threshold = cfg['training']['threshold']

    # دقیقاً همان پیش‌پردازش زمان آموزش؛ نه مسیر متفاوت Predictor.
    samples = [load_sample(r, size) for r in validation]
    images = np.stack([a for a, _, _ in samples])
    targets = np.stack([m for _, m, _ in samples])
    x = torch.from_numpy(
        images.astype(np.float32) / 255
    )[:, None].to(device)

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = work / 'checks' / f'DRIVE_diagnostic_{stamp}'
    out.mkdir(parents=True, exist_ok=False)

    report = dict(
        purpose='validation diagnostics only; NOT test evaluation',
        device=device,
        threshold=threshold,
        manifest_sha256=digest,
        checkpoints={}
    )

    for name in ('best', 'last'):
        path = run / 'weights' / f'{name}.pt'
        checkpoint = torch.load(
            path, map_location='cpu', weights_only=True
        )

        if (
            checkpoint['dataset'] != 'DRIVE'
            or checkpoint['manifest_sha256'] != digest
            or checkpoint['training'] != cfg['training']
            or checkpoint['data_fingerprint'] != fingerprint
        ):
            raise ValueError(f'Checkpoint/data/config mismatch: {name}')

        epoch = checkpoint['trained_epochs']
        if not 1 <= epoch <= len(history):
            raise ValueError('Checkpoint epoch/history mismatch')

        net = UNet(cfg['training']['base_channels']).to(device)
        net.load_state_dict(checkpoint['state_dict'], strict=True)
        net.eval()

        with torch.inference_mode():
            probabilities = net(x).sigmoid()[:, 0].cpu().numpy()

        if probabilities.shape != targets.shape:
            raise ValueError('Prediction shape mismatch')

        scores = [
            dict(
                id=r['id'],
                **probability_summary(p, m, threshold)
            )
            for r, p, m in zip(validation, probabilities, targets)
        ]

        summary = dict(
            epoch=epoch,
            stale=checkpoint['stale'],
            recorded_val_dice=history[epoch - 1]['val_dice'],
            recomputed_val_dice=float(
                np.mean([s['dice'] for s in scores])
            ),
            checkpoint_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            samples=scores
        )
        report['checkpoints'][name] = summary

        print('\nCHECKPOINT:', name)
        print(json.dumps(summary, ensure_ascii=False, indent=2))

        fig, axes = plt.subplots(4, 4, figsize=(12, 12))
        for i, (r, p, m) in enumerate(
            zip(validation, probabilities, targets)
        ):
            panels = [images[i] / 255.0, m, p, p >= threshold]
            titles = [
                f"Input {r['id']}",
                'Reference',
                'Probability [0,1]',
                f'Mask >= {threshold}'
            ]
            for ax, panel, title in zip(axes[i], panels, titles):
                ax.imshow(panel, cmap='gray', vmin=0, vmax=1)
                ax.set_title(title)
                ax.axis('off')

        fig.suptitle(
            f'{name}.pt | epoch {epoch} | validation at training resolution'
        )
        fig.tight_layout()
        fig.savefig(out / f'{name}_validation.png', dpi=140)
        plt.show()
        plt.close(fig)
        del net, checkpoint

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for phase in ('train', 'val'):
        for ax, metric in zip(axes, ('loss', 'dice')):
            ax.plot(
                [h['epoch'] for h in history],
                [h[f'{phase}_{metric}'] for h in history],
                label=phase
            )
            ax.set_xlabel('Epoch')
            ax.set_title(metric)
            ax.legend()
            ax.grid(alpha=.2)

    fig.tight_layout()
    fig.savefig(out / 'history.png', dpi=140)
    plt.show()
    plt.close(fig)

    (out / 'diagnostic.json').write_text(
        json.dumps(
            report, ensure_ascii=False, indent=2, allow_nan=False
        ),
        encoding='utf-8'
    )
    print('\nDiagnostic report:', out)
    print('آموزش یا تغییر وزن انجام نشد؛ مرحلهٔ ۶ همچنان اجرا نشود.')


if 'WORK' not in globals():
    raise RuntimeError('ابتدا اتصال Drive و تنظیم WORK را برقرار کنید.')

diagnose_drive(globals()['WORK'])
```
