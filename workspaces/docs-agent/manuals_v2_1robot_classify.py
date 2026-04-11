# -*- coding: utf-8 -*-
"""1_robot 분류 + 복사 스크립트 (sonnet 판독 기반)

입력:
  - manuals_v2_1robot_unique.jsonl (111건)
  - manuals_v2_1robot_duplicates.jsonl (88건)

출력:
  - data/manuals-v2/1_robot/{Mfr}_{Model}_{DocType}_{Lang}.pdf (유효)
  - data/manuals-v2/_filtered/duplicate/ (88건)
  - data/manuals-v2/_filtered/ocr_needed/ (CID 바이너리)
  - data/manuals-v2/_filtered/docx/ (DOCX)
  - manuals_v2_1robot_classification.csv (분류 결과)
"""
import os, sys, io, json, re, shutil, csv
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

UNIQUE = r'C:\MES\wta-agents\workspaces\docs-agent\manuals_v2_1robot_unique.jsonl'
DUPS   = r'C:\MES\wta-agents\workspaces\docs-agent\manuals_v2_1robot_duplicates.jsonl'
CSV_OUT= r'C:\MES\wta-agents\workspaces\docs-agent\manuals_v2_1robot_classification.csv'

DST_ROOT = r'C:\MES\wta-agents\data\manuals-v2'
DST_OK   = os.path.join(DST_ROOT, '1_robot')
DST_DUP  = os.path.join(DST_ROOT, '_filtered', 'duplicate', '1_robot')
DST_OCR  = os.path.join(DST_ROOT, '_filtered', 'ocr_needed', '1_robot')
DST_DOCX = os.path.join(DST_ROOT, '_filtered', 'docx', '1_robot')

for d in [DST_OK, DST_DUP, DST_OCR, DST_DOCX]:
    os.makedirs(d, exist_ok=True)

# ============ 수동 분류 오버라이드 (111 unique 파일) ============
# 파일명 → (mfr, model, doctype, lang)
# sonnet(나)가 텍스트 본문/파일명 판독 후 확정
MANUAL_OVERRIDE = {
    # Mitsubishi BFP-A* 이미 표준화된 파일들 — 기존 네이밍 유지
    # 외부에서 받은 원본 파일들 주력으로 처리

    # ABB
    '3HAC029963 PS IRB 360-en.pdf': ('ABB','IRB360','ProductSpec','EN'),

    # Cognex In-Sight 5000
    '597-0028-04.pdf': ('Cognex','IS5000','QuickStart','EN'),
    '597-0027-06KO.pdf': ('Cognex','IS5000','QuickStart','KO'),

    # Mitsubishi BFP 코드 추출형 원본 파일들 (OCR 대상 일부 포함)
    'BASIC-INSTRUCTION-LIST.PDF': ('Mitsubishi','CRn','InstructionList','EN'),  # CID binary → OCR 필요
    'bfp-a8108d_Series Ethernet Interface.pdf': ('Mitsubishi','BFP-A8108','EthernetInterface','EN'),
    'bfp-a8614j_추적기능매뉴얼 .pdf': ('Mitsubishi','BFP-A8614','TrackingManual','JA'),
    'bfp-a8659Z.pdf': ('Mitsubishi','BFP-A8659','SetupGuide','EN'),
    'bfp-a8525g.pdf': ('Mitsubishi','BFP-A8525','MelfaWorks','EN'),
    'bfp-a8662b.pdf': ('Mitsubishi','BFP-A8662','Troubleshooting','EN'),
    'bfp-a8661a.pdf': ('Mitsubishi','BFP-A8661','OperationManual','EN'),
    'bfp-a8660a.pdf': ('Mitsubishi','BFP-A8660','SetupGuide','EN'),
    'bfp-a8658Z.pdf': ('Mitsubishi','BFP-A8658','StandardSpec','EN'),
    'bfp-a8885n_NewCR750-QCR751-Q 컨트롤러 설명서 컨트롤러 설정과 기본 조작 에서 보수까지.pdf':
        ('Mitsubishi','BFP-A8885','SetupGuide','JA'),
    'bfp-a8868p_NewCR750CR751 컨트롤러 설명서 기능 과 조작의 상세 해설.pdf':
        ('Mitsubishi','BFP-A8868','OperationManual','JA'),
    'bfp-a8587p_부가축제어 매뉴얼.pdf': ('Mitsubishi','BFP-A8587','AdditionalAxis','JA'),

    'CC-LINK인터페이스(CR750-D_CR751-D컨트롤러).pdf':
        ('Mitsubishi','BFP-A8615','CCLinkInterface','KO'),
    'RV-4F 매뉴얼 (일문).pdf': ('Mitsubishi','RV-4F','StandardSpec','JA'),
    'RH-6SH.12SH.18SH-J0506.pdf': ('Mitsubishi','RH-6SH','Catalog','JA'),
    '비젼센서 취급설명서 BFP-A8476B-1.1.pdf':
        ('Mitsubishi','BFP-A8476','VisionSensorManual','KO'),
    '종합카타로그-MITSUBISHI.pdf': ('Mitsubishi','Comprehensive','Catalog','KO'),  # CID → OCR 필요
    '미쓰비시 로봇 카탈로그.pdf': ('Mitsubishi','Robot','Catalog','KO'),           # CID → OCR 필요

    # Yaskawa
    'Sanmotion R Advanced Model.pdf': ('Sanyo','SanmotionR','ProductSpec','EN'),
    'V1000매뉴얼(국문).pdf': ('Yaskawa','V1000','TechnicalManual','KO'),

    # LS
    'LS_SANMOTION_SetupGuide_EN.pdf': ('LS','SANMOTION','InstructionManual','EN'),
    'LS_SPOT-CHAPTER4_Manual_EN.pdf': ('LS','SPOT-CH4','Manual','EN'),  # CID → OCR
    'LS_Unknown_Datasheet_EN.pdf':    ('LS','DeltaRobot','Datasheet','EN'),
}

