"""Generate a clean Colab notebook and distributable archive from maintained sources."""
import hashlib
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

def notebook():
    cells = []
    def md(text): cells.append({'cell_type': 'markdown', 'metadata': {}, 'source': text})
    def code(text): cells.append({'cell_type': 'code', 'execution_count': None, 'metadata': {}, 'outputs': [], 'source': text})
    md('# اجرای پژوهشی پایان‌نامه در Google Colab\n\nابتدا README_FA و CONFORMANCE_FA را بخوانید. آموزش و آزمون با دادهٔ واقعی انجام می‌شود؛ خروجی ساختگی نداریم. هفت پارامتر معادلهٔ اصلی نامشخص و دستگاه پیوست متفاوت و مستعد واگرایی است. هیچ عدد فصل چهارم از پیش تأیید نشده است. این بسته برای دادهٔ شناسایی‌پذیر بیمار یا استفادهٔ بالینی نیست.')
    md('## ۱. بارگذاری ZIP بسته\nفایل `medical_thesis_colab.zip` را انتخاب کنید؛ این فایل فقط شامل کد و مستندات است. نوت‌بوک قدیمی اجرا نمی‌شود.')
    code("from pathlib import Path\nimport os, sys, json, zipfile, subprocess\nfrom google.colab import files\nuploaded = files.upload()\narchives = [Path(name) for name in uploaded if name.endswith('.zip')]\nif len(archives) != 1: raise ValueError('دقیقاً ZIP بسته را انتخاب کنید')\nROOT = Path('/content/thesis_toolkit')\nROOT.mkdir(exist_ok=True)\nwith zipfile.ZipFile(archives[0]) as z:\n    for name in z.namelist():\n        if not (ROOT/name).resolve().is_relative_to(ROOT.resolve()): raise ValueError('Unsafe zip')\n    z.extractall(ROOT)\nPACKAGE = ROOT/'medsec_colab'\nos.chdir(PACKAGE)\nsys.path.insert(0, str(PACKAGE))\nprint('مسیر بسته:', PACKAGE)")
    md('## ۲. نصب و آزمون نرم‌افزار\nآزمون‌های خودکار از دادهٔ کوچک مصنوعی **فقط برای بررسی نرم‌افزار** استفاده می‌کنند؛ آن‌ها آزمایش پزشکی یا بازتولید نتایج نیستند.')
    code("subprocess.run([sys.executable, 'scripts/install_colab.py'], check=True)\nsubprocess.run([sys.executable, '-m', 'pytest', 'scripts/tests', '-q'], check=True)\nfrom scripts.artifacts import environment\nprint(json.dumps(environment(), indent=2, ensure_ascii=False))")
    md('## ۳. مسیرهای ماندگار و تنظیمات\nنام/نسخهٔ دقیق داده و مسیر واقعی آن را وارد کنید. مسیر WORK برای وزن و گزارش است؛ DATA_ROOT باید پوشهٔ داده‌های دریافت‌شده با مجوز باشد. برای هر دیتاست جدا اجرا کنید.')
    code("MOUNT_DRIVE = True\nif MOUNT_DRIVE:\n    from google.colab import drive\n    drive.mount('/content/drive')\nos.environ['THESIS_WORKDIR'] = '/content/drive/MyDrive/Thesis_Research' if MOUNT_DRIVE else '/content/Thesis_Research'\nWORK = Path(os.environ['THESIS_WORKDIR']); WORK.mkdir(parents=True, exist_ok=True)\nDATASET = 'DRIVE'  # DRIVE / RITE / BraTS2020 / COVID19_CXR\nDATA_ROOT = WORK/'data_sources'/DATASET\nSOURCE = ''  # شناسه/نسخه و منشأ واقعی داده؛ خالی مجاز نیست\nCXR_CSV = WORK/'cxr_index.csv'\nMANIFEST = WORK/f'{DATASET}.jsonl'\nWEIGHTS = WORK/'weights'/DATASET\nPAYLOAD = WORK/'metadata.bin'  # فایل آزمایشی فاقد اطلاعات هویتی بیمار\nRUN_DIR = WORK/'runs'/f'{DATASET}_001'  # در اجرای جدید نام تازه انتخاب کنید\nPROFILE = PACKAGE/'scripts/thesis_reference.json'  # نسخه مستند تکمیل‌شده خودتان را جایگزین کنید\nRUN_TRAINING = False\nRESUME_TRAINING = False\nRUN_EXPERIMENTS = False\nRUN_NIST = False\nimport torch\nDEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'\nprint('device:', DEVICE)")
    md('## ۴. ساخت فهرست دادهٔ واقعی\nاگر ساختار شما متفاوت است، مطابق README فایل JSONL صریح تهیه کنید. این سلول هیچ داده‌ای دانلود یا جعل نمی‌کند. برای BraTS اسلایس‌ها بعد از تقسیم بیمار ساخته می‌شوند؛ DRIVE/RITE از گروه‌های مشترک استفاده می‌کنند.')
    code("from scripts.prepare import prepare\nfrom scripts.data import load_manifest, load_sample\nif not MANIFEST.exists():\n    prepare(DATASET, DATA_ROOT, MANIFEST, SOURCE, csv_path=CXR_CSV if DATASET == 'COVID19_CXR' else None,\n            modalities=['flair', 't1', 't1ce', 't2'], stride=1)\nrecords = load_manifest(MANIFEST)\nfrom collections import Counter\nprint(Counter((r['dataset'], r['split']) for r in records))\nexample, reference_mask, prep = load_sample(records[0])\nimport matplotlib.pyplot as plt\nfig, axes = plt.subplots(1, 2, figsize=(10, 5))\naxes[0].imshow(example, cmap='gray'); axes[0].set_title('Real processed input')\naxes[1].imshow(reference_mask, cmap='gray'); axes[1].set_title('Reference ROI')\nplt.show(); print(prep)")
    md('## ۵. آموزش و ارزیابی U-Net\nآموزش به عددهای ODE نیاز ندارد. `RUN_TRAINING=True` را پس از بررسی داده فعال کنید؛ دوره‌ها و دیگر تنظیمات در کپی JSON قابل تغییرند. بهترین وزن فقط از اعتبارسنجی انتخاب می‌شود. با قطع نشست و همان تنظیمات، RESUME_TRAINING را فعال کنید.')
    code("from scripts.training import train\nfrom scripts.experiments import evaluate_segmentation\ncfg = json.loads(PROFILE.read_text())\nif RUN_TRAINING:\n    print(train(MANIFEST, DATASET, cfg, WEIGHTS, DEVICE, resume=RESUME_TRAINING))\nCHECKPOINT = WEIGHTS/'best.pt'\nif CHECKPOINT.exists():\n    evaluation = evaluate_segmentation(MANIFEST, DATASET, CHECKPOINT, WORK/'evaluation'/f'{DATASET}.json', DEVICE)\n    print({k:v for k,v in evaluation.items() if k not in ('records','environment')})\nelse:\n    print('وزن آموزش‌دیده موجود نیست؛ ارزیابی یا استنتاج با وزن تصادفی انجام نشد.')")
    md('## ۶. اعتبار روش پیش از رمزنگاری\nتنظیمات معادلهٔ ۳–۲ عمداً ناقص‌اند. پروفایل پیوست جایگزین بی‌نام نیست. برای استفادهٔ آزمایشی از آن باید PROFILE را صریحاً تغییر دهید و نتیجه را تفسیر پیوست بنامید. عددهای مطلوب دلیل انتخاب پارامتر نیستند.')
    code("from scripts.config import validate\nfrom scripts.model import Predictor\nfrom scripts.chaos import roi_digest, stream\nfrom scripts.artifacts import write_json\nMETHOD_READY = False\ntry:\n    validate(cfg)\n    predictor = Predictor(CHECKPOINT, DEVICE)\n    selected = next(r for r in records if r['split'] == 'test')\n    image, target, preprocessing = load_sample(selected)\n    predicted_roi = predictor(image)\n    digest, moments = roi_digest(image, predicted_roi)\n    raw = stream(digest, image.size, cfg, raw=True)\n    METHOD_READY = True\n    print('پیش‌بررسی این نمونه موفق؛ هنوز اثبات پایداری یا امنیت نیست.', moments)\nexcept Exception as exc:\n    write_json(WORK/'method_preflight.json', {'status':'blocked','error':f'{type(exc).__name__}: {exc}','config':cfg})\n    print('مانع ثبت‌شده:', exc)")
    md('## ۷. اجرای آزمایش‌ها\nبرای هر چهار مجموعه جدا اجرا کنید. پیش‌فرض ۱۰۰ تلاش تفاضلی در هر مجموعه است؛ نویز/برش، حساسیت digest، حذف مؤلفه‌ها و بازیابی دقیق هم ثبت می‌شوند. طول پیام و ظرفیت واقعی‌اند. اجرای همهٔ مجموعه‌ها ممکن است از زمان یک نشست کولب طولانی‌تر باشد.')
    code("from scripts.experiments import run\nfrom scripts.reporting import make_report\nif RUN_EXPERIMENTS:\n    if not METHOD_READY: raise RuntimeError('ابتدا مانع مشخصات/وزن/دینامیک را رفع و مستند کنید')\n    if not PAYLOAD.is_file(): raise FileNotFoundError('فایل فراداده آزمایشی لازم است: '+str(PAYLOAD))\n    status = run(MANIFEST, DATASET, CHECKPOINT, cfg, PAYLOAD, RUN_DIR, DEVICE, include_ablations=True)\n    print(status)\n    print(make_report(RUN_DIR))\nelse:\n    print('اجرای پژوهشی فعال نشده است؛ نتیجه‌ای ساخته نشد.')")
    md('## ۸. رفت‌وبرگشت مستقل تصویر و پیام\nفایل راز خارج از گزارش و فایل‌های ارسالی نگه‌داری می‌شود. گیرنده به stego، recovery.msr و همان راز نیاز دارد. این افزونهٔ اصلاحی با ادعای گیرندهٔ بدون فایل کمکی پایان‌نامه متفاوت است.')
    code("def cli(*args):\n    return subprocess.run([sys.executable, '-m', 'scripts', *map(str,args)], check=True)\nRUN_DELIVERY = False\nif RUN_DELIVERY:\n    if not METHOD_READY: raise RuntimeError('روش آماده نیست')\n    KEYFILE = WORK/'private_research.key'\n    if not KEYFILE.exists(): cli('keygen','--output',KEYFILE)\n    SENT = WORK/'sent_001'; RECEIVED = WORK/'received_001'\n    cli('send','--manifest',MANIFEST,'--dataset',DATASET,'--id',selected['id'],'--checkpoint',CHECKPOINT,\n        '--config',PROFILE,'--payload',PAYLOAD,'--keyfile',KEYFILE,'--output',SENT,'--device',DEVICE)\n    cli('receive','--stego',SENT/'stego.png','--sidecar',SENT/'recovery.msr','--keyfile',KEYFILE,'--output',RECEIVED)")
    md('## ۹. برآورد لیاپانوف و پرترهٔ فاز\nاین برآورد زمان محدود است. طول‌های متفاوت، چند شرایط اولیه و گام‌های کوچکتر برای بررسی همگرایی لازم‌اند؛ علامت مثبت به‌تنهایی اثبات نیست.')
    code("from scripts.dynamics import lyapunov\nif METHOD_READY and RUN_EXPERIMENTS:\n    dynamics = lyapunov(digest, cfg, steps=100000, qr_interval=10, output=WORK/'dynamics'/f'{DATASET}.json')\n    print({k:v for k,v in dynamics.items() if k not in ('phase','convergence','environment')})\n    if dynamics['status'] == 'ok':\n        import numpy as np\n        phase = np.array(dynamics['phase'])\n        fig = plt.figure(); ax = fig.add_subplot(111, projection='3d')\n        ax.plot(phase[:,0], phase[:,1], phase[:,2], linewidth=.4)\n        ax.set_xlabel('x'); ax.set_ylabel('y'); ax.set_zlabel('z'); plt.show()")
    md('## ۱۰. NIST رسمی: دریافت، ساخت و اجرا\nاین مرحله بدون دادهٔ کافی متوقف می‌شود؛ هیچ پرکردن/تکرار تصویر برای رسیدن به صد میلیون بیت انجام نمی‌شود. خروجی تمام ۱۵ خانواده و مؤلفه‌های آن‌ها در پوشهٔ نتیجه باقی می‌ماند. دادهٔ کمتر با برچسب آزمون نرم‌افزار از این مرحلهٔ پژوهشی جدا است.')
    code("os.environ['NIST_STS_URL'] = 'https://csrc.nist.gov/CSRC/media/Projects/Random-Bit-Generation/documents/sts-2_1_2.zip'\nNIST_RUNS = [WORK/'runs'/f'{name}_001' for name in ['DRIVE','RITE','BraTS2020','COVID19_CXR']]\nif RUN_NIST:\n    import urllib.request\n    from scripts.nist import build_official, export_streams, run_official\n    archive = WORK/'sts-2_1_2.zip'\n    if not archive.exists(): urllib.request.urlretrieve(os.environ['NIST_STS_URL'], archive)\n    BUILD = WORK/'nist_build'\n    if not BUILD.exists(): sts_root = build_official(archive, BUILD)\n    else: sts_root = Path(json.loads((BUILD/'build.json').read_text())['assess']).parent\n    nist_input = WORK/'nist_input_001'\n    if not nist_input.exists(): export_streams(NIST_RUNS, nist_input, sequences=100, bits=1000000)\n    nist_result = run_official(sts_root, nist_input, WORK/'nist_results_001', timeout=7200)\n    print(nist_result['status'], 'families:', nist_result['families'])")
    md('## ۱۱. جمع‌بندی و دریافت جدول‌ها\nفقط گزارش اجرای انتخابی بسته‌بندی می‌شود؛ فایل راز و دادهٔ خام پزشکی در ZIP گزارش نیست. جدول literature_reported.csv نقل از پایان‌نامه است و بازاجرای مقاله‌ها نیست. زمان کولب را زمان Jetson معرفی نکنید.')
    code("if (RUN_DIR/'status.json').exists():\n    make_report(RUN_DIR)\n    import shutil\n    archive = shutil.make_archive(str(WORK/f'{DATASET}_report'), 'zip', RUN_DIR/'reports')\n    files.download(archive)\nelse:\n    print('هنوز اجرای ثبت‌شده‌ای برای گزارش وجود ندارد.')")
    return {'cells': cells, 'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                                       'language_info': {'name': 'python'}, 'colab': {'name': 'Thesis_Colab.ipynb'}},
            'nbformat': 4, 'nbformat_minor': 5}

