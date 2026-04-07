"""
매뉴얼 파일 복사 + 중복 제거 스크립트
- 출처: \\192.168.1.6\motion\1.Robot & Motion\DB
- 대상: C:/MES/wta-agents/data/manuals/{카테고리}/
- 파일명 기반 분류 (DRM으로 내용 확인 불가)
- 중복 제거: 동일 파일명 중 최신 버전만 유지
"""
import os
import shutil
import hashlib
import re
from pathlib import Path
from collections import defaultdict

SRC = r"\\192.168.1.6\motion\1.Robot & Motion\DB"
DST = r"C:\MES\wta-agents\data\manuals"

DOC_EXTS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.hwp'}

# 폴더명/파일명 키워드 → 카테고리 매핑
CATEGORY_RULES = [
    ('1_robot',  ['robot', 'yaskawa', 'denso', 'abb', 'mitsubishi robot', 'fanuc', '로봇', 'scara', '스카라', 'sanyo', 'roboworker', 'sankyo', 'wtр']),
    ('2_sensor', ['sensor', 'keyence', 'sick', 'panasonic sensor', '센서', 'camera', 'dalsa', 'euresys', 'probe', 'laser', '레이저', 'area', '바코드', 'barcode', 'scanner']),
    ('3_hmi',    ['touch', 'hmi', 'pro-face', 'proface', 'beijer', 'hauto tp', 'delta tau']),
    ('4_servo',  ['servo', 'csd', '서보', 'ls servo', 'panasonic servo', 'mitsubishi servo', 'yaskawa servo', 'samsung servo', 'hitachi ada servo', 'sanmotion', 'leadshine', 'softservo', 'moons', 'tecnotion', '파스텍', 'ezi', '하이젠', '하이윈', 'inovance', 'veichi']),
    ('5_inverter', ['inverter', '인버터', 'hitachi inverter', 'ls inverter', 'mitsubishi inverter', 'yaskawa inverter', 'fuji', 'adt inverter', 'oemax']),
    ('6_plc',    ['plc', 'mitsubishi plc', 'ls electric', 'lsis', 'omron', 'codesys', 'cc-link', 'device-net', 'modbus', 'ethercat', 'profibus', 'mc protocol', 'beckhoff', 'kunbus']),
    ('7_pneumatic', ['smc', 'ckd', 'spg', 'smps', 'patlite', 'pilz', 'safect', 'ups', 'chint', 'elmon']),
    ('8_etc',    []),  # 위 규칙에 안 걸리는 나머지
]

# 카테고리 폴더 생성
for cat, _ in CATEGORY_RULES:
    Path(os.path.join(DST, cat)).mkdir(parents=True, exist_ok=True)

def get_category(folder_path: str, filename: str) -> str:
    """폴더명+파일명으로 카테고리 결정"""
    text = (folder_path + ' ' + filename).lower()
    for cat, keywords in CATEGORY_RULES[:-1]:  # 8_etc 제외
        for kw in keywords:
            if kw in text:
                return cat
    return '8_etc'

def version_key(filename: str):
    """파일명에서 버전 숫자 추출 (정렬용)"""
    nums = re.findall(r'\d+', filename)
    return [int(n) for n in nums] if nums else [0]

def collect_files():
    """문서 파일 수집 - {정규화이름: [(경로, mtime), ...]}"""
    groups = defaultdict(list)
    total = 0
    for root, dirs, files in os.walk(SRC):
        for f in files:
            ext = Path(f).suffix.lower()
            if ext not in DOC_EXTS:
                continue
            full = os.path.join(root, f)
            try:
                mtime = os.path.getmtime(full)
            except Exception:
                mtime = 0
            # 정규화: 확장자 제거, 소문자, 공백/특수문자 통일
            stem = Path(f).stem.lower()
            stem_norm = re.sub(r'[\s_\-\.]+', ' ', stem).strip()
            groups[stem_norm].append((full, mtime, root))
            total += 1
    print(f"[수집] 문서 파일 총 {total}개, 고유 이름 그룹 {len(groups)}개")
    return groups

def pick_latest(candidates):
    """버전/mtime 기준 최신 파일 선택"""
    # 먼저 버전 번호로 정렬, 같으면 mtime
    candidates.sort(key=lambda x: (version_key(Path(x[0]).stem), x[1]), reverse=True)
    return candidates[0]

def run():
    print("=== 매뉴얼 복사 시작 ===")
    groups = collect_files()

    copied = 0
    skipped = 0
    errors = 0
    cat_counts = defaultdict(int)

    for stem_norm, candidates in groups.items():
        best_path, best_mtime, best_root = pick_latest(candidates)
        filename = os.path.basename(best_path)

        # 폴더 경로에서 제조사 폴더명 추출 (SRC 하위 첫 번째 폴더)
        rel = os.path.relpath(best_root, SRC)
        top_folder = rel.split(os.sep)[0] if rel != '.' else ''

        cat = get_category(top_folder, filename)
        dst_file = os.path.join(DST, cat, filename)

        # 동일 파일명이 대상 폴더에 이미 있으면 mtime 비교
        if os.path.exists(dst_file):
            try:
                existing_mtime = os.path.getmtime(dst_file)
                if existing_mtime >= best_mtime:
                    skipped += 1
                    continue
            except Exception:
                pass

        try:
            shutil.copy2(best_path, dst_file)
            copied += 1
            cat_counts[cat] += 1
            if copied % 100 == 0:
                print(f"  진행: {copied}개 복사됨...")
        except Exception as e:
            errors += 1
            if errors <= 10:
                print(f"  [오류] {filename}: {e}")

    print("\n=== 복사 완료 ===")
    print(f"복사: {copied}개 / 스킵(최신 이미 있음): {skipped}개 / 오류: {errors}개")
    print("\n[카테고리별]")
    for cat, cnt in sorted(cat_counts.items()):
        print(f"  {cat}: {cnt}개")

    # 중복 버전 통계
    dup_count = sum(len(v)-1 for v in groups.values() if len(v) > 1)
    print(f"\n중복 제거(구버전 제외): {dup_count}개")

if __name__ == '__main__':
    run()
