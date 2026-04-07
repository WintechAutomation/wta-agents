"""classify-wta-manuals.py — WTA 장비 매뉴얼 파일 분류 스크립트.

data/wta-manuals/ 5,075+ 파일을 파일명 기준으로 분류:
- 사용자 매뉴얼 → data/wta-manuals-ready/
- 비매뉴얼 (도면, 사양서, 검사성적서 등) → 제외
- 중복 제거 (같은 장비 다른 수주건)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import hashlib
import json
import os
import re
import shutil
from pathlib import Path

SRC_DIR = Path("C:/MES/wta-agents/data/wta-manuals")
DST_DIR = Path("C:/MES/wta-agents/data/wta-manuals-ready")
REPORT_FILE = Path("C:/MES/wta-agents/data/wta-manuals-classify-report.json")

# 매뉴얼 포함 키워드 (파일명에 이 중 하나라도 있으면 매뉴얼 후보)
MANUAL_KEYWORDS = [
    # 한국어
    "매뉴얼", "메뉴얼", "취급설명서", "사용자", "조작", "유지보수",
    "유지 보수", "사용설명", "작동설명", "운전매뉴얼", "운전 매뉴얼",
    # 영어
    "user manual", "manual", "manu_", "_manu", "instruction", "operation guide",
    "maintenance", "operator",
    # 일본어
    "マニュアル", "取扱", "操作",
    # 중국어
    "使用手册", "操作手册", "用户手册", "使用手冊",
]

# 비매뉴얼 제외 키워드 (이 키워드가 있으면 매뉴얼이 아님)
EXCLUDE_KEYWORDS = [
    # 도면류
    "도면", "layout", "lay out", "lay-out", "외형도", "조립도", "assembly", "drawing",
    "배치도", "배선도", "회로도", "wiring", "schematic",
    "electrical diagram", "pneumatic diagram", "pneumatic circuit",
    "공압도", "(외형)", "(전체)", "외형)", "전체)",
    "assy", "total_assy",
    # 사양/검사류
    "사양서", "검사성적", "성적서", "시험성적", "검사 성적",
    "spec sheet", "datasheet", "data_sheet", "data sheet",
    "ctlg", "catalog", "카탈로그",
    # 행정/상업 서류
    "견적", "quotation", "invoice", "패킹", "packing list",
    "납품", "거래명세", "발주", "주문", "계약",
    # 기타 비매뉴얼
    "명판", "nameplate", "소모품", "consumables", "spare", "bom", "부품표",
    "사진", "photo", "img", "이미지",
    "interlock", "pneumatic", "preumatic",
    # 임시 파일
    "~$",
    # 번호만 있는 파일 (1.pdf, 2.pdf 등)
]

# 순수 숫자 파일명 패턴 (1.pdf, 2.pdf 등)
NUMERIC_ONLY_PATTERN = re.compile(r"^\d+\.(?:pdf|docx)$", re.IGNORECASE)

# 도면 번호 패턴: XX-XX-AXX-X (예: 16-01-A01-0, 03-05-A02-0)
DRAWING_NUMBER_PATTERN = re.compile(r"^\d{2,3}-\d{2}-[A-Z]\d{2}-\d")


def is_manual(filename: str) -> tuple[bool, str]:
    """파일명으로 매뉴얼 여부 판단. (is_manual, reason) 반환."""
    name_lower = filename.lower()
    basename_no_ext = Path(filename).stem

    # 0. 임시 파일 (~$) 제외
    if filename.startswith("~$"):
        return False, "temp_file"

    # 0.5. 순수 숫자 파일명 (1.pdf, 2.pdf) → 내용 불명, 제외
    if NUMERIC_ONLY_PATTERN.match(filename):
        return False, "numeric_only"

    # 1. 제외 키워드 체크 (우선, 단 매뉴얼 키워드도 함께 있으면 매뉴얼 우선)
    has_exclude = None
    for kw in EXCLUDE_KEYWORDS:
        if kw.lower() in name_lower:
            has_exclude = kw
            break

    # 2. 매뉴얼 키워드 체크
    has_manual = None
    for kw in MANUAL_KEYWORDS:
        if kw.lower() in name_lower:
            has_manual = kw
            break

    # "1. User Manual (xxx).pdf" 패턴
    if not has_manual and re.match(r"^\d+\.\s*(user\s+)?manual", name_lower):
        has_manual = "numbered_manual"

    # 매뉴얼 + 제외 키워드 동시 → 매뉴얼 우선 (예: "유지 보수 공압도" → 매뉴얼)
    if has_manual:
        return True, f"keyword:{has_manual}"

    if has_exclude:
        return False, f"exclude:{has_exclude}"

    # 3. 도면 번호 패턴 체크
    if DRAWING_NUMBER_PATTERN.match(basename_no_ext):
        return False, "drawing_number"

    # 4. 수주번호 패턴 (WT1806-CBN01-S02-A000-0 등) → 도면
    if re.match(r"^(WT|HG|HP|HS|HA)\w+-", basename_no_ext, re.IGNORECASE):
        return False, "project_drawing"

    # 5. WTA 자체 제작 장비 문서 패턴 (고객사+장비명 형태)
    # "press handler HP3", "핸들러", "handler" 등
    wta_equipment_patterns = [
        r"handler\s+hp\d",              # handler HP3 등
        r"press\s+handler",             # press handler
        r"핸들러",                       # 한국어 핸들러
        r"(?:loading|unloading)\s+mc",  # Loading MC, Unloading MC
        r"프레스핸들러",
        r"프레스\s*매뉴얼",
        r"使用说明书",                   # 중국어 사용설명서
    ]
    for pat in wta_equipment_patterns:
        if re.search(pat, name_lower):
            return True, f"wta_equipment:{pat}"

    # 6. 키워드 없음 → 불확실, 기본 제외
    return False, "no_keyword"


def file_hash(filepath: Path) -> str:
    """파일 SHA256 해시 (앞 16자)."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def classify():
    """전체 분류 실행."""
    results = {
        "manual": [],       # 매뉴얼로 분류된 파일
        "excluded": [],     # 제외된 파일
        "duplicate": [],    # 중복 제거된 파일
    }
    stats = {
        "total_files": 0,
        "manual_count": 0,
        "excluded_count": 0,
        "duplicate_count": 0,
        "by_category": {},
        "exclude_reasons": {},
    }

    # 해시 기반 중복 체크
    seen_hashes = {}  # hash → first filepath

    DST_DIR.mkdir(parents=True, exist_ok=True)

    for cat_dir in sorted(SRC_DIR.iterdir()):
        if not cat_dir.is_dir():
            continue
        cat_name = cat_dir.name
        cat_stats = {"total": 0, "manual": 0, "excluded": 0, "duplicate": 0}

        dst_cat = DST_DIR / cat_name
        # 실제 복사는 분류 완료 후

        for fpath in sorted(cat_dir.iterdir()):
            if not fpath.is_file():
                continue
            stats["total_files"] += 1
            cat_stats["total"] += 1

            fname = fpath.name
            is_man, reason = is_manual(fname)

            if not is_man:
                results["excluded"].append({
                    "path": f"{cat_name}/{fname}",
                    "reason": reason,
                })
                cat_stats["excluded"] += 1
                stats["exclude_reasons"][reason] = stats["exclude_reasons"].get(reason, 0) + 1
                continue

            # 중복 체크
            fhash = file_hash(fpath)
            if fhash in seen_hashes:
                results["duplicate"].append({
                    "path": f"{cat_name}/{fname}",
                    "duplicate_of": seen_hashes[fhash],
                    "hash": fhash,
                })
                cat_stats["duplicate"] += 1
                stats["duplicate_count"] += 1
                continue

            seen_hashes[fhash] = f"{cat_name}/{fname}"
            results["manual"].append({
                "path": f"{cat_name}/{fname}",
                "reason": reason,
                "hash": fhash,
                "size_mb": round(fpath.stat().st_size / (1024 * 1024), 1),
            })
            cat_stats["manual"] += 1
            stats["manual_count"] += 1

        stats["by_category"][cat_name] = cat_stats
        stats["excluded_count"] += cat_stats["excluded"]

    # 결과 저장
    report = {"stats": stats, "results": results}
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return stats, results


