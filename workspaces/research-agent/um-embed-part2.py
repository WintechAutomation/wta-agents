"""
UM 스페이스 part2 임베딩 (574건)
- confluence-UserManual/ HTML에서 텍스트 추출
- Qwen3-Embedding-8B (182.224.6.147:11434) 임베딩
- manual.wta_documents에 저장 (category: Confluence_UM)
"""
import requests, os, json, time, re, sys, hashlib, logging
from pathlib import Path

try:
    from bs4 import BeautifulSoup
    USE_BS4 = True
except ImportError:
    USE_BS4 = False

import psycopg2
from psycopg2.extras import execute_values

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── 설정 ──
BASE_DIR = Path('C:/MES/wta-agents/reports/MAX/confluence-UserManual')
PAGES_FILE = 'C:/MES/wta-agents/workspaces/research-agent/um-pages-part2.json'
PROGRESS_FILE = 'C:/MES/wta-agents/workspaces/research-agent/um-extract-part2-progress.json'

EMBED_URL = os.environ.get('EMBED_URL', 'http://182.224.6.147:11434/api/embed')
EMBED_MODEL = 'hf.co/Qwen/Qwen3-Embedding-8B-GGUF:Q4_K_M'
EMBED_DIM = 2000
EMBED_BATCH = 8
EMBED_DELAY = 0.5
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

DB_TABLE = 'manual.wta_documents'
CATEGORY = 'Confluence_UM'
DB_CONFIG = {
    'host': 'localhost',
    'port': 55432,
    'user': 'postgres',
    'password': 'your-super-secret-and-long-postgres-password',
    'dbname': 'postgres',
}

logging.basicConfig(
    level=logging.INFO,
    format='[um-embed] %(asctime)s %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('um-embed')

# ── 진행 상태 ──
if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, encoding='utf-8') as f:
        progress = json.load(f)
else:
    progress = {'done': [], 'failed': [], 'embedded': []}

embedded_set = set(progress.get('embedded', []))


def save_progress():
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


# ── 유틸 ──
def safe_dirname(page_id, title):
    safe = re.sub(r'[<>:"/\\|?*]', '_', title)
    return f'{page_id}-{safe.strip()[:60]}'


def html_to_text(html_content: str) -> str:
    """HTML에서 순수 텍스트 추출"""
    if USE_BS4:
        soup = BeautifulSoup(html_content, 'html.parser')
        # meta, style, script 제거
        for tag in soup(['style', 'script', 'meta', 'link']):
            tag.decompose()
        # .meta, .breadcrumb, .source-link div 제거
        for tag in soup.find_all(class_=['meta', 'breadcrumb', 'source-link']):
            tag.decompose()
        text = soup.get_text(separator='\n')
    else:
        # BeautifulSoup 없을 때 간단 정규식 처리
        text = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&#\d+;', '', text)
    # 빈 줄 정리
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l]
    return '\n'.join(lines)


# ── 청킹 ──
def chunk_text(text: str) -> list:
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - CHUNK_OVERLAP
    return chunks


# ── 임베딩 ──
def embed_texts(texts: list) -> list:
    try:
        r = requests.post(
            EMBED_URL,
            json={'model': EMBED_MODEL, 'input': texts},
            timeout=120,
        )
        if r.status_code == 200:
            embeddings = r.json().get('embeddings', [])
            # 2000차원 슬라이싱
            return [e[:EMBED_DIM] if len(e) > EMBED_DIM else e for e in embeddings]
        log.error(f'임베딩 API 오류: {r.status_code} {r.text[:200]}')
    except Exception as e:
        log.error(f'임베딩 오류: {e}')
    return None


# ── DB 저장 ──
def upsert_to_db(conn, rows: list) -> int:
    if not rows:
        return 0
    source_files = list({r['source_file'] for r in rows})
    cur = conn.cursor()
    for sf in source_files:
        cur.execute(
            f'DELETE FROM {DB_TABLE} WHERE source_file = %s AND category = %s',
            (sf, CATEGORY),
        )
    execute_values(
        cur,
        f'''INSERT INTO {DB_TABLE}
            (source_file, file_hash, category, chunk_index, chunk_type, page_number,
             content, image_url, metadata, embedding)
            VALUES %s''',
        [(
            r['source_file'], r['file_hash'], CATEGORY,
            r['chunk_index'], r['chunk_type'], 0,
            r['content'], r.get('image_url'),
            json.dumps(r.get('metadata', {}), ensure_ascii=False),
            r['embedding'],
        ) for r in rows],
        template='(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
    )
    conn.commit()
    cur.close()
    return len(rows)


