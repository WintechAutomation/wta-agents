"""
매뉴얼 복사 현황 분석
1. 원본에서 동일 파일명 중복 목록 추출 (덮어쓰기 위험)
2. 현재 로컬 vs 원본 대조
3. 버전 중복 감지
"""
import os
import re
from pathlib import Path
from collections import defaultdict

SRC = r"\\192.168.1.6\motion\1.Robot & Motion\DB"
DST = r"C:\MES\wta-agents\data\manuals"
DOC_EXTS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.hwp'}

def collect_src():
    """원본 문서 파일 수집: {파일명소문자: [(전체경로, 상위폴더)]}"""
    groups = defaultdict(list)
    for root, dirs, files in os.walk(SRC):
        for f in files:
            if Path(f).suffix.lower() in DOC_EXTS:
                rel = os.path.relpath(root, SRC)
                top = rel.split(os.sep)[0] if rel != '.' else ''
                groups[f.lower()].append((os.path.join(root, f), top, f))
    return groups

def collect_dst():
    """로컬 파일 수집: {파일명소문자: (카테고리, 전체경로)}"""
    local = {}
    for cat in os.listdir(DST):
        cat_path = os.path.join(DST, cat)
        if not os.path.isdir(cat_path):
            continue
        for f in os.listdir(cat_path):
            local[f.lower()] = (cat, os.path.join(cat_path, f))
    return local

print("=== 원본 파일 수집 중... ===")
src_groups = collect_src()
total_src = sum(len(v) for v in src_groups.values())
print(f"원본 고유 파일명: {len(src_groups)}개 (전체 파일: {total_src}개)")

# 덮어쓰기 위험: 동일 파일명이 여러 폴더에 존재
overwrite_risk = {k: v for k, v in src_groups.items() if len(v) > 1}
print(f"\n[덮어쓰기 위험] 동일 파일명 복수 위치: {len(overwrite_risk)}개")
if overwrite_risk:
    print("상위 20개:")
    for fname, locs in list(overwrite_risk.items())[:20]:
        print(f"  {fname}")
        for path, top, orig in locs:
            size = os.path.getsize(path) if os.path.exists(path) else 0
            print(f"    └ [{top}] {size//1024}KB")

print("\n=== 로컬 파일 수집 중... ===")
dst_files = collect_dst()
print(f"로컬 파일 수: {len(dst_files)}개")

# 원본에 있지만 로컬에 없는 파일 (덮어쓰기로 누락된 파일)
missing = []
for fname_lower, locs in src_groups.items():
    if fname_lower not in dst_files:
        for path, top, orig in locs:
            missing.append((orig, top, path))

print(f"\n[누락 파일] 원본에 있지만 로컬에 없는 파일: {len(missing)}개")
if missing:
    print("상위 30개:")
    for orig, top, path in missing[:30]:
        print(f"  [{top}] {orig}")

# 덮어쓰기된 파일 중 크기 차이로 다른 내용 감지
print(f"\n[덮어쓰기 충돌 상세] 동일 파일명이지만 다른 폴더 출처:")
size_mismatch = []
for fname, locs in overwrite_risk.items():
    if fname in dst_files:
        dst_path = dst_files[fname][1]
        dst_size = os.path.getsize(dst_path) if os.path.exists(dst_path) else 0
        for src_path, top, orig in locs:
            src_size = os.path.getsize(src_path) if os.path.exists(src_path) else 0
            if abs(src_size - dst_size) > 1024:  # 1KB 이상 차이
                size_mismatch.append((orig, top, src_size, dst_size))

print(f"크기 불일치(내용 다를 가능성): {len(size_mismatch)}개")
for orig, top, ss, ds in size_mismatch[:20]:
    print(f"  {orig}: 원본[{top}] {ss//1024}KB vs 로컬 {ds//1024}KB")

print("\n=== 분석 완료 ===")
