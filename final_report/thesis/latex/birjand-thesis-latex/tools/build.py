"""Rebuild reviewed chapters without modifying any original source files."""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from render import Renderer, inline
from references import build_references
from source_map import source_names, DRAFTS


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def build_chapter(root, number):
    sources = root / 'sources'
    title = (sources / DRAFTS[number]).read_text().split('\n')[0]
    renderer = Renderer(root, sources, number)
    names = source_names(number)
    text = '% !TeX encoding = UTF-8\n% Reviewed conversion; see reports/revision-log.docx and bibliography.json.\n'
    text += r'\SourceChapter{' + str(number) + '}{' + inline(title) + '}\n'
    for name in names:
        text += renderer.convert(name)
    (root / 'chapters' / f'chapter{number:02}.tex').write_text(text, encoding='utf-8')
    wrapper = '\n'.join([r'% !TeX program = xelatex', r'\input{preamble.tex}', r'\begin{document}',
                         r'\pagenumbering{arabic}', r'\input{chapters/chapter' + f'{number:02}' + '.tex}',
                         r'\input{references.tex}', r'\end{document}'])
    (root / f'chapter-{number:02}.tex').write_text(wrapper, encoding='utf-8')
    summary = {'number': number, 'title': title, 'source_count': len(names), 'sources': names,
               'source_hashes': {name: hashlib.sha256((sources / name).read_bytes()).hexdigest() for name in names},
               'images': renderer.images, 'tables': renderer.tables, 'code_blocks': renderer.codes,
               'issues': renderer.issues, 'records': renderer.records,
               'tex_file': f'chapters/chapter{number:02}.tex', 'tex_sha256': hashlib.sha256(text.encode()).hexdigest()}
    save_json(root / 'reports' / f'chapter{number:02}.json', summary)
    report = [f'# گزارش اصلاح {title}', '', f'- فایل خروجی: chapters/chapter{number:02}.tex',
              '- متن خام sources تغییر نکرده است؛ اصلاحات ضروری با اجازهٔ نویسنده انجام شده‌اند.',
              '- قبل، بعد، محل و علت هر تغییر در revision-log.docx و revision-events.json ثبت است.',
              '- شماره‌های شکل/رابطه و ارجاع‌های متنی اصلاح شده‌اند؛ فایل‌های تصویری تغییر نکرده‌اند.',
              '- اعداد و طراحی‌های نیازمند مدرک در editorial-decisions.json مشخص شده‌اند.',
              f'- تعداد تصاویر: {len(renderer.images)}؛ جدول‌های متنی: {len(renderer.tables)}؛ بلوک‌های کد: {len(renderer.codes)}.',
              '', '## فایل‌های مبدأ', *[f'- {name}' for name in names], '', '## تصاویر',
              *[f'- {image["type"]} {image["number"]}: {image["filename"]}' for image in renderer.images]]
    (root / 'reports' / f'chapter{number:02}.md').write_text('\n'.join(report), encoding='utf-8')
    return summary


def publish(root):
    reports = [json.loads(path.read_text()) for n in range(1, 6)
               if (path := root / 'reports' / f'chapter{n:02}.json').exists()]
    lines = [r'% !TeX program = xelatex', r'\input{preamble.tex}', r'\begin{document}',
             r'\input{frontmatter/title-fa.tex}', r'\pagenumbering{harfi}',
             r'\input{frontmatter/forms.tex}', r'\input{frontmatter/abstract-fa.tex}',
             r'\clearpage\tableofcontents', r'\clearpage\listoffigures', r'\clearpage\listoftables',
             r'\clearpage\pagenumbering{arabic}']
    lines += [r'\input{chapters/chapter' + f'{r["number"]:02}' + '.tex}' for r in reports]
    lines += [r'\input{references.tex}', r'\input{appendices.tex}', r'\input{frontmatter/abstract-en.tex}',
              r'\input{frontmatter/title-en.tex}', r'\end{document}']
    (root / 'main.tex').write_text('\n'.join(lines), encoding='utf-8')
    summary = {'status': 'complete' if len(reports) == 5 else 'in_progress',
               'updated_at': datetime.now(timezone.utc).isoformat(),
               'chapters': [{key: r[key] for key in ['number', 'title', 'source_count', 'tex_file']} for r in reports],
               'totals': {'sections': sum(r['source_count'] for r in reports),
                          'image_placements': sum(len(r['images']) for r in reports),
                          'missing_images': sum(not image['exists'] for r in reports for image in r['images']),
                          'tables': sum(len(r['tables']) for r in reports),
                          'code_blocks': sum(len(r['code_blocks']) for r in reports)}}
    save_json(root / 'reports/manifest.json', summary)
    return summary


def issues_report(root):
    decisions = json.loads((root / 'reports/editorial-decisions.json').read_text())
    lines = ['# اصلاحات ضروری و تصمیم‌های باقیمانده', '',
             'فایل‌های خام sources تغییر نکرده‌اند؛ تغییرات خروجی با اجازهٔ نویسنده ثبت شده‌اند.',
             'گزارش کامل قبل/بعد/علت: revision-log.docx؛ جزئیات ماشینی: revision-events.json.', '']
    for section, items in decisions.items():
        lines += ['## ' + section]
        lines += ['- ' + item['item'] + ' — ' + item['decision'] + '؛ ' + item['reason'] for item in items]
    (root / 'reports/source-issues.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--chapter', type=int, choices=range(1, 6))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    from revision_report import write_revision_log
    build_references(root)
    for number in ([args.chapter] if args.chapter else range(1, 6)):
        report = build_chapter(root, number)
        write_revision_log(root, completed=number)
        print(json.dumps({key: report[key] for key in ['number', 'title', 'source_count']}, ensure_ascii=False))
    print(json.dumps(publish(root), ensure_ascii=False))
    issues_report(root)
    if not args.chapter:
        from frontmatter import create
        create(root)
        write_revision_log(root)