"""
네트워크 motion 폴더 xlsx/xls 수집 + 로컬 복사
수집 기준 (파일명에 하나라도 포함):
  - 체크리스트 / checklist / information / infomation / Axis
  - 프로젝트 코드 패턴 (알파벳대문자 3~6자 + 숫자 5자 이상)
  - 호기 포함
결과: workspaces/db-manager/motion-xlsx/ 에 경로 prefix 붙여 복사
"""
import sys, os, json, re, shutil
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = '//192.168.1.6/motion/1.Robot & Motion'
OUT_DIR = 'C:/MES/wta-agents/workspaces/db-manager/motion-xlsx'
RESULT_FILE = 'C:/MES/wta-agents/workspaces/db-manager/motion-xlsx-result.json'
EXTS = ('.xlsx', '.xls')

# 키워드 매칭 (대소문자 무시)
KEYWORDS = ['체크리스트', 'checklist', 'information', 'infomation', 'axis', '호기']

# 프로젝트 코드 패턴: 대문자 알파벳 3-6자 + 숫자 5자 이상 (예: HPLPB02305001, HIMF12508001, HS3ME02203003)
PROJECT_CODE_PATTERN = re.compile(r'[A-Z]{2,6}\d{5,}')

os.makedirs(OUT_DIR, exist_ok=True)

def should_include(fname):
    fl = fname.lower()
    # 키워드 체크
    if any(kw.lower() in fl for kw in KEYWORDS):
        return True
    # 프로젝트 코드 패턴 체크 (원본 파일명 대소문자 유지)
    if PROJECT_CODE_PATTERN.search(fname):
        return True
    return False

def make_dest_name(rel_path):
    """상대경로를 prefix로 붙인 파일명 생성"""
    # rel_path 예: 1. 한국야금\1. NC Press\16. 26~27th(NC10-5,6)\NC10-5 호기 체크리스트.xlsx
    parts = rel_path.replace('/', os.sep).split(os.sep)
    # 각 부분 정제 (특수문자 → _)
    cleaned = []
    for p in parts:
        c = re.sub(r'[<>:"/\\|?*]', '_', p)  # 파일시스템 금지문자 제거
        c = c.strip('. ')  # 앞뒤 점/공백 제거
        if c:
            cleaned.append(c)
    return '_'.join(cleaned)

print(f'탐색 시작: {BASE}')
print(f'출력 폴더: {OUT_DIR}')
print()

found = []
errors = []
scanned_dirs = 0
total_xlsx = 0
total_xls = 0

for root, dirs, files in os.walk(BASE, followlinks=False):
    scanned_dirs += 1
    if scanned_dirs % 500 == 0:
        print(f'  {scanned_dirs}개 폴더 탐색 중... (발견: {len(found)}개)')

    for fname in files:
        fl = fname.lower()
        if fl.endswith('.xlsx'):
            total_xlsx += 1
        elif fl.endswith('.xls'):
            total_xls += 1
        else:
            continue

        if not should_include(fname):
            continue

        fpath = os.path.join(root, fname)
        rel_path = os.path.relpath(fpath, BASE)

        try:
            size = os.path.getsize(fpath)
            dest_name = make_dest_name(rel_path)
            dest_path = os.path.join(OUT_DIR, dest_name)

            # 이미 복사된 파일이면 스킵
            if os.path.exists(dest_path):
                found.append({'name': fname, 'rel_path': rel_path,
                              'size_kb': round(size / 1024, 1),
                              'dest': dest_name, 'status': 'skipped'})
                continue

            shutil.copy2(fpath, dest_path)
            found.append({'name': fname, 'rel_path': rel_path,
                          'size_kb': round(size / 1024, 1),
                          'dest': dest_name, 'status': 'copied'})

        except Exception as e:
            errors.append({'path': fpath, 'error': str(e)})
            if len(errors) <= 10:
                print(f'  ERR: {fname} — {e}')

print(f'\n탐색 완료: {scanned_dirs}개 폴더')
print(f'전체 xlsx: {total_xlsx}개, xls: {total_xls}개')
print(f'수집 대상: {len(found)}개, 오류: {len(errors)}개')

copied = sum(1 for f in found if f['status'] == 'copied')
skipped = sum(1 for f in found if f['status'] == 'skipped')
print(f'복사 완료: {copied}개, 스킵(기존): {skipped}개')

# 결과 저장
result = {
    'total': len(found),
    'copied': copied,
    'skipped': skipped,
    'errors': len(errors),
    'scanned_dirs': scanned_dirs,
    'total_xlsx_in_tree': total_xlsx,
    'total_xls_in_tree': total_xls,
    'files': found,
    'error_list': errors[:50]
}
with open(RESULT_FILE, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f'결과 저장: {RESULT_FILE}')

# 샘플 출력
print('\n샘플 (최대 20개):')
for item in found[:20]:
    print(f'  [{item["size_kb"]}KB] {item["name"]}')
    print(f'    -> {item["dest"]}')
