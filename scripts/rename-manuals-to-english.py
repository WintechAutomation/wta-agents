"""rename-manuals-to-english.py — WTA 매뉴얼 파일/폴더명 한글→영어 변환.

data/wta-manuals-final/ 하위 폴더명 + 파일명을 영어로 변환.
원본→변환 매핑 로그를 data/rename_log.json에 저장.

Usage:
  py scripts/rename-manuals-to-english.py --dry-run   # 미리보기만
  py scripts/rename-manuals-to-english.py              # 실제 변환
"""

import argparse
import hashlib
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_DIR = os.path.join(BASE_DIR, "data", "wta-manuals-final")

# 카테고리(폴더) 매핑
CATEGORY_MAP = {
    "CBN": "CBN",
    "CVD": "CVD",
    "PVD": "PVD",
    "WBM_WVR대성호닝": "WBM_WVR_Daesung_Honing",
    "검사기": "Inspection",
    "라벨부착기": "Labeling",
    "레이저마킹기": "Laser_Marking",
    "리팔레팅": "Repalleting",
    "마스크자동기": "Mask_Auto",
    "마코호": "Macoho",
    "상하면연삭기": "Double_Side_Grinder",
    "소결취출기": "Sintering_Sorter",
    "편면연삭기": "Single_Side_Grinder",
    "포장기": "Packaging",
    "프레스": "Press",
    "호닝기": "Honing",
    "호닝형상검사기": "Honing_Inspection",
    "후지산기연삭핸들러": "Fujisanki_Grinding_Handler",
}

# 파일명 한글→영어 단어 매핑
WORD_MAP = {
    # 장비/기계
    "소결취출기": "Sintering_Sorter",
    "프레스": "Press",
    "핸들러": "Handler",
    "편면연삭기": "Single_Side_Grinder",
    "연삭기": "Grinder",
    "검사기": "Inspection",
    "마킹기": "Marking",
    "포장기": "Packaging",
    "호닝기": "Honing",
    "상하면": "Double_Side",
    "라벨부착기": "Labeling",
    "리팔레팅": "Repalleting",
    "마스크자동기": "Mask_Auto",
    # 문서 유형
    "유지 보수": "Maintenance",
    "유지보수": "Maintenance",
    "사용자 매뉴얼": "User_Manual",
    "사용자매뉴얼": "User_Manual",
    "매뉴얼": "Manual",
    "메뉴얼": "Manual",
    "취급설명서": "Instruction_Manual",
    "사용설명서": "Instruction_Manual",
    "설비 외형": "Equipment_Outline",
    "외형": "Outline",
    "조작설명서": "Operation_Manual",
    "작동설명서": "Operation_Manual",
    "操作说明书": "Operation_Manual",
    "使用说明书": "User_Manual",
    "使用手册": "User_Manual",
    "包装机": "Packaging",
    "华锐": "Huarui",
    "株洲钻石": "Zhuzhou_Diamond",
    "烧结后整列机": "Sintering_Sorter",
    "梱包機": "Packaging_Machine",
    "パッキング装置": "Packaging_Equipment",
    "マニュアル書": "Manual",
    "マニュアル": "Manual",
    "アクシス": "Axis",
    "プレス整列機": "Press_Sorter",
    "プレス": "Press",
    "整列機": "Sorter",
    "号機": "Unit",
    "号": "Unit",
    "　": "_",
    # 회사/고객명
    "다인정공": "Dain_Precision",
    "한국야금": "Korea_Tungsten",
    "한국교세라": "Korea_Kyocera",
    "교세라": "Kyocera",
    "몰디노": "Moldino",
    "스탈리": "Stahli",
    "후지산키": "Fujisanki",
    "후지산기": "Fujisanki",
    "대성호닝": "Daesung_Honing",
    "마코호": "Macoho",
    "화루이": "Huarui",
    "기후": "Gifu",
    "하이썽": "Haisheng",
    "삼성": "Samsung",
    "미쓰비시": "Mitsubishi",
    "三菱マテリアル": "Mitsubishi_Materials",
    "プレスマニュアル": "Press_Manual",
    "세라티즈": "Ceratizit",
    "탕가로이": "Tungaloy",
    "웨이카이": "Weikai",
    "리펑": "Lifeng",
    "주주쫜스": "Zhuzhou",
    # 동작/상태
    "번역 완료": "Translated",
    "완성본": "Final",
    "사진수정본": "Photo_Revised",
    "소모품 업데이트 버전": "Consumables_Updated",
    "작업자": "Operator",
    "출력 가능": "Printable",
    "1차 수정": "Rev1",
    "1차 제출": "Rev1_Submit",
    "최종본": "Final",
    "자동 복구됨": "Auto_Recovered",
    "미완성": "Draft",
    "진짜 마지막": "Final",
    "진짜": "Real",
    "수정": "Revised",
    "한문": "Chinese",
    "매뉴얼용": "For_Manual",
    # 기타
    "컨베어타입": "Conveyor_Type",
    "하부": "Lower",
    "상부": "Upper",
    "중국어": "Chinese",
    "일본어": "Japanese",
    "中文": "Chinese",
    "연삭": "Grinding",
    "호닝형상": "Honing_Shape",
    "레이저": "Laser",
    "청주": "Cheongju",
    "로딩": "Loading",
    "언로딩": "Unloading",
    "호기": "Unit",
}

