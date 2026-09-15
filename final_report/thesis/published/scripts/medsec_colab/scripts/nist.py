"""Bridge to unmodified official STS 2.1.2; all raw outputs retained."""
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
import numpy as np
from scipy.stats import chisquare
from .artifacts import sha256_file, write_json

OFFICIAL_SHA256 = '0238d2f1d26e120e3cc748ed2d4c674cdc636de37fc4027c76cc2a394fff9157'
FAMILIES = ('Frequency BlockFrequency CumulativeSums Runs LongestRun Rank FFT NonOverlappingTemplate '
            'OverlappingTemplate Universal ApproximateEntropy RandomExcursions RandomExcursionsVariant Serial LinearComplexity').split()

def export_streams(runs, output, sequences=100, bits=1000000):
    if sequences < 1 or bits < 8 or bits % 8: raise ValueError('Positive count and byte-aligned bit length required')
    output = Path(output)
    if output.exists(): raise FileExistsError(output)
    needed = bits//8; groups, hashes, pending, origins, collected, membership = set(), set(), bytearray(), [], [], []
    profiles = set(); skipped = []
    for run in map(Path, runs):
        info = json.loads((run/'run.json').read_text())
        profiles.add(json.dumps(info['config'], sort_keys=True))
        if len(profiles) > 1: raise ValueError('Do not pool different cipher configurations into one NIST run')
        for line in (run/'samples.jsonl').read_text().splitlines():
            r = json.loads(line)
            if r['status'] != 'ok': continue
            if len(collected) >= sequences: break
            if r['group_id'] in groups or r['processed_sha256'] in hashes:
                skipped.append({'id': r['id'], 'reason': 'duplicate subject/image'}); continue
            cipher = np.load(run/r['folder']/'cipher.npy', allow_pickle=False)
            if cipher.dtype != np.uint8 or cipher.ndim != 2: raise ValueError('Expected uint8 ciphertext image')
            groups.add(r['group_id']); hashes.add(r['processed_sha256'])
            pending.extend(cipher.tobytes())
            origins.append({'run': str(run.resolve()), 'id': r['id'], 'dataset': r['dataset'], 'group_id': r['group_id'],
                            'cipher_sha256': sha256_file(run/r['folder']/'cipher.npy')})
            if len(pending) >= needed:
                collected.append(bytes(pending[:needed])); membership.append({'sources': origins, 'discarded_bytes': len(pending)-needed})
                pending, origins = bytearray(), []
    if len(collected) != sequences:
        raise ValueError(f'Insufficient distinct-subject ciphertext: {len(collected)}/{sequences} sequences; no padding/repetition allowed')
    output.mkdir(parents=True); (output/'bits.bin').write_bytes(b''.join(collected))
    meta = {'sequences': sequences, 'bits_per_sequence': bits, 'format': 'binary bytes, MSB first',
            'input_sha256': sha256_file(output/'bits.bin'), 'membership': membership, 'skipped': skipped,
            'statistical_independence_proven': False, 'thesis_size': sequences == 100 and bits == 1000000}
    write_json(output/'input.json', meta); return meta

def build_official(archive, output):
    if sha256_file(archive) != OFFICIAL_SHA256: raise ValueError('Archive differs from inspected official STS 2.1.2 release')
    output = Path(output)
    if output.exists(): raise FileExistsError(output)
    output.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            destination = (output/member.filename).resolve()
            if not destination.is_relative_to(output.resolve()): raise ValueError('Unsafe archive entry')
        z.extractall(output)
    roots = list(output.rglob('src/assess.c'))
    if len(roots) != 1: raise ValueError('Unexpected STS layout')
    root = roots[0].parent.parent
    command = ['gcc', '-O2', '-fcommon', '-Iinclude', *[str(p.relative_to(root)) for p in sorted((root/'src').glob('*.c'))], '-lm', '-o', 'assess']
    compiled = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=180)
    (output/'build.log').write_text(compiled.stdout+compiled.stderr)
    if compiled.returncode: raise RuntimeError('STS build failed; see build.log')
    write_json(output/'build.json', {'archive_sha256': OFFICIAL_SHA256, 'command': command,
                                    'assess': str((root/'assess').resolve()), 'source_modified': False})
    return root

