"""
매뉴얼 누락 파일 재복사 + 크기 불일치(구버전) 교체
1. 원본에 있지만 로컬에 없는 파일 → 복사
2. 동일 파일명인데 원본이 더 큰 경우 → 원본으로 교체 (더 큰 = 더 많은 내용)
"""
import os
import shutil
import re
from pathlib import Path
from collections import defaultdict

SRC = r"\\192.168.1.6\motion\1.Robot & Motion\DB"
DST = r"C:\MES\wta-agents\data\manuals"
DOC_EXTS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.hwp'}

CATEGORY_RULES = [
    ('1_robot',     ['robot', 'yaskawa', 'denso', 'abb', 'mitsubishi robot', 'fanuc', '로봇', 'scara', '스카라', 'sanyo', 'roboworker', 'sankyo']),
    ('2_sensor',    ['sensor', 'keyence', 'sick', 'panasonic sensor', '센서', 'camera', 'dalsa', 'euresys', 'probe', 'laser', '레이저', 'barcode', 'scanner', '바코드']),
    ('3_hmi',       ['touch', 'hmi', 'pro-face', 'proface', 'beijer', 'hauto tp', 'delta tau']),
    ('4_servo',     ['servo', 'csd', '서보', 'ls servo', 'panasonic servo', 'mitsubishi servo', 'yaskawa servo',
                     'samsung servo', 'hitachi ada servo', 'sanmotion', 'leadshine', 'softservo', 'moons',
                     'tecnotion', '파스텍', 'ezi', '하이젠', '하이윈', 'inovance', 'veichi', 'acs', 'spiiplus',
                     'mc4u', 'hssi']),
    ('5_inverter',  ['inverter', '인버터', 'hitachi inverter', 'ls inverter', 'mitsubishi inverter',
                     'yaskawa inverter', 'fuji', 'adt inverter', 'oemax']),
    ('6_plc',       ['plc', 'mitsubishi plc', 'ls electric', 'lsis', 'omron', 'codesys', 'cc-link',
                     'device-net', 'modbus', 'ethercat', 'profibus', 'mc protocol', 'beckhoff', 'kunbus', 'crevis']),
    ('7_pneumatic', ['smc', 'ckd', 'spg', 'smps', 'patlite', 'pilz', 'safect', 'ups', 'chint', 'elmon']),
    ('8_etc',       []),
]

def get_category(top_folder: str, filename: str) -> str:
    text = (top_folder + ' ' + filename).lower()
    for cat, keywords in CATEGORY_RULES[:-1]:
        for kw in keywords:
            if kw in text:
                return cat
    return '8_etc'

def collect_src():
    groups = defaultdict(list)
    for root, dirs, files in os.walk(SRC):
        for f in files:
            if Path(f).suffix.lower() in DOC_EXTS:
                rel = os.path.relpath(root, SRC)
                top = rel.split(os.sep)[0] if rel != '.' else ''
                full = os.path.join(root, f)
                try:
                    size = os.path.getsize(full)
                except:
                    size = 0
                groups[f.lower()].append({'path': full, 'top': top, 'name': f, 'size': size})
    return groups

def collect_dst():
    local = {}
    for cat in os.listdir(DST):
        cat_path = os.path.join(DST, cat)
        if not os.path.isdir(cat_path):
            continue
        for f in os.listdir(cat_path):
            fp = os.path.join(cat_path, f)
            try:
                size = os.path.getsize(fp)
            except:
                size = 0
            local[f.lower()] = {'cat': cat, 'path': fp, 'size': size}
    return local

print("=== 수집 중... ===")
src_groups = collect_src()
dst_files = collect_dst()

copied = 0
replaced = 0
errors = 0

# 1. 누락 파일 복사
print("\n[1단계] 누락 파일 복사")
for fname_lower, locs in src_groups.items():
    if fname_lower not in dst_files:
        # 여러 위치 중 가장 큰 파일 선택
        best = max(locs, key=lambda x: x['size'])
        cat = get_category(best['top'], best['name'])
        dst_path = os.path.join(DST, cat, best['name'])
        try:
            shutil.copy2(best['path'], dst_path)
            copied += 1
            if copied % 50 == 0:
                print(f"  복사 진행: {copied}개...")
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  [오류] {best['name']}: {e}")

print(f"  누락 파일 복사 완료: {copied}개")

# 2. 크기 불일치 - 원본이 더 큰 경우 교체
print("\n[2단계] 구버전 교체 (원본이 더 큰 경우)")
for fname_lower, locs in src_groups.items():
    if fname_lower in dst_files:
        dst_info = dst_files[fname_lower]
        best_src = max(locs, key=lambda x: x['size'])
        if best_src['size'] > dst_info['size'] + 10240:  # 10KB 이상 차이
            try:
                shutil.copy2(best_src['path'], dst_info['path'])
                replaced += 1
                print(f"  교체: {best_src['name']} ({dst_info['size']//1024}KB → {best_src['size']//1024}KB)")
            except Exception as e:
                errors += 1
                print(f"  [오류] 교체 실패 {best_src['name']}: {e}")

print(f"  구버전 교체 완료: {replaced}개")

# 최종 집계
print("\n=== 완료 ===")
print(f"복사: {copied}개 / 교체: {replaced}개 / 오류: {errors}개")

# 카테고리별 최종 파일 수
print("\n[카테고리별 최종 파일 수]")
for cat in sorted(os.listdir(DST)):
    cat_path = os.path.join(DST, cat)
    if os.path.isdir(cat_path):
        cnt = len(os.listdir(cat_path))
        print(f"  {cat}: {cnt}개")