# DOCX는 별도 처리
DOCX_CLASSIFY = {
    '야스카와 인버터 J1000 기본셋업 (IO제어,가감속).docx': ('Yaskawa','J1000','SetupGuide','KO'),
    '원점설정 방법.docx': ('Mitsubishi','Generic','OriginSetup','KO'),
    '인버터 셋업 방법(V1000).docx': ('Yaskawa','V1000','SetupGuide','KO'),
}

# ============ 자동 분류 (이미 표준명인 파일 처리) ============
STD_RE = re.compile(r'^(?P<mfr>[A-Z][A-Za-z]+)_(?P<model>[A-Za-z0-9\-]+)_(?P<dt>[A-Za-z]+)_(?P<lang>[A-Z]{2})(?:_\d+|_v\d+)?\.pdf$')

def cid_ratio(text):
    if not text: return 0
    cids = text.count('(cid:')
    return cids / max(len(text)/10, 1)  # 거칠게

def detect_lang(text):
    if not text: return 'EN'
    ko = sum(1 for c in text if '\uac00' <= c <= '\ud7a3')
    ja = sum(1 for c in text if '\u3040' <= c <= '\u30ff' or '\u4e00' <= c <= '\u9fff')
    en = sum(1 for c in text if c.isascii() and c.isalpha())
    if ko > ja and ko > en/5: return 'KO'
    if ja > en/5: return 'JA'
    return 'EN'

def classify_file(r):
    """우선순위: 수동 override → 표준명 파싱 → 실패(unknown)"""
    fn = r['filename']
    text = r.get('text','') or ''

    # 1) DOCX
    if fn.lower().endswith(('.docx','.doc')):
        if fn in DOCX_CLASSIFY:
            mfr,mdl,dt,lg = DOCX_CLASSIFY[fn]
            return ('docx', mfr, mdl, dt, lg)
        return ('docx','Unknown','Unknown','Manual','KO')

    # 2) CID 바이너리 (OCR 필요)
    cr = cid_ratio(text)
    if cr > 5.0:  # 매우 많은 cid
        if fn in MANUAL_OVERRIDE:
            mfr,mdl,dt,lg = MANUAL_OVERRIDE[fn]
            return ('ocr', mfr, mdl, dt, lg)
        return ('ocr','Unknown','Unknown','Manual','EN')

    # 3) 수동 override
    if fn in MANUAL_OVERRIDE:
        mfr,mdl,dt,lg = MANUAL_OVERRIDE[fn]
        return ('ok', mfr, mdl, dt, lg)

    # 4) 이미 표준명
    m = STD_RE.match(fn)
    if m:
        return ('ok', m.group('mfr'), m.group('model'), m.group('dt'), m.group('lang'))

    # 5) fallback
    return ('unknown','Unknown','Unknown','Manual',detect_lang(text))

