"""Cumulative Persian Word change log, refreshed after every chapter."""
import json
import re
from pathlib import Path
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Mm
from editorial import EVENTS


def safe(text):
    return ''.join(f'[U+{ord(c):04X}]' if ord(c) < 32 and c not in '\n\r' else c for c in str(text))


def paragraph(document, text, style=None):
    p = document.add_paragraph(safe(text), style=style)
    bidi = OxmlElement('w:bidi')
    p._p.get_or_add_pPr().append(bidi)
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(12)
        fonts = run._element.get_or_add_rPr().get_or_add_rFonts()
        fonts.set(qn('w:cs'), 'B Nazanin')
        size = OxmlElement('w:szCs')
        size.set(qn('w:val'), '28')
        run._element.rPr.append(size)
    return p


def section_for(event):
    match = re.search(r'_Chapter([1-5])\.txt$', event['source'])
    return 'فصل ' + match[1].translate(str.maketrans('12345', '۱۲۳۴۵')) if match else ('پیوست‌ها' if event['source'] == 'Appendices.txt' else 'چکیده‌ها')


def write_revision_log(root, completed=None):
    file = root / 'reports/revision-events.json'
    old = json.loads(file.read_text()) if file.exists() else []
    keyed = {(e['source'], e['line'], e['kind']): e for e in old}
    for e in EVENTS:
        keyed[(e['source'], e['line'], e['kind'])] = e
    events = list(keyed.values())
    file.write_text(json.dumps(events, ensure_ascii=False, indent=2))
    decisions = json.loads((root / 'reports/editorial-decisions.json').read_text())
    document = Document()
    sec = document.sections[0]
    sec.page_width, sec.page_height = Mm(210), Mm(297)
    sec.right_margin, sec.left_margin = Mm(30), Mm(25)
    sec.top_margin = sec.bottom_margin = Mm(25)
    paragraph(document, 'گزارش فصل‌به‌فصل اصلاحات پایان‌نامهٔ لاتک', 'Title')
    paragraph(document, 'برای هر اصلاح: محل، علت، متن قبل و متن بعد. متن ورد و فایل‌های خام sources تغییر نکرده‌اند. شمارهٔ خط به فایل خام مبدأ اشاره دارد؛ محل متن خروجی با توضیح SOURCE در لاتک قابل یافتن است.')
    paragraph(document, 'نویسه‌های خرابِ غیرقابل درج در Word با [U+XXXX] نمایش داده شده‌اند؛ نسخهٔ دقیق قبل و بعد در revision-events.json نیز موجود است. تغییر شمارهٔ شکل/رابطه، نام فایل تصویر را تغییر نمی‌دهد.')
    paragraph(document, f'تعداد تغییرات ثبت‌شده: {len(events)}. اعداد و طراحی‌های نیازمند شواهد تجربی تصحیح حدسی نشده‌اند.')
    for section, choices in decisions.items():
        paragraph(document, section, 'Heading 1')
        selected = [e for e in events if section_for(e) == section]
        for i, event in enumerate(selected, 1):
            paragraph(document, f"اصلاح {i} — {event['source']}، خط {event['line']}", 'Heading 2')
            paragraph(document, 'علت: ' + event['reason'])
            paragraph(document, 'قبل: ' + event['before'])
            paragraph(document, 'بعد: ' + event['after'])
        if section == 'منابع':
            bib = json.loads((root / 'bibliography.json').read_text())
            original = (root / 'sources/Final_Remarks_Chapter5.txt').read_text()
            for entry in bib['entries']:
                previous = next((line for line in original.splitlines() if entry['title'].lower() in line.lower()), 'مدخل مطابق در فهرست قبلی لاتک وجود نداشت یا مشخصات آن ناسازگار بود.')
                paragraph(document, f"منبع ثابت [{entry['number']}] — {entry['key']}", 'Heading 2')
                paragraph(document, 'قبل: ' + previous)
                paragraph(document, 'بعد: ' + entry['authors'] + ', "' + entry['title'] + '," ' + entry['journal'] + ', ' + entry['details'] + ', doi: ' + entry['doi'])
                paragraph(document, 'علت و شاهد: ' + entry['evidence'])
            paragraph(document, 'قالب قبل: منابع انگلیسی با اندازهٔ۱۴ و بدون تأکید نام نشریه؛ بعد: Times New Roman۱۲، نام نشریه ایتالیک، عنوان مقاله در گیومه، شماره‌های ثابت به ترتیب اولین ظهور و ارجاع قابل کلیک. مبنا: بند۲۱۵ قالب بیرجند و راهنمایIEEE ضمیمه.')
        paragraph(document, 'تصمیم دربارهٔ موارد اصلاح‌شده یا حفظ‌شده', 'Heading 2')
        for choice in choices:
            paragraph(document, choice['item'], 'Heading 3')
            paragraph(document, 'تصمیم: ' + choice['decision'] + '\nعلت: ' + choice['reason'])
    paragraph(document, 'دریافت فایل‌ها و بازسازی', 'Heading 1')
    paragraph(document, 'قبل: دکمه به انتشار قدیمی Word متصل و در وضعیت فعلی پاسخ۵۰۳ می‌داد. بعد: هر درخواست پوشهٔ فعلی لاتک را درZIPجدید می‌سازد؛ گزارشWordاز مسیر جداگانه قابل دریافت است. هیچZIPقدیمی مبنای دانلود نیست.')
    paragraph(document, 'اصلاحات در tools/editorial.py و فهرست ثابت در bibliography.json ثبت شده‌اند. بازسازی با python tools/build.py آن‌ها را حفظ می‌کند؛ گزارش پس از هر فصل به‌روزرسانی می‌شود.')
    target = root / 'reports/revision-log.docx'
    temporary = target.with_suffix('.tmp.docx')
    document.save(temporary)
    temporary.replace(target)
    if completed:
        # Cumulative checkpoint requested by the author after each chapter.
        checkpoint = root / f'reports/revision-after-chapter{completed:02}.docx'
        checkpoint.write_bytes(target.read_bytes())
    return len(events)