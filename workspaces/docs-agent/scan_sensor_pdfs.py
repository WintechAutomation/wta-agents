# -*- coding: utf-8 -*-
"""2_sensor 폴더 137개 PDF 전수 분석 → rename plan CSV 생성"""
import os, sys, io, re, csv, json
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pdfplumber

SRC_DIR = r'C:\MES\wta-agents\data\manuals-ready\2_sensor'
OUT_CSV = r'C:\MES\wta-agents\workspaces\docs-agent\2_sensor_rename_plan.csv'
OUT_JSON = r'C:\MES\wta-agents\workspaces\docs-agent\2_sensor_rename_plan.json'

# --- 제조사 표준 표기 사전 ---
MFR_CANONICAL = {
    'abb': 'ABB', 'panasonic': 'Panasonic', '파나소닉': 'Panasonic',
    'mitsubishi': 'Mitsubishi', '미쓰비시': 'Mitsubishi',
    'keyence': 'Keyence', '키엔스': 'Keyence',
    'omron': 'Omron', '옴론': 'Omron',
    'sick': 'SICK', 'sensick': 'SICK',
    'cognex': 'Cognex', 'basler': 'Basler',
    'fastech': 'Fastech', '파스텍': 'Fastech',
    'pilz': 'Pilz', 'baumer': 'Baumer',
    'banner': 'Banner', 'datalogic': 'Datalogic',
    'balluff': 'Balluff', 'leuze': 'Leuze',
    'ifm': 'IFM', 'turck': 'Turck', 'festo': 'Festo',
    'smc': 'SMC', 'wago': 'WAGO', 'beckhoff': 'Beckhoff',
    'yaskawa': 'Yaskawa', '야스카와': 'Yaskawa',
    'delta': 'Delta', 'lsis': 'LSIS', 'ls': 'LSIS',
    'dalsa': 'Teledyne DALSA', 'teledyne': 'Teledyne DALSA',
    'hikrobot': 'Hikrobot', 'hikvision': 'Hikvision',
    'kowa': 'Kowa', 'computar': 'Computar',
    'fanuc': 'FANUC', 'siemens': 'Siemens',
    'yokogawa': 'Yokogawa', 'rockwell': 'Rockwell',
    'allen-bradley': 'Rockwell', 'ab': 'Rockwell',
    'autonics': 'Autonics', '오토닉스': 'Autonics',
    'hanyoung': 'Hanyoung', '한영': 'Hanyoung',
    'panasonic-id': 'Panasonic', 'neff': 'NEFF',
    'ni': 'National Instruments',
    'moritex': 'Moritex', 'ccs': 'CCS',
    'effector': 'Effector', 'sunx': 'SUNX',
    'optex': 'OPTEX',
}

# 문서유형 키워드
DOCTYPE_KEYWORDS = [
    ('UserManual', ['user manual', 'user\'s manual', 'users manual', 'operator manual', '사용설명서', '사용자 매뉴얼', '취급설명서', 'operating instructions']),
    ('InstallGuide', ['installation', 'install guide', '설치설명서', '설치 가이드', 'mounting', 'getting started']),
    ('CommManual', ['communication', 'protocol', 'ethernet', 'ethercat', 'modbus', '통신', 'rs-232', 'rs232', 'rs-485', 'profinet']),
    ('ParameterManual', ['parameter', '파라미터']),
    ('MaintenanceManual', ['maintenance', 'service manual', '유지보수', '정비']),
    ('SetupGuide', ['setup', 'configuration', '셋업', '설정']),
    ('Datasheet', ['datasheet', 'data sheet', '데이터시트', 'specification', 'spec sheet']),
    ('Catalog', ['catalog', 'catalogue', '카탈로그']),
    ('ProgrammingManual', ['programming manual', '프로그래밍']),
    ('Manual', ['manual', '매뉴얼', '설명서']),
]

# 센서 카테고리 키워드 (category_valid 판정)
SENSOR_KEYWORDS = [
    'sensor', 'photoelectric', 'proximity', 'laser', 'vision', 'camera',
    'fiber optic', 'safety light', 'light curtain', 'encoder', 'barcode',
    'ultrasonic', 'infrared', 'displacement', 'distance', 'inductive',
    'capacitive', 'pressure', 'temperature', 'flow', 'level', 'strain',
    '센서', '광전', '근접', '레이저', '비전', '카메라', '광섬유',
    '안전', '엔코더', '바코드', '초음파', '적외선', '변위', '거리',
    'measurement', 'detector', 'optical', 'image processing', 'machine vision',
]

