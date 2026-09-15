"""Merge exact source reference entries; never invent a missing reference."""
import hashlib
import json
import re
from render import REF, REFHEAD, DIGITS, inline


def build_references(root):
    source = root/'sources'
    paths = sorted(source.glob('*.txt'))
    preferred = source/'Final_Remarks_Chapter5.txt'
    paths = [preferred] + [p for p in paths if p != preferred]
    unique, entries, occurrences = {}, [], []
    for path in paths:
        in_refs = False
        for index,line in enumerate(path.read_text().split('\n')):
            if REFHEAD.match(line): in_refs = True
            match = REF.match(line) if in_refs else None
            if not match: continue
            original_number, body = match.groups()
            key = re.sub(r'\s+',' ',body).strip()
            if key not in unique:
                unique[key] = len(entries)+1
                entries.append({'number':unique[key],'text':body,'first_source':path.name,'line':index+1})
            occurrences.append({'source':path.name,'line':index+1,'original_number':int(original_number.translate(DIGITS)),
                                'global_number':unique[key], 'text_sha256':hashlib.sha256(body.encode()).hexdigest()})
    tex = [r'\clearpage\chapter*{مراجع}\phantomsection\addcontentsline{toc}{chapter}{مراجع}',
           r'\begin{LTR}\latinfont\fontsize{14}{18}\selectfont',r'\begin{list}{}{\setlength{\leftmargin}{10mm}\setlength{\labelwidth}{8mm}\setlength{\itemsep}{8pt}}']
    for entry in entries:
        tex.append(r'\item[\lr{['+str(entry['number'])+r']}] '+inline(entry['text'],latin=True))
    tex.extend([r'\end{list}',r'\end{LTR}'])
    (root/'references.tex').write_text('\n'.join(tex),encoding='utf-8')
    audit={'unique_count':len(entries),'duplicate_occurrences_removed':len(occurrences)-len(entries),
           'entries':entries,'occurrences':occurrences,
           'numbering_conflicts':[o for o in occurrences if o['original_number']!=o['global_number']],
           'policy':'All in-text citation characters are preserved. Original chapter-1 numbering conflicts are reported, not guessed or renumbered.'}
    (root/'reports/references-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    return audit