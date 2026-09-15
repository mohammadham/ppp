# بستهٔ پژوهشی پایان‌نامه برای Google Colab

## اول این بخش را بخوانید
این بسته اجرای پژوهشی را فراهم می‌کند، نه تأیید نتایج فصل چهارم. `CONFORMANCE_FA.md` مرجع انطباق و `STATUS_FA.md` برنامه/موانع است. دو فایل قدیمی حفظ شده‌اند، اما داخل بستهٔ جدید قابل دریافت نیستند و اجرا نمی‌شوند.

**دو مانع واقعی:** هفت عدد معادلهٔ ۳–۲ نامشخص‌اند؛ پروفایل پیوست دستگاه دیگری است و در بررسی عددی مسیر `digest='12'*32` با ۶۵۵۳۶ نمونه واگرا شد. هر دو واقعیت گزارش می‌شوند، نه اینکه پارامترها برای رسیدن به اعداد مطلوب تنظیم شوند. برای اجرای مرجع باید فایل `thesis_reference.json` را کپی کنید، پارامترهای دارای مرجع معتبر و `parameter_source` را وارد کنید؛ اصل فایل مرجع را حفظ کنید. آموزش U-Net به پارامترهای ODE نیاز ندارد.

**کاربرد بالینی ممنوع:** هستهٔ آشوبی امنیت اثبات‌شده ندارد. زلیب رمزنگاری نیست. AES-GCM فقط فایل کمکی را حفاظت می‌کند. از اطلاعات هویتی/پزشکی واقعی در این محیط پژوهشی استفاده نکنید. فایل راز را جدا نگه دارید. بسته تضمین محرمانگی سامانهٔ تولیدی یا کیفیت تشخیصی ارائه نمی‌دهد.

## شروع در کولب
۱. فایل ZIP بسته را دریافت کنید. نوت‌بوک `Thesis_Colab.ipynb` را از آن بیرون آورده و در Google Colab باز کنید.
۲. برای آموزش، از منوی Runtime نوع GPU را انتخاب کنید (CPU هم ممکن ولی کندتر است). سلول بارگذاری ZIP همان بسته را اجرا کنید.
۳. نصب وابستگی‌ها، اتصال اختیاری Drive و تنظیم مسیرها را به‌ترتیب انجام دهید. داده‌ها از خود شما و پس از رعایت مجوز دریافت می‌شوند؛ هیچ دادهٔ ساختگی جایگزین نمی‌شود.
۴. نوت‌بوک را بخش‌به‌بخش اجرا کنید، نه اجرای کور همهٔ سلول‌ها: در سلول تنظیمات `RUN_TRAINING`، `RUN_EXPERIMENTS` و `RUN_NIST` را فقط بعد از آماده‌کردن ورودی‌های مربوط فعال کنید.
۵. خروجی‌ها را در Drive نگه دارید تا قطع شدن نشست موجب از دست رفتن وزن‌ها و نتایج نشود. نصب NIST به gcc نیاز دارد که در کولب معمولاً موجود است. STS ممکن است طولانی اجرا شود.

## اجرا خارج از کولب
Python 3.10+ و فضای کافی برای PyTorch و داده‌ها لازم است. از پوشهٔ مادر `scripts` اجرا کنید:

```bash
python scripts/install_colab.py
python -m scripts doctor
python -m scripts --help
python -m pytest scripts/tests -q
```

نسخه‌های آزموده‌شدهٔ CPU در `TESTED_ENVIRONMENT.txt` است؛ این فایل دستور نصب CUDA نیست. کولب ممکن است نسخه/سخت‌افزار متفاوت داشته باشد. PyTorch، CUDA و CPU واقعی در هر اجرای پژوهشی ثبت می‌شوند. RK4 و NumPy روی CPU هستند؛ داشتن GPU زمان رمزنگاری زیر سه ثانیه را تضمین نمی‌کند.