# 긴 키부터 매칭 (부분 매칭 방지)
_SORTED_WORDS = sorted(WORD_MAP.keys(), key=len, reverse=True)


def translate_name(name):
    """한글 포함 파일/폴더명을 영어로 변환."""
    # 확장자 분리
    stem, ext = os.path.splitext(name)

    # 이미 ASCII-only면 특수문자만 정리
    if re.match(r"^[a-zA-Z0-9._() #,\[\]-]+$", stem):
        clean = re.sub(r"[^a-zA-Z0-9._-]", "_", stem)
        clean = re.sub(r"_+", "_", clean).strip("_")
        return clean + ext

    result = stem
    # 한글/중국어/일본어 단어를 영어로 치환
    for kr in _SORTED_WORDS:
        result = result.replace(kr, WORD_MAP[kr])

    # 남은 non-ASCII 제거, 공백/특수문자 → underscore
    result = re.sub(r"[^a-zA-Z0-9._-]", "_", result)
    result = re.sub(r"_+", "_", result).strip("_")

    if not result:
        result = hashlib.md5(stem.encode("utf-8")).hexdigest()[:12]

    return result + ext


def check_collision(mapping):
    """변환 후 파일명 충돌 확인 및 해결."""
    # 폴더별로 그룹
    by_folder = {}
    for entry in mapping:
        folder = entry["new_folder"]
        new_name = entry["new_name"]
        key = f"{folder}/{new_name}"
        by_folder.setdefault(key, []).append(entry)

    collisions = 0
    for key, entries in by_folder.items():
        if len(entries) > 1:
            collisions += 1
            # 충돌 시 원본 해시 접미사 추가
            for i, entry in enumerate(entries[1:], 1):
                stem, ext = os.path.splitext(entry["new_name"])
                short_hash = hashlib.md5(
                    entry["old_name"].encode("utf-8")
                ).hexdigest()[:6]
                entry["new_name"] = f"{stem}_{short_hash}{ext}"

    return collisions


