"""네트워크 폴더 xlsx 파일 수집 (information/체크리스트/checklist 조건)"""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = '//192.168.1.6/motion/1.Robot & Motion'
OUT_LIST = 'C:/MES/wta-agents/workspaces/db-manager/network-xlsx-list.json'

KEYWORDS = ['information', '체크리스트', 'checklist']

found = []
errors = []
total_size = 0
scanned_dirs = 0

def should_include(fname):
    fl = fname.lower()
    return any(kw.lower() in fl for kw in KEYWORDS)

print(f'탐색 시작: {BASE}')
print(f'조건: {KEYWORDS}')
print()

for root, dirs, files in os.walk(BASE, followlinks=False):
    scanned_dirs += 1
    if scanned_dirs % 100 == 0:
        print(f'  {scanned_dirs}개 폴더 탐색 중... (발견: {len(found)}개)')

    for fname in files:
        if not fname.lower().endswith('.xlsx'):
            continue
        if not should_include(fname):
            continue

        fpath = os.path.join(root, fname)
        try:
            size = os.path.getsize(fpath)
            rel_path = os.path.relpath(fpath, BASE)
            found.append({
                'name': fname,
                'path': fpath,
                'rel_path': rel_path,
                'size_kb': round(size / 1024, 1),
            })
            total_size += size
        except Exception as e:
            errors.append({'path': fpath, 'error': str(e)})

print(f'\n탐색 완료: {scanned_dirs}개 폴더')
print(f'발견 파일: {len(found)}개, 총 {total_size//1024//1024}MB')
print(f'오류: {len(errors)}개')

# 결과 저장
result = {
    'total': len(found),
    'total_size_mb': round(total_size / 1024 / 1024, 1),
    'scanned_dirs': scanned_dirs,
    'errors': len(errors),
    'files': found
}
with open(OUT_LIST, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f'목록 저장: {OUT_LIST}')

# 샘플 출력
print('\n샘플 파일 (최대 20개):')
for item in found[:20]:
    print(f'  [{item["size_kb"]}KB] {item["rel_path"]}')
