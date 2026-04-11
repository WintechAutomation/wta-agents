# -*- coding: utf-8 -*-
"""Step 1: manuals/ 1,965건 텍스트 추출 + 메타 수집 (체크포인트 지원)"""
import os, sys, io, json, hashlib, warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pdfplumber

SRC = r'C:\MES\wta-agents\data\manuals\1_robot'
OUT = r'C:\MES\wta-agents\workspaces\docs-agent\manuals_v2_1robot_extract.jsonl'
CKPT = r'C:\MES\wta-agents\workspaces\docs-agent\manuals_v2_1robot_extract.ckpt'

def collect():
    items = []
    for root, dirs, files in os.walk(SRC):
        cat = os.path.relpath(root, SRC).split(os.sep)[0] if root != SRC else '_root'
        for f in files:
            if f.lower().endswith(('.pdf','.docx','.doc')):
                items.append((cat, os.path.join(root, f), f))
    return items

def md5_full(path):
    try:
        h = hashlib.md5()
        with open(path,'rb') as fp:
            while True:
                chunk = fp.read(1024*1024)
                if not chunk: break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ''

def extract_pdf(path, max_pages=5):
    try:
        with pdfplumber.open(path) as pdf:
            pages = pdf.pages[:max_pages]
            texts = []
            for p in pages:
                try:
                    t = p.extract_text() or ''
                    texts.append(t)
                except Exception:
                    pass
            return '\n'.join(texts), len(pdf.pages)
    except Exception as e:
        return f'__ERR__{e}', 0

def process(item):
    cat, path, fname = item
    size = 0
    try:
        size = os.path.getsize(path)
    except Exception:
        pass
    ext = os.path.splitext(fname)[1].lower()
    if ext == '.pdf':
        text, npages = extract_pdf(path)
        if text.startswith('__ERR__'):
            status = 'extract_err'
            reason = text[7:200]
            text = ''
        elif len(text.strip()) < 30:
            status = 'no_text'
            reason = 'empty or too short'
            text = text.strip()
        else:
            status = 'ok'
            reason = ''
    else:
        # docx/doc — skip text extraction, mark for later
        text, npages = '', 0
        status = 'docx'
        reason = 'not pdf'
    return {
        'src_category': cat,
        'src_path': path,
        'filename': fname,
        'size': size,
        'pages': npages,
        'md5': md5_full(path),
        'text': text[:8000],  # 앞 8KB만 저장
        'status': status,
        'reason': reason,
    }

def main():
    items = collect()
    print(f'발견: {len(items)}건')
    # 체크포인트 로드
    done = set()
    if os.path.exists(CKPT):
        with open(CKPT,'r',encoding='utf-8') as f:
            done = set(json.load(f))
        print(f'체크포인트: {len(done)}건 완료')
    remaining = [it for it in items if it[1] not in done]
    print(f'남은 작업: {len(remaining)}건')
    # append 모드
    mode = 'a' if done else 'w'
    ok = 0; no_text = 0; err = 0; docx = 0
    with open(OUT, mode, encoding='utf-8') as fout:
        with ThreadPoolExecutor(max_workers=16) as ex:
            futs = {ex.submit(process, it): it for it in remaining}
            for i, fut in enumerate(as_completed(futs), 1):
                r = fut.result()
                fout.write(json.dumps(r, ensure_ascii=False) + '\n')
                done.add(r['src_path'])
                if r['status'] == 'ok': ok += 1
                elif r['status'] == 'no_text': no_text += 1
                elif r['status'] == 'docx': docx += 1
                else: err += 1
                if i % 100 == 0:
                    print(f'  진행 {i}/{len(remaining)} (ok={ok}, no_text={no_text}, docx={docx}, err={err})')
                    # 체크포인트 저장
                    with open(CKPT,'w',encoding='utf-8') as cf:
                        json.dump(list(done), cf)
    # 최종 체크포인트
    with open(CKPT,'w',encoding='utf-8') as cf:
        json.dump(list(done), cf)
    print(f'\n=== Step 1 완료 ===')
    print(f'  ok: {ok}')
    print(f'  no_text: {no_text}')
    print(f'  docx: {docx}')
    print(f'  err: {err}')
    print(f'  출력: {OUT}')

if __name__ == '__main__':
    main()
