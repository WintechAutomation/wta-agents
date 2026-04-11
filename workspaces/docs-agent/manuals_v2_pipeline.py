# -*- coding: utf-8 -*-
"""manuals-v2 파이프라인 (카테고리 단위 end-to-end)

사용법:
  python manuals_v2_pipeline.py 2_sensor
  python manuals_v2_pipeline.py all   # 2_sensor~8_etc 전체

단계:
  1) PDF 텍스트 추출 (앞 5페이지, 8KB)
  2) md5 기준 중복 제거
  3) 룰 기반 분류 (제조사/모델/DocType/Lang)
  4) manuals-v2/{cat}/ 에 표준명으로 복사
  5) CSV 저장
"""
import os, sys, io, json, re, hashlib, shutil, csv, warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pdfplumber

SRC_ROOT = r'C:\MES\wta-agents\data\manuals'
DST_ROOT = r'C:\MES\wta-agents\data\manuals-v2'
WORK = r'C:\MES\wta-agents\workspaces\docs-agent'

CATEGORIES = ['1_robot','2_sensor','3_hmi','4_servo','5_inverter','6_plc','7_pneumatic','8_etc']

# ============ 제조사 키워드 (본문 우선) ============
MFR_BODY_KEYWORDS = [
    # (정규식 - case insensitive, 표준명)
    (r'미쓰비시\s*전기|Mitsubishi\s*Electric|MELFA|MITSUBISHI|三菱電機', 'Mitsubishi'),
    (r'YASKAWA|야스카와|安川', 'Yaskawa'),
    (r'KEYENCE|キーエンス|키엔스', 'Keyence'),
    (r'Panasonic|파나소닉|松下', 'Panasonic'),
    (r'OMRON|オムロン|옴론', 'Omron'),
    (r'ABB\s*(?:Robotics|ROBOTICS|\b)', 'ABB'),
    (r'Cognex|In-Sight', 'Cognex'),
    (r'Hyundai\s*Robotics|현대로보틱스|현대중공업', 'Hyundai'),
    (r'FANUC|화낙', 'Fanuc'),
    (r'KUKA', 'Kuka'),
    (r'SMC\s*Corporation|SMC\s*코퍼레이션', 'SMC'),
    (r'Festo|페스토', 'Festo'),
    (r'Schneider\s*Electric|슈나이더', 'Schneider'),
    (r'Siemens|SIMATIC|지멘스', 'Siemens'),
    (r'Allen-?Bradley|Rockwell', 'Rockwell'),
    (r'Delta\s*Electronics|델타\s*일렉트로닉', 'Delta'),
    (r'LS\s*Industrial|LSIS|LS\s*일렉트릭|LS\s*ELECTRIC|엘에스산전', 'LS'),
    (r'Sanyo\s*Denki|Sanmotion|山洋電気', 'Sanyo'),
    (r'Yamaha\s*Motor|야마하', 'Yamaha'),
    (r'Videojet|비디오젯', 'Videojet'),
    (r'Honeywell|허니웰', 'Honeywell'),
    (r'Autonics|오토닉스', 'Autonics'),
    (r'Balluff|발루프', 'Balluff'),
    (r'IFM\s*Electronic|이에프엠', 'IFM'),
    (r'Pepperl\s*\+?\s*Fuchs|페퍼플', 'PepperlFuchs'),
    (r'Turck|턱크', 'Turck'),
    (r'Wenglor', 'Wenglor'),
    (r'Banner\s*Engineering', 'Banner'),
    (r'Leuze', 'Leuze'),
    (r'Weidmuller|바이드뮐러', 'Weidmuller'),
    (r'Phoenix\s*Contact|피닉스', 'Phoenix'),
    (r'Moxa|목사', 'Moxa'),
    (r'Advantech|어드밴텍', 'Advantech'),
]
MFR_RE_LIST = [(re.compile(p, re.I), m) for p, m in MFR_BODY_KEYWORDS]