# 모델 접두어 기반 제조사 추정 (본문/파일명에서 제조사 미식별 시)
MODEL_PREFIX_MFR = [
    # Keyence
    (re.compile(r'^(AL|CA|CV|DL|DF|EM|FD|FS|FU|GT2|HL-G|IA|IB|IG|IL|IM|IV|IX|KV|LJ|LK|LR-[TXZ]|LS-|LT|LV|MD-X|MK|ML|MR|NA|NR|OP|PJ|PN|PS|PZ|SJ|SL|SR|ST-|TM|UD|VF|VT|XG|XT|GL-R)', re.I), 'Keyence'),
    # Panasonic (SUNX)
    (re.compile(r'^(CX-|EX-|FT-|FX-|GA-|GS-|GU-|GX-|HG-|LA-|LG-|LX-|NX-|PM-|RX-|SU-|UX-|EZ-|CN-|ER-)', re.I), 'Panasonic'),
    # Omron
    (re.compile(r'^(E3[A-Z]|E2[A-Z]|F3S|F39|V400|V530|Z4[A-Z])', re.I), 'Omron'),
    # Videojet
    (re.compile(r'^(VJ|CLARiTY)', re.I), 'Videojet'),
    # Honeywell
    (re.compile(r'^XENON', re.I), 'Honeywell'),
    # Cognex (IS/ISXX/DM/InSight)
    (re.compile(r'^(IS|DM|AW000)', re.I), 'Cognex'),
]

def infer_mfr_by_model(model):
    if not model:
        return ''
    for pat, mfr in MODEL_PREFIX_MFR:
        if pat.match(model):
            return mfr
    return ''

NON_SENSOR_HINTS = {
    'drive': 'actuator/drive',
    'servo': 'actuator/motion',
    'inverter': 'actuator/drive',
    'robot': 'robot',
    'plc': 'controller',
    'hmi': 'hmi',
    'motor': 'actuator/motion',
    'cylinder': 'pneumatic',
    'valve': 'pneumatic',
}

def extract_text(pdf_path, max_pages=3):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = pdf.pages[:max_pages]
            texts = []
            for p in pages:
                try:
                    t = p.extract_text() or ''
                    texts.append(t)
                except Exception:
                    pass
            return '\n'.join(texts)
    except Exception as e:
        return f'__ERROR__ {e}'

def detect_language(text):
    if not text:
        return 'EN'
    ko = sum(1 for c in text if '\uac00' <= c <= '\ud7a3')
    ja = sum(1 for c in text if '\u3040' <= c <= '\u30ff')
    zh = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' and not ('\u3040' <= c <= '\u30ff'))
    total = len(text)
    if total == 0: return 'EN'
    if ko / total > 0.02: return 'KO'
    if ja / total > 0.01: return 'JA'
    if zh / total > 0.03: return 'ZH'
    return 'EN'

def detect_manufacturer(text, filename_hint):
    t = text.lower() if text else ''
    # 본문에서 우선 탐색
    best = None
    for key, canon in MFR_CANONICAL.items():
        if len(key) <= 2:
            # 짧은 키워드는 단어 경계 확인
            if re.search(r'\b' + re.escape(key) + r'\b', t):
                best = canon
                break
        else:
            if key in t:
                best = canon
                break
    if best:
        return best
    # 파일명 힌트
    fn = filename_hint.lower()
    for key, canon in MFR_CANONICAL.items():
        if key in fn:
            return canon
    return ''

def detect_doctype(text, filename_hint):
    t = (text or '').lower()
    fn = filename_hint.lower()
    # 본문 우선
    for dt, kws in DOCTYPE_KEYWORDS:
        for k in kws:
            if k in t:
                return dt
    # 파일명 힌트
    for dt, kws in DOCTYPE_KEYWORDS:
        for k in kws:
            k2 = k.replace(' ', '').replace("'", '')
            if k2 in fn.replace('_', '').replace(' ', ''):
                return dt
        if dt.lower() in fn.replace('_', '').replace(' ', ''):
            return dt
    return 'Manual'

def detect_model(text, mfr, filename_hint):
    """첫 페이지에서 모델명 추출 시도 (휴리스틱)"""
    if not text:
        return ''
    # 파일명 기존 모델 필드 확인
    parts = filename_hint.replace('.pdf','').split('_')
    if len(parts) >= 2:
        candidate = parts[1]
        if candidate and candidate.lower() not in ('unknown', (mfr or '').lower()) and len(candidate) < 30:
            return candidate
    # 본문 첫 20줄에서 숫자/영문 혼합 패턴 탐색
    lines = text.split('\n')[:25]
    for line in lines:
        line = line.strip()
        if not line or len(line) > 100: continue
        m = re.search(r'\b([A-Z][A-Z0-9][\w\-/]{2,25})\b', line)
        if m:
            cand = m.group(1)
            if cand.lower() not in ('manual', 'user', 'guide', 'installation', 'service', 'system'):
                return cand
    return ''