def main():
    parser = argparse.ArgumentParser(description="WTA 매뉴얼 파일명 한→영 변환")
    parser.add_argument("--dry-run", action="store_true", help="미리보기만")
    args = parser.parse_args()

    if not os.path.isdir(SOURCE_DIR):
        print(f"ERROR: {SOURCE_DIR} 없음")
        sys.exit(1)

    # 1. 매핑 생성
    mapping = []
    folders = sorted(os.listdir(SOURCE_DIR))
    for folder in folders:
        folder_path = os.path.join(SOURCE_DIR, folder)
        if not os.path.isdir(folder_path):
            continue

        new_folder = CATEGORY_MAP.get(folder, folder)

        for fname in sorted(os.listdir(folder_path)):
            fpath = os.path.join(folder_path, fname)
            if not os.path.isfile(fpath):
                continue

            new_name = translate_name(fname)
            changed = (folder != new_folder) or (fname != new_name)

            mapping.append({
                "old_folder": folder,
                "new_folder": new_folder,
                "old_name": fname,
                "new_name": new_name,
                "changed": changed,
            })

    # 2. 충돌 해결
    collisions = check_collision(mapping)

    # 3. 통계
    total = len(mapping)
    changed = sum(1 for m in mapping if m["changed"])
    folder_changes = len(
        {m["old_folder"] for m in mapping if m["old_folder"] != m["new_folder"]}
    )

    print(f"총 파일: {total}")
    print(f"변경 대상: {changed}")
    print(f"폴더 변경: {folder_changes}")
    print(f"충돌 해결: {collisions}")
    print()

    # 4. 변환 샘플 출력
    print("=== 폴더 매핑 ===")
    seen_folders = set()
    for m in mapping:
        key = m["old_folder"]
        if key not in seen_folders and key != m["new_folder"]:
            seen_folders.add(key)
            print(f"  {key} => {m['new_folder']}")
    print()

    print("=== 파일명 변환 샘플 (최대 30개) ===")
    count = 0
    for m in mapping:
        if m["old_name"] != m["new_name"]:
            print(f"  [{m['old_folder']}] {m['old_name']}")
            print(f"    => {m['new_name']}")
            count += 1
            if count >= 30:
                print(f"  ... (나머지 {changed - count}개 생략)")
                break
    print()

    if args.dry_run:
        print("[DRY-RUN] 실제 변경 없음.")
        # 매핑 로그만 저장
        log_path = os.path.join(BASE_DIR, "data", "rename_log.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        print(f"매핑 로그: {log_path}")
        return

    # 5. 실제 변환
    print("=== 변환 실행 ===")

    # 5a. 파일명 변환 (폴더 내부부터)
    renamed_files = 0
    errors = []
    for m in mapping:
        if m["old_name"] == m["new_name"]:
            continue
        old_path = os.path.join(SOURCE_DIR, m["old_folder"], m["old_name"])
        new_path = os.path.join(SOURCE_DIR, m["old_folder"], m["new_name"])
        if os.path.exists(old_path):
            # 대상이 이미 존재하면 해시 접미사 추가
            if os.path.exists(new_path) and old_path != new_path:
                stem, ext = os.path.splitext(m["new_name"])
                short_hash = hashlib.md5(
                    m["old_name"].encode("utf-8")
                ).hexdigest()[:6]
                m["new_name"] = f"{stem}_{short_hash}{ext}"
                new_path = os.path.join(
                    SOURCE_DIR, m["old_folder"], m["new_name"]
                )
            for attempt in range(3):
                try:
                    os.rename(old_path, new_path)
                    renamed_files += 1
                    break
                except PermissionError:
                    import time
                    time.sleep(1)
            else:
                errors.append(f"PERM: {old_path}")

    print(f"  파일명 변환: {renamed_files}개")
    if errors:
        print(f"  실패: {len(errors)}개")
        for e in errors[:5]:
            print(f"    {e}")

    # 5b. 폴더명 변환
    renamed_folders = 0
    for old_folder, new_folder in CATEGORY_MAP.items():
        if old_folder == new_folder:
            continue
        old_path = os.path.join(SOURCE_DIR, old_folder)
        new_path = os.path.join(SOURCE_DIR, new_folder)
        if os.path.exists(old_path) and not os.path.exists(new_path):
            os.rename(old_path, new_path)
            renamed_folders += 1

    print(f"  폴더명 변환: {renamed_folders}개")

    # 6. 매핑 로그 저장
    log_path = os.path.join(BASE_DIR, "data", "rename_log.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"\n매핑 로그: {log_path}")
    print("완료!")


if __name__ == "__main__":
    main()