# 파일명 prefix → 제조사
MODEL_PREFIX_MFR = [
    (re.compile(r'^(AL|CA|CV|DL|DF|EM|FD|FS|FU|GT2|HL-G|IA|IB|IG|IL|IM|IV|IX|KV|LJ|LK|LR-[TXZ]|LS-|LT|LV|MD-X|MK|ML|MR|NA|NR|OP|PJ|PN|PS|PZ|SJ|SL|SR|ST-|TM|UD|VF|VT|XG|XT|GL-R)', re.I), 'Keyence'),
    (re.compile(r'^(CX-|EX-|FT-|FX-|GA-|GS-|GU-|GX-|HG-|LA-|LG-|LX-|NX-|PM-|RX-|SU-|UX-|EZ-|CN-|ER-)', re.I), 'Panasonic'),
    (re.compile(r'^(E3[A-Z]|E2[A-Z]|F3S|F39|V400|V530|Z4[A-Z])', re.I), 'Omron'),
    (re.compile(r'^(VJ|CLARiTY)', re.I), 'Videojet'),
    (re.compile(r'^XENON', re.I), 'Honeywell'),
    (re.compile(r'^(IS|DM|AW000)', re.I), 'Cognex'),
    (re.compile(r'^(IRB|3HAC)', re.I), 'ABB'),
    (re.compile(r'^(UP|VS|J1000|V1000|XRC)', re.I), 'Yaskawa'),
    (re.compile(r'^(RV-|RH-|RP-|CRn|CR1|CR2|CR3|CR4|CR7|CR8|CR9|CR750|CR751|CR800|BFP-A|MELFA|Mitsubishi)', re.I), 'Mitsubishi'),
    (re.compile(r'^(SANMOTION|Sanmotion)', re.I), 'Sanyo'),
]

# ============ DocType 키워드 (본문 + 파일명) ============
DOCTYPE_KEYWORDS = [
    (r'(?:트러블|Trouble\s*shooting|Troubleshooting)', 'Troubleshooting'),
    (r'(?:Quick\s*Start|빠른\s*시작)', 'QuickStart'),
    (r'(?:카탈로그|카타로그|Catalog|Catalogue|綜合)', 'Catalog'),
    (r'(?:User[\'’]?s?\s*Manual|사용자\s*매뉴얼)', 'UserManual'),
    (r'(?:Standard\s*Specifications|표준사양서|標準仕様書)', 'StandardSpec'),
    (r'(?:Setup|セットアップ|셋[-\s]*업|셋업|설정과)', 'SetupGuide'),
    (r'(?:Maintenance|保守|유지보수|취급설명서)', 'MaintenanceManual'),
    (r'(?:Install(?:ation)?\s*Guide|설치\s*안내)', 'InstallGuide'),
    (r'(?:Operation\s*Manual|조작설명|操作説明|Instruction\s*Manual)', 'OperationManual'),
    (r'(?:Product\s*Specification|제품\s*사양|ProductSpec)', 'ProductSpec'),
    (r'(?:Data\s*Sheet|Datasheet|데이터\s*시트)', 'Datasheet'),
    (r'(?:Parameter|파라미터)', 'ParameterManual'),
    (r'(?:Wiring|배선|結線)', 'WiringGuide'),
    (r'(?:Tracking|추적기능|トラッキング)', 'TrackingManual'),
    (r'(?:CC-?Link|CCLink)', 'CCLinkInterface'),
    (r'(?:Ethernet)', 'EthernetInterface'),
    (r'(?:RT\s*ToolBox)', 'RTToolBox'),
    (r'(?:MELFA-?Works)', 'MelfaWorks'),
]
DT_RE_LIST = [(re.compile(p, re.I), d) for p, d in DOCTYPE_KEYWORDS]

# ============ 표준명 파서 ============
STD_RE = re.compile(r'^(?P<mfr>[A-Z][A-Za-z]+)_(?P<model>[A-Za-z0-9\-\.]+)_(?P<dt>[A-Za-z]+)_(?P<lang>[A-Z]{2})(?:_\d+|_v\d+)?\.pdf$')

# BFP 코드 패턴 (Mitsubishi)
BFP_RE = re.compile(r'(BFP-?A\d{4,5})', re.I)
# 일반적 모델 패턴
MODEL_RE = re.compile(r'([A-Z]{1,4}-?\d{1,5}[A-Z]*)')

# ============ 유틸 ============
def md5_full(path):
    try:
        h = hashlib.md5()
        with open(path,'rb') as fp:
            while True:
                chunk = fp.read(1024*1024)
                if not chunk: break
                h.update(chunk)
        return h.hexdigest()
    except Exception: return ''

def extract_pdf(path, max_pages=5):
    try:
        with pdfplumber.open(path) as pdf:
            pages = pdf.pages[:max_pages]
            texts = []
            for p in pages:
                try:
                    t = p.extract_text() or ''
                    texts.append(t)
                except Exception: pass
            return '\n'.join(texts), len(pdf.pages)
    except Exception as e:
        return f'__ERR__{e}', 0

def cid_ratio(text):
    if not text: return 0.0
    cids = text.count('(cid:')
    return cids / max(len(text)/100, 1)

def detect_lang(text, fname=''):
    s = (text or '') + ' ' + fname
    ko = sum(1 for c in s if '\uac00' <= c <= '\ud7a3')
    ja = sum(1 for c in s if '\u3040' <= c <= '\u30ff')
    zh = sum(1 for c in s if '\u4e00' <= c <= '\u9fff')  # CJK han
    en = sum(1 for c in s if c.isascii() and c.isalpha())
    if ko > 20: return 'KO'
    if ja > 20: return 'JA'
    if zh > 50 and en < zh: return 'ZH'
    return 'EN'

