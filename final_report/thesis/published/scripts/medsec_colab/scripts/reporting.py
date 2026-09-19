"""Tables from observed records only; reported literature never mixed into measurements."""
import csv
import json
import numbers
import shutil
from pathlib import Path
import numpy as np
from .artifacts import write_json

def flatten(value, prefix=''):
    result = {}
    for key, item in value.items():
        name = f'{prefix}.{key}' if prefix else key
        if isinstance(item, dict): result.update(flatten(item, name))
        elif not isinstance(item, (list, tuple)): result[name] = item
    return result

def csv_rows(path, rows):
    keys = sorted({k for r in rows for k in r})
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys); writer.writeheader(); writer.writerows(rows)

def make_report(run):
    run = Path(run); output = run/'reports'; output.mkdir(exist_ok=True)
    samples_file = run/'samples.jsonl'
    samples = [json.loads(line) for line in samples_file.read_text().splitlines()] if samples_file.exists() else []
    csv_rows(output/'samples.csv', [flatten(r) for r in samples])
    summary = {'attempted': len(samples), 'successful': sum(r['status'] == 'ok' for r in samples), 'metrics': {},
               'reproduced_thesis': False, 'status': json.loads((run/'status.json').read_text())}
    # Each measured field has its own n. A failed payload can still have a valid cipher measurement.
    flat = [flatten(r) for r in samples]
    for key in sorted({k for row in flat for k in row}):
        vals = [r[key] for r in flat if isinstance(r.get(key), numbers.Real) and not isinstance(r.get(key), bool)]
        infinite_count = sum(r.get(key) == 'Infinity' for r in flat)
        if vals:
            summary['metrics'][key] = {'n': len(vals), 'mean': float(np.mean(vals)),
                                       'std': float(np.std(vals, ddof=1)) if len(vals) > 1 else None,
                                       'min': float(np.min(vals)), 'max': float(np.max(vals)),
                                       'infinite_count': infinite_count}
        elif infinite_count:
            summary['metrics'][key] = {'n': 0, 'mean': 'Infinity', 'std': None, 'infinite_count': infinite_count}
    write_json(output/'summary.json', summary)
    for name, pattern in [('differential', None), ('channel', 'sample_*/channel.json'),
                          ('ablations', 'sample_*/ablations.json'), ('keys', 'sample_*/key_sensitivity.json')]:
        rows = []
        if pattern:
            for p in sorted(run.glob(pattern)):
                data = json.loads(p.read_text()); data = data if isinstance(data, list) else [data]
                for r in data: rows.append({'sample_folder': p.parent.name, **flatten(r)})
        elif (run/'differential.jsonl').exists():
            rows = [flatten(json.loads(line)) for line in (run/'differential.jsonl').read_text().splitlines()]
        csv_rows(output/(name+'.csv'), rows)
        if name == 'differential':
            grouped = {}
            for region in ('inside', 'outside'):
                attempted = [r for r in rows if r.get('region') == region]
                valid = [r for r in attempted if r.get('status') == 'ok']
                grouped[region] = {'attempted': len(attempted), 'valid': len(valid), 'failed': len(attempted)-len(valid)}
                for metric in ('npcr', 'uaci'):
                    values = [r[metric] for r in valid]
                    grouped[region][metric+'_mean'] = float(np.mean(values)) if values else None
                    grouped[region][metric+'_std'] = float(np.std(values, ddof=1)) if len(values)>1 else None
                grouped[region]['both_ideal_criteria_pass_count'] = sum(r['npcr_not_below_ideal_at_alpha'] and r['uaci_in_ideal_interval'] for r in valid)
            write_json(output/'differential_summary.json', grouped)
    lines = ['# گزارش اجرای پژوهشی', '', f"نمونه‌های موفق: {summary['successful']} از {summary['attempted']}.",
             'جدول‌ها فقط از فایل‌های همین اجرا ساخته شده‌اند؛ شکست‌ها حذف نشده‌اند.',
             'Infinity یعنی PSNR بی‌نهایت؛ null یعنی تعریف‌نشده. این‌ها با صفر یا ۱۰۰ جایگزین نشده‌اند.',
             'بازیابی دقیق فقط دربارهٔ تصویر خاکستری ۸بیتی ورودی الگوریتم است، نه فایل پزشکی اولیه.',
             'حریم خصوصی/امنیت و اعتبار تشخیصی با این سنجه‌ها اثبات نمی‌شود.', '',
             '| معیار | n | میانگین | انحراف معیار |', '|---|---:|---:|---:|']
    for key, s in summary['metrics'].items():
        mean = f"{s['mean']:.6g}" if isinstance(s['mean'], numbers.Real) else s['mean']
        lines.append(f"| {key} | {s['n']} (∞: {s['infinite_count']}) | {mean} | {s['std']} |")
    (output/'REPORT_FA.md').write_text('\n'.join(lines), encoding='utf-8')
    shutil.copy2(Path(__file__).parent/'literature_reported.csv', output/'literature_reported_NOT_reproduced.csv')
    # Visual evidence generated solely from run arrays; no decorative/example images.
    if any(r['status'] == 'ok' for r in samples):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from PIL import Image
        first = next(r for r in samples if r['status'] == 'ok'); folder = run/first['folder']
        fig, axes = plt.subplots(2, 3, figsize=(12, 7))
        arrays = [np.array(Image.open(folder/'processed.png')), np.load(folder/'cipher.npy', allow_pickle=False),
                  np.array(Image.open(folder/'stego.png'))]
        for col, (title, image) in enumerate(zip(('Processed input', 'Cipher', 'Stego'), arrays)):
            axes[0, col].imshow(image, cmap='gray', vmin=0, vmax=255); axes[0, col].set_title(title); axes[0, col].axis('off')
            axes[1, col].hist(image.ravel(), bins=256, range=(0, 256)); axes[1, col].set_xlabel('8-bit intensity')
        fig.tight_layout(); fig.savefig(output/'observed_images_histograms.png', dpi=140); plt.close(fig)
    return summary