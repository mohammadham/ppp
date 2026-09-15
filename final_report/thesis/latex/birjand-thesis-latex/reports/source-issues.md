# نکات و ابهام‌های مبدأ — خارج از متن پایان‌نامه

این گزارش جزو متن پایان‌نامه نیست. هیچ مورد زیر بدون اجازهٔ کاربر تصحیح نشده است.

## انتخاب نسخه‌ها
- فایل‌های جداگانهٔ بخش‌ها با نام بدون «(1)» بر نسخهٔ کامل فصل اولویت دارند. نسخهٔ کامل فقط عنوان/ساختار و فهرست منابع را تأمین کرده است.
- برای فصل سوم، ساختار ۳-۱ تا ۳-۷ مطابق فایل‌های جداگانه و Chapter3_Full_Completed است؛ بخش‌های اضافی نسخه قدیمی Chapter3_Completed به فصل تحمیل نشده‌اند.
- `Addressing_Gaps_Chapter5 (1).txt`: کاملاً یکسان با فایل بدون پسوند است؛ یک‌بار استفاده شد.
- `Chapter4_Full_Completed (1).txt`: متفاوت است؛ نسخهٔ بدون «(1)» مبناست و هر دو نسخه دست‌نخورده در sources محفوظ‌اند.
- `Stego_Quality_Chapter4 (1).txt`: کاملاً یکسان با فایل بدون پسوند است؛ یک‌بار استفاده شد.
- `Synthesis_Research_Gap_Chapter2 (1).txt`: متفاوت است؛ نسخهٔ بدون «(1)» مبناست و هر دو نسخه دست‌نخورده در sources محفوظ‌اند.
- `UNet_KeyGen_Chapter3 (1).txt`: کاملاً یکسان با فایل بدون پسوند است؛ یک‌بار استفاده شد.
- `eq5_4_clinical_contributions_math (1).png`: کاملاً یکسان با فایل بدون پسوند است؛ یک‌بار استفاده شد.
- `eq5_7_final_takeaway_math (1).png`: کاملاً یکسان با فایل بدون پسوند است؛ یک‌بار استفاده شد.

## منابع
- 10 مدخل یکتا ثبت شد؛ 70 تکرار فهرست‌های منابع وارد فهرست نهایی نشد.
- ترتیب مرجع یکپارچه مطابق Final_Remarks_Chapter5 و فهرست‌های فصل دوم به بعد است؛ متن هر مدخل عین مبدأ است.
- در فهرست نسخه کامل فصل اول، [6]، [8]، [9] و [10] نسبت به فهرست سایر فصل‌ها به مقالات متفاوتی اشاره می‌کنند. متن ارجاع‌های بخش‌های فصل اول تغییر نکرده؛ تعیین نگاشت نهایی نیازمند تأیید نویسنده است.
- شماره‌های ارجاع‌شده بدون مدخل در ورودی‌ها: [11]. منبع جدیدی حدس زده یا ساخته نشده است.
- کلیدهای مدخل‌ها، حذف تکرارها و اختلاف شماره‌ها در references-audit.json ثبت شده‌اند.

## شماره‌گذاری شکل‌ها و تکرار شبه‌کدها
- جدول ۲-۱ برای 2 جایگاه آمده است: Literature_Review_Chapter2.txt, Synthesis_Research_Gap_Chapter2.txt؛ شماره/توضیح تغییر نکرد.
- شکل ۳-۲ برای 2 جایگاه آمده است: Introduction_Chapter3.txt, Architecture_Dataflow_Chapter3.txt؛ شماره/توضیح تغییر نکرد.
- شبه‌کدهای تکرارشده در بخش‌های مستقل و بخش پیچیدگی فصل سوم حذف یا ادغام نشده‌اند، چون حذف متن مجاز نبود.
- تصویرهای رابطه عین فایل تحویلی درج شدند؛ معادلات موجود در تصویر دوباره استخراج یا اصلاح نشده‌اند. بعضی تصویرهای مبدأ مانند eq3_1_sha256_key_gen.png خودشان فرمان‌های خام لاتک دارند؛ این اشکال داخل تصویر بازنویسی نشده است.

