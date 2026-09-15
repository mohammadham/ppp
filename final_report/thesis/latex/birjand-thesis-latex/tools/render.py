"""Formatting-only, deterministic conversion with line-by-line provenance."""
import hashlib
import re
import shutil

DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
HEADING = re.compile(r'^([۰-۹0-9]+(?:[-–][۰-۹0-9]+){1,3})[.．]\s*(.+)$')
IMAGE = re.compile(r'^\[(شکل|رابطه|جدول)\s+([^:]+):\s*(.*?)\s+-\s+([^\]]+\.(?:png|jpg|jpeg|webp))\]$')
REF = re.compile(r'^\[([0-9۰-۹]+)\]\s+(.+)$')
REFHEAD = re.compile(r'^(?:فهرست\s+(?:مراجع|منابع)|منابع|مراجع|References)')
ESC = {'\\': r'\textbackslash{}', '{': r'\{', '}': r'\}', '$': r'\$', '&': r'\&', '#': r'\#', '%': r'\%', '_': r'\_', '~': r'\SourceGlyph{007E}', '^': r'\SourceGlyph{005E}', '٪': r'\SourceGlyph{066A}', '\u200f': r'\SourceControl{200F}'}
SYMBOLS = dict(zip('×≈≤≥∞λμσπΔ∈→⊕±∑√≠∂∏αβγθΩ', [r'\times',r'\approx',r'\leq',r'\geq',r'\infty',r'\lambda',r'\mu',r'\sigma',r'\pi',r'\Delta',r'\in',r'\rightarrow',r'\oplus',r'\pm',r'\sum',r'\sqrt{}',r'\neq',r'\partial',r'\prod',r'\alpha',r'\beta',r'\gamma',r'\theta',r'\Omega']))


def escape(text):
    out = []
    for ch in text:
        if ch in ESC:
            out.append(ESC[ch])
        elif ord(ch) < 32 and ch not in '\n\r':
            out.append(r'\SourceControl{' + f'{ord(ch):04X}' + '}')
        elif ch in 'ıχ²³–—…><|•✓':
            out.append(r'\SourceGlyph{' + f'{ord(ch):04X}' + '}')
        elif ch == '-':
            out.append('{-}')
        elif ch in SYMBOLS:
            out.append(r'\ensuremath{' + SYMBOLS[ch] + '}')
        else:
            out.append(ch)
    return ''.join(out)


def prose(text, latin=False):
    if latin:
        # Persian comments/phrases must retain their own direction in LTR blocks.
        return ''.join(r'\rl{' + escape(t) + '}' if re.search('[آ-ی]', t) else escape(t)
                       for t in re.split(r'([\u0600-\u06ff\u200c]+(?:[ \u200c]+[\u0600-\u06ff\u200c]+)*)', text))
    # Include both parentheses/brackets in the same directional span.
    atom = r'A-Za-z0-9\u00c0-\u024f'
    pattern = (r'(\([^()\u0600-\u06ff]*\)|\[[0-9۰-۹,،\s–\-]+\]|[' + atom +
               r'](?:[' + atom + r' _.,:/+%<>=&\-]*[' + atom + r'%])?)')
    return ''.join(r'\lr{' + re.sub(r'[۰-۹]+', lambda m: r'\rl{\persianfont '+m[0]+'}', escape(t)) + '}' if i % 2 else escape(t)
                   for i, t in enumerate(re.split(pattern, text)))


def inline(text, latin=False):
    result = []
    # Bold delimiters and valid math are formatting, not manuscript wording.
    for token in re.split(r'(\$\$.*?\$\$|\$[^$\n]*?\$|\*\*.*?\*\*)', text, flags=re.S):
        if token.startswith('**') and token.endswith('**') and len(token) > 4:
            result.append(r'\textbf{' + inline(token[2:-2], latin) + '}')
        elif token.startswith('$') and token.endswith('$') and len(token) > 1:
            if any(ord(c) < 32 and c not in '\n\r' for c in token):
                result.append(r'\lr{' + escape(token) + '}')
            elif token.startswith('$$'):
                result.append(r'\[' + math_text(token[2:-2]) + r'\]')
            else:
                result.append('$' + math_text(token[1:-1]) + '$')
        else:
            result.append(prose(token, latin))
    return ''.join(result)


