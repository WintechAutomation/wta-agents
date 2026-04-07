"""
WTA 프로젝트 사용자매뉴얼 수집
- 출처: \\192.168.1.6\Project\{제품}\{프로젝트}\4. 사용자매뉴얼\
- 대상: PDF, DOCX
- 중복 제거: 동일 파일명 중 최신(mtime) 유지
- 저장: C:/MES/wta-agents/data/wta-manuals/{제품}/
"""
import os
import shutil
import re
from pathlib import Path
from collections import defaultdict

SRC = r"\\192.168.1.6\Project"
DST = r"C:\MES\wta-agents\data\wta-manuals"
DOC_EXTS = {'.pdf', '.docx'}

MANUAL_FOLDER_KEYWORDS = ['4. 사용자매뉴얼', '4.사용자매뉴얼', '사용자매뉴얼', '사용자 매뉴얼']

# 최상위 제품 폴더 제외 목록
SKIP_FOLDERS = {'#recycle', '0. 기본폴더구성', 'thumbs.db', '기본양식'}

def normalize_product(name: str) -> str:
    """제품 폴더명에서 번호 제거 후 정규화"""
    name = re.sub(r'^\d+\.\s*', '', name)  # "1. 프레스" → "프레스"
    return name.strip().replace(' ', '_').replace('/', '_').replace(',', '')

def is_manual_folder(folder_name: str) -> bool:
    fn_lower = folder_name.lower()
    return any(kw.lower() in fn_lower for kw in MANUAL_FOLDER_KEYWORDS)

def collect():
    # 제품별 {파일명소문자: [(경로, mtime, 원본파일명)]} 수집
    product_files = defaultdict(lambda: defaultdict(list))

    try:
        top_folders = os.listdir(SRC)
    except Exception as e:
        print(f"[오류] 네트워크 경로 접근 실패: {e}")
        return

    for top in sorted(top_folders):
        if top.lower() in {s.lower() for s in SKIP_FOLDERS}:
            continue
        top_path = os.path.join(SRC, top)
        if not os.path.isdir(top_path):
            continue

        product = normalize_product(top)
        print(f"[탐색] {top} → {product}")

        # 프로젝트 폴더 순회
        try:
            proj_folders = os.listdir(top_path)
        except Exception:
            continue

        for proj in proj_folders:
            proj_path = os.path.join(top_path, proj)
            if not os.path.isdir(proj_path):
                continue

            # "4. 사용자매뉴얼" 폴더 탐색 (직접 또는 1단계 하위)
            manual_dirs = []

            # 직접 확인
            try:
                for sub in os.listdir(proj_path):
                    if is_manual_folder(sub):
                        manual_dirs.append(os.path.join(proj_path, sub))
            except Exception:
                continue

            # 사용자매뉴얼 폴더가 없으면 하위 한 단계 더 탐색
            if not manual_dirs:
                try:
                    for sub in os.listdir(proj_path):
                        sub_path = os.path.join(proj_path, sub)
                        if os.path.isdir(sub_path):
                            for sub2 in os.listdir(sub_path):
                                if is_manual_folder(sub2):
                                    manual_dirs.append(os.path.join(sub_path, sub2))
                except Exception:
                    pass

            for manual_dir in manual_dirs:
                try:
                    for root, dirs, files in os.walk(manual_dir):
                        for f in files:
                            ext = Path(f).suffix.lower()
                            if ext in DOC_EXTS:
                                fpath = os.path.join(root, f)
                                try:
                                    mtime = os.path.getmtime(fpath)
                                except Exception:
                                    mtime = 0
                                product_files[product][f.lower()].append((fpath, mtime, f))
                except Exception:
                    continue

    # 결과 복사
    os.makedirs(DST, exist_ok=True)
    total_copied = 0
    total_skipped = 0
    errors = 0
    product_counts = {}

    for product, file_groups in sorted(product_files.items()):
        dst_cat = os.path.join(DST, product)
        os.makedirs(dst_cat, exist_ok=True)
        copied = 0
        skipped = 0

        for fname_lower, candidates in file_groups.items():
            if len(candidates) > 1:
                # 최신 파일 선택
                best = max(candidates, key=lambda x: x[1])
                skipped += len(candidates) - 1
            else:
                best = candidates[0]

            src_path, mtime, orig_name = best
            dst_path = os.path.join(dst_cat, orig_name)

            # 이미 있으면 mtime 비교
            if os.path.exists(dst_path):
                try:
                    if os.path.getmtime(dst_path) >= mtime:
                        skipped += 1
                        continue
                except Exception:
                    pass

            try:
                shutil.copy2(src_path, dst_path)
                copied += 1
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  [오류] {orig_name}: {e}")

        product_counts[product] = copied
        total_copied += copied
        total_skipped += skipped
        if copied > 0:
            print(f"  {product}: {copied}개 복사")

    print(f"\n=== 수집 완료 ===")
    print(f"복사: {total_copied}개 / 중복제거(구버전): {total_skipped}개 / 오류: {errors}개")
    print(f"\n[제품별 파일 수]")
    for product, cnt in sorted(product_counts.items()):
        if cnt > 0:
            print(f"  {product}: {cnt}개")

if __name__ == '__main__':
    collect()
