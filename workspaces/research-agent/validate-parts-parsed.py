"""
parts-parsed/ 품질 검증 스크립트
- 빈 파일, 짧은 파일, CID 코드, 표 추출, 텍스트 깨짐 확인
"""
import sys, os, json, re
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTPUT_BASE = Path('C:/MES/wta-agents/data/parts-parsed')
CATEGORIES = ['4_servo', '5_inverter', '6_plc', '7_pneumatic', '8_etc']
REPORT_FILE = Path('C:/MES/wta-agents/workspaces/research-agent/parts-validate-report.json')

CID_PATTERN = re.compile(r'\(cid:\d+\)')
TABLE_PATTERN = re.compile(r'^\|.+\|', re.MULTILINE)
KOREAN_PATTERN = re.compile(r'[\uAC00-\uD7A3]')

results = {}
summary = {'total': 0, 'empty': 0, 'too_short': 0, 'cid_issues': 0, 'has_table': 0, 'has_korean': 0}

for cat in CATEGORIES:
    cat_dir = OUTPUT_BASE / cat
    if not cat_dir.exists():
        print(f'[{cat}] 폴더 없음 (아직 파싱 안 됨)')
        continue

    md_files = sorted(cat_dir.glob('*.md'))
    total = len(md_files)
    if total == 0:
        print(f'[{cat}] MD 파일 없음')
        continue

    # 10개마다 1개 샘플 선택
    sample_step = max(1, total // 10)
    samples = md_files[::sample_step][:10]

    cat_result = {
        'total': total,
        'empty': [],
        'too_short': [],
        'cid_issues': [],
        'no_table': [],
        'broken_text': [],
        'samples': []
    }

    print(f'\n[{cat}] {total}개 MD 파일 검증 중...')

    for md_file in md_files:
        size = md_file.stat().st_size
        if size == 0:
            cat_result['empty'].append(md_file.name)
            continue

        content = md_file.read_text(encoding='utf-8', errors='replace')
        char_count = len(content)

        if char_count < 100:
            cat_result['too_short'].append({'file': md_file.name, 'chars': char_count})

        if CID_PATTERN.search(content):
            cid_count = len(CID_PATTERN.findall(content))
            cat_result['cid_issues'].append({'file': md_file.name, 'cid_count': cid_count})

    # 샘플 상세 검증
    for md_file in samples:
        if not md_file.exists():
            continue
        content = md_file.read_text(encoding='utf-8', errors='replace')
        has_table = bool(TABLE_PATTERN.search(content))
        has_korean = bool(KOREAN_PATTERN.search(content))
        cid_count = len(CID_PATTERN.findall(content))
        # 앞 200자 미리보기
        preview = content[200:400].replace('\n', ' ')[:100]

        sample_info = {
            'file': md_file.name,
            'size_bytes': md_file.stat().st_size,
            'chars': len(content),
            'has_table': has_table,
            'has_korean': has_korean,
            'cid_count': cid_count,
            'preview': preview
        }
        cat_result['samples'].append(sample_info)

        if has_table:
            summary['has_table'] += 1
        if has_korean:
            summary['has_korean'] += 1

    # 출력
    print(f'  총: {total}개')
    print(f'  빈 파일: {len(cat_result["empty"])}개')
    print(f'  100자 미만: {len(cat_result["too_short"])}개')
    print(f'  CID 이슈: {len(cat_result["cid_issues"])}개')
    if cat_result['cid_issues'][:3]:
        for c in cat_result['cid_issues'][:3]:
            print(f'    - {c["file"]}: CID {c["cid_count"]}개')
    print(f'  샘플 {len(cat_result["samples"])}개:')
    for s in cat_result['samples'][:3]:
        print(f'    [{s["file"][:40]}] {s["chars"]}자, 표:{s["has_table"]}, 한국어:{s["has_korean"]}, CID:{s["cid_count"]}')

    summary['total'] += total
    summary['empty'] += len(cat_result['empty'])
    summary['too_short'] += len(cat_result['too_short'])
    summary['cid_issues'] += len(cat_result['cid_issues'])
    results[cat] = cat_result

print(f'\n=== 전체 검증 요약 ===')
print(f'총 MD 파일: {summary["total"]}개')
print(f'빈 파일: {summary["empty"]}개')
print(f'100자 미만: {summary["too_short"]}개')
print(f'CID 이슈: {summary["cid_issues"]}개')

with open(REPORT_FILE, 'w', encoding='utf-8') as f:
    json.dump({'summary': summary, 'categories': results}, f, ensure_ascii=False, indent=2)
print(f'리포트 저장: {REPORT_FILE}')