def build(output=None):
    scripts = Path(__file__).resolve().parent
    output = Path(output) if output else scripts.parent/'colab_delivery'; output.mkdir(parents=True, exist_ok=True)
    nb = notebook()
    for i, cell in enumerate(nb['cells']): cell['id'] = f'thesis-cell-{i:03d}'
    nbpath = output/'Thesis_Colab.ipynb'; nbpath.write_text(json.dumps(nb, ensure_ascii=False, indent=2), encoding='utf-8')
    archive = output/'medical_thesis_colab.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(nbpath, 'medsec_colab/Thesis_Colab.ipynb')
        if __package__:
            from .build_mixed_notebook import notebook as mixed_notebook
        else:
            from build_mixed_notebook import notebook as mixed_notebook
        mixed_path = output/'MIXED.ipynb'
        mixed_path.write_text(json.dumps(mixed_notebook(), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        z.write(mixed_path, 'medsec_colab/MIXED.ipynb')
        diagnosis_dir = scripts.parent/'mixed_diagnosis'
        for name in ('REPORT_FA.md', 'numerical_diagnostics.json', 'final_tests.txt', 'baseline_tests.txt', 'TESTED_ENVIRONMENT.txt'):
            diagnosis = diagnosis_dir/name
            if diagnosis.is_file(): z.write(diagnosis, 'medsec_colab/mixed_diagnosis/'+name)
        for diagnosis in sorted(diagnosis_dir.glob('run*_cell_*.png')):
            z.write(diagnosis, 'medsec_colab/mixed_diagnosis/'+diagnosis.name)
        for p in sorted(scripts.rglob('*')):
            relative = p.relative_to(scripts)
            if not p.is_file() or any(part.startswith('.') or part == '__pycache__' for part in relative.parts): continue
            if p.name in ('Untitled1.ipynb', 'untitled1.py') or p.suffix not in ('.py', '.md', '.json', '.csv', '.txt'): continue
            z.write(p, 'medsec_colab/scripts/'+relative.as_posix())
        sources = list(scripts.parent.glob('نسخه نهایی*.docx'))
        if len(sources) == 1:
            doc = sources[0]
            with zipfile.ZipFile(doc) as original:
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                paragraphs = ET.fromstring(original.read('word/document.xml')).findall('./w:body/w:p', ns)
                text = '\n'.join(f'P{i}: '+''.join(p.itertext()) for i,p in enumerate(paragraphs))
            z.writestr('medsec_colab/reference/thesis_extracted.txt', text)
            evidence = {'filename': doc.name, 'sha256': hashlib.sha256(doc.read_bytes()).hexdigest(),
                        'paragraph_index': 'zero-based body paragraphs', 'figures': {}}
            for name in ('eq3_1_sha256_key_gen.png','eq3_2_5d_hyperchaos_rk4.png','eq3_3_zigzag_dna.png','eq3_4_saliency_stego.png'):
                p = scripts.parent/'bases'/name
                if p.is_file():
                    z.write(p, 'medsec_colab/reference/'+name)
                    evidence['figures'][name] = hashlib.sha256(p.read_bytes()).hexdigest()
            z.writestr('medsec_colab/reference/provenance.json', json.dumps(evidence, ensure_ascii=False, indent=2))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output/'SHA256SUMS.txt').write_text(checksum+'  '+archive.name+'\n', encoding='utf-8')
    print(json.dumps({'zip': str(archive), 'notebook': str(nbpath), 'sha256': checksum, 'bytes': archive.stat().st_size}, indent=2))
    return archive

if __name__ == '__main__': build()