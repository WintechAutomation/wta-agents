"""filter-wta-manuals.py — WTA 매뉴얼 추가 필터링.

wta-manuals-ready/ → wta-manuals-final/
1. 동일 장비 수주건별 중복 제거 (SHA256 해시 기준)
2. 같은 내용의 docx/pdf 쌍 → pdf만 유지
3. 국가별(언어별) 매뉴얼은 모두 유지
4. "수정중", "복사본" 등 작업 중 파일 제외
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import hashlib
import json
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path

SRC_DIR = Path("C:/MES/wta-agents/data/wta-manuals-ready")
DST_DIR = Path("C:/MES/wta-agents/data/wta-manuals-final")
REPORT_FILE = Path("C:/MES/wta-agents/data/wta-manuals-filter-report.json")


def file_hash(filepath: Path) -> str:
    """SHA256 해시."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def detect_language(filename: str) -> str:
    """파일명에서 언어 감지."""
    name = filename.lower()
    # 명시적 언어 태그
    if re.search(r'\(kr\)|\(kor\)|_kr\b|_kor\b|한국어|korean', name):
        return 'KO'
    if re.search(r'\(en\)|\(eng\)|_en\b|_eng\b|english|\ben\b.*manual', name):
        return 'EN'
    if re.search(r'\(jp\)|\(jpn\)|_jp\b|_jpn\b|日本語|japanese|マニュアル|取扱', name):
        return 'JP'
    if re.search(r'\(cn\)|\(chn\)|_cn\b|_chn\b|中文|中國|chinese|중국어|使用手册|操作说明|气压|气动', name):
        return 'CN'
    # 한국어 파일명
    if re.search(r'[가-힣]{2,}', filename):
        return 'KO'
    # 기본값
    return 'UNKNOWN'


def normalize_equipment_name(filename: str) -> str:
    """파일명에서 장비명 추출하여 정규화 (중복 판별용)."""
    name = Path(filename).stem.lower()
    # 언어 태그 제거
    name = re.sub(r'\s*\((kr|ko|en|eng|jp|jpn|cn|chn|kor|중문|中文|중국어|한국어|일본어)\)\s*', '', name, flags=re.IGNORECASE)
    # 버전 태그 제거
    name = re.sub(r'_v\d+\.\d+', '', name)
    name = re.sub(r'\s*v\d+\.\d+', '', name)
    # 날짜 태그 제거
    name = re.sub(r'\[?\d{6,8}\]?\s*', '', name)
    # 수주번호 제거 (HGDCH02305001 등)
    name = re.sub(r'^[A-Z]{2,5}\d{8,}[-~]?\d*\s*', '', name)
    # 공백/특수문자 정규화
    name = re.sub(r'[\s_\-]+', ' ', name).strip()
    return name


def is_draft_or_copy(filename: str) -> bool:
    """수정중/복사본/작업중 파일 판별."""
    name = filename.lower()
    draft_patterns = [
        '수정중', '복사본', '작업중', '편집중', '편집후',
        '임시', 'temp', 'draft', 'copy', '(com)',
        '참고용', '출력용', '_old', '_bak',
    ]
    for pat in draft_patterns:
        if pat in name:
            return True
    return False


