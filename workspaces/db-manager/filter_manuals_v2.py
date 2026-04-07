"""
매뉴얼 2차 필터링 v2 — CS 이력 실제 분석 기반
CS 이력 분석 결과:
  - 장치 카테고리: 서보드라이브(104), 로봇(379), 센서(369), HMI(266)
  - 제조사명(영문): CSD5(43), ACS(26), EtherCAT(13), SMC(13), Modbus(9)
  - 제조사명(한글): 미쓰비시(9), 파나소닉(2), 파스텍(1), 프로페이스(1), LS메카피온(1)

필터링 전략:
  1. 장치 카테고리 기반: robot/sensor/hmi/servo 전체 포함
  2. CS 이력 제조사명 직접 매칭: CSD5, ACS, EtherCAT, SMC, Mitsubishi, Modbus, Panasonic 등
  3. 제외: 카탈로그, 도면, 사양서, 수리이력(TMA)
  4. 언어 중복: 한국어 우선
"""
import os
import re
import shutil
from pathlib import Path
from collections import defaultdict

SRC_DIR = r"C:\MES\wta-agents\data\manuals"
DST_DIR = r"C:\MES\wta-agents\data\manuals-filtered"

# CS 이력 기반 허용 키워드 (제조사명/장치명)
CS_MATCHED_KEYWORDS = [
    # 서보드라이브/모션 (CS 이력 최다 언급)
    'csd5', 'csd-5', 'csd3',
    'acs', 'spiiplus', 'spii plus', 'mc4u', 'hssi', 'acspl',
    'fastech', '파스텍', 'ezi-servo', 'ezi servo',
    'ls메카피온', 'mekapy', 'l7n', 'l7e', 'l7c', 'l7h',
    'inovance', 'is620',
    'leadshine',
    'sanmotion', 'r1aa',
    'softservo',
    'hitachi ada', 'hitachi servo',
    'samsung servo',
    # 모션컨트롤러/통신 (EtherCAT 13건, Modbus 9건)
    'ethercat', 'ek1100', 'ek9000',
    'modbus', 'profibus', 'devicenet', 'cc-link',
    'twincat', 'beckhoff',
    'codesys',
    'trio motion', 'triomc',
    # PLC/인버터 (미쓰비시 9건)
    'mitsubishi', 'melsec', 'melfa', 'fr-e', 'fr-a', 'fr-f', 'cr800', 'cr750',
    'ls electric', 'lselectric', 'ls전기', 'xgi-', 'xgk-', 'xgb-',
    'omron',
    'fuji', 'frenic',
    # HMI (프로페이스 1건, 하지만 HMI 카테고리 CS 266건)
    'pro-face', 'proface', 'gp4', 'gp37', 'gp3000',
    'beijer',
    # 센서 (KEYENCE/SICK — 카테고리로 369건, 제조사명 직접은 적음)
    'keyence', 'lv-', 'lk-', 'lj-', 'lm-', 'gt2-', 'iv2-',
    'sick', 'lms2', 'tim2', 'ild',
    'panasonic', 'minas',
    # 로봇 (로봇 카테고리 CS 379건)
    'yaskawa', 'motoman',
    'denso', 'rc8', 'vs-6', 'vs-087',
    'abb', 'irc5',
    'sankyo',
    'roboworker',
    'delta tau', 'deltatau', 'pmac', 'power pmac',
    # 기타 CS 언급 장비
    'smc',
    'crevis', 'na-9',
    'dalsa', 'teledyne',
    'euresys',
    'pilz', 'pnoz',
    'kyocera',  # CS 이력에 55건 등장
    'smps',     # CS 이력에 29건
    'autonics',
    'omron',
]

# 카테고리 전체 허용 (CS 이력 장치 카테고리 기반)
HIGH_FREQ_CATS = {'1_robot', '2_sensor', '3_hmi', '4_servo'}

