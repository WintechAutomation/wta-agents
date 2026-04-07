"""
매뉴얼 2차 필터링
기준 1: CS 이력 키워드 매칭 (제조사/장비명이 파일명 또는 카테고리폴더에 포함)
기준 2: 한국어 매뉴얼 우선 (KO/EN 중복 시 한국어만)
기준 3: 사용자 매뉴얼만 (카탈로그/도면/사양서/설치 제외)
"""
import os
import re
import shutil
from pathlib import Path
from collections import defaultdict

SRC_DIR = r"C:\MES\wta-agents\data\manuals"
DST_DIR = r"C:\MES\wta-agents\data\manuals-filtered"

# ── 기준1: CS 이력 기반 허용 키워드 (제조사/장비) ──────────────────────────
CS_KEYWORDS = [
    # CS 이력 상위 빈도
    'yaskawa', 'ya skawa',
    'keyence', 'lv-', 'lk-', 'lj-', 'gt2-', 'im-', 'iv2-', 'sl-', 'xl-', 'cv-', 'vt-',
    'mitsubishi', 'melsec', 'melfa', 'cr800', 'cr750', 'rv-', 'rh-', 'fr-e', 'fr-a', 'fr-f',
    'denso', 'rc8', 'vs-', 'vp-', 'vm-', 'hm-',
    'pro-face', 'proface', 'gp4', 'gp37', 'gp377', 'gp3000', 'st400',
    'beckhoff', 'el6', 'el1', 'el2', 'el3', 'el4', 'cx-', 'bk', 'ek1',
    'sick', 'lms', 'tim', 'drs', 'ild',
    'omron', 'ns-', 'nb-', 'cj', 'cp1',
    'panasonic', 'minas', 'a6', 'fp',
    'acs', 'spiiplus', 'mc4u', 'hssi',
    'smc', 'sy3', 'sy5', 'mxp', 'cq2', 'cy1',
    'fastech', '파스텍', 'ezi', 'ez-s', 'ez-c',
    'ls servo', 'ls메카피온', 'mekapy', 'l7',
    'csd5', 'csd-5',
    'crevis', 'na-9',
    'delta tau', 'deltatau', 'pmac',
    'sankyo', '산쿄',
    'ethercat', 'ek9', 'ek1100',
    'inovance', 'is620',
    'leadshine', 'em3', 'dm3',
    'samsung servo', '삼성서보',
    'hitachi ada', 'hitachi servo',
    'sanmotion', 'r1aa',
    'abb', 'irc5', 'flexpendant',
    'roboworker',
    # 카테고리가 sensor/robot/hmi이면 CS 빈도 높으므로 폴더 기준 허용
]

# 카테고리 폴더 자체가 CS 이력에서 빈도 높은 경우 → 폴더 전체 허용
HIGH_FREQ_CATS = {'1_robot', '2_sensor', '3_hmi', '4_servo'}

# ── 기준3: 제외 키워드 (카탈로그/도면/사양서/설치) ──────────────────────────
EXCLUDE_KEYWORDS = [
    'catalog', 'catalogue', '카탈로그', 'catalo',
    'drawing', 'dwg', 'dxf', '도면', '도면집',
    'cad', '3d model',
    '사양서', 'spec sheet', 'specification',
    'installation guide', 'install guide', '설치가이드', '설치 가이드', '설치매뉴얼',
    'wiring diagram', '배선도', '결선도',
    'parts list', 'parts catalog', '부품목록', '부품표',
    'brochure',
    'release note', 'release notes', 'revision history',
    'quick start', 'quickstart',  # 너무 얇은 문서
    'certificate', '인증서',
    'compliance',
]

# ── 기준2: 한국어 판별 ──────────────────────────────────────────────────────
KO_MARKERS = ['_ko', '-ko', '_kr', '-kr', '_kor', '-kor', '(ko)', '(kr)',
              '한국어', '국문', 'korean']
EN_MARKERS = ['_en', '-en', '_eng', '-eng', '(en)', '(eng)', 'english']

def has_korean_chars(text: str) -> bool:
    return bool(re.search(r'[\uac00-\ud7a3]', text))

def is_korean_manual(filename: str) -> bool:
    fn = filename.lower()
    if any(m in fn for m in KO_MARKERS):
        return True
    if has_korean_chars(filename):
        return True
    return False