def summarize(raw, count):
    result = []
    for family in FAMILIES:
        folder = raw/family
        parts = sorted(folder.glob('data*.txt')) or [folder/'results.txt']
        for part in parts:
            values = np.array([float(x) for x in part.read_text().split()])
            finite = np.isfinite(values) & (values >= 0) & (values <= 1)
            eligible = finite & ((values > 0) if family.startswith('RandomExcursions') else True)
            p = values[eligible]; n = len(p); passed = int(np.sum(p >= .01))
            threshold = .99-3*np.sqrt(.99*.01/n) if n else None
            uniformity = float(chisquare(np.histogram(p, bins=10, range=(0, 1))[0]).pvalue) if n >= 55 else None
            result.append({'family': family, 'component': part.stem, 'raw_p_values': values.tolist(),
                           'raw_count': len(values), 'expected_count': count, 'eligible': n, 'passed': passed,
                           'invalid_p_values': int((~finite).sum()), 'pass_proportion': passed/n if n else None,
                           'lower_proportion_bound': threshold, 'proportion_acceptable': passed/n >= threshold if n else None,
                           'p_value_uniformity': uniformity, 'uniformity_acceptable': uniformity >= .0001 if uniformity is not None else None,
                           'notes': 'Excursion zero placeholders excluded per official STS; inspect stats.txt for cycle eligibility. Uniformity not assessed below 55.'})
    return result

def run_official(sts_root, input_dir, output, timeout=7200, allow_small=False):
    sts_root, input_dir, output = Path(sts_root), Path(input_dir), Path(output)
    meta = json.loads((input_dir/'input.json').read_text()); count, bits = meta['sequences'], meta['bits_per_sequence']
    if (count != 100 or bits != 1000000) and not allow_small: raise ValueError('Thesis run requires 100 x 1,000,000 bits; --allow-small only for software checks')
    data = input_dir/'bits.bin'
    if data.stat().st_size*8 != count*bits or sha256_file(data) != meta['input_sha256']: raise ValueError('NIST input length/hash mismatch')
    if output.exists(): raise FileExistsError(output)
    output.mkdir(parents=True)
    # A fresh working tree prevents stale reports and protects concurrent independent runs.
    shutil.copy2(sts_root/'assess', output/'assess'); shutil.copytree(sts_root/'templates', output/'templates')
    shutil.copy2(data, output/'bits.bin')
    raw = output/'experiments'/'AlgorithmTesting'
    for family in FAMILIES: (raw/family).mkdir(parents=True)
    answers = f'0\nbits.bin\n1\n0\n{count}\n1\n'
    try:
        process = subprocess.run(['./assess', str(bits)], input=answers, cwd=output, capture_output=True, text=True, timeout=timeout)
        (output/'console.log').write_text(process.stdout+process.stderr)
        report = raw/'finalAnalysisReport.txt'
        # Official main returns 1 on success (assess.c line 112).
        if process.returncode not in (0, 1) or not report.is_file() or 'STATISTICAL TEST' not in report.read_text():
            raise RuntimeError('STS failed/incomplete; see console.log')
        for family in FAMILIES:
            if not (raw/family/'results.txt').is_file() or not (raw/family/'results.txt').stat().st_size:
                raise RuntimeError(f'Missing results for {family}')
        rows = summarize(raw, count)
        if any(r['raw_count'] != count for r in rows): raise RuntimeError('Incomplete per-component STS outputs')
        result = {'status': 'executed_not_a_security_certificate', 'source_sha256': OFFICIAL_SHA256,
                  'input': meta, 'families': len(FAMILIES), 'components': rows, 'official_report': str(report),
                  'full_thesis_size': count == 100 and bits == 1000000}
        write_json(output/'summary.json', result); return result
    except Exception as exc:
        write_json(output/'status.json', {'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'})
        raise