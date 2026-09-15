"""Extract provided front matter; do not create thesis narrative."""
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as E
from render import Renderer, inline
from editorial import record


def create(root):
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    abstract=(root/'sources/English_Abstract.txt').read_text().split('\n')
    split=next(i for i,l in enumerate(abstract) if l.startswith('چکیده فارسی'))
    renderer=Renderer(root,root/'sources',0)
    fa=renderer.convert('English_Abstract.txt','\n'.join(abstract[split:]),line_offset=split)
    en=renderer.convert('English_Abstract.txt','\n'.join(abstract[:split]),latin=True)
    (root/'frontmatter/abstract-fa.tex').write_text(r'\clearpage\phantomsection\addcontentsline{toc}{chapter}{چکیده}'+'\n'+fa)
    (root/'frontmatter/abstract-en.tex').write_text(r'\clearpage\begin{latin}'+'\n'+en+'\n'+r'\end{latin}')
    fa_keywords = 'واژه‌های کلیدی: امنیت تصاویر پزشکی، یادگیری عمیق U-Net، آشوب پنج‌بعدی، رمزنگاری DNA، پنهان‌نگاری آگاه به برجستگی، اینترنت اشیای پزشکی و پردازش لبه.'
    fa += '\n' + inline(fa_keywords) + r'\par' + '\n'
    record('English_Abstract.txt', 31, '(کلیدواژهٔ فارسی درج نشده بود)', fa_keywords,
           'افزودن شش کلیدواژهٔ متناظر با موضوعات موجود؛ مطابق بند۵۰قالب بیرجند.')
    old_keywords = abstract[8]
    new_keywords = old_keywords.replace('Internet of Medical Things (IoMT), Edge Computing (NVIDIA Jetson TX2)',
                                        'Internet of Medical Things (IoMT) and Edge Computing (NVIDIA Jetson TX2)')
    en = en.replace(inline(old_keywords, latin=True), inline(new_keywords, latin=True))
    record('English_Abstract.txt', 9, old_keywords, new_keywords,
           'ادغام دو موضوع مرتبط در یک کلیدواژه؛ کاهش تعداد از۷به۶بدون حذف مفهوم، مطابق قالب دانشگاه.')
    (root/'frontmatter/abstract-fa.tex').write_text(r'\clearpage\phantomsection\addcontentsline{toc}{chapter}{چکیده}'+'\n'+fa)
    (root/'frontmatter/abstract-en.tex').write_text(r'\clearpage\begin{latin}'+'\n'+en+'\n'+r'\end{latin}')
    (root/'reports/frontmatter.json').write_text(json.dumps({'source':'English_Abstract.txt','records':renderer.records},ensure_ascii=False,indent=2))
    title=next(l.removeprefix('Title: ') for l in abstract if l.startswith('Title: '))
    encover=[r'\begin{titlepage}\begin{latin}\centering',r'\includegraphics[height=27mm]{template/image14.png}\par',
             'University of Birjand'+r'\par',r'[Department / School]\par\vspace{12mm}',
             r'{\bfseries\Large '+inline(title,latin=True)+r'\par}\vspace{10mm}',
             'A Thesis Submitted in Partial Fulfillment of the Requirement for the Degree of Master of Science in Computer Engineering / Information Security'+r'\par\vspace{10mm}',
             r"[Master's Student]\par\vspace{10mm}",r'Supervisor:\par [Thesis Supervisor]\par\vspace{6mm}',
             r'Advisor:\par [Thesis Advisor]\par\vfill [Month / Year]\end{latin}\end{titlepage}']
    (root/'frontmatter/title-en.tex').write_text('\n'.join(encover))
    appendix=Renderer(root,root/'sources',0)
    (root/'appendices.tex').write_text(r'\clearpage\chapter*{پیوست‌ها}\phantomsection\addcontentsline{toc}{chapter}{پیوست‌ها}'+'\n'+appendix.convert('Appendices.txt'))
    (root/'reports/appendices.json').write_text(json.dumps({'records':appendix.records,'tables':appendix.tables,'code_blocks':appendix.codes},ensure_ascii=False,indent=2))
    with zipfile.ZipFile(root/'template/university-template.docx') as archive:
        xml=E.fromstring(archive.read('word/document.xml'))
        tables=xml.findall('./w:body/w:tbl',ns)[:2]
    forms=[]
    for table in tables:
        forms += [r'\clearpage\begingroup\fontsize{10}{12}\selectfont\setstretch{1}']
        for row in table.findall('w:tr',ns):
            cells=[]
            for cell in row.findall('w:tc',ns):
                paragraphs=[''.join(t.text or '' for t in p.findall('.//w:t',ns)) for p in cell.findall('w:p',ns)]
                cells.append(r'\par '.join(inline(s) for s in paragraphs if s))
            # The template's dummy faculty and student number are not real metadata.
            cells=[c.replace(r'\lr{999999999}',r'\StudentNumber{}').replace('ادبيات و علوم انسانی',r'\FacultyName{}') for c in cells]
            n=len(cells)
            if n>1:
                width=r'\dimexpr(\linewidth-'+str(2*n)+r'\tabcolsep)/'+str(n)+r'\relax'
                forms += [r'\noindent\begin{tabular}{@{}'+('p{'+width+'}')*n+'@{}}', ' & '.join(cells)+r' \\', r'\end{tabular}\par\smallskip']
            elif cells:
                forms += [r'\noindent '+cells[0]+r'\par\smallskip']
        forms.append(r'\endgroup')
    (root/'frontmatter/forms.tex').write_text('\n'.join(forms))


if __name__=='__main__':
    root = Path(__file__).resolve().parent.parent
    create(root)
    from revision_report import write_revision_log
    write_revision_log(root)