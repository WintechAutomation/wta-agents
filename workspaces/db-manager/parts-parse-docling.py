"""
부품매뉴얼 Docling 파싱 — part1 (1_robot, 2_sensor, 3_hmi)
파싱만 수행, 임베딩은 제외.
결과: data/parts-parsed/{category}/{파일명}.md
진행상태: workspaces/db-manager/parts-parse-progress.json (멱등성)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os, json, logging, time, re
from pathlib import Path

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions, TableStructureOptions, TableFormerMode,
)
from docling.datamodel.base_models import InputFormat

# --- 설정 ---
BASE = Path('C:/MES/wta-agents')
MANUALS_DIR = BASE / 'data' / 'manuals-ready'
OUTPUT_DIR = BASE / 'data' / 'parts-parsed'
PROGRESS_FILE = BASE / 'workspaces' / 'db-manager' / 'parts-parse-progress.json'
LOG_FILE = BASE / 'workspaces' / 'db-manager' / 'parts-parse.log'

CATEGORIES = ['1_robot', '2_sensor', '3_hmi']

logging.basicConfig(
    level=logging.INFO,
    format='[parts-parse] %(asctime)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_FILE), encoding='utf-8'),
    ]
)
log = logging.getLogger('parts-parse')

# --- 진행상태 로드 ---
if PROGRESS_FILE.exists():
    with open(PROGRESS_FILE, encoding='utf-8') as f:
        progress = json.load(f)
else:
    progress = {'done': [], 'failed': [], 'skipped': []}

done_set = set(progress['done'])
failed_set = set(progress['failed'])

def save_progress():
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

# --- Docling 컨버터 (싱글턴) ---
_converter = None

def get_converter():
    global _converter
    if _converter is not None:
        return _converter
    pipeline_options = PdfPipelineOptions()
    pipeline_options.generate_picture_images = False
    pipeline_options.generate_page_images = False
    pipeline_options.force_backend_text = True
    pipeline_options.do_ocr = False  # 속도 우선, OCR 제외
    pipeline_options.table_structure_options = TableStructureOptions(
        mode=TableFormerMode.FAST,  # ACCURATE → FAST: std::bad_alloc 방지 (MAX 사전 승인)
        do_cell_matching=True,
    )
    _converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )
    log.info('Docling 컨버터 초기화 완료')
    return _converter

def safe_stem(fname):
    return re.sub(r'[<>:"/\\|?*]', '_', Path(fname).stem)

# --- 전체 파일 목록 구성 ---
all_files = []
for cat in CATEGORIES:
    cat_dir = MANUALS_DIR / cat
    if not cat_dir.exists():
        log.warning(f'{cat} 디렉토리 없음')
        continue
    pdfs = sorted(f for f in os.listdir(cat_dir) if f.lower().endswith('.pdf'))
    for fname in pdfs:
        all_files.append((cat, fname, cat_dir / fname))

total = len(all_files)
log.info(f'대상 파일: {total}개 ({", ".join(f"{c}: {sum(1 for x in all_files if x[0]==c)}개" for c in CATEGORIES)})')
log.info(f'이미 완료: {len(done_set)}개, 실패: {len(failed_set)}개')

# --- 파싱 실행 ---
success = 0
failed = 0
skipped = 0

for idx, (cat, fname, fpath) in enumerate(all_files, 1):
    key = f'{cat}/{fname}'

    if key in done_set:
        skipped += 1
        continue

    out_dir = OUTPUT_DIR / cat
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'{safe_stem(fname)}.md'

    # 이미 MD 파일 존재하면 done 처리
    if out_path.exists() and out_path.stat().st_size > 100:
        progress['done'].append(key)
        done_set.add(key)
        skipped += 1
        if skipped % 20 == 0:
            save_progress()
        continue

    log.info(f'[{idx}/{total}] {key}')
    t0 = time.time()

    try:
        converter = get_converter()
        result = converter.convert(str(fpath))
        md_text = result.document.export_to_markdown()

        if not md_text or len(md_text.strip()) < 50:
            log.warning(f'  텍스트 부족 ({len(md_text)}자) — 건너뜀')
            progress['skipped'].append(key)
            save_progress()
            skipped += 1
            continue

        # 메타데이터 헤더 추가
        header = f'---\nsource_file: {fname}\ncategory: {cat}\n---\n\n'
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(header + md_text)

        elapsed = round(time.time() - t0, 1)
        log.info(f'  완료: {len(md_text):,}자, {elapsed}s → {out_path.name}')

        progress['done'].append(key)
        done_set.add(key)
        success += 1

    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        log.error(f'  실패: {e} ({elapsed}s)')
        progress['failed'].append(key)
        failed_set.add(key)
        failed += 1

    # 10개마다 저장
    if (success + failed) % 10 == 0:
        save_progress()
        log.info(f'  진행: done={len(done_set)}, failed={len(failed_set)}, skipped={skipped}')

save_progress()
log.info(f'=== 완료 === 성공:{success}, 실패:{failed}, 건너뜀:{skipped}, 누적완료:{len(done_set)}')
