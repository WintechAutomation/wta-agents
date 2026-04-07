"""5개 HTML을 zip으로 묶어 dashboard /api/upload로 업로드 (외부 접근용)."""
import sys
import zipfile
import urllib.request
import uuid
import json
from pathlib import Path
from urllib.parse import quote

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUT = Path('C:/MES/wta-agents/workspaces/docs-agent')
TOPICS = [
    ('장비물류', 1),
    ('분말검사', 2),
    ('연삭측정제어', 3),
    ('포장혼입검사', 4),
    ('호닝신뢰성', 5),
]

# 1. 개별 업로드도 시도 (dashboard API는 html 미허용이므로 zip 권장)
# 여기서는 zip 생성
zip_path = OUT / 'research_notes_v3.zip'
print(f'=== zip 생성: {zip_path.name} ===')
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for topic, idx in TOPICS:
        fname = f'연구개발-{idx}-{topic}.html'
        fpath = OUT / fname
        if fpath.exists():
            zf.write(fpath, arcname=fname)
            print(f'  + {fname} ({fpath.stat().st_size/1024/1024:.2f} MB)')

size_mb = zip_path.stat().st_size / 1024 / 1024
print(f'\n총 zip 크기: {size_mb:.2f} MB\n')


def build_multipart(field: str, filename: str, data: bytes, content_type: str):
    boundary = '----WtaDocsBoundary' + uuid.uuid4().hex
    fname_enc = quote(filename, safe='')
    parts = []
    parts.append(f'--{boundary}'.encode())
    parts.append(
        f'Content-Disposition: form-data; name="{field}"; filename="upload.zip"; filename*=UTF-8\'\'{fname_enc}'.encode()
    )
    parts.append(f'Content-Type: {content_type}'.encode())
    parts.append(b'')
    parts.append(data)
    parts.append(f'--{boundary}--'.encode())
    parts.append(b'')
    body = b'\r\n'.join(parts)
    ct = f'multipart/form-data; boundary={boundary}'
    return body, ct


data = zip_path.read_bytes()
body, ct = build_multipart('file', zip_path.name, data, 'application/zip')

print('=== dashboard /api/upload (외부) ===')
req = urllib.request.Request(
    'https://agent.mes-wta.com/api/upload',
    data=body, method='POST',
)
req.add_header('Content-Type', ct)
req.add_header('Content-Length', str(len(body)))
try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        status = resp.status
        body_text = resp.read().decode('utf-8')
    print(f'status={status}')
    print(body_text)
    if status == 200:
        resp_data = json.loads(body_text)
        if resp_data.get('ok'):
            stored = resp_data['file']['stored_name']
            dl_url = f'https://agent.mes-wta.com/api/files/{stored}'
            # 검증
            req2 = urllib.request.Request(dl_url, method='GET')
            with urllib.request.urlopen(req2, timeout=30) as r2:
                print(f'\n검증 GET {r2.status}: {dl_url}')
except Exception as e:
    print(f'오류: {e}')