## نویسه‌های خراب در مبدأ
برخی فایل‌ها شامل TAB، BEL، BACKSPACE یا FORM FEED در محل فرمان‌های فرمول هستند؛ بعضی فرمان‌ها نیز به صورت imes یا ext درآمده‌اند. رشتهٔ اصلی بدون حدس‌زنی نگه داشته شده و کنترل‌های چاپ‌ناپذیر با [U+....] نشان داده می‌شوند. اصل بایتی در sources موجود است.
- `Literature_Review_Chapter2.txt:15` — source-control-or-damaged-escape; U+0009
- `Architecture_Dataflow_Chapter3.txt:3` — source-control-or-damaged-escape; U+0009
- `Architecture_Dataflow_Chapter3.txt:28` — source-control-or-damaged-escape; U+0009
- `UNet_KeyGen_Chapter3.txt:5` — source-control-or-damaged-escape; U+0009
- `UNet_KeyGen_Chapter3.txt:7` — source-control-or-damaged-escape; U+0009
- `Zigzag_DNA_Chapter3.txt:3` — source-control-or-damaged-escape; U+0007
- `Zigzag_DNA_Chapter3.txt:8` — source-control-or-damaged-escape; U+0009, U+0007
- `Zigzag_DNA_Chapter3.txt:18` — source-control-or-damaged-escape; U+0008
- `Saliency_Steganography_Chapter3.txt:22` — source-control-or-damaged-escape; U+0007
- `Complexity_Edge_Chapter3.txt:90` — source-control-or-damaged-escape; U+0009, U+0009, U+0009
- `Complexity_Edge_Chapter3.txt:91` — source-control-or-damaged-escape; U+0009, U+0009
- `Complexity_Edge_Chapter3.txt:92` — source-control-or-damaged-escape; U+0009, U+0009
- `Complexity_Edge_Chapter3.txt:93` — source-control-or-damaged-escape; U+0009, U+0009, U+0009
- `Complexity_Edge_Chapter3.txt:95` — source-control-or-damaged-escape; U+0009, U+0009, U+0009
- `Complexity_Edge_Chapter3.txt:102` — source-control-or-damaged-escape; U+0009
- `Complexity_Edge_Chapter3.txt:108` — source-control-or-damaged-escape; U+0009, U+0009
- `Entropy_Histogram_Chapter4.txt:5` — source-control-or-damaged-escape; U+000C, U+0007
- `Entropy_Histogram_Chapter4.txt:9` — source-control-or-damaged-escape; U+0007
- `Correlation_Chapter4.txt:3` — source-control-or-damaged-escape; U+0007
- `Correlation_Chapter4.txt:5` — source-control-or-damaged-escape; U+0007
- `Correlation_Chapter4.txt:29` — source-control-or-damaged-escape; U+0009

## اطلاعات تکمیل‌نشده و انطباق قالب
- نام دانشجو، استادان، دانشکده، رشته/گرایش فارسی و تاریخ دفاع ارائه نشده‌اند؛ در metadata.tex به صورت جای تکمیل هستند. اطلاعات نمونهٔ فرم Word اطلاعات واقعی دانشجو نیست.
- عنوان فارسی و انگلیسی و هر دو چکیده از English_Abstract.txt برداشته شدند، بدون ترجمه، خلاصه‌سازی یا ویرایش. چکیده‌های بلند ممکن است بیش از یک صفحه باشند؛ محدودیت یک‌صفحه‌ای قالب با منع تغییر متن تعارض دارد.
- تفاوت مقادیر هندسی داخلی Word و دستورهای متنی، قلم مکمل Lotus/Zar و ترتیب صفحات در template-rules.md توضیح داده شده است.
- انتقال، تأیید علمی نتایج ادعاشده یا اصلاح تناقض‌های عددی متن نیست. داده‌ها و نتایج پژوهشی بازنویسی یا تولید نشده‌اند.