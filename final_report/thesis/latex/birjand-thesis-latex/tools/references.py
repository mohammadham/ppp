"""Frozen, identity-based IEEE reference list, verified against primary documents."""
import json
from render import inline


def build_references(root):
    data = json.loads((root / 'bibliography.json').read_text())
    entries = data['entries']
    assert [e['number'] for e in entries] == list(range(1, len(entries) + 1))
    assert len({e['key'] for e in entries}) == len(entries)
    lines = [r'\clearpage\chapter*{مراجع}\phantomsection\addcontentsline{toc}{chapter}{مراجع}',
             r'\begin{LTR}\ReferenceLatinFont\fontsize{12}{14.4}\selectfont',
             r'\begin{list}{}{\setlength{\leftmargin}{10mm}\setlength{\labelwidth}{8mm}\setlength{\itemsep}{8pt}}']
    for entry in entries:
        n = str(entry['number'])
        title = entry['title'].replace('2^8', '$2^8$')
        text = inline(entry['authors'] + ', "' + title + '," ', latin=True)
        text += r'\textit{' + inline(entry['journal'], latin=True) + '}, '
        text += inline(entry['details'] + ', doi: ' + entry['doi'] + '.', latin=True)
        lines.append(r'\item[\lr{[' + n + r']}]\hypertarget{ref-' + n + '}{} ' + text)
    lines += [r'\end{list}', r'\end{LTR}']
    (root / 'references.tex').write_text('\n'.join(lines), encoding='utf-8')
    audit = {'unique_count': len(entries), 'entries': entries, 'policy': data['policy'],
             'chapter1_original': data['chapter1_original'], 'other_original': data['other_original']}
    (root / 'reports/references-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2))
    return audit