def copy_manuals(results):
    """분류된 매뉴얼을 wta-manuals-ready/로 복사."""
    copied = 0
    for item in results["manual"]:
        src = SRC_DIR / item["path"]
        dst = DST_DIR / item["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(str(src), str(dst))
            copied += 1
    return copied


def main():
    print("=" * 60)
    print("WTA 장비 매뉴얼 분류")
    print(f"소스: {SRC_DIR}")
    print(f"대상: {DST_DIR}")
    print("=" * 60)

    # 1. 분류
    print("\n[1/2] 파일 분류 중...")
    stats, results = classify()

    print(f"\n전체 파일: {stats['total_files']}개")
    print(f"매뉴얼:    {stats['manual_count']}개")
    print(f"제외:      {stats['excluded_count']}개")
    print(f"중복:      {stats['duplicate_count']}개")

    print("\n카테고리별:")
    for cat, cs in sorted(stats["by_category"].items()):
        print(f"  {cat}: 전체 {cs['total']} → 매뉴얼 {cs['manual']} / 제외 {cs['excluded']} / 중복 {cs['duplicate']}")

    print("\n제외 사유:")
    for reason, cnt in sorted(stats["exclude_reasons"].items(), key=lambda x: -x[1]):
        print(f"  {reason}: {cnt}개")

    # 2. 복사
    print("\n[2/2] 매뉴얼 파일 복사 중...")
    copied = copy_manuals(results)
    print(f"복사 완료: {copied}개")

    print(f"\n상세 리포트: {REPORT_FILE}")


if __name__ == "__main__":
    main()