def detect_mfr(text, fname):
    # 1) 본문 키워드
    for rx, m in MFR_RE_LIST:
        if rx.search(text or ''): return m
    # 2) 표준명 앞부분
    m = STD_RE.match(fname)
    if m: return m.group('mfr')
    # 3) 파일명 prefix
    fn_upper = fname.upper()
    for rx, m in MODEL_PREFIX_MFR:
        if rx.match(fname):
            return m
    return 'Unknown'

def detect_doctype(text, fname):
    # 본문 + 파일명 합쳐서 검색
    blob = (text or '') + ' ' + fname
    for rx, d in DT_RE_LIST:
        if rx.search(blob): return d
    m = STD_RE.match(fname)
    if m: return m.group('dt')
    return 'Manual'

def detect_model(text, fname, mfr):
    # 표준명 우선
    m = STD_RE.match(fname)
    if m: return m.group('model')
    # Mitsubishi BFP 코드
    if mfr == 'Mitsubishi':
        b = BFP_RE.search(fname) or BFP_RE.search(text or '')
        if b: return b.group(1).upper().replace('BFPA','BFP-A')
    # 파일명에서 첫 영숫자 토큰 (확장자 제외)
    stem = os.path.splitext(fname)[0]
    # 한글/공백 제거한 토큰 추출
    tokens = re.findall(r'[A-Za-z][A-Za-z0-9\-]{1,20}', stem)
    for t in tokens:
        if t.lower() not in ('pdf','manual','guide','spec','catalog','new','old','ver','kr','en','ko','jp','cn','backcover','title'):
            return t[:20]
    return 'Unknown'

# ============ Step 1: 추출 ============
def collect(cat):
    src = os.path.join(SRC_ROOT, cat)
    items = []
    for root, dirs, files in os.walk(src):
        for f in files:
            if f.lower().endswith(('.pdf','.docx','.doc')):
                items.append((cat, os.path.join(root, f), f))
    return items

def process_file(item):
    cat, path, fname = item
    try: size = os.path.getsize(path)
    except Exception: size = 0
    ext = os.path.splitext(fname)[1].lower()
    if ext == '.pdf':
        text, npages = extract_pdf(path)
        if text.startswith('__ERR__'):
            status = 'extract_err'; text = ''
        elif len(text.strip()) < 30:
            status = 'no_text'
        else:
            status = 'ok'
    else:
        text, npages = '', 0
        status = 'docx'
    return {
        'src_category': cat, 'src_path': path, 'filename': fname,
        'size': size, 'pages': npages, 'md5': md5_full(path),
        'text': text[:8000], 'status': status,
    }

def step1_extract(cat):
    items = collect(cat)
    print(f'[{cat}] 발견: {len(items)}건')
    rows = []
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(process_file, it): it for it in items}
        for i, fut in enumerate(as_completed(futs), 1):
            rows.append(fut.result())
            if i % 100 == 0:
                print(f'  extract {i}/{len(items)}')
    return rows

# ============ Step 2: dedup ============
def score_row(r):
    fn = r['filename']; s = 0
    if STD_RE.match(fn): s += 1000
    korean = sum(1 for c in fn if '\uac00' <= c <= '\ud7a3')
    s -= korean * 2
    s -= len(fn) * 0.1
    s += (r.get('size',0) / 10000)
    s += min(len(r.get('text','')), 3000) / 100
    return s

def step2_dedup(rows):
    by_md5 = defaultdict(list)
    for r in rows: by_md5[r['md5']].append(r)
    uniques = []; dups = []
    for md5, group in by_md5.items():
        if not md5: uniques.extend(group); continue
        group.sort(key=score_row, reverse=True)
        uniques.append(group[0])
        for r in group[1:]:
            r['dup_of'] = group[0]['filename']
            dups.append(r)
    return uniques, dups

# ============ Step 3/4: 분류 + 복사 ============
def classify(r):
    fn = r['filename']; text = r.get('text','') or ''
    if fn.lower().endswith(('.docx','.doc')):
        kind = 'docx'
    elif cid_ratio(text) > 3.0 or len(text.strip()) < 50:
        kind = 'ocr'  # CID 바이너리 또는 텍스트 없음
    else:
        kind = 'ok'
    mfr = detect_mfr(text, fn)
    dt  = detect_doctype(text, fn)
    mdl = detect_model(text, fn, mfr)
    lg  = detect_lang(text, fn)
    return kind, mfr, mdl, dt, lg

def build_name(mfr, model, dt, lg, ext, existing):
    base = f'{mfr}_{model}_{dt}_{lg}{ext}'
    if base not in existing:
        existing.add(base); return base
    for i in range(2, 50):
        c = f'{mfr}_{model}_{dt}_{lg}_v{i}{ext}'
        if c not in existing:
            existing.add(c); return c
    existing.add(base); return base

