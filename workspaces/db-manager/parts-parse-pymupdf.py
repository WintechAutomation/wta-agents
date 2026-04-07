"""
부품매뉴얼 PyMuPDF 파싱 — part1 (1_robot, 2_sensor, 3_hmi)
Docling 대비 100배 빠름. 깨진 유니코드 파일은 별도 목록으로 분류.
결과: data/parts-parsed/{category}/{파일명}.md
진행상태: workspaces/db-manager/parts-parse-progress.json (멱등성, 기존 완료 유지)
"""
import sys, os, json, time, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path
import fitz  # PyMuPDF

BASE = Path('C:/MES/wta-agents')
SOURCE_BASE = BASE / 'data' / 'manuals-ready'
OUTPUT_BASE = BASE / 'data' / 'parts-parsed'
PROGRESS_FILE = BASE / 'workspaces' / 'db-manager' / 'parts-parse-progress.json'
BROKEN_LIST_FILE = BASE / 'workspaces' / 'db-manager' / 'parts-parse-broken.json'

CATEGORIES = ['1_robot', '2_sensor', '3_hmi']

# --- 진행상태 로드 (기존 Docling 완료분 유지) ---
if PROGRESS_FILE.exists():
    with open(PROGRESS_FILE, encoding='utf-8') as f:
        progress = json.load(f)
else:
    progress = {'done': [], 'failed': [], 'skipped': []}

# 기존 done은 파일명 기반(cat/fname), 신규도 동일 키 사용
done_set = set(progress['done'])
broken_files = []

def save_progress():
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

def detect_broken(text):
    """깨진 유니코드 비율 감지 (비표준 폰트 → 대체문자 다수)"""
    if not text:
        return True
    replacement = text.count('\ufffd')  # 유니코드 대체문자
    total = len(text)
    if total == 0:
        return True
    ratio = replacement / total
    return ratio > 0.05  # 5% 이상이면 깨진 것으로 판단

def extract_pdf_pymupdf(src_file):
    """PyMuPDF로 PDF 텍스트 추출 → Markdown"""
    doc = fitz.open(str(src_file))
    pages_md = []
    for pno in range(len(doc)):
        page = doc[pno]
        blocks = page.get_text('blocks', sort=True)
        page_lines = []
        for b in blocks:
            text = b[4].strip()
            if text:
                page_lines.append(text)
        if page_lines:
            pages_md.append(f'## 페이지 {pno+1}\n\n' + '\n\n'.join(page_lines))
    doc.close()
    return '\n\n---\n\n'.join(pages_md)

print('[init] PyMuPDF 파서 준비 완료')
print(f'[init] 기존 완료: {len(done_set)}개 (건너뜀)')

total_success = 0
total_failed = 0
total_skipped = 0
total_broken = 0

for cat in CATEGORIES:
    src_dir = SOURCE_BASE / cat
    out_dir = OUTPUT_BASE / cat
    out_dir.mkdir(parents=True, exist_ok=True)

    if not src_dir.exists():
        print(f'[SKIP] {cat}: 폴더 없음')
        continue

    files = sorted(f for f in src_dir.iterdir() if f.suffix.lower() == '.pdf')
    total = len(files)
    already = sum(1 for f in files if f'{cat}/{f.name}' in done_set)
    print(f'\n[{cat}] {total}개 파일 (이미 완료: {already}개)')

    cat_success = 0
    cat_failed = 0
    cat_broken = 0

    for i, src_file in enumerate(files):
        key = f'{cat}/{src_file.name}'

        if key in done_set:
            total_skipped += 1
            continue

        out_md = out_dir / (src_file.stem + '.md')
        # 기존 MD 파일 있으면 skip (Docling 결과 보존)
        if out_md.exists() and out_md.stat().st_size > 100:
            progress['done'].append(key)
            done_set.add(key)
            total_skipped += 1
            continue

        t0 = time.time()
        try:
            md_text = extract_pdf_pymupdf(src_file)
            elapsed = round(time.time() - t0, 2)
        except Exception as e:
            print(f'  [{i+1}/{total}] ERR {src_file.name}: {e}')
            progress['failed'].append({'file': key, 'error': str(e)})
            cat_failed += 1
            total_failed += 1
            continue

        if not md_text or len(md_text.strip()) < 10:
            print(f'  [{i+1}/{total}] WARN 내용 없음: {src_file.name}')

        # 깨진 유니코드 감지
        is_broken = detect_broken(md_text)
        if is_broken:
            cat_broken += 1
            total_broken += 1
            broken_files.append({'file': key, 'size': src_file.stat().st_size})

        # 메타데이터 헤더
        header = (f'---\nsource: {src_file.name}\ncategory: {cat}\n'
                  f'method: pymupdf\nbroken: {is_broken}\n'
                  f'parsed_at: {time.strftime("%Y-%m-%d %H:%M:%S")}\n---\n\n')
        out_md.write_text(header + md_text, encoding='utf-8')

        progress['done'].append(key)
        done_set.add(key)
        cat_success += 1
        total_success += 1

        if (i + 1) % 50 == 0:
            print(f'  [{i+1}/{total}] 진행 중... (성공:{cat_success}, 실패:{cat_failed}, 깨짐:{cat_broken})')
            save_progress()
        elif cat_success <= 3 or cat_success % 20 == 0:
            print(f'  [{i+1}/{total}] {src_file.name} ({len(md_text):,}자, {elapsed}s, broken={is_broken})')

    save_progress()
    print(f'[{cat}] 완료: {cat_success}성공, {cat_failed}실패, {cat_broken}깨짐')

# 깨진 파일 목록 저장
with open(BROKEN_LIST_FILE, 'w', encoding='utf-8') as f:
    json.dump({'total': total_broken, 'files': broken_files}, f, ensure_ascii=False, indent=2)

save_progress()
print(f'\n=== 전체 완료 ===')
print(f'성공: {total_success}개, 실패: {total_failed}개, 스킵: {total_skipped}개, 깨짐: {total_broken}개')
print(f'깨진 파일 목록: {BROKEN_LIST_FILE}')