def math_text(text):
    text = text.replace(',', r',\allowbreak{}')
    return re.sub(r'[۰-۹]+(?:\.[۰-۹]+)?',
                  lambda m: r'\OriginalMathText{\SourceGlyphFont ' + m[0] + '}', text)


class Renderer:
    def __init__(self, root, source, chapter):
        self.root, self.source, self.chapter = root, source, chapter
        self.records, self.images, self.tables, self.codes, self.issues = [], [], [], [], []

    def emit(self, filename, start, lines, kind, tex):
        raw = '\n'.join(lines)
        self.records.append({'source': filename, 'start': start + 1, 'end': start + len(lines),
                             'kind': kind, 'source_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                             'tex_sha256': hashlib.sha256(tex.encode()).hexdigest()})
        return f'% SOURCE {filename}:{start+1}-{start+len(lines)} [{kind}]\n' + tex + '\n'

    def code(self, lines):
        self.codes.append({'line_count': len(lines)})
        tex = [r'\begin{sourcecode}', r'\begin{LTR}\ttfamily\fontsize{9}{13}\selectfont\raggedright']
        for line in lines:
            spaces = len(line) - len(line.lstrip(' '))
            content = prose(line[spaces:], latin=True)
            # Break opportunities preserve the characters in long code tokens.
            content = content.replace(r'\_', r'\_\allowbreak{}')
            tex.append(r'\CodeLine{' + str(spaces * .5) + '}{' + (content or r'\strut') + '}')
        tex.extend([r'\end{LTR}', r'\end{sourcecode}'])
        return '\n'.join(tex)

    def table(self, lines, caption):
        rows = [[c.strip() for c in l.strip().strip('|').split('|')] for l in lines if l.strip().startswith('|')]
        n = len(rows[0])
        if any(len(row) != n for row in rows):
            raise ValueError('Inconsistent table column count: ' + caption)
        self.tables.append({'caption': caption, 'rows': len(rows), 'columns': n})
        wide = n >= 5 or caption.startswith('جدول ب')
        width = r'\dimexpr(\linewidth-' + str(2*n) + r'\tabcolsep)/' + str(n) + r'\relax'
        tex = [r'\clearpage\begin{landscape}' if wide else r'\par\addvspace{\baselineskip}',
               r'\begingroup\fontsize{12}{15}\selectfont\setlength{\tabcolsep}{4pt}',
               r'\renewcommand{\arraystretch}{1.25}', r'\SourceCaption{lot}{' + inline(caption) + '}',
               r'\begin{NoHyper}\begin{longtable}{@{}' + (r'>{\raggedleft\arraybackslash}p{' + width + '}') * n + '@{}}', r'\toprule']
        for i, row in enumerate(rows):
            tex.append(' & '.join(inline(cell) for cell in row) + r' \\')
            if i == 0:
                tex.extend([r'\midrule\endfirsthead', ' & '.join(inline(cell) for cell in row) + r' \\\midrule\endhead'])
        tex.extend([r'\bottomrule', r'\end{longtable}\end{NoHyper}\endgroup', r'\end{landscape}\clearpage' if wide else r'\par\addvspace{\baselineskip}'])
        return '\n'.join(tex)

    def picture(self, match, original, filename, line):
        kind, number, caption, image = match.groups()
        path = self.source / image
        exists = path.is_file()
        self.images.append({'type': kind, 'number': number, 'caption': caption, 'filename': image,
                            'exists': exists, 'source': filename, 'line': line + 1})
        if not exists:
            self.issues.append({'type': 'missing_image', 'source': filename, 'line': line+1, 'text': original})
            return inline(original)
        shutil.copy2(path, self.root/'figures'/image)
        label = f'{kind} {number}: {caption}'
        mode = {'شکل': 0, 'جدول': 1, 'رابطه': 2}[kind]
        return r'\SourcePicture{' + image + '}{' + inline(label) + '}{' + inline(original) + '}{' + str(mode) + '}'

    def convert(self, filename, text=None, skip_chapter_title=True, latin=False, line_offset=0):
        raw = (self.source/filename).read_bytes().decode('utf-8') if text is None else text
        lines = raw.split('\n')  # splitlines would silently eat damaged \f / \v source characters.
        out, i, in_references = [], 0, False
        while i < len(lines):
            line, start = lines[i], i
            stripped = line.strip(' \r\t')
            heading = HEADING.match(stripped)
            image = IMAGE.match(stripped)
            if REFHEAD.match(stripped):
                in_references = True
            if in_references:
                tex, kind = '', 'reference-moved'
            elif not stripped:
                tex, kind = '', 'spacing'
            elif skip_chapter_title and re.match(r'^فصل\s+(?:اول|دوم|سوم|چهارم|پنجم)\s*:', stripped):
                tex, kind = '', 'chapter-title-in-wrapper'
            elif stripped.startswith('جدول ') and re.match(r'^جدول\s+[^:]+:', stripped):
                j = i + 1
                while j < len(lines) and not lines[j].strip(): j += 1
                if j < len(lines) and lines[j].startswith('+'):
                    k = j
                    while k < len(lines) and lines[k].startswith(('+','|')): k += 1
                    tex, kind, i = self.table(lines[j:k], stripped), 'table', k - 1
                else:
                    tex, kind = inline(line, latin)+r'\par', 'paragraph'
            elif stripped.startswith('[شبه‌کد') and i+1 < len(lines) and lines[i+1].startswith('---'):
                j = i+2
                while j < len(lines) and not lines[j].startswith('---'): j += 1
                tex = r'\Needspace{5\baselineskip}\noindent ' + inline(stripped) + r'\par' + self.code(lines[i+2:j])
                kind, i = 'pseudocode', min(j,len(lines)-1)
            elif re.fullmatch('-{6,}', stripped) and i+1 < len(lines) and re.match(r'^(?:import |def |from )',lines[i+1]):
                j = i+1
                while j < len(lines) and not re.match(r'^(?:[۰-۹]+\. |={6,})', lines[j]): j += 1
                tex, kind, i = self.code(lines[i+1:j]), 'python-listing', j-1
            elif image:
                tex, kind = self.picture(image,stripped,filename,i), 'image'
            elif heading:
                level = min(3,len(re.split('[-–]',heading.group(1)))-1)
                tex, kind = r'\SourceHeading{' + str(level) + '}{' + inline(stripped) + '}', 'heading'
            elif stripped.startswith('$$') and not (stripped.endswith('$$') and len(stripped)>4):
                j=i+1
                while j<len(lines) and '$$' not in lines[j]: j+=1
                tex, kind, i = inline('\n'.join(lines[i:j+1]),latin), 'display-math', min(j,len(lines)-1)
            elif re.fullmatch('[=\-]{6,}',stripped):
                tex,kind = r'\par\medskip\hrule\medskip', 'separator'
            elif stripped.startswith('پیوست ') and ':' in stripped:
                tex,kind = r'\clearpage\SourceHeading{1}{'+inline(stripped)+'}', 'appendix-heading'
            else:
                tex,kind = inline(line,latin)+r'\par', 'paragraph'
            used = lines[start:i+1]
            for offset, original in enumerate(used):
                controls = [f'U+{ord(c):04X}' for c in original if ord(c)<32 and c not in '\n\r']
                if controls or re.search(r'\s{2,}(?:imes|ext\{)',original):
                    self.issues.append({'type':'source-control-or-damaged-escape','source':filename,'line':line_offset+start+offset+1,'controls':controls,'text':original})
            out.append(self.emit(filename,start+line_offset,used,kind,tex))
            i += 1
        return '\n'.join(out)