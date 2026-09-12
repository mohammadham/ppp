"""Read-only, atomic publication of the latest thesis manuscript."""
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

load_dotenv(Path(__file__).with_name('.env'))
PUBLICATIONS = Path(os.environ['THESIS_PUBLISHED_DIR']).resolve()
app = FastAPI(title='Thesis download', docs_url=None, redoc_url=None)


def latest():
    try:
        info = json.loads((PUBLICATIONS / 'latest.json').read_text())
        path = (PUBLICATIONS / info['filename']).resolve()
        if path.parent != PUBLICATIONS or path.suffix != '.docx':
            raise ValueError('Invalid publication')
        return info, path
    except (OSError, ValueError, KeyError):
        raise HTTPException(503, 'نسخه در حال آماده‌سازی است؛ کمی بعد دوباره دانلود کنید.')


@app.get('/api/health')
def health():
    info, path = latest()
    if not path.is_file():
        raise HTTPException(503, 'فایل در دسترس نیست.')
    return {'status': 'ok', 'version': info['version']}


@app.api_route('/api/thesis/download', methods=['GET', 'HEAD'])
def download():
    info, path = latest()
    try:
        data = path.read_bytes()
    except OSError:
        raise HTTPException(503, 'دریافت فایل ممکن نشد؛ دوباره تلاش کنید.')
    filename = quote('پایان‌نامه-نسخه-درحال‌تکمیل.docx')
    return Response(data, media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document', headers={
        'Content-Disposition': f'attachment; filename="thesis-latest.docx"; filename*=UTF-8\'\'{filename}',
        'Cache-Control': 'no-store, max-age=0',
        'X-Content-Type-Options': 'nosniff',
        'X-Thesis-Version': str(info['version']),
        'ETag': '"' + hashlib.sha256(data).hexdigest() + '"',
    })