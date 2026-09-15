"""Explicit, logged corrections; source manuscripts remain byte-for-byte intact."""
import json
import re
from pathlib import Path
from functools import lru_cache

ROOT = Path(__file__).resolve().parent.parent
EVENTS = []
CONTROL_FIXES = {'\t'+'imes': r'\times', '\t'+'ext': r'\text', '\a'+'pprox': r'\approx',
                 '\a'+'lpha': r'\alpha', '\b'+'mod': r'\bmod', '\f'+'rac': r'\frac'}
EXACT = {
    'Structure_Chapter1.txt': [(' [۱-۱۰]', '', 'حذف سه استناد اضافی از شرح ساختار همین پایان‌نامه؛ در ورد نیز وجود نداشتند.')],
    'Synthesis_Research_Gap_Chapter2.txt': [('افت افت کیفیت', 'افت کیفیت', 'حذف تکرار سهوی واژه.')],
    'Zigzag_DNA_Chapter3.txt': [('مجوار', 'مجاور', 'تصحیح غلط املایی بدون تغییر مفهوم.')],
    'Complexity_Edge_Chapter3.txt': [
        ('پیچیدگی زمانی کل سیستم از مرتبه خطی', 'پیچیدگی زمانی کل سیستم از مرتبه شبه‌خطی', 'تطبیق توصیف با رابطهٔ موجود O(N log N)؛ خود رابطه تغییر نکرد.'),
        ('شبه‌کدهای اجرایی زنجیره پردازشی فرستنده و گیرنده', 'شبه‌کدهای اجرایی زنجیره پردازشی فرستنده', 'بدنهٔ چهار شبه‌کد فقط مسیر فرستنده را پوشش می‌دهد؛ شرح گیرنده در ۳-۲ حفظ شده است.'),
        ('پنهان‌نگاری Saliency فراداده و بازسازی گیرنده', 'پنهان‌نگاری Saliency فراداده', 'حذف عبارت نادرست از عنوان؛ هیچ گام الگوریتمی حذف نشد.')],
    'Methodological_Contributions_Chapter5.txt': [('طبقه بلیت می‌گردند', 'طبقه‌بندی می‌گردند', 'تصحیح خرابی آشکار واژه.')],
    'Final_Remarks_Chapter5.txt': [('در بستر بسترهای', 'در بسترهای', 'حذف تکرار سهوی واژه.')],
    'Addressing_Gaps_Chapter5.txt': [('پرسش‌های اصلی پژوهش (تدوین‌شده در بخش ۱-۳)', 'پرسش‌های اصلی پژوهش (تدوین‌شده در بخش ۱-۴-۱)', 'محل واقعی پرسش‌ها بخش ۱-۴-۱ است؛ ۱-۳ اهداف پژوهش است.')],
    'NIST_Tests_Chapter4.txt': [
        ('صفات و یک‌ها', 'صفرها و یک‌ها', 'اصلاح واژهٔ اشتباه در تعریف توالی دودویی.'),
        ('استاندارد ملی فناوری و استانداردهای ایالات متحده', 'مؤسسه ملی استانداردها و فناوری ایالات متحده', 'نام صحیح NIST.'),
        ('فرضیه صفر پذیرفته شده', 'فرضیه صفر رد نشده', 'قبولی آزمون، اثبات فرض صفر نیست؛ مطابق محدودیت آماری استاندارد NIST.')],
    'Entropy_Histogram_Chapter4.txt': [('فرض صفر ($H_0$) مبنی بر یکنواختی کامل هیستوگرام پذیرفته می‌شود', 'فرض صفر ($H_0$) مبنی بر یکنواختی هیستوگرام رد نمی‌شود', 'تصحیح تفسیر آزمون فرض؛ مقدار آستانه و نتایج دست‌نخورده‌اند.')],
    'English_Abstract.txt': [('segmentates', 'segments', 'اصلاح صرف فعل انگلیسی.'),
        ('brain MRI volumes (BraTS 2020)', 'two-dimensional brain MRI slices (BraTS 2020)', 'تطبیق نوع ورودی با محدودیت صریح فصل پنجم: ارزیابی اسلایس دوبعدی، نه حجم سه‌بعدی.'),
        ('chest X-ray/CT images (COVID-19 CXR)', 'chest X-ray images (COVID-19 CXR)', 'CXR رادیوگرافی قفسه سینه است، نه CT؛ مطابق شرح دادگان.')],
}
FIGURE_MAPS = {
    'Architecture_Dataflow_Chapter3.txt': {'۳-۲': '۳-۳', '۳-۳': '۳-۴'},
    'UNet_KeyGen_Chapter3.txt': {'۳-۴': '۳-۵'}, 'Hyperchaos_5D_Chapter3.txt': {'۳-۵': '۳-۶'},
    'Zigzag_DNA_Chapter3.txt': {'۳-۶': '۳-۷'}, 'Saliency_Steganography_Chapter3.txt': {'۳-۷': '۳-۸'},
    'Complexity_Edge_Chapter3.txt': {'۳-۸': '۳-۹'},
    'Cyber_Attacks_Chapter4.txt': {'۴-۶': '۴-۵'}, 'NIST_Tests_Chapter4.txt': {'۴-۷': '۴-۶'},
    'Comparative_Analysis_Chapter4.txt': {'۴-۸': '۴-۷'}, 'Summary_Chapter4.txt': {'۴-۹': '۴-۸'},
}
GAP_LINKS = {
    'اکثر سامانه‌های رمزشده آشوبی': ' این شکاف مستقیماً با «فرضیه اول پژوهش» (تولید کلید پویا بر پایه استخراج ویژگی‌های آماری ROI شبکه U-Net و تابع هش SHA-256) پاسخ داده می‌شود.',
    'روش‌های پنهان‌نگاری موجود': ' این شکاف مستقیماً با «فرضیه سوم پژوهش» (پنهان‌نگاری فراداده فشرده‌سازی‌شده بیمار بر پایه نقشه برجستگی بصری Saliency Detection در پس‌زمینه بی‌اهمیت تصویر با PSNR > 50 dB و SSIM ~ 1) برطرف می‌شود.',
    'هیچ‌یک از کارهای پیشین': ' این شکاف مستقیماً با «فرضیه دوم پژوهش» (طراحی معماری هیبریدی سبک با شکستن کامل همبستگی پیکسل‌ها و پایداری در برابر تحلیل‌های آماری در بسترهای IoMT) پوشش داده می‌شود.',
}
RELATION_MAPS = {'۳-۰': '۳-۱', '۳-۱': '۳-۲', '۳-۲': '۳-۳', '۳-۳': '۳-۴', '۳-۴': '۳-۵', '۳-۵': '۳-۶',
                 '۵-۰': '۵-۱', '۵-۲': '۵-۲', '۵-۱': '۵-۳', '۵-۳': '۵-۴', '۵-۴': '۵-۵', '۵-۵': '۵-۶', '۵-۶': '۵-۷', '۵-۷': '۵-۸'}
DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
REFERENCE = re.compile(r'(?<![A-Za-z0-9_])\[([0-9۰-۹,، \-–]+)\]')


def record(filename, line, before, after, reason, kind='text'):
    if before != after:
        EVENTS.append({'source': filename, 'line': line, 'before': before, 'after': after,
                       'reason': reason, 'kind': kind})


@lru_cache(maxsize=1)
def bibliography():
    return json.loads((ROOT / 'bibliography.json').read_text())


def remap_citations(filename, text):
    data = bibliography()
    scheme = data['chapter1_original'] if filename.endswith('_Chapter1.txt') else data['other_original']
    numbers = {entry['key']: entry['number'] for entry in data['entries']}
    def replace(match):
        value = match[1].translate(DIGITS)
        old = []
        for part in re.split('[,،]', value):
            nums = [int(x) for x in re.findall(r'\d+', part)]
            if len(nums) == 2 and re.search('[-–]', part):
                old.extend(range(nums[0], nums[1] + 1))
            else:
                old.extend(nums)
        if not old or any(str(x) not in scheme for x in old):
            return match[0]  # e.g. [0, 255], not a bibliography citation
        return ', '.join('[' + str(n) + ']' for n in sorted({numbers[scheme[str(x)]] for x in old}))
    # Mathematical intervals and code are not citations.
    return ''.join(t if i % 2 else REFERENCE.sub(replace, t)
                   for i, t in enumerate(re.split(r'(\$\$.*?\$\$|\$[^$]*\$)', text, flags=re.S)))


