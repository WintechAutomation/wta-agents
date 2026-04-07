"""5개 HTML 파일을 upload-server로 업로드 (UTF-8 filename).

upload-server.py는 RFC5987 filename*=UTF-8''... 포맷을 파싱함.
Python requests는 기본적으로 filename만 보내서 한글 파일명이 깨짐 →
직접 multipart body 구성하여 filename*= 헤더 포함.
"""
import sys
import uuid
from pathlib import Path
from urllib.parse import quote
import urllib.request
import urllib.error
import json

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 로컬 업로드 서버 (cf 터널 연결 확인 필요)
UPLOAD_URLS = [
    'http://localhost:8080/upload',
]
OUT = Path('C:/MES/wta-agents/workspaces/docs-agent')
TOPICS = [
    ('장비물류', 1),
    ('분말검사', 2),
    ('연삭측정제어', 3),
    ('포장혼입검사', 4),
    ('호닝신뢰성', 5),
]


def build_multipart(filename: str, data: bytes):
    """multipart/form-data body with RFC5987 filename*= encoding."""
    boundary = '----WtaDocsBoundary' + uuid.uuid4().hex
    fname_enc = quote(filename, safe='')
    lines = []
    lines.append(f'--{boundary}'.encode())
    lines.append(
        f'Content-Disposition: form-data; name="file"; filename="upload.html"; filename*=UTF-8\'\'{fname_enc}'.encode()
    )
    lines.append(b'Content-Type: text/html')
    lines.append(b'')
    lines.append(data)
    lines.append(f'--{boundary}--'.encode())
    lines.append(b'')
    body = b'\r\n'.join(lines)
    content_type = f'multipart/form-data; boundary={boundary}'
    return body, content_type


def upload(url: str, fname: str, data: bytes):
    body, ct = build_multipart(fname, data)
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', ct)
    req.add_header('Content-Length', str(len(body)))
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.status, resp.read().decode('utf-8')


def verify(url: str) -> int:
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        print(f'    verify 오류: {e}')
        return 0


def main():
    print('=== HTML 업로드 + 검증 ===\n')
    results = []
    for topic, idx in TOPICS:
        fname = f'연구개발-{idx}-{topic}.html'
        fpath = OUT / fname
        if not fpath.exists():
            print(f'[{idx}] 파일 없음: {fname}')
            continue
        data = fpath.read_bytes()
        size_mb = len(data) / 1024 / 1024
        print(f'[{idx}] {fname} ({size_mb:.2f} MB)')

        uploaded = False
        for base in UPLOAD_URLS:
            try:
                status, body = upload(base, fname, data)
                print(f'    POST {base} → {status}')
                if status == 200:
                    resp = json.loads(body)
                    file_id = resp['id']
                    saved = resp['filename']
                    # 로컬 검증
                    local_url = f'http://localhost:8080/api/files/{file_id}/{quote(saved)}'
                    code = verify(local_url)
                    print(f'    로컬 검증 {code}: {local_url[:80]}...')
                    # 외부 URL
                    ext_url = f'https://agent.mes-wta.com/api/files/{file_id}/{quote(saved)}'
                    ext_code = verify(ext_url)
                    print(f'    외부 검증 {ext_code}: {ext_url[:80]}...')
                    results.append({
                        'topic': topic,
                        'idx': idx,
                        'file_id': file_id,
                        'filename': saved,
                        'local_url': local_url,
                        'local_code': code,
                        'ext_url': ext_url,
                        'ext_code': ext_code,
                    })
                    uploaded = True
                    break
            except Exception as e:
                print(f'    오류: {e}')
        if not uploaded:
            print(f'    ⚠️ 업로드 실패')
        print()

    print('\n=== 최종 결과 ===')
    for r in results:
        ok = '✓' if r['ext_code'] == 200 else ('△' if r['local_code'] == 200 else '✗')
        print(f"{ok} [{r['idx']}] {r['topic']}: {r['ext_url']}")
        print(f'     local={r["local_code"]} ext={r["ext_code"]}')


if __name__ == '__main__':
    main()
