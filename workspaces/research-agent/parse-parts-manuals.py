"""
부품매뉴얼 Docling 파싱 스크립트 (파트2: 4_servo ~ 8_etc)
임베딩 없이 파싱만 수행, data/parts-parsed/{카테고리}/{파일명}.md 저장
"""
import sys, os, json, time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PYTHON311 = r'C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe'
BASE_DIR = Path('C:/MES/wta-agents')
SOURCE_BASE = BASE_DIR / 'data' / 'manuals-ready'
OUTPUT_BASE = BASE_DIR / 'data' / 'parts-parsed'
PROGRESS_FILE = BASE_DIR / 'workspaces' / 'research-agent' / 'parts-parse-progress.json'

CATEGORIES = ['4_servo', '5_inverter', '6_plc', '7_pneumatic', '8_etc']
SUPPORTED_EXTS = {'.pdf', '.docx'}

# 진행 상황 로드
if PROGRESS_FILE.exists():
    with open(PROGRESS_FILE, encoding='utf-8') as f:
        progress = json.load(f)
else:
    progress = {'done': [], 'failed': [], 'skipped': []}

done_set = set(progress['done'])

def save_progress():
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

import fitz  # PyMuPDF

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

def extract_docx(src_file):
    """python-docx로 DOCX 텍스트 추출 → Markdown"""
    try:
        from docx import Document
        doc = Document(str(src_file))
        lines = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                style = para.style.name if para.style else ''
                if 'Heading 1' in style:
                    lines.append(f'# {text}')
                elif 'Heading 2' in style:
                    lines.append(f'## {text}')
                elif 'Heading 3' in style:
                    lines.append(f'### {text}')
                else:
                    lines.append(text)
        return '\n\n'.join(lines)
    except Exception as e:
        return f'[DOCX 추출 실패: {e}]'

print('[init] PyMuPDF 파서 준비 완료')

total_success = 0
total_failed = 0
total_skipped = 0

for cat in CATEGORIES:
    src_dir = SOURCE_BASE / cat
    out_dir = OUTPUT_BASE / cat
    out_dir.mkdir(parents=True, exist_ok=True)

    if not src_dir.exists():
        print(f'[SKIP] {cat}: 폴더 없음')
        continue

    files = [f for f in src_dir.iterdir()
             if f.suffix.lower() in SUPPORTED_EXTS
             and '_excluded' not in str(f)]
    files.sort()
    total = len(files)
    cat_success = 0
    cat_failed = 0

    print(f'\n[{cat}] {total}개 파일 파싱 시작 (이미 완료: {sum(1 for f in files if str(f) in done_set)}개)')

    for i, src_file in enumerate(files):
        file_key = str(src_file)

        if file_key in done_set:
            total_skipped += 1
            continue

        out_md = out_dir / (src_file.stem + '.md')
        print(f'  [{i+1}/{total}] {src_file.name}')

        try:
            ext = src_file.suffix.lower()
            if ext == '.pdf':
                md_text = extract_pdf_pymupdf(src_file)
                method = 'pymupdf'
            elif ext == '.docx':
                md_text = extract_docx(src_file)
                method = 'python-docx'
            else:
                print(f'    SKIP 미지원 형식: {src_file.suffix}')
                continue
        except Exception as e:
            print(f'    ERR: {e}')
            progress['failed'].append({'file': file_key, 'error': str(e)})
            cat_failed += 1
            total_failed += 1
            continue

        if not md_text or len(md_text.strip()) < 10:
            print(f'    WARN 내용 없음: {src_file.name}')

        # 메타데이터 헤더 추가
        header = f'---\nsource: {src_file.name}\ncategory: {cat}\nmethod: {method}\nparsed_at: {time.strftime("%Y-%m-%d %H:%M:%S")}\n---\n\n'
        out_md.write_text(header + md_text, encoding='utf-8')

        progress['done'].append(file_key)
        done_set.add(file_key)
        cat_success += 1
        total_success += 1

        # 20개마다 저장
        if (cat_success + cat_failed) % 20 == 0:
            save_progress()
            print(f'  → 진행: {cat_success}완료/{cat_failed}실패/{total}전체')

    save_progress()
    print(f'[{cat}] 완료: {cat_success}개 성공, {cat_failed}개 실패')

save_progress()
print(f'\n=== 전체 완료 ===')
print(f'성공: {total_success}개, 실패: {total_failed}개, 스킵: {total_skipped}개')
print(f'저장: {OUTPUT_BASE}')