# ── 페이지 임베딩 ──
def embed_page(page_id: str, page_dir: Path, metadata: dict, conn) -> int:
    # 1. page-text.txt 캐시 확인
    cache_path = page_dir / 'page-text.txt'
    if cache_path.exists():
        raw_text = cache_path.read_text(encoding='utf-8')
    else:
        # 2. index.html에서 텍스트 추출
        html_path = page_dir / 'index.html'
        if not html_path.exists():
            log.warning(f'  HTML 없음: {page_dir}')
            return 0
        html_content = html_path.read_text(encoding='utf-8', errors='replace')
        raw_text = html_to_text(html_content)
        # 캐시 저장
        cache_path.write_text(raw_text, encoding='utf-8')

    page_title = metadata.get('page_title', page_id)
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', page_title)[:60]
    source_file = f'confluence-UM/{page_id}-{safe_title}'
    file_hash = hashlib.md5(raw_text.encode()).hexdigest()
    chunks = chunk_text(raw_text)
    if not chunks:
        log.warning(f'  텍스트 없음: {page_id}')
        return 0

    rows = []
    for batch_start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[batch_start: batch_start + EMBED_BATCH]
        embeddings = embed_texts(batch)
        if embeddings is None:
            log.error(f'  임베딩 실패 {page_id} batch={batch_start}')
            return 0
        for i, (chunk, emb) in enumerate(zip(batch, embeddings)):
            rows.append({
                'source_file': source_file,
                'file_hash': file_hash,
                'chunk_index': batch_start + i,
                'chunk_type': 'text',
                'content': chunk,
                'metadata': metadata,
                'embedding': emb,
            })
        if batch_start + EMBED_BATCH < len(chunks):
            time.sleep(EMBED_DELAY)

    saved = upsert_to_db(conn, rows)
    return saved


# ── 메인 ──
with open(PAGES_FILE, encoding='utf-8') as f:
    pages = json.load(f)

total = len(pages)
success_embed = 0
failed = 0
skipped = 0

log.info(f'[UM-PART2] {total}개 페이지 임베딩 시작 (이미 완료: {len(embedded_set)}개)')
log.info(f'BeautifulSoup4: {"사용" if USE_BS4 else "미사용 (정규식 대체)"}')

conn = psycopg2.connect(**DB_CONFIG)
log.info('DB 연결 완료')

for i, page in enumerate(pages):
    page_id = str(page['id'])
    page_title = page.get('title', f'page-{page_id}')
    dir_name = safe_dirname(page_id, page_title)
    page_dir = BASE_DIR / dir_name

    if page_id in embedded_set:
        skipped += 1
        if (i + 1) % 50 == 0:
            log.info(f'진행: {i+1}/{total} (임베딩: {success_embed}, 스킵: {skipped}, 실패: {failed})')
        continue

    print(f'[{i+1}/{total}] {page_id} — {page_title[:50]}')

    metadata = {
        'page_id': page_id,
        'page_title': page_title,
        'space': 'UM',
        'url': f'https://iwta.atlassian.net/wiki/spaces/UM/pages/{page_id}',
    }

    saved = embed_page(page_id, page_dir, metadata, conn)
    if saved > 0:
        progress['embedded'].append(page_id)
        embedded_set.add(page_id)
        success_embed += 1
        print(f'  → {saved}청크 저장')
    else:
        progress['failed'].append({'id': page_id, 'title': page_title})
        failed += 1

    if (i + 1) % 20 == 0:
        save_progress()
        log.info(f'진행: {i+1}/{total} | 임베딩: {success_embed} | 스킵: {skipped} | 실패: {failed}')

    time.sleep(0.2)

save_progress()
if conn:
    conn.close()

print(f'\n=== UM PART2 임베딩 완료 ===')
print(f'임베딩 성공: {success_embed}건, 스킵: {skipped}건, 실패: {failed}건 / 전체 {total}건')