def is_english_only(filename: str) -> bool:
    fn = filename.lower()
    if any(m in fn for m in EN_MARKERS):
        return True
    return False

def passes_cs_filter(filename: str, category: str) -> bool:
    """기준1: CS 이력 키워드 또는 고빈도 카테고리"""
    if category in HIGH_FREQ_CATS:
        return True
    fn_lower = filename.lower()
    return any(kw in fn_lower for kw in CS_KEYWORDS)

def passes_content_filter(filename: str) -> bool:
    """기준3: 사용자 매뉴얼 여부"""
    fn_lower = filename.lower()
    return not any(kw in fn_lower for kw in EXCLUDE_KEYWORDS)

def run():
    # 대상 폴더 생성
    os.makedirs(DST_DIR, exist_ok=True)

    total = 0
    passed = 0
    skip_cs = 0
    skip_content = 0
    skip_lang = 0

    # 카테고리별 파일 목록 수집
    cat_files = defaultdict(list)  # cat → [(filename, filepath)]
    for cat in sorted(os.listdir(SRC_DIR)):
        cat_path = os.path.join(SRC_DIR, cat)
        if not os.path.isdir(cat_path):
            continue
        for f in os.listdir(cat_path):
            cat_files[cat].append((f, os.path.join(cat_path, f)))
            total += 1

    print(f"전체 파일: {total}개")

    # 기준1+3 필터 먼저 적용
    filtered1 = defaultdict(list)
    for cat, files in cat_files.items():
        for fname, fpath in files:
            if not passes_cs_filter(fname, cat):
                skip_cs += 1
                continue
            if not passes_content_filter(fname):
                skip_content += 1
                continue
            filtered1[cat].append((fname, fpath))

    print(f"기준1(CS) 제외: {skip_cs}개")
    print(f"기준3(내용유형) 제외: {skip_content}개")

    # 기준2: 한국어 우선 처리
    # stem(확장자 제외) 기준으로 그룹핑 → 한국어 있으면 영어 제외
    for cat, files in filtered1.items():
        dst_cat = os.path.join(DST_DIR, cat)
        os.makedirs(dst_cat, exist_ok=True)

        # stem 정규화 그룹핑
        stem_groups = defaultdict(list)
        for fname, fpath in files:
            stem = Path(fname).stem.lower()
            # 언어 표시 제거한 stem
            stem_clean = stem
            for m in KO_MARKERS + EN_MARKERS:
                stem_clean = stem_clean.replace(m, '')
            stem_clean = re.sub(r'[\s_\-]+', ' ', stem_clean).strip()
            stem_groups[stem_clean].append((fname, fpath))

        for stem_clean, group in stem_groups.items():
            if len(group) == 1:
                # 단독 파일
                fname, fpath = group[0]
                shutil.copy2(fpath, os.path.join(dst_cat, fname))
                passed += 1
            else:
                # 여러 파일 → 한국어 우선
                ko_files = [(f, p) for f, p in group if is_korean_manual(f)]
                en_files = [(f, p) for f, p in group if is_english_only(f)]
                other_files = [(f, p) for f, p in group
                               if not is_korean_manual(f) and not is_english_only(f)]

                if ko_files:
                    # 한국어 버전 있으면 한국어만
                    for fname, fpath in ko_files:
                        shutil.copy2(fpath, os.path.join(dst_cat, fname))
                        passed += 1
                    skip_lang += len(en_files)
                else:
                    # 한국어 없으면 나머지 모두 복사
                    for fname, fpath in en_files + other_files:
                        shutil.copy2(fpath, os.path.join(dst_cat, fname))
                        passed += 1

    print(f"기준2(언어중복) 제외: {skip_lang}개")
    print(f"\n=== 필터링 완료 ===")
    print(f"전체: {total}개 → 통과: {passed}개 (제외: {total - passed}개)")

    print(f"\n[카테고리별]")
    grand = 0
    for cat in sorted(os.listdir(DST_DIR)):
        cat_path = os.path.join(DST_DIR, cat)
        if os.path.isdir(cat_path):
            cnt = len(os.listdir(cat_path))
            grand += cnt
            print(f"  {cat}: {cnt}개")
    print(f"  합계: {grand}개")

if __name__ == '__main__':
    run()