## داده و مجوز
- DRIVE: دریافت از وبگاه رسمی چالش با رعایت شرایط آن؛ ساختار `training/images`، `training/1st_manual`، `test/images` و `test/1st_manual`. آزمون رسمی ۲۰ تصویر دست‌نخورده است؛ شناسه‌های ۲۱،۲۶،۳۱،۳۶ از آموزش برای اعتبارسنجی نگه داشته می‌شوند (تصمیم اجرایی).
- RITE: ساختار `training/images` و `training/av` و متناظر test. همهٔ رنگ‌های غیرصفر ماسک A/V به ROI عروق تبدیل می‌شوند. group_idهای DRIVE و RITE باید برای تصویر مشترک یکسان باشند. ادغام مجموعه‌ها بدون کنترل این موضوع مجاز نیست.
- BraTS **2020**: دسترسی مجاز به فایل‌های اصلی `_flair.nii.gz`, `_t1.nii.gz`, `_t1ce.nii.gz`, `_t2.nii.gz`, `_seg.nii.gz` لازم است. تقسیم ۷۰/۱۵/۱۵ با هش گروه بیمار، پیش از اسلایس‌ها است؛ به علت اندازهٔ محدود الزاماً دقیقاً همین نسبت نمونه‌ای نمی‌شود. ماسک >۰، ROI کل تومور است. همهٔ اسلایس‌ها حفظ می‌شوند؛ موارد بدون ROI برای کلیدسازی خطا ثبت می‌کنند. افاین تصویر/ماسک بررسی می‌شود.
- COVID-19 CXR/CT: نام/نسخهٔ دقیق در پایان‌نامه مشخص نیست؛ مجموعهٔ محبوب مشابه را خودکار جایگزین نمی‌کنیم. CSV شامل `id,patient_id,image,mask,mask_definition,split` تهیه کنید. مسیرها نسبت به `--root`، تقسیم از train/val/test و تعریف ماسک باید دقیق باشد. اگر split خالی باشد سیاست گروهی ۷۰/۱۵/۱۵ اعمال می‌شود. برچسب طبقه‌بندی COVID جانشین ماسک قطعه‌بندی نیست؛ ماسک ریه نیز خودکار ماسک ضایعه محسوب نمی‌شود.

نمونهٔ دستورات (مسیر و source را با واقعیت خودتان جایگزین کنید):

```bash
python -m scripts prepare --dataset DRIVE --root DATA/DRIVE --source 'نام نسخه و منشأ واقعی شما' --output data/drive.jsonl
python -m scripts prepare --dataset RITE --root DATA/RITE --source 'نام نسخه و منشأ واقعی شما' --output data/rite.jsonl
python -m scripts prepare --dataset BraTS2020 --root DATA/BraTS2020 --source 'نسخه و مجوز شما' --modalities flair t1 t1ce t2 --stride 1 --output data/brats.jsonl
python -m scripts prepare --dataset COVID19_CXR --root DATA/CXR --source 'شناسه دقیق مجموعه/نسخه' --csv cxr.csv --output data/cxr.jsonl
python -m scripts validate-data --manifest data/drive.jsonl
```

در صورت ساختار متفاوت، manifest JSONL مستقیم با فیلدهای `id,dataset,patient_id,group_id,split,image,mask,source,mask_definition` تهیه کنید. مسیرهای نسبی نسبت به خود manifest هستند. NIfTI به `axis` و `slice` هم نیاز دارد. هش فایل‌ها خودکار محاسبه می‌شود؛ اگر هش موجود باشد تغییر فایل رد می‌شود. تغییر split بدون بازسازی آموزش معتبر نیست. برای بررسی مشترک چند مجموعه، سطرهای JSONL را در manifest ترکیبی قرار دهید و اعتبارسنجی کنید.

## پیش‌پردازش و معنای بازیابی
تصویر رنگی با روشنایی Pillow به خاکستری ۸بیتی تبدیل می‌شود. NIfTI با min/max همان اسلایس به ۸ بیت نگاشت می‌شود. این تبدیل نسبت به فایل اصلی **اتلافی** است؛ حداقل/حداکثر و ابعاد ثبت می‌شود. عکس ۱۶بیتی raster خودکار به ۸ بیت بریده نمی‌شود و خطا می‌دهد. برای آموزش resize=256، تصویر bilinear و ماسک nearest است. ارزیابی/رمزنگاری به‌صورت پیش‌فرض ابعاد اصلی نسخهٔ خاکستری را حفظ می‌کند؛ `--evaluation-size` فقط برای آزمایش جداگانه با برچسب مشخص است. مقایسهٔ bit-exact مربوط به همین آرایهٔ پیش‌پردازش‌شده است، نه RGB/DICOM/NIfTI اصلی.

