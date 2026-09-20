"""Compile the current manuscript without regenerating or rewriting its content."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def source_hashes(root):
    paths = sorted(root.glob('*.tex'))
    for folder in ('chapters', 'frontmatter', 'figures', 'fonts', 'template'):
        paths += sorted(p for p in (root / folder).rglob('*') if p.is_file())
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def build(root, workdir):
    for tool in ('latexmk', 'xelatex', 'pdfinfo', 'pdffonts'):
        if not shutil.which(tool):
            raise RuntimeError(f'{tool} is missing; see README.md for required TeX packages.')
    workdir.mkdir(parents=True, exist_ok=True)
    before = source_hashes(root)
    command = ['latexmk', '-xelatex', '-interaction=nonstopmode', '-halt-on-error',
               '-file-line-error', f'-outdir={workdir}', 'main.tex']
    with (workdir / 'build-output.log').open('w') as output:
        subprocess.run(command, cwd=root, stdout=output, stderr=subprocess.STDOUT, check=True)
    result = workdir / 'main.pdf'
    details = subprocess.check_output(['pdfinfo', str(result)], text=True)
    pages = int(re.search(r'^Pages:\s+(\d+)', details, re.MULTILINE).group(1))
    if pages < 1 or result.read_bytes()[:5] != b'%PDF-':
        raise RuntimeError('No readable PDF was generated.')
    if before != source_hashes(root):
        raise RuntimeError('Manuscript changed during compilation; run again before publishing.')
    fonts = subprocess.check_output(['pdffonts', str(result)], text=True)
    log = (workdir / 'main.log').read_text(errors='replace')
    warnings = [line.strip() for line in log.splitlines() if any(token in line for token in (
        'Warning:', 'Overfull', 'Underfull', 'Missing character:', 'undefined references', 'undefined citations'))]
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'pdf_file': 'thesis.pdf',
              'scope': 'Current complete manuscript; scientific revisions remain pending.',
              'pages': pages, 'bytes': result.stat().st_size,
              'sha256': hashlib.sha256(result.read_bytes()).hexdigest(),
              'engine': subprocess.check_output(['xelatex', '--version'], text=True).splitlines()[0],
              'source_hashes': before, 'pdfinfo': details, 'fonts': fonts,
              'warnings': warnings, 'command': command}
    temporary = root / 'thesis.pdf.part'
    shutil.copyfile(result, temporary)
    os.replace(temporary, root / 'thesis.pdf')
    report_path = root / 'reports' / 'pdf-build.json'
    temporary_report = report_path.with_suffix('.json.part')
    temporary_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    os.replace(temporary_report, report_path)
    print(json.dumps({key: report[key] for key in ('pdf_file', 'pages', 'bytes', 'sha256')}, indent=2))
    print(f'Build warnings: {len(warnings)}; details: {report_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work-dir', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    workdir = args.work_dir.resolve() if args.work_dir else root.parent / '.pdf-build'
    build(root, workdir)