def step34_copy(cat, uniques, dups):
    dst_ok   = os.path.join(DST_ROOT, cat)
    dst_ocr  = os.path.join(DST_ROOT, '_filtered', 'ocr_needed', cat)
    dst_docx = os.path.join(DST_ROOT, '_filtered', 'docx', cat)
    dst_dup  = os.path.join(DST_ROOT, '_filtered', 'duplicate', cat)
    for d in [dst_ok, dst_ocr, dst_docx, dst_dup]:
        os.makedirs(d, exist_ok=True)

    ex_ok=set(); ex_ocr=set(); ex_docx=set(); ex_dup=set()
    rows_csv = []
    stats = {'ok':0,'ocr':0,'docx':0,'dup':0,'error':0}
    mfr_count = defaultdict(int)

    for i, r in enumerate(uniques, 1):
        kind, mfr, mdl, dt, lg = classify(r)
        ext = os.path.splitext(r['filename'])[1]
        if kind == 'ok':
            new = build_name(mfr, mdl, dt, lg, ext, ex_ok); dst_dir = dst_ok
        elif kind == 'ocr':
            new = build_name(mfr, mdl, dt, lg, ext, ex_ocr); dst_dir = dst_ocr
        elif kind == 'docx':
            new = build_name(mfr, mdl, dt, lg, ext, ex_docx); dst_dir = dst_docx
        else:
            new = build_name(mfr, mdl, dt, lg, ext, ex_ok); dst_dir = dst_ok
        try:
            shutil.copy2(r['src_path'], os.path.join(dst_dir, new))
            stats[kind] += 1
            if kind == 'ok': mfr_count[mfr] += 1
        except Exception as e:
            stats['error'] += 1; print(f'  ERR {r["filename"]}: {e}'); new = ''
        rows_csv.append({
            'idx': i, 'status': kind, 'category': cat,
            'old_filename': r['filename'], 'new_filename': new,
            'mfr': mfr, 'model': mdl, 'doctype': dt, 'lang': lg,
            'size': r.get('size',0), 'pages': r.get('pages',0), 'md5': r.get('md5',''),
        })

    # 중복 복사
    for r in dups:
        fn = r['filename']; base = fn
        if base in ex_dup:
            n, e = os.path.splitext(fn); idx = 2
            while f'{n}_dup{idx}{e}' in ex_dup: idx += 1
            base = f'{n}_dup{idx}{e}'
        ex_dup.add(base)
        try:
            shutil.copy2(r['src_path'], os.path.join(dst_dup, base))
            stats['dup'] += 1
        except Exception as e:
            stats['error'] += 1

    return rows_csv, stats, mfr_count

def run_category(cat):
    print(f'\n=========== {cat} ===========')
    rows = step1_extract(cat)
    # JSONL 저장
    ext_jsonl = os.path.join(WORK, f'manuals_v2_{cat}_extract.jsonl')
    with open(ext_jsonl,'w',encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False)+'\n')
    uniques, dups = step2_dedup(rows)
    print(f'[{cat}] unique={len(uniques)} dup={len(dups)}')
    rows_csv, stats, mfr_count = step34_copy(cat, uniques, dups)
    # CSV
    csv_path = os.path.join(WORK, f'manuals_v2_{cat}_classification.csv')
    with open(csv_path,'w',encoding='utf-8-sig',newline='') as f:
        w = csv.DictWriter(f, fieldnames=['idx','status','category','old_filename','new_filename','mfr','model','doctype','lang','size','pages','md5'])
        w.writeheader(); w.writerows(rows_csv)
    print(f'[{cat}] 완료: {stats}')
    top_mfr = sorted(mfr_count.items(), key=lambda x:-x[1])[:10]
    print(f'[{cat}] 제조사 Top10: {top_mfr}')
    return {'category':cat, 'total':len(rows), 'unique':len(uniques), 'dup':len(dups), 'stats':stats, 'top_mfr':top_mfr}

if __name__ == '__main__':
    targets = sys.argv[1:] if len(sys.argv) > 1 else ['all']
    if targets == ['all']:
        targets = ['2_sensor','3_hmi','4_servo','5_inverter','6_plc','7_pneumatic','8_etc']
    summary = []
    for cat in targets:
        if cat not in CATEGORIES:
            print(f'skip unknown category: {cat}'); continue
        summary.append(run_category(cat))
    # 요약 저장
    with open(os.path.join(WORK,'manuals_v2_summary.json'),'w',encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print('\n=== 전체 요약 ===')
    for s in summary:
        print(f'  {s["category"]}: total={s["total"]} unique={s["unique"]} dup={s["dup"]} stats={s["stats"]}')