## آموزش، ادامه و ارزیابی
چهار مرحلهٔ encoder، اتصالات پرشی، دو convolution در هر بلوک، logits و loss=BCE+soft Dice، Adam، بدون augmentation؛ همه انتخاب اجرایی‌اند، نه ادعای معماری دقیق ناگفتهٔ پایان‌نامه. مدل جدا برای هر دیتاست. بهترین وزن صرفاً بر اساس Dice اعتبارسنجی انتخاب می‌شود؛ آزمون وارد آموزش/انتخاب وزن نمی‌شود. Dice برای دو ماسک خالی ۱ است و تعداد ماسک‌های خالی جدا گزارش می‌شود.

```bash
python -m scripts train --manifest data/drive.jsonl --dataset DRIVE --config scripts/thesis_reference.json --output weights/drive --device cuda
python -m scripts train --manifest data/drive.jsonl --dataset DRIVE --config scripts/thesis_reference.json --output weights/drive --device cuda --resume
python -m scripts evaluate --manifest data/drive.jsonl --dataset DRIVE --checkpoint weights/drive/best.pt --output evaluation/drive.json --device cuda
```

Resume برای همان تنظیمات، manifest و dataset است و وضعیت optimizer و RNG را از last.pt ادامه می‌دهد. `best.pt` برای ارزیابی است. checkpoint فقط از منبع مورداعتماد بارگذاری شود. مقادیر base_channels=32، epochs=100، batch=4، lr=.001، patience=15، threshold=.5 در JSON قابل تنظیم‌اند؛ برای آزمایش کوتاه تنظیمات مستقل بسازید. Dice/IoU باید پیش از تفسیر ROI بررسی شوند؛ برنامه ماسک خالی را با ماسک ساختگی پر نمی‌کند.

## آزمایش‌های مشترک
انتخاب بهترین وزن بر پایهٔ Dice اعتبارسنجی است؛ در تساوی Dice، loss کمتر اعتبارسنجی ملاک می‌شود تا مدل با خروجی زیر آستانه و loss رو به کاهش بی‌دلیل روی دورهٔ اول نماند. Resume علاوه بر فایل فهرست، تغییر محتوای واقعی تصویر/ماسک را هم رد می‌کند. این اصلاح هیچ استفاده‌ای از مجموعهٔ آزمون نمی‌کند.

```bash
python -m scripts run --manifest data/drive.jsonl --dataset DRIVE --checkpoint weights/drive/best.pt --config confirmed_profile.json --payload metadata.bin --output runs/drive_001 --device cuda --ablations
python -m scripts report --run runs/drive_001
```

`confirmed_profile.json` باید توسط شما از تنظیمات مستند ساخته شود. برای بررسی تفسیر پیوست می‌توان صریحاً `scripts/appendix_experiment.json` را داد؛ واگرایی احتمالی نتیجهٔ شکست است، نه خطای قابل دورزدن با RNG. run شکست‌ها را در samples.jsonl و status.json نگه می‌دارد و CLI در اجرای ناموفق exit=2 می‌دهد. پوشهٔ نتیجهٔ موجود بازنویسی نمی‌شود. اندازهٔ کوچک یا limit آزمون نرم‌افزار است، نه اجرای کل مجموعه.

خروجی‌ها: تصویر پردازش‌شده، ماسک پیش‌بینی، cipher، stego، recovered، معیارهای جداگانهٔ segmentation/security/stego/recovery، زمان I/O/استنتاج/رمز/جاسازی/فایل کمکی/گیرنده، ظرفیت خام و فشرده و هزینهٔ فایل کمکی. `total_transport_bytes_raw` شامل آرایهٔ خام+sidecar است؛ اندازهٔ فایل PNG یا هزینهٔ شبکه نیست. شروع JIT/model warm-up جدا ثبت می‌شود.

