"""Build only manually revised chapters, then atomically publish a new Word file."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from docx.enum.section import WD_SECTION_START
from docx.shared import Cm
from docx_styles import setup, paragraph, markdown, field, element, direction

ROOT = Path(__file__).resolve().parent
TITLE = 'افزایش امنیت و حریم خصوصی در تصاویر پزشکی با استفاده از رمزگذاری و استگانوگرافی مبتنی بر یادگیری عمیق و نظریه آشوب'


def section(doc, fmt=None, start=None, show=True):
    s = doc.add_section(WD_SECTION_START.NEW_PAGE)
    s.footer.is_linked_to_previous = False
    if fmt:
        attrs = {'fmt': fmt}
        if start is not None:
            attrs['start'] = start
        element(s._sectPr, 'pgNumType', **attrs)
    if show:
        p = s.footer.paragraphs[0]; direction(p)
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Cm(0)
        field(p, ' PAGE ')
    return s


def cover(doc, english=False):
    if english:
        rows = ['ISLAMIC AZAD UNIVERSITY', '[Branch]', '[Faculty / Department]', 'Thesis submitted for a Master’s degree in [Field]', 'Enhancing Security and Privacy in Medical Images Using Encryption and Steganography Based on Deep Learning and Chaos Theory', 'Supervisor: [Name]', 'Advisor: [Name, if applicable]', 'Author: [Student name]', '[Season and year of defense]']
    else:
        rows = ['دانشگاه آزاد اسلامی', 'واحد [نام واحد دانشگاهی]', 'دانشکده [نام دانشکده] ـ گروه [نام گروه آموزشی]', 'پایان‌نامه برای دریافت درجه کارشناسی ارشد', 'رشته: [نام رشته] ـ گرایش: [نام گرایش]', 'عنوان', TITLE, 'استاد راهنما: [نام و نام خانوادگی]', 'استاد مشاور: [در صورت وجود]', 'نگارش: [نام و نام خانوادگی دانشجو]', '[فصل و سال دفاع]']
    for row in rows:
        p = paragraph(doc, row, center=True, rtl=not english)
        p.paragraph_format.space_after = Cm(.45)


def build():
    d = setup()
    chapters = sorted((ROOT / 'revised').glob('chapter*.md'))
    cover(d)
    section(d, 'arabicAbjad', 1)
    paragraph(d, 'بسم الله الرحمن الرحیم', center=True)
    d.add_page_break()
    paragraph(d, 'منشور اخلاقی پژوهش', center=True)
    paragraph(d, '[متن و فرم رسمی مصوب واحد دانشگاهی در این صفحه درج شود.]')
    paragraph(d, 'این محل برای فرم رسمی محفوظ است. متن مصوب، تاریخ و امضا پس از تعیین واحد و تأیید پژوهشگر افزوده خواهد شد؛ هیچ تأییدیه یا امضایی در این نسخه درج نشده است.')
    d.add_page_break()
    paragraph(d, 'تعهدنامه اصالت پایان‌نامه', center=True)
    paragraph(d, '[فرم رسمی تعهد اصالت واحد دانشگاهی، نام دانشجو، تاریخ و امضا پس از تکمیل و تأیید پژوهش جایگزین شود.]')
    d.add_page_break(); cover(d)
    d.add_page_break()
    paragraph(d, 'سپاسگزاری', center=True)
    paragraph(d, '[متن شخصی سپاسگزاری پس از تأیید دانشجو درج شود.]')
    d.add_page_break()
    paragraph(d, 'تقدیم', center=True)
    paragraph(d, '[این صفحه اختیاری است و به انتخاب دانشجو تکمیل یا حذف می‌شود.]')
    d.add_page_break()
    paragraph(d, 'یادداشت وضعیت نسخه', center=True)
    paragraph(d, f'نسخه پژوهشی در حال تکمیل؛ {len(chapters)} فصل بازنویسی‌شده از پنج فصل. موضوع و محتوای اصلی از پوشه article_chapters گرفته شده است. بازنویسی برای روانی نثر علمی انجام شده و به معنای تأیید نتایج یا اصالت‌سنجی نیست.')
    paragraph(d, 'فایل‌های اولیه شامل طرح آزمایش‌اند و نتایج عددی روش پیشنهادی را در بر ندارند. بنابراین فصل چهارم طرح ارزیابی است و فصل پنجم نتیجه‌گیری در سطح طراحی؛ این نسخه پایان‌نامه نهایی آماده دفاع نیست.')
    paragraph(d, 'نام واحد، رشته، گرایش، دانشجو و استادان در مدارک مربوط مشخص نشده‌اند. عنوان فرم DOCX بیرون پوشه با عنوان فصل‌ها متفاوت است؛ مطابق درخواست، عنوان فصل‌ها مبنا قرار گرفته است.')
    paragraph(d, 'صفحه‌آرایی موقت بر پایه شیوه‌نامه واحد علوم و تحقیقات، سال ۱۳۹۱، نسخه بازنشرشده انجام شده است: A4، حاشیه راست/بالا/پایین ۳ و چپ ۲ سانتی‌متر، قلم لوتوس ۱۴، فاصله تک‌خط و شماره صفحه در پایین وسط. عبارت فاصله سطر در راهنما ابهام دارد؛ گزینه صریح single مبنا قرار گرفته است. تطبیق با آخرین شیوه‌نامه واحد دانشجو ضروری است.')
    paragraph(d, 'ارجاع‌های علمی در نسخه نهایی این پیش‌نویس به روش نویسنده–سال و فهرست منابع APA تنظیم می‌شوند؛ زیرا فرم پژوهشی موجود APA را درخواست کرده است. این انتخاب لزوماً با روش ترابیان در راهنمای قدیمی یکسان نیست و باید به تأیید واحد برسد.')
    paragraph(d, 'پیوند راهنمای استفاده‌شده:')
    paragraph(d, 'https://dl.heyvagroup.com/admin/Files/upload/97192679آیین%20نامه%20نگارش%20پایان%20نامه%20دانشگاه%20آزاد%20علوم%20تحقیقات.pdf', rtl=False)
    paragraph(d, 'برای نمایش دقیق قلم، B Lotus و Times New Roman باید در سامانه خواننده موجود باشند. برای به‌روزرسانی فهرست، در Word روی فهرست کلیک راست و Update Field / Update entire table را انتخاب کنید.')
    d.add_page_break()
    paragraph(d, 'فهرست مطالب', center=True)
    field(d.add_paragraph(), ' TOC \\o "1-3" \\h \\z \\u ', 'فهرست خودکار: در Word گزینه Update Field را اجرا کنید.')
    if any('جدول ' in f.read_text() for f in chapters):
        d.add_page_break(); paragraph(d, 'فهرست جدول‌ها', center=True)
        for f in chapters:
            for line in f.read_text().splitlines():
                if line.startswith('جدول '):
                    paragraph(d, line)
    section(d, 'decimal', 1)
    front = ROOT / 'abstract_fa.md'
    if front.exists():
        markdown(d, front.read_text())
    else:
        paragraph(d, 'چکیده', 'Heading 1')
        paragraph(d, 'این پژوهش چارچوبی برای حفاظت از تصاویر پزشکی با ترکیب ناحیه‌بندی U-Net، رمزنگاری ابرآشوبی پنج‌بعدی و پنهان‌نگاری مبتنی بر برجستگی بصری پیشنهاد می‌کند. متن حاضر در مرحله تدوین است؛ چکیده کامل پس از بازنویسی فصل‌ها افزوده می‌شود.')
    for chapter in chapters:
        d.add_page_break(); markdown(d, chapter.read_text())
    for name in ['references.md', 'appendices.md', 'abstract_en.md']:
        f = ROOT / name
        if f.exists():
            d.add_page_break(); markdown(d, f.read_text())
    section(d, show=False); cover(d, True)
    d.core_properties.title = TITLE
    d.core_properties.subject = 'پیش‌نویس پژوهشی کارشناسی ارشد؛ فاقد نتایج تجربی نهایی'
    d.core_properties.author = '[نام دانشجو]'
    d.core_properties.language = 'fa-IR'
    now = datetime.now(timezone.utc)
    version = now.strftime('%Y%m%dT%H%M%S%fZ')
    published = ROOT / 'published'; published.mkdir(exist_ok=True)
    filename = f'thesis-{version}.docx'
    temporary = published / f'.{filename}.tmp'
    d.save(temporary); os.replace(temporary, published / filename)
    info = {'version': version, 'filename': filename, 'chapters': len(chapters), 'updated_at': now.isoformat(), 'status': 'draft_without_experimental_results'}
    temp = published / '.latest.json.tmp'; temp.write_text(json.dumps(info, ensure_ascii=False, indent=2))
    os.replace(temp, published / 'latest.json')
    print(json.dumps(info, ensure_ascii=False))


if __name__ == '__main__':
    build()