def build_new_name(mfr, model, dt, lang, existing):
    base = f'{mfr}_{model}_{dt}_{lang}.pdf'
    if base not in existing:
        existing.add(base); return base
    for i in range(2, 20):
        cand = f'{mfr}_{model}_{dt}_{lang}_v{i}.pdf'
        if cand not in existing:
            existing.add(cand); return cand
    return base

# ============ 메인 ============
uniques = []
with open(UNIQUE,'r',encoding='utf-8') as f:
    for line in f: uniques.append(json.loads(line))

dups = []
with open(DUPS,'r',encoding='utf-8') as f:
    for line in f: dups.append(json.loads(line))

print(f'Unique: {len(uniques)}, Dups: {len(dups)}')

rows_csv = []
stats = {'ok':0,'ocr':0,'docx':0,'unknown':0,'dup':0,'error':0}
existing_ok = set()
existing_ocr = set()
existing_docx = set()
existing_dup = set()

# --- unique 처리 ---
for i, r in enumerate(uniques, 1):
    kind, mfr, mdl, dt, lg = classify_file(r)
    src = r['src_path']
    if kind == 'ok':
        new = build_new_name(mfr, mdl, dt, lg, existing_ok)
        dst_dir = DST_OK
    elif kind == 'ocr':
        new = build_new_name(mfr, mdl, dt, lg, existing_ocr)
        dst_dir = DST_OCR
    elif kind == 'docx':
        # 확장자 유지
        ext = os.path.splitext(r['filename'])[1]
        base = f'{mfr}_{mdl}_{dt}_{lg}{ext}'
        idx = 2
        while base in existing_docx:
            base = f'{mfr}_{mdl}_{dt}_{lg}_v{idx}{ext}'; idx += 1
        existing_docx.add(base); new = base
        dst_dir = DST_DOCX
    else:
        new = build_new_name(mfr, mdl, dt, lg, existing_ok)
        dst_dir = DST_OCR  # unknown은 OCR 폴더로 격리

    dst = os.path.join(dst_dir, new)
    try:
        shutil.copy2(src, dst)
        stats[kind if kind in stats else 'unknown'] += 1
    except Exception as e:
        stats['error'] += 1
        print(f'  ERR {r["filename"]}: {e}')
        new = ''

    rows_csv.append({
        'idx': i,
        'status': kind,
        'src_category': r.get('src_category',''),
        'old_filename': r['filename'],
        'new_filename': new,
        'dst_folder': dst_dir,
        'mfr': mfr, 'model': mdl, 'doctype': dt, 'lang': lg,
        'size': r.get('size',0),
        'pages': r.get('pages',0),
        'md5': r.get('md5',''),
    })
    if i % 50 == 0:
        print(f'  progress: {i}/{len(uniques)} ok={stats["ok"]} ocr={stats["ocr"]} docx={stats["docx"]}')

# --- 중복 처리 ---
for r in dups:
    src = r['src_path']
    fn = r['filename']
    # 중복은 원본 이름 유지 (+ 필요 시 suffix)
    base = fn
    if base in existing_dup:
        n, ext = os.path.splitext(fn); idx = 2
        while f'{n}_dup{idx}{ext}' in existing_dup: idx += 1
        base = f'{n}_dup{idx}{ext}'
    existing_dup.add(base)
    dst = os.path.join(DST_DUP, base)
    try:
        shutil.copy2(src, dst)
        stats['dup'] += 1
    except Exception as e:
        stats['error'] += 1
        print(f'  DUP ERR {fn}: {e}')

# --- CSV 저장 ---
with open(CSV_OUT,'w',encoding='utf-8-sig',newline='') as f:
    w = csv.DictWriter(f, fieldnames=['idx','status','src_category','old_filename','new_filename','dst_folder','mfr','model','doctype','lang','size','pages','md5'])
    w.writeheader()
    w.writerows(rows_csv)

print(f'\n=== 완료 ===')
for k,v in stats.items():
    print(f'  {k}: {v}')
print(f'CSV: {CSV_OUT}')
print(f'OK:    {DST_OK}')
print(f'OCR:   {DST_OCR}')
print(f'DOCX:  {DST_DOCX}')
print(f'DUP:   {DST_DUP}')