تفاضلی: دقیقاً ۱۰۰ تلاش برای هر مجموعه، ۵۰ داخل و ۵۰ خارج ROI، با بازاستنتاج ماسک و بازتولید هش؛ تصویرهای موفق به نوبت انتخاب می‌شوند. این stratification قرارداد اجرایی برای آشکارشدن ضعف خارج ROI است. خطاها از مخرج حذف نمی‌شوند. آزمون fixed-mask در فایل جدا برای کشف نقص moments است، نه جایگزین آزمایش اصلی. حساسیت یک بیت digest و رمزگشایی با digest اشتباه جدا محاسبه می‌شود. بدون راز مستقل، وابستگی به تصویر اثبات مقاومت CPA/KPA نیست.

حذف مؤلفه‌ها: بدون saliency، بدون zigzag، بدون DNA، و ROI مرجع به‌جای U-Net (oracle صرفاً تحلیلی، نه طرح قابل استقرار). هدف تغییر ندادن همزمان چند مؤلفه است. با حذف DNA هم همچنان جریان تولید می‌شود؛ این ablation سرعت بخش تولید جریان را حذف نمی‌کند.

نویز/برش: سناریوهای دقیق در CONFORMANCE. هسته با digest فرستنده روی cipher خراب رمزگشایی می‌شود؛ اما گیرندهٔ احرازشده باید stego خراب را رد کند. این خروجی‌ها مخلوط نمی‌شوند. هیچ اصلاح خطا یا بازیابی جادویی قسمت بریده‌شده وجود ندارد.

## مسیر فرستنده/گیرنده
```bash
python -m scripts keygen --output private.key
python -m scripts send --manifest data/drive.jsonl --dataset DRIVE --id 01 --checkpoint weights/drive/best.pt --config confirmed_profile.json --payload metadata.bin --keyfile private.key --output sent_01 --device cuda
python -m scripts receive --stego sent_01/stego.png --sidecar sent_01/recovery.msr --keyfile private.key --output received_01
```

**این فایل کمکی افزونهٔ اصلاحی است.** بدون آن دو بیت اصلی بازنویسی‌شده قابل بازیابی نیستند. گیرنده به مدل یا تصویر واضح نیاز ندارد؛ digest و موقعیت‌ها از sidecar احرازشده می‌آیند. راز جداگانه مبادله می‌شود و وارد ZIP/گزارش نمی‌شود. در JPEG ذخیره نکنید. ادعای معماری گیرندهٔ پایان‌نامه همچنان نیازمند اصلاح است.

## لیاپانوف
```bash
python -m scripts lyapunov --config confirmed_profile.json --digest YOUR_64_HEX_DIGEST --steps 100000 --qr-interval 10 --output dynamics/run01.json
```
مقدار واقعی digest مربوط به ROI انتخابی را با `roi_digest` به دست آورید. پنج معادلهٔ مماسی با ژاکوبین تحلیلی و RK4 همزمان حل می‌شوند. history طیف زمان محدود و trace ژاکوبین ثبت می‌شود. برای بررسی همگرایی، چند طول مسیر، چند شرایط اولیه و گام‌های کوچکتر را جدا اجرا کنید. دو توان مثبت در یک مسیر کوتاه اثبات ابرآشوب نیست. خطر گسسته‌سازی بالاتر از دقت صحیح float64 گزارش می‌شود؛ بزرگی 1e14 تضمین کیفیت کلید نیست.

## NIST رسمی، نه مجموعهٔ ناقصِ مشابه
از صفحهٔ رسمی «NIST Random Bit Generation — Documentation and Software» فایل **sts-2_1_2.zip** را دریافت کنید. نشانی رسمی در سلول تنظیمات نوت‌بوک قرار دارد. هش نسخهٔ بررسی‌شده باید `0238d2f1d26e120e3cc748ed2d4c674cdc636de37fc4027c76cc2a394fff9157` باشد.

```bash
python -m scripts nist-build --archive sts-2_1_2.zip --output nist_build
python -m scripts nist-export --runs runs/drive_001 runs/rite_001 runs/brats_001 runs/cxr_001 --output nist_input
python -m scripts nist-run --sts-root nist_build/sts-2.1.2/sts-2.1.2 --input nist_input --output nist_results
```

