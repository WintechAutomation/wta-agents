"""불필요 문서 150개를 manuals-ready/_excluded/로 이동"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json, os, shutil
from pathlib import Path

BASE = Path('C:/MES/wta-agents/data/manuals-ready')
EXCL = BASE / '_excluded'
LOG_FILE = Path('C:/MES/wta-agents/workspaces/db-manager/excluded-files.txt')

with open('C:/MES/wta-agents/workspaces/db-manager/manuals-analysis.json', encoding='utf-8') as f:
    data = json.load(f)

# 카테고리 결정: 한 파일이 여러 이유일 경우 일본어 > 중국어 > 카탈로그 우선
def get_excl_subdir(file_info):
    lang = file_info['lang']
    if lang == 'ja':
        return 'japanese'
    if lang == 'zh':
        return 'chinese'
    return 'catalog'

moved = []
errors = []

for cat_name, cat_info in data['details'].items():
    for f in cat_info['files']:
        if not f['is_unnecessary']:
            continue

        src = BASE / cat_name / f['name']
        subdir = get_excl_subdir(f)
        dst_dir = EXCL / subdir / cat_name
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f['name']

        if not src.exists():
            errors.append(f'[NOT FOUND] {cat_name}/{f["name"]}')
            continue
        if dst.exists():
            errors.append(f'[ALREADY EXISTS] {subdir}/{cat_name}/{f["name"]}')
            continue

        try:
            shutil.move(str(src), str(dst))
            moved.append(f'{subdir}/{cat_name}/{f["name"]}  (원본: {cat_name}/{f["name"]}, 이유: {f["reason"]})')
            print(f'  이동: {cat_name}/{f["name"]} -> _excluded/{subdir}/{cat_name}/')
        except Exception as e:
            errors.append(f'[ERROR] {cat_name}/{f["name"]}: {e}')

# 결과 확인
print(f'\n=== 이동 결과 ===')
print(f'이동 완료: {len(moved)}개')
print(f'오류: {len(errors)}개')

# 카테고리별 남은 파일 수 확인
print(f'\n=== 유효 문서 잔여 확인 ===')
total_remaining = 0
for cat in sorted(d for d in os.listdir(BASE) if os.path.isdir(BASE / d) and not d.startswith('_')):
    files = [f for f in os.listdir(BASE / cat) if f.lower().endswith('.pdf')]
    total_remaining += len(files)
    print(f'  {cat}: {len(files)}개')
print(f'  합계: {total_remaining}개 (목표: 1,145개)')

# _excluded 하위 확인
print(f'\n=== _excluded 폴더 확인 ===')
for subdir in ['japanese', 'chinese', 'catalog']:
    subpath = EXCL / subdir
    if subpath.exists():
        cnt = sum(len([f for f in os.listdir(subpath / cat) if f.lower().endswith('.pdf')])
                  for cat in os.listdir(subpath) if os.path.isdir(subpath / cat))
        print(f'  _excluded/{subdir}/: {cnt}개')

# 로그 파일 저장
with open(LOG_FILE, 'w', encoding='utf-8') as f:
    f.write(f'=== 불필요 문서 이동 목록 (총 {len(moved)}개) ===\n\n')
    for line in moved:
        f.write(line + '\n')
    if errors:
        f.write(f'\n=== 오류 ({len(errors)}개) ===\n')
        for line in errors:
            f.write(line + '\n')

print(f'\n로그 저장: {LOG_FILE}')

if errors:
    print('\n[오류 목록]')
    for e in errors:
        print(f'  {e}')