# 제외 키워드 (카탈로그/도면/수리이력/사양서)
EXCLUDE_KEYWORDS = [
    'catalog', 'catalogue', '카탈로그',
    'drawing', '도면', 'cad', 'dxf',
    '사양서', 'spec sheet',
    'installation guide', '설치가이드', '설치매뉴얼',
    'wiring diagram', '배선도', '결선도',
    'parts list', 'parts catalog', '부품목록',
    'brochure',
    'release note', 'revision history',
    'certificate', '인증서',
    '_tma',   # ACS_WTA*TMA.xls 수리이력 파일
    '-tacs',  # ACS_WTA*TACS 수리이력
    '회사 소개서', '회사소개서',
]

KO_MARKERS = ['_ko', '-ko', '_kr', '-kr', '(ko)', '(kr)', '한국어', '국문', 'korean']
EN_MARKERS = ['_en', '-en', '_eng', '-eng', '(en)', '(eng)', 'english']

def has_korean(text): return bool(re.search(r'[\uac00-\ud7a3]', text))
def is_korean(fn): return any(m in fn.lower() for m in KO_MARKERS) or has_korean(fn)
def is_english_only(fn): return any(m in fn.lower() for m in EN_MARKERS)

def passes_cs(fname, cat):
    if cat in HIGH_FREQ_CATS:
        return True
    fn = fname.lower()
    return any(kw in fn for kw in CS_MATCHED_KEYWORDS)

def passes_content(fname):
    fn = fname.lower()
    return not any(kw in fn for kw in EXCLUDE_KEYWORDS)

def run():
    # 기존 필터링 결과 삭제 후 재생성
    if os.path.exists(DST_DIR):
        shutil.rmtree(DST_DIR)
    os.makedirs(DST_DIR)

    total = skip_cs = skip_content = skip_lang = passed = 0

    cat_files = defaultdict(list)
    for cat in sorted(os.listdir(SRC_DIR)):
        cp = os.path.join(SRC_DIR, cat)
        if os.path.isdir(cp):
            for f in os.listdir(cp):
                cat_files[cat].append((f, os.path.join(cp, f)))
                total += 1

    print(f"전체: {total}개")

    filtered = defaultdict(list)
    for cat, files in cat_files.items():
        for fname, fpath in files:
            if not passes_cs(fname, cat):
                skip_cs += 1; continue
            if not passes_content(fname):
                skip_content += 1; continue
            filtered[cat].append((fname, fpath))

    print(f"CS 미매칭 제외: {skip_cs}개 / 내용유형 제외: {skip_content}개")

    for cat, files in filtered.items():
        dst_cat = os.path.join(DST_DIR, cat)
        os.makedirs(dst_cat, exist_ok=True)

        stem_groups = defaultdict(list)
        for fname, fpath in files:
            stem = Path(fname).stem.lower()
            stem_clean = stem
            for m in KO_MARKERS + EN_MARKERS:
                stem_clean = stem_clean.replace(m, '')
            stem_clean = re.sub(r'[\s_\-]+', ' ', stem_clean).strip()
            stem_groups[stem_clean].append((fname, fpath))

        for stem_clean, group in stem_groups.items():
            if len(group) == 1:
                fname, fpath = group[0]
                shutil.copy2(fpath, os.path.join(dst_cat, fname))
                passed += 1
            else:
                ko = [(f, p) for f, p in group if is_korean(f)]
                en = [(f, p) for f, p in group if is_english_only(f)]
                other = [(f, p) for f, p in group if not is_korean(f) and not is_english_only(f)]
                if ko:
                    for fname, fpath in ko:
                        shutil.copy2(fpath, os.path.join(dst_cat, fname))
                        passed += 1
                    skip_lang += len(en)
                else:
                    for fname, fpath in en + other:
                        shutil.copy2(fpath, os.path.join(dst_cat, fname))
                        passed += 1

    print(f"언어중복 제외: {skip_lang}개")
    print(f"\n결과: {total}개 → {passed}개 (제외: {total-passed}개)")
    print("\n[카테고리별]")
    grand = 0
    for cat in sorted(os.listdir(DST_DIR)):
        cp = os.path.join(DST_DIR, cat)
        if os.path.isdir(cp):
            cnt = len(os.listdir(cp))
            grand += cnt
            print(f"  {cat}: {cnt}개")
    print(f"  합계: {grand}개")

if __name__ == '__main__':
    run()