خروجی دقیق export: صد توالی یک‌میلیون‌بیتی، هیچ padding یا تکرار برای رسیدن به طول لازم. بین توالی‌ها بیمار/تصویر تکرار نمی‌شود؛ پس مجموعه‌های کوچک شبکیه به‌تنهایی کافی نیستند. تصویر ۲۵۶×۲۵۶ کمتر از یک‌میلیون بیت است؛ چند تصویر از گروه‌های متفاوت ممکن است در یک توالی کنار هم قرار گیرند و منشأ ثبت شود. باقی‌ماندهٔ یک گروه در توالی دیگر تکرار نمی‌شود. این قرارداد سخت‌گیرانه به معنی اثبات استقلال آماری نیست. نسخه‌ها/تنظیمات متفاوت در یک run NIST مخلوط نمی‌شوند.

۱۵ خانوادهٔ آزمون رسمی با پیش‌فرض‌های STS اجرا می‌شود. چندخروجی‌ها و ۱۴۸ الگوی NonOverlapping همگی حفظ می‌شوند؛ summary.json هر مؤلفه را جدا دارد. سطح تک‌توالی .01 و uniformity=.0001 است. توالی‌های بدون شرایط RandomExcursions نباید قبول اعلام شوند. برای کمتر از ۵۵ توالی واجدشرایط، uniformity در جمع‌بندی ما ارزیابی نمی‌شود. فایل official `finalAnalysisReport.txt` و همهٔ `stats/results/data*.txt` همراه لاگ حفظ می‌شوند. `--allow-small` فقط برای آزمون نصب با تعداد کمتر است و برچسب اجرای کامل ندارد. هیچ «همه پاس شدند» پیش‌فرضی وجود ندارد.

## مقایسه و گزارش
`literature_reported.csv` ده ردیف نقل‌شده از جدول پایان‌نامه دارد، نه بازاجرای مقالات. از آن برای نمودار منصفانهٔ رتبه‌بندی زمان با سخت‌افزارهای متفاوت استفاده نکنید. `reports/samples.csv`, `channel.csv`, `differential.csv`, `ablations.csv` و REPORT_FA.md فقط از اجرای خودتان ساخته می‌شوند. بازاجرای ۱۰ الگوریتم بدون مشخصات/کد معتبرِ آن‌ها انجام نشده است. زمان Jetson فقط با اجرای همین کد روی Jetson واقعی قابل گزارش است.

## خطاهای مورد انتظار
- `parameters ... عدد ندارند`: مانع مشخصات؛ پارامتر دارای منبع لازم است.
- `ODE diverged`: شکست روش/شرایط اولیه؛ خروجی تصادفی جایگزین نکنید.
- `Empty/Constant ROI`: وزن/نمونه و تعریف ROI را بررسی و شکست را گزارش کنید؛ ماسک مرجع را بی‌برچسب جانشین پیش‌بینی نکنید.
- `Insufficient capacity`: طول واقعی پس از zlib همراه سربرگ جا نمی‌شود؛ ظرفیت را گزارش کنید یا محتوای پیام آزمایش را با ثبت تغییر کاهش دهید.
- `NO_ELIGIBLE_PIXELS`: کل ROI/شرط برجستگی هیچ زمینهٔ مجازی باقی نگذاشته؛ خروجی ساختگی ایجاد نمی‌شود. CLI تعداد بیت لازم، بیت قابل‌استفاده و `embedded_bits=0` را برمی‌گرداند. حفاظت ROI برای موفق نشان دادن اجرا حذف نمی‌شود.
- `Patient/group leakage`: تقسیم صحیح و آموزش دوباره لازم است؛ دورزدن کنترل درست نیست.
- `Plaintext hash mismatch`: نسخهٔ محاسبات float64 و محیط فرستنده/گیرنده باید سازگار باشد؛ صحت بین معماری‌های متفاوت تضمین نشده است.

پس از اجرای واقعی، داده‌های خام خروجی و profile و منشأ را بررسی کنید؛ اعداد پایان‌نامه را فقط در صورت شاهد معتبر اصلاح کنید، حتی اگر نتیجه ضعیف‌تر از اعداد فعلی باشد.