# -*- coding: utf-8 -*-
"""Phase 2b: Unknown 27건 OCR 재스캔 (PyMuPDF 렌더 + EasyOCR)"""
import os, sys, io, csv, json, re, warnings
warnings.filterwarnings('ignore')

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import fitz  # pymupdf
import numpy as np
from PIL import Image

SRC_DIR = r'C:\MES\wta-agents\data\manuals-ready\2_sensor'
CSV_IN = r'C:\MES\wta-agents\workspaces\docs-agent\2_sensor_unknown_27.csv'
CSV_OUT = r'C:\MES\wta-agents\workspaces\docs-agent\2_sensor_ocr_rescan_result.csv'
LOG_OUT = r'C:\MES\wta-agents\workspaces\docs-agent\2_sensor_ocr_rescan_log.json'

# scan_sensor_pdfs.py의 키워드 재사용
sys.path.insert(0, os.path.dirname(__file__))
from scan_sensor_pdfs import (
    MFR_CANONICAL, DOCTYPE_KEYWORDS, NON_SENSOR_HINTS,
    MODEL_PREFIX_MFR, infer_mfr_by_model,
    detect_language, detect_doctype, check_sensor_category,
)

print('EasyOCR 초기화 중...(ko+en, CPU)')
import easyocr
reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)
print('OCR 준비 완료')

def render_page(pdf_path, page_no=0, dpi=200):
    with fitz.open(pdf_path) as doc:
        if page_no >= len(doc):
            return None
        page = doc[page_no]
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        return np.array(img)

def ocr_first_pages(pdf_path, max_pages=2):
    texts = []
    for i in range(max_pages):
        img = render_page(pdf_path, i)
        if img is None:
            break
        try:
            result = reader.readtext(img, detail=0, paragraph=True)
            texts.append('\n'.join(result))
        except Exception as e:
            texts.append(f'[ocr_err {e}]')
    return '\n'.join(texts)

def detect_mfr(text):
    t = (text or '').lower()
    for key, canon in MFR_CANONICAL.items():
        if len(key) <= 2:
            if re.search(r'\b' + re.escape(key) + r'\b', t):
                return canon
        else:
            if key in t:
                return canon
    return ''

def extract_model(text):
    if not text:
        return ''
    lines = [l.strip() for l in text.split('\n') if l.strip()][:30]
    for line in lines:
        if len(line) > 120: continue
        m = re.search(r'\b([A-Z][A-Z0-9][\w\-/]{2,25})\b', line)
        if m:
            cand = m.group(1)
            if cand.lower() not in ('manual','user','guide','installation','service','system','series','version','time','din2','mtbf'):
                return cand
    return ''

def confidence(mfr, model, text):
    if not text or len(text) < 50:
        return 'low'
    if mfr and model:
        return 'high'
    if mfr or model:
        return 'medium'
    return 'low'

# 입력 로드
with open(CSV_IN, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

print(f'{len(rows)}건 OCR 재스캔 시작')

results = []
for i, r in enumerate(rows, 1):
    old = r['old_filename']
    path = os.path.join(SRC_DIR, old)
    print(f'  [{i}/{len(rows)}] {old}')
    if not os.path.exists(path):
        results.append({**r, 'ocr_text_sample':'', 'new_manufacturer':'', 'new_model':'', 'new_doctype':'', 'new_lang':'', 'confidence':'low', 'status':'file_missing'})
        continue
    try:
        text = ocr_first_pages(path, max_pages=2)
    except Exception as e:
        results.append({**r, 'ocr_text_sample':'', 'new_manufacturer':'', 'new_model':'', 'new_doctype':'', 'new_lang':'', 'confidence':'low', 'status':f'failed_ocr: {e}'})
        continue
    sample = (text or '')[:200].replace('\n',' ').replace('\r',' ')
    mfr = detect_mfr(text)
    model = extract_model(text)
    if not mfr:
        mfr = infer_mfr_by_model(model)
    doctype = detect_doctype(text, old)
    lang = detect_language(text)
    conf = confidence(mfr, model, text)
    status = 'ambiguous' if conf != 'high' else 'success'
    if not text or len(text) < 30:
        status = 'failed_ocr'
    results.append({
        'old_filename': old,
        'ocr_text_sample': sample,
        'new_manufacturer': mfr,
        'new_model': model,
        'new_doctype': doctype,
        'new_lang': lang,
        'confidence': conf,
        'status': status,
    })

# CSV 저장
with open(CSV_OUT, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['old_filename','ocr_text_sample','new_manufacturer','new_model','new_doctype','new_lang','confidence','status'])
    w.writeheader()
    for r in results:
        w.writerow(r)

# 자동 rename 대상 (high only)
auto_rename = []
for r in results:
    if r['confidence'] == 'high' and r['status'] == 'success' and r['new_manufacturer'] and r['new_model']:
        mfr = r['new_manufacturer']
        model = r['new_model']
        dt = r['new_doctype'] or 'Manual'
        lang = r['new_lang'] or 'EN'
        new_name = f'{mfr}_{model}_{dt}_{lang}.pdf'
        new_name = re.sub(r'[^\w\-.]', '-', new_name)
        auto_rename.append({'old': r['old_filename'], 'new': new_name})

# 실제 rename 실행
from datetime import datetime, timezone, timedelta
KST = timezone(timedelta(hours=9))
def now(): return datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')

existing = set(os.listdir(SRC_DIR))
log = []
success = 0
for item in auto_rename:
    old = item['old']
    new = item['new']
    old_abs = os.path.join(SRC_DIR, old)
    if not os.path.exists(old_abs):
        log.append({'old': old, 'new': new, 'ts': now(), 'status':'error', 'reason':'missing'})
        continue
    final = new
    if final in existing and final != old:
        base, ext = os.path.splitext(new)
        idx = 2
        while True:
            cand = f'{base}_v{idx}{ext}'
            if cand not in existing:
                final = cand
                break
            idx += 1
    new_abs = os.path.join(SRC_DIR, final)
    try:
        os.rename(old_abs, new_abs)
        existing.discard(old); existing.add(final)
        log.append({'old':old,'new':final,'ts':now(),'status':'success'})
        success += 1
    except Exception as e:
        log.append({'old':old,'new':final,'ts':now(),'status':'error','reason':str(e)})

with open(LOG_OUT, 'w', encoding='utf-8') as f:
    json.dump({
        'phase':'2b',
        'executed_at':now(),
        'total_rescanned':len(results),
        'auto_renamed':success,
        'auto_rename_candidates':len(auto_rename),
        'entries':log,
    }, f, ensure_ascii=False, indent=2)

# 요약
high = sum(1 for r in results if r['confidence']=='high')
medium = sum(1 for r in results if r['confidence']=='medium')
low = sum(1 for r in results if r['confidence']=='low')
failed = sum(1 for r in results if r['status']=='failed_ocr')

print(f'\n=== Phase 2b 결과 ===')
print(f'총 {len(results)}건')
print(f'confidence high: {high} / medium: {medium} / low: {low}')
print(f'failed_ocr: {failed}')
print(f'auto rename 실행: {success}건')
print(f'CSV: {CSV_OUT}')
print(f'로그: {LOG_OUT}')