def main():
    print("=" * 60)
    print("WTA 매뉴얼 추가 필터링")
    print(f"입력: {SRC_DIR}")
    print(f"출력: {DST_DIR}")
    print("=" * 60)

    # 모든 파일 수집
    all_files = []
    for cat_dir in sorted(SRC_DIR.iterdir()):
        if not cat_dir.is_dir():
            continue
        for fpath in sorted(cat_dir.iterdir()):
            if fpath.is_file():
                all_files.append({
                    'path': fpath,
                    'cat': cat_dir.name,
                    'name': fpath.name,
                    'rel': f"{cat_dir.name}/{fpath.name}",
                })

    print(f"\n입력 파일: {len(all_files)}개")

    # 1단계: 수정중/복사본 제외
    draft_removed = []
    remaining = []
    for f in all_files:
        if is_draft_or_copy(f['name']):
            draft_removed.append(f['rel'])
        else:
            remaining.append(f)
    print(f"수정중/복사본 제외: {len(draft_removed)}개")

    # 2단계: 해시 계산
    for f in remaining:
        f['hash'] = file_hash(f['path'])
        f['lang'] = detect_language(f['name'])
        f['ext'] = f['path'].suffix.lower()
        f['size'] = f['path'].stat().st_size
        f['equip'] = normalize_equipment_name(f['name'])

    # 3단계: 해시 기반 완전 중복 제거 (카테고리 간)
    hash_groups = defaultdict(list)
    for f in remaining:
        hash_groups[f['hash']].append(f)

    hash_dedup = []
    hash_removed = []
    for h, group in hash_groups.items():
        if len(group) == 1:
            hash_dedup.append(group[0])
        else:
            # 같은 내용 여러 카테고리 → 첫 번째만 유지
            # PDF 우선 (같은 내용이면 PDF > DOCX)
            group.sort(key=lambda f: (0 if f['ext'] == '.pdf' else 1, f['cat']))
            hash_dedup.append(group[0])
            for f in group[1:]:
                hash_removed.append({
                    'removed': f['rel'],
                    'kept': group[0]['rel'],
                    'hash': h,
                })
    print(f"해시 중복 제거: {len(hash_removed)}개")

    # 4단계: docx/pdf 쌍 제거 (같은 폴더, 같은 파일명, 다른 확장자)
    # 같은 카테고리 + 같은 stem → PDF만 유지
    stem_groups = defaultdict(list)
    for f in hash_dedup:
        stem = Path(f['name']).stem
        key = f"{f['cat']}/{stem}"
        stem_groups[key].append(f)

    pair_dedup = []
    pair_removed = []
    for key, group in stem_groups.items():
        if len(group) == 1:
            pair_dedup.append(group[0])
        else:
            exts = {f['ext'] for f in group}
            if '.pdf' in exts and '.docx' in exts:
                # PDF 유지, DOCX 제거
                for f in group:
                    if f['ext'] == '.pdf':
                        pair_dedup.append(f)
                    else:
                        pair_removed.append({
                            'removed': f['rel'],
                            'reason': 'docx_pdf_pair',
                        })
            else:
                # 같은 stem + 같은 확장자 → 크기 큰 것 유지
                group.sort(key=lambda f: -f['size'])
                pair_dedup.append(group[0])
                for f in group[1:]:
                    pair_removed.append({
                        'removed': f['rel'],
                        'reason': 'same_stem_dup',
                    })
    print(f"docx/pdf 쌍 제거: {len(pair_removed)}개")

    # 5단계: 언어별 통계
    lang_stats = defaultdict(int)
    for f in pair_dedup:
        lang_stats[f['lang']] += 1

    print(f"\n최종 파일: {len(pair_dedup)}개")
    print("언어별:")
    for lang, cnt in sorted(lang_stats.items(), key=lambda x: -x[1]):
        print(f"  {lang}: {cnt}개")

    # 카테고리별 통계
    cat_stats = defaultdict(int)
    for f in pair_dedup:
        cat_stats[f['cat']] += 1
    print("\n카테고리별:")
    for cat, cnt in sorted(cat_stats.items()):
        print(f"  {cat}: {cnt}개")

    # 6단계: 복사
    DST_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    for f in pair_dedup:
        dst = DST_DIR / f['cat'] / f['name']
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(str(f['path']), str(dst))
            copied += 1

    print(f"\n복사 완료: {copied}개 → {DST_DIR}")

    # 리포트 저장
    report = {
        'input_count': len(all_files),
        'output_count': len(pair_dedup),
        'draft_removed': len(draft_removed),
        'hash_removed': len(hash_removed),
        'pair_removed': len(pair_removed),
        'lang_stats': dict(lang_stats),
        'cat_stats': dict(cat_stats),
        'details': {
            'drafts': draft_removed,
            'hash_dups': hash_removed,
            'pair_dups': pair_removed,
        },
        'final_files': [
            {'rel': f['rel'], 'lang': f['lang'], 'hash': f['hash'],
             'size_mb': round(f['size'] / (1024*1024), 1)}
            for f in pair_dedup
        ],
    }
    with open(REPORT_FILE, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(f"리포트: {REPORT_FILE}")


if __name__ == "__main__":
    main()
