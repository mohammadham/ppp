"""Rebuild selected chapters without modifying any source text files."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from render import Renderer, inline, DIGITS
from references import build_references
from source_map import source_names, DRAFTS


def save_json(path, value):
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def build_chapter(root, number):
    sources = root/'sources'
    title = (sources/DRAFTS[number]).read_text().split('\n')[0]
    renderer = Renderer(root, sources, number)
    names = source_names(number)
    text = '% !TeX encoding = UTF-8\n% Formatting-only conversion; see reports for source provenance.\n'
    text += r'\SourceChapter{'+str(number)+'}{'+inline(title)+'}\n'
    for name in names:
        text += renderer.convert(name)
    (root/'chapters'/f'chapter{number:02}.tex').write_text(text, encoding='utf-8')
    wrapper = '\n'.join([r'% !TeX program = xelatex',r'\input{preamble.tex}',r'\begin{document}',
                          r'\pagenumbering{arabic}',r'\input{chapters/chapter'+f'{number:02}'+'.tex}',
                          r'\input{references.tex}',r'\end{document}'])
    (root/f'chapter-{number:02}.tex').write_text(wrapper, encoding='utf-8')
    summary = {'number': number, 'title':title, 'source_count':len(names), 'sources':names,
               'source_hashes':{name:hashlib.sha256((sources/name).read_bytes()).hexdigest() for name in names},
               'images': renderer.images, 'tables': renderer.tables, 'code_blocks': renderer.codes,
               'issues':renderer.issues, 'records':renderer.records,
               'tex_file':f'chapters/chapter{number:02}.tex', 'tex_sha256':hashlib.sha256(text.encode()).hexdigest()}
    save_json(root/'reports'/f'chapter{number:02}.json', summary)
    md = [f'# گزارش انتقال {title}', '', f'- خروجی فصل: `chapters/chapter{number:02}.tex`',
          f'- ورودی مستقل قابل کامپایل از ریشه پروژه: `chapter-{number:02}.tex`',
          f'- متن اصلی از {len(names)} فایل جداگانه؛ متن نسخه کامل وارد فصل نشده است.',
          '- هیچ بازنویسی، تصحیح املایی، تصحیح علمی یا تغییر اعداد و ارجاع‌ها صورت نگرفته است.',
          '- تغییرات محدود به نشانه‌گذاری لاتک، عنوان‌بندی، نمایش چپ‌به‌راست عبارت‌های لاتین، جدول‌بندی و قالب‌بندی کد است.',
          f'- جای‌گذاری تصاویر/روابط تصویری: {sum(im["exists"] for im in renderer.images)} مورد از {len(renderer.images)} نشانه.',
          f'- جدول متنی تبدیل‌شده به جدول واقعی: {len(renderer.tables)}؛ بلوک کد/شبه‌کد قالب‌بندی‌شده: {len(renderer.codes)}.',
          '- فهرست منابع داخل فایل‌ها به `references.tex` منتقل و منابع تکراری یک‌بار ثبت می‌شوند.',
          '- شماره‌ها و زیرنویس‌های مبدأ عیناً حفظ شده‌اند؛ تصویر مفقود با همان براکت باقی می‌ماند.',
          '', '## فایل‌های بخش‌ها به ترتیب', *[f'{i+1}. `{n}`' for i,n in enumerate(names)], '',
          '## تصاویر', *[f'- {im["type"]} {im["number"]}: `{im["filename"]}` — '+('جای‌گذاری شد' if im['exists'] else 'مفقود؛ براکت حفظ شد') for im in renderer.images], '',
          '## نکات مبدأ', f'- {len(renderer.issues)} محل دارای نویسهٔ کنترلی یا نشانهٔ خراب فرمول ثبت شده است. نویسه‌های غیرقابل چاپ با کد Unicode نمایش می‌یابند؛ متن خام دقیق در `sources/` محفوظ است.',
          '- جزئیات اختلاف نسخه‌ها، شماره‌ها و منابع را در `reports/source-issues.md` بخوانید.',
          '- گزارش ماشینی خط‌به‌خط و SHA-256 فایل مبدأ و خروجی در فایل JSON هم‌نام موجود است.']
    (root/'reports'/f'chapter{number:02}.md').write_text('\n'.join(md),encoding='utf-8')
    return summary


def publish(root):
    reports=[]
    for n in range(1,6):
        p=root/'reports'/f'chapter{n:02}.json'
        if p.exists(): reports.append(json.loads(p.read_text()))
    lines=[r'% !TeX program = xelatex',r'\input{preamble.tex}',r'\begin{document}',
           r'\input{frontmatter/title-fa.tex}',r'\pagenumbering{harfi}',
           r'\input{frontmatter/forms.tex}',r'\input{frontmatter/abstract-fa.tex}',
           r'\clearpage\tableofcontents',r'\clearpage\listoffigures',r'\clearpage\listoftables',
           r'\clearpage\pagenumbering{arabic}']
    lines.extend(r'\input{chapters/chapter'+f'{r["number"]:02}'+'.tex}' for r in reports)
    lines += [r'\input{references.tex}',r'\input{appendices.tex}',r'\input{frontmatter/abstract-en.tex}',
              r'\input{frontmatter/title-en.tex}',r'\end{document}']
    (root/'main.tex').write_text('\n'.join(lines),encoding='utf-8')
    summary={'status':'complete' if len(reports)==5 else 'in_progress','updated_at':datetime.now(timezone.utc).isoformat(),
             'chapters':[{k:r[k] for k in ['number','title','source_count','tex_file']} for r in reports],
             'totals':{'sections':sum(r['source_count'] for r in reports),
                       'image_placements':sum(len(r['images']) for r in reports),
                       'missing_images':sum(not i['exists'] for r in reports for i in r['images']),
                       'tables':sum(len(r['tables']) for r in reports),
                       'code_blocks':sum(len(r['code_blocks']) for r in reports)}}
    save_json(root/'reports/manifest.json',summary)
    return summary


def issues_report(root):
    reports=[json.loads(p.read_text()) for p in sorted((root/'reports').glob('chapter??.json'))]
    refs=json.loads((root/'reports/references-audit.json').read_text())
    selected={s for r in reports for s in r['sources']}
    duplicates=[]
    for path in sorted((root/'sources').glob('* (1).*')):
        base=path.with_name(path.name.replace(' (1)',''))
        duplicates.append(f'- `{path.name}`: '+('کاملاً یکسان با فایل بدون پسوند است؛ یک‌بار استفاده شد.' if path.read_bytes()==base.read_bytes() else 'متفاوت است؛ نسخهٔ بدون «(1)» مبناست و هر دو نسخه دست‌نخورده در sources محفوظ‌اند.'))
    images=[i for r in reports for i in r['images']]
    repeated={}
    for image in images:
        key=(image['type'],image['number'])
        repeated.setdefault(key,[]).append(image)
    used=set()
    for name in selected:
        source_text=(root/'sources'/name).read_text()
        source_text=re.sub(r'\$\$.*?\$\$|\$[^$]*\$', '', source_text, flags=re.S)
        for citation in re.findall(r'(?<![A-Za-z0-9_])\[([0-9۰-۹,،\s\-–]+)\]',source_text):
            # [0, 255] / [0, 1] are numeric intervals, not bibliography citations.
            if '0' in re.findall(r'\d+', citation.translate(DIGITS)):
                continue
            for part in re.split('[,،]',citation.translate(DIGITS)):
                nums=re.findall(r'\d+',part)
                if len(nums)==2 and re.search('[-–]',part): used.update(range(int(nums[0]),int(nums[1])+1))
                else: used.update(map(int,nums))
    missing=sorted(used-set(e['number'] for e in refs['entries']))
    lines=['# نکات و ابهام‌های مبدأ — خارج از متن پایان‌نامه', '',
           'این گزارش جزو متن پایان‌نامه نیست. هیچ مورد زیر بدون اجازهٔ کاربر تصحیح نشده است.', '',
           '## انتخاب نسخه‌ها',
           '- فایل‌های جداگانهٔ بخش‌ها با نام بدون «(1)» بر نسخهٔ کامل فصل اولویت دارند. نسخهٔ کامل فقط عنوان/ساختار و فهرست منابع را تأمین کرده است.',
           '- برای فصل سوم، ساختار ۳-۱ تا ۳-۷ مطابق فایل‌های جداگانه و Chapter3_Full_Completed است؛ بخش‌های اضافی نسخه قدیمی Chapter3_Completed به فصل تحمیل نشده‌اند.',
           *duplicates,'','## منابع',
           f'- {refs["unique_count"]} مدخل یکتا ثبت شد؛ {refs["duplicate_occurrences_removed"]} تکرار فهرست‌های منابع وارد فهرست نهایی نشد.',
           '- ترتیب مرجع یکپارچه مطابق Final_Remarks_Chapter5 و فهرست‌های فصل دوم به بعد است؛ متن هر مدخل عین مبدأ است.',
           '- در فهرست نسخه کامل فصل اول، [6]، [8]، [9] و [10] نسبت به فهرست سایر فصل‌ها به مقالات متفاوتی اشاره می‌کنند. متن ارجاع‌های بخش‌های فصل اول تغییر نکرده؛ تعیین نگاشت نهایی نیازمند تأیید نویسنده است.',
           f'- شماره‌های ارجاع‌شده بدون مدخل در ورودی‌ها: {missing or "هیچ‌کدام"}. منبع جدیدی حدس زده یا ساخته نشده است.',
           '- کلیدهای مدخل‌ها، حذف تکرارها و اختلاف شماره‌ها در references-audit.json ثبت شده‌اند.',
           '', '## شماره‌گذاری شکل‌ها و تکرار شبه‌کدها']
    for (kind,number), group in repeated.items():
        if len(group)>1:
            lines.append(f'- {kind} {number} برای {len(group)} جایگاه آمده است: '+', '.join(i['source'] for i in group)+'؛ شماره/توضیح تغییر نکرد.')
    lines.extend(['- شبه‌کدهای تکرارشده در بخش‌های مستقل و بخش پیچیدگی فصل سوم حذف یا ادغام نشده‌اند، چون حذف متن مجاز نبود.',
                  '- تصویرهای رابطه عین فایل تحویلی درج شدند؛ معادلات موجود در تصویر دوباره استخراج یا اصلاح نشده‌اند. بعضی تصویرهای مبدأ مانند eq3_1_sha256_key_gen.png خودشان فرمان‌های خام لاتک دارند؛ این اشکال داخل تصویر بازنویسی نشده است.',
                  '', '## نویسه‌های خراب در مبدأ',
                  'برخی فایل‌ها شامل TAB، BEL، BACKSPACE یا FORM FEED در محل فرمان‌های فرمول هستند؛ بعضی فرمان‌ها نیز به صورت imes یا ext درآمده‌اند. رشتهٔ اصلی بدون حدس‌زنی نگه داشته شده و کنترل‌های چاپ‌ناپذیر با [U+....] نشان داده می‌شوند. اصل بایتی در sources موجود است.'])
    for r in reports:
        for issue in r['issues']:
            lines.append(f'- `{issue["source"]}:{issue["line"]}` — {issue["type"]}; '+', '.join(issue.get('controls',[])))
    lines += ['', '## اطلاعات تکمیل‌نشده و انطباق قالب',
              '- نام دانشجو، استادان، دانشکده، رشته/گرایش فارسی و تاریخ دفاع ارائه نشده‌اند؛ در metadata.tex به صورت جای تکمیل هستند. اطلاعات نمونهٔ فرم Word اطلاعات واقعی دانشجو نیست.',
              '- عنوان فارسی و انگلیسی و هر دو چکیده از English_Abstract.txt برداشته شدند، بدون ترجمه، خلاصه‌سازی یا ویرایش. چکیده‌های بلند ممکن است بیش از یک صفحه باشند؛ محدودیت یک‌صفحه‌ای قالب با منع تغییر متن تعارض دارد.',
              '- تفاوت مقادیر هندسی داخلی Word و دستورهای متنی، قلم مکمل Lotus/Zar و ترتیب صفحات در template-rules.md توضیح داده شده است.',
              '- انتقال، تأیید علمی نتایج ادعاشده یا اصلاح تناقض‌های عددی متن نیست. داده‌ها و نتایج پژوهشی بازنویسی یا تولید نشده‌اند.']
    (root/'reports/source-issues.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--chapter',type=int,choices=range(1,6))
    args=parser.parse_args()
    root=Path(__file__).resolve().parent.parent
    build_references(root)
    numbers=[args.chapter] if args.chapter else list(range(1,6))
    for n in numbers:
        report=build_chapter(root,n)
        print(json.dumps({k:report[k] for k in ['number','title','source_count']},ensure_ascii=False))
    print(json.dumps(publish(root),ensure_ascii=False))
    issues_report(root)