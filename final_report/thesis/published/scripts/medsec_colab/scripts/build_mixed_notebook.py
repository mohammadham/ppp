"""Maintained source for MIXED.ipynb; generated outputs are deliberately empty."""
import json
from pathlib import Path


def notebook():
    cells = []
    def md(text): cells.append({'cell_type': 'markdown', 'metadata': {}, 'source': text})
    def code(text): cells.append({'cell_type': 'code', 'metadata': {}, 'source': text,
                                 'execution_count': None, 'outputs': []})
    md('''# MIXED — اجرای قابل‌ردیابی CHASE_DB1 + STARE
این نسخه خطاهای دو اجرای قبلی را اصلاح می‌کند؛ **موفقیت بازیابی با امنیت رمز یکسان نیست**.
گزارش ریشه‌یابی در `mixed_diagnosis/REPORT_FA.md` است. دو اجرای قبلی تغییر نکرده‌اند.

پروفایل پیش‌فرض، **آزمایش تشخیصی معادلات موجود در پچ قبلی** است، نه تأیید ابرآشوب یا پارامترهای معادلهٔ ۳–۲.
واگرایی، کمبود ظرفیت و ضعف آماری صریحاً ثبت می‌شوند؛ هیچ clipping، minmax، کلید تصادفی جایگزین یا تنظیم برای رسیدن به اعداد مقاله نداریم.
بازیابی bit-exact فقط برای آرایهٔ خاکستری ۸بیتی ورودی رمز تعریف شده، نه فایل رنگی اصلی. دادهٔ هویتی بیمار وارد نکنید.''')
    md('## ۱. بارگذاری بستهٔ اصلاح‌شده\nZIP ساخته‌شده از همین نسخه را در نشست جدید بارگذاری کنید؛ پوشهٔ استخراج تازه است.')
    code('''from pathlib import Path
import os, sys, json, zipfile, tempfile, subprocess
from google.colab import files
if any(name == 'scripts' or name.startswith('scripts.') for name in sys.modules):
    raise RuntimeError('برای جلوگیری از مخلوط‌شدن ماژول‌های قدیمی، این بسته را در نشست جدید اجرا کنید.')
uploaded = files.upload()
archives = [Path(name) for name in uploaded if name.lower().endswith('.zip')]
if len(archives) != 1: raise ValueError('دقیقاً ZIP بستهٔ اصلاح‌شده را انتخاب کنید.')
ROOT = Path(tempfile.mkdtemp(prefix='medsec_mixed_'))
with zipfile.ZipFile(archives[0]) as z:
    for name in z.namelist():
        if not (ROOT/name).resolve().is_relative_to(ROOT.resolve()): raise ValueError('Unsafe ZIP path')
    z.extractall(ROOT)
PACKAGE = ROOT/'medsec_colab'
if not (PACKAGE/'scripts/mixed_manifest.py').is_file(): raise ValueError('این ZIP نسخهٔ اصلاح‌شده نیست.')
os.chdir(PACKAGE)
sys.path.insert(0, str(PACKAGE))
subprocess.run([sys.executable, 'scripts/install_colab.py'], check=True)
subprocess.run([sys.executable, '-m', 'pip', 'install', 'kagglehub', 'pandas'], check=True)
print('بستهٔ فعال:', PACKAGE)
''')
    md('''## ۲. تنظیمات واحد
برای آزمایش جدید فقط `RUN_LABEL` تازه انتخاب کنید؛ هیچ وزن/نتیجه‌ای حذف نمی‌شود.
برای ادامهٔ همان آموزش `RESUME_TRAINING=True`؛ تنظیمات و manifest باید یکسان باشند.
پارامترهای اصلی معادلهٔ ۳–۲ هنوز نامشخص‌اند؛ برای آن روش، پروفایل مستند جدا لازم است.
تغییر dt یا پیام، آزمایش جدید است و نباید با اجرای قبلی به‌عنوان بهبود همان شرایط مقایسه شود.''')
    code('''import torch
from scripts.artifacts import environment, sha256_file, write_json
MOUNT_DRIVE = True
if MOUNT_DRIVE:
    from google.colab import drive
    drive.mount('/content/drive')
os.environ['THESIS_WORKDIR'] = '/content/drive/MyDrive/Thesis_Research' if MOUNT_DRIVE else '/content/Thesis_Research'
WORK = Path(os.environ['THESIS_WORKDIR']); WORK.mkdir(parents=True, exist_ok=True)
DATASET = 'CHASE_STARE_Merged'
RUN_LABEL = 'mixed_v2_001'
MANIFEST = WORK/'mixed_subject_v2.jsonl'
WEIGHTS = WORK/'weights'/RUN_LABEL
CHECKPOINT = WEIGHTS/'best.pt'
RUN_DIR = WORK/'runs'/RUN_LABEL
PROFILE = PACKAGE/'scripts/mixed_diagnostic.json'
cfg = json.loads(PROFILE.read_text(encoding='utf-8'))
RUN_TRAINING = True
RESUME_TRAINING = False
RUN_EXPERIMENTS = True
EVALUATION_SIZE = None  # ابعاد اصلی خاکستری؛ resize آزمون باید آزمایش جدا نام‌گذاری شود
PAYLOAD_BYTES = 1000  # پیام نرم‌افزاری فاقد دادهٔ بیمار؛ افزایش آن ممکن است ظرفیت را رد کند
PAYLOAD = WORK/f'metadata_seed2026_{PAYLOAD_BYTES}.bin'
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
print('device:', DEVICE, '\\nprofile:', cfg['profile'])
print('Training uses grayscale:', cfg['training'])
print('No parallel-RK4 claim: recurrence is sequential and JIT-compiled.')
print(environment())
''')
    md('## ۳. دریافت همان نسخه‌های CHASE و STARE\nمسیر واقعی برگشتی دانلود استفاده می‌شود؛ فرضی دربارهٔ ساختار کش نداریم. مجوز مجموعه‌ها را رعایت کنید.')
    code('''import kagglehub
os.environ['KAGGLEHUB_CACHE'] = str(WORK/'data_sources'/'_kaggle_cache')
os.environ['DISABLE_COLAB_CACHE'] = 'true'
catalog = {'CHASE_DB1': 'namnguynnnn/chase-db1/versions/1',
           'STARE': 'aryankamani/stare-dataset-20images/versions/1'}
DATA_PATHS = {}
for name, handle in catalog.items():
    DATA_PATHS[name] = Path(kagglehub.dataset_download(handle)).resolve()
    if not DATA_PATHS[name].is_dir(): raise FileNotFoundError(DATA_PATHS[name])
    print(name, DATA_PATHS[name])
write_json(WORK/'mixed_dataset_sources.json', {'handles': catalog, 'paths': {k:str(v) for k,v in DATA_PATHS.items()}})
''')
    md('''## ۴. manifest بیمارمحور و کنترل ورودی
STARE فقط `imNNNN` تصویر است؛ `.ah/.vk` ماسک‌اند. دو چشم CHASE یک بیمار محسوب می‌شوند.
تقسیم پیش از آموزش و جدا برای هر منبع است؛ فایل متفاوت روی manifest قبلی نوشته نمی‌شود.
در STARE شناسهٔ تصویر جانشین شناسهٔ بیمار است؛ اگر فرادادهٔ بیمار دارید، گروه‌ها را با آن تطبیق دهید.''')
    code('''from scripts.mixed_manifest import build_mixed_manifest
from scripts.data import load_manifest, load_sample
from scripts.training import SegmentationDataset
from torch.utils.data import DataLoader
from collections import Counter
import numpy as np
import matplotlib.pyplot as plt
summary = build_mixed_manifest(DATA_PATHS['CHASE_DB1'], DATA_PATHS['STARE'], MANIFEST, seed=cfg['seed'])
print(summary)
records = load_manifest(MANIFEST)
train_records = [r for r in records if r['split'] == 'train']
loader = DataLoader(SegmentationDataset(train_records, cfg['training']['size']), batch_size=cfg['training']['batch_size'])
images, masks = next(iter(loader))
print('Actual training tensors:', images.shape, masks.shape, 'mask values:', torch.unique(masks))
for origin in ('CHASE_DB1', 'STARE'):
    r = next(r for r in train_records if r['origin_dataset'] == origin)
    image, mask, prep = load_sample(r)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].imshow(image, cmap='gray', vmin=0, vmax=255); axes[0].set_title(origin+' input')
    axes[1].imshow(mask, cmap='gray', vmin=0, vmax=1); axes[1].set_title('Primary observer mask')
    for ax in axes: ax.axis('off')
    plt.show(); print(r['image'], r['mask'], prep)
''')
    md('## ۵. پیام با طول و هش ثابت\nفایل موجود با محتوای متفاوت رد می‌شود؛ پیام بی‌سر‌وصدا کوچک یا بزرگ نمی‌شود.')
    code('''if not isinstance(PAYLOAD_BYTES, int) or PAYLOAD_BYTES < 0: raise ValueError('Invalid payload size')
payload = np.random.default_rng(cfg['seed']).integers(0, 256, PAYLOAD_BYTES, dtype=np.uint8).tobytes()
if PAYLOAD.exists() and PAYLOAD.read_bytes() != payload:
    raise ValueError('محتوای پیام با seed/طول اعلام‌شده متفاوت است؛ فایل مستقل انتخاب کنید.')
if not PAYLOAD.exists(): PAYLOAD.write_bytes(payload)
print('Payload bytes:', PAYLOAD.stat().st_size, 'SHA256:', sha256_file(PAYLOAD))
''')
    md('''## ۶. آموزش واقعی U-Net
آموزش و پیش‌بینی هر دو خاکستری‌اند؛ نمایش قبلی RGB/512 مسیر آموزش واقعی نبود.
انتخاب وزن پیش‌فرض بر اساس Dice آستانه‌دار اعتبارسنجی است؛ soft Dice جدا نام‌گذاری می‌شود.
افزایش epoch تضمین همگرایی نیست؛ دادهٔ آزمون برای انتخاب وزن/پارامتر استفاده نمی‌شود.''')
    code('''from scripts.training import train
if RUN_TRAINING:
    training_result = train(MANIFEST, DATASET, cfg, WEIGHTS, DEVICE, resume=RESUME_TRAINING)
    print(training_result)
if not CHECKPOINT.is_file(): raise FileNotFoundError('ابتدا آموزش معتبر را اجرا کنید: '+str(CHECKPOINT))
''')
    md('## ۷. ارزیابی و رمزنگاری — فقط یک مسیر اجرایی\nدقیقاً test ارزیابی می‌شود. ظرفیت بر اساس پیام فشرده + سربرگ سنجیده می‌شود. شکست‌ها همراه مرحله و علت حفظ می‌شوند.')
    code('''from scripts.config import validate
from scripts.experiments import run
if RUN_EXPERIMENTS:
    validate(cfg)
    result = run(MANIFEST, DATASET, CHECKPOINT, cfg, PAYLOAD, RUN_DIR, DEVICE,
                 evaluation_size=EVALUATION_SIZE, include_ablations=False)
    print(result)
    if result['status'] != 'completed': print('این اجرا شکست ثبت‌شده دارد؛ گزارش را موفقیت کامل معرفی نکنید.')
else:
    print('اجرای جدید فعال نشده است؛ فقط گزارش پوشهٔ انتخاب‌شده خوانده می‌شود.')
''')
    md('''## ۸. جدول‌های معتبر — بدون صفرِ جایگزین
آنتروپی/همبستگی روی cipher؛ PSNR/SSIM جاسازی بین cipher و stego؛ بازیابی بین ورودی خاکستری و recovered.
NPCR/UACI در فایل‌های `differential` درصد هستند: **ضرب مجدد در ۱۰۰ ممنوع**.
حساسیت کلید از `cipher_sensitivity` خوانده می‌شود و با حساسیت تغییر پیکسل یکی نیست.
NaN/سلول خالی یعنی اندازه‌گیری موجود نیست، نه صفر. `completed` به معنی اثبات امنیت نیست.''')
    code('''import pandas as pd
from scripts.reporting import make_report
if not (RUN_DIR/'status.json').exists(): raise FileNotFoundError('اجرای ثبت‌شده‌ای در RUN_DIR نیست.')
report = make_report(RUN_DIR)
print('Run status:', report['status'])
for filename in ('samples.csv', 'keys.csv', 'differential.csv', 'channel.csv'):
    path = RUN_DIR/'reports'/filename
    print('\\n'+filename)
    if path.stat().st_size > 3:
        display(pd.read_csv(path))
    else: print('اندازه‌گیری موجود نیست؛ علت را در status/samples بررسی کنید.')
print(json.loads((RUN_DIR/'reports/differential_summary.json').read_text()))
''')
    md('''## ۹. بازیابی مستقل آرایه و پیام ذخیره‌شده
هش پیام با هش تصویر فرق دارد. همهٔ نمونه‌ها بررسی می‌شوند، نه فقط اولین نمونه.
این سلول فایل‌های واقعی بازیابی‌شده را با ورودی ثبت‌شده مقایسه می‌کند؛ آزمون دوبارهٔ گیرندهٔ احرازشده نیست.''')
    code('''from PIL import Image
provenance = json.loads((RUN_DIR/'run.json').read_text())
if provenance.get('payload_sha256') != sha256_file(PAYLOAD):
    raise ValueError('پیام فعلی متعلق به اجرای انتخاب‌شده نیست.')
rows = [json.loads(line) for line in (RUN_DIR/'samples.jsonl').read_text().splitlines() if line.strip()]
checks = []
for row in rows:
    check = {'id': row['id'], 'status': row['status'], 'error': row.get('error')}
    if row['status'] == 'ok':
        folder = RUN_DIR/row['folder']
        a = np.array(Image.open(folder/'processed.png'))
        b = np.array(Image.open(folder/'recovered.png'))
        received = (folder/'recovered_payload.bin').read_bytes()
        check.update({'image_bit_exact': np.array_equal(a,b),
                      'payload_exact': received == PAYLOAD.read_bytes(),
                      'recovered_payload_sha256': sha256_file(folder/'recovered_payload.bin'),
                      'recorded_payload_ber': row.get('payload_ber')})
        if not check['image_bit_exact'] or not check['payload_exact']: raise AssertionError(check)
    checks.append(check)
display(pd.DataFrame(checks))
print('Verified successful samples:', sum(r['status']=='ok' for r in checks), '/', len(checks))
''')
    md('''## ۱۰. شواهد تصویری و حملات
تصاویر با دامنهٔ ثابت ۰–۲۵۵ نمایش داده می‌شوند؛ صرف تولید نویز، آزمون مقاومت نیست.
`channel.csv` کیفیت رمزگشایی هسته پس از تخریب را ثبت می‌کند؛ گیرندهٔ احرازشده باید stego دستکاری‌شده را رد کند.''')
    code('''successful = [r for r in rows if r['status'] == 'ok']
if successful:
    folder = RUN_DIR/successful[0]['folder']
    arrays = [np.array(Image.open(folder/'processed.png')), np.load(folder/'cipher.npy', allow_pickle=False),
              np.array(Image.open(folder/'stego.png')), np.array(Image.open(folder/'recovered.png'))]
    fig, axes = plt.subplots(2, 4, figsize=(16, 7))
    for col, (title, array) in enumerate(zip(['Processed','Cipher','Stego','Recovered'], arrays)):
        axes[0,col].imshow(array, cmap='gray', vmin=0, vmax=255); axes[0,col].set_title(title); axes[0,col].axis('off')
        axes[1,col].hist(array.ravel(), bins=256, range=(0,256)); axes[1,col].set_xlim(0,255)
    plt.tight_layout(); plt.show()
for row in rows:
    path = RUN_DIR/row['folder']/'authenticated_channel.json'
    print(row['id'], json.loads(path.read_text()) if path.exists() else 'Authenticated channel test unavailable')
''')
    md('''## ۱۱. محدودیت‌های باقی‌مانده
- لحظه‌های ROI اطلاعات کامل تصویر نیستند؛ تغییر بیرون ROI و جابه‌جایی پیکسل‌های آن می‌تواند هش را ثابت نگه دارد. نتیجهٔ ضعیف تفاضلی را حذف نکنید.
- پروفایل تشخیصی ممکن است در طول واقعی تصاویر واگرا شود؛ بدون منبع علمی عدد جدیدی تزریق نکنید. کوچک‌کردن dt طول زمانی مسیر را تغییر می‌دهد، نه اینکه امنیت را اثبات کند.
- آزمایش لیاپانوف فقط برآورد زمان محدود است. QR اصلاح شده، ولی ابرآشوب نیازمند بررسی همگرایی و کرانداری مستقل است.
- این مجموعهٔ کوچک به‌تنهایی برای پروتکل ۱۰۰ توالی مستقل NIST کافی نیست؛ در این نوت‌بوک NIST کامل ادعا نشده است.
- نتایج قدیمی با split و preprocessing جدید قابل ادغام نیستند. وزن‌ها باید روی manifest اصلاح‌شده بازآموزی شوند.''')
    for i, cell in enumerate(cells): cell['id'] = f'mixed-v2-{i:03d}'
    return {'cells': cells, 'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                                       'language_info': {'name': 'python'}, 'colab': {'name': 'MIXED.ipynb'}},
            'nbformat': 4, 'nbformat_minor': 5}


def build(output=None):
    output = Path(output) if output else Path(__file__).resolve().parents[1]/'MIXED.ipynb'
    output.write_text(json.dumps(notebook(), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return output


if __name__ == '__main__': print(build())