def check_sensor_category(text):
    t = (text or '').lower()
    sensor_hits = sum(1 for k in SENSOR_KEYWORDS if k in t)
    for hint, cat in NON_SENSOR_HINTS.items():
        if re.search(r'\b' + hint + r'\b', t):
            if sensor_hits < 2:
                return False, f'suggest: {cat}'
    return (sensor_hits >= 1), ''

def analyze(filename):
    path = os.path.join(SRC_DIR, filename)
    text = extract_text(path, max_pages=3)
    if text.startswith('__ERROR__'):
        return {
            'old_filename': filename,
            'new_filename': filename,
            'manufacturer': '',
            'model': '',
            'doctype': 'Manual',
            'language': 'EN',
            'category_valid': '',
            'notes': 'PDF 읽기 실패: ' + text[10:100],
        }
    mfr = detect_manufacturer(text, filename)
    doctype = detect_doctype(text, filename)
    lang = detect_language(text)
    model = detect_model(text, mfr, filename)
    # 모델 접두어로 제조사 추정
    if not mfr:
        inferred = infer_mfr_by_model(model)
        if inferred:
            mfr = inferred
    valid, sug = check_sensor_category(text)

    # new filename 생성
    parts = []
    parts.append(mfr if mfr else 'Unknown')
    parts.append(model if model else 'Unknown')
    parts.append(doctype)
    parts.append(lang)
    new_name = '_'.join(parts) + '.pdf'
    # 파일명 안전 처리
    new_name = re.sub(r'[^\w\-.]', '-', new_name)

    notes = []
    if not mfr:
        notes.append('manufacturer unidentified')
    elif not detect_manufacturer(text, filename):
        notes.append(f'mfr inferred from model prefix')
    if not model:
        notes.append('model unidentified')
    if sug:
        notes.append(sug)

    return {
        'old_filename': filename,
        'new_filename': new_name,
        'manufacturer': mfr,
        'model': model,
        'doctype': doctype,
        'language': lang,
        'category_valid': 'true' if valid else 'false',
        'notes': '; '.join(notes),
    }

def main():
    files = sorted(os.listdir(SRC_DIR))
    pdfs = [f for f in files if f.lower().endswith('.pdf')]
    print(f'총 {len(pdfs)}개 PDF 분석 시작')

    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(analyze, f): f for f in pdfs}
        done = 0
        for fut in as_completed(futures):
            results.append(fut.result())
            done += 1
            if done % 10 == 0:
                print(f'  진행 {done}/{len(pdfs)}')

    # old_filename 기준 정렬
    results.sort(key=lambda x: x['old_filename'])

    # 중복 new_filename 처리 (_v2, _v3)
    seen = {}
    for r in results:
        nf = r['new_filename']
        if nf in seen:
            seen[nf] += 1
            base, ext = os.path.splitext(nf)
            r['new_filename'] = f'{base}_v{seen[nf]}{ext}'
        else:
            seen[nf] = 1

    # CSV 저장
    with open(OUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=[
            'old_filename','new_filename','manufacturer','model',
            'doctype','language','category_valid','notes'
        ])
        w.writeheader()
        for r in results:
            w.writerow(r)

    # JSON 백업
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 요약 통계
    mfr_stats = {}
    lang_stats = {}
    type_stats = {}
    invalid_cnt = 0
    unknown_mfr = 0
    unknown_model = 0
    for r in results:
        mfr_stats[r['manufacturer'] or 'Unknown'] = mfr_stats.get(r['manufacturer'] or 'Unknown', 0) + 1
        lang_stats[r['language']] = lang_stats.get(r['language'], 0) + 1
        type_stats[r['doctype']] = type_stats.get(r['doctype'], 0) + 1
        if r['category_valid'] == 'false': invalid_cnt += 1
        if not r['manufacturer']: unknown_mfr += 1
        if not r['model']: unknown_model += 1

    print(f'\n=== 결과 요약 ===')
    print(f'총 {len(results)}건 분석 완료')
    print(f'CSV: {OUT_CSV}')
    print(f'\n[제조사 분포]')
    for k, v in sorted(mfr_stats.items(), key=lambda x: -x[1]):
        print(f'  {k}: {v}')
    print(f'\n[언어 분포]')
    for k, v in sorted(lang_stats.items(), key=lambda x: -x[1]):
        print(f'  {k}: {v}')
    print(f'\n[문서유형 분포]')
    for k, v in sorted(type_stats.items(), key=lambda x: -x[1]):
        print(f'  {k}: {v}')
    print(f'\n[미식별]')
    print(f'  manufacturer 미식별: {unknown_mfr}건')
    print(f'  model 미식별: {unknown_model}건')
    print(f'  category_valid=false: {invalid_cnt}건')

if __name__ == '__main__':
    main()