def review_text(filename, raw, offset=0):
    lines = raw.split('\n')
    refs = False
    for index, original in enumerate(lines):
        if re.match(r'^(?:فهرست\s+(?:مراجع|منابع)|منابع|مراجع|References)', original):
            refs = True
        if refs:
            continue
        text = original
        reasons = []
        for before, after in CONTROL_FIXES.items():
            if before in text:
                text = text.replace(before, after)
                reasons.append('بازیابی دستور خراب فرمول از توالی escape شناخته‌شده، بدون تغییر عدد یا رابطه.')
        for before, after, reason in EXACT.get(filename, []):
            if before in text:
                text = text.replace(before, after)
                reasons.append(reason)
        if filename in FIGURE_MAPS:
            fixed = re.sub(r'شکل ([۰-۹]+-[۰-۹]+)', lambda m: 'شکل ' + FIGURE_MAPS[filename].get(m[1], m[1]), text)
            if fixed != text:
                reasons.append('شماره‌گذاری یکتا و پیوستهٔ شکل‌ها؛ هم عنوان و هم اشارهٔ متنی اصلاح شد، فایل تصویر تغییر نکرد.')
            text = fixed
        fixed = re.sub(r'رابطه ([۳۵]-[۰-۹]+)', lambda m: 'رابطه ' + RELATION_MAPS.get(m[1], m[1]), text)
        if fixed != text:
            reasons.append('شماره‌گذاری روابط از ۱ و به ترتیب ظهور؛ محتوای علمی و فایل تصویر حفظ شد.')
        text = fixed
        if filename == 'Synthesis_Research_Gap_Chapter2.txt' and text.startswith('[جدول ۲-۱:'):
            text = 'ماتریس مقایسه‌ای کارهای پیشین در جدول ۲-۱ ارائه شده است.'
            reasons.append('حذف درج مجدد همان تصویر جدول ۲-۱؛ ارجاع به جدول قبلی جایگزین شد.')
        if filename == 'Synthesis_Research_Gap_Chapter2.txt':
            for beginning, sentence in GAP_LINKS.items():
                if text.startswith(beginning):
                    text += sentence
                    reasons.append('بازگرداندن جملهٔ حذف‌شدهٔ اتصال شکاف به فرضیه، عیناً از بندهای ۳۴۰، ۳۴۳ و ۳۴۶ ورد؛ افزودن نتیجهٔ تجربی تازه نیست.')
        record(filename, index + offset + 1, original, text, ' '.join(dict.fromkeys(reasons)))
        mapped = text if filename == 'Appendices.txt' else remap_citations(filename, text)
        # Standards must cite the primary standard, not unrelated comparison papers.
        if filename == 'NIST_Tests_Chapter4.txt' and index + offset + 1 in (3, 5, 9):
            mapped = re.sub(r'(?:\[\d+\](?:, )?)+', '[12]', mapped)
        if filename == 'Future_Recommendations_Chapter5.txt' and 'CRYSTALS-Kyber' in mapped:
            mapped = re.sub(r'(?:\[\d+\](?:, )?)+', '[13]', mapped)
        record(filename, index + offset + 1, text, mapped,
               'اتصال ارجاع به هویت ثابت مقاله با لحاظ فهرست مبدأ همان فصل و شمارهٔ نهایی IEEE؛ استنادهای تعریف NIST و پساکوانتومی به استاندارد اصلی هدایت شدند.', 'citation')
        lines[index] = mapped
    return '\n'.join(lines)