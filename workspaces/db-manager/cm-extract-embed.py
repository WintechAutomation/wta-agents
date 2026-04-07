"""
CM 스페이스 후반부 추출 + 임베딩 (db-manager 담당: 385~767번, 383개 페이지)
research-agent extract-cm-part1.py와 동일 구조 + 벡터 임베딩 추가

실행:
  python cm-extract-embed.py              # 전체 처리 (추출 + 임베딩)
  python cm-extract-embed.py --skip-embed # HTML 추출만 (임베딩 없음)
  python cm-extract-embed.py --embed-only # 이미 추출된 HTML을 임베딩만
"""
import requests, os, json, time, re, sys, html as html_module, hashlib, logging
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── 설정 ──
TOKEN = open('C:/MES/wta-agents/config/atlassian-api-token.txt').read().strip()
AUTH = ('hjcho@wta.kr', TOKEN)
BASE = 'https://iwta.atlassian.net'
BASE_DIR = Path('C:/MES/wta-agents/reports/MAX/confluence-CM')
BASE_DIR.mkdir(parents=True, exist_ok=True)

PAGES_FILE = 'C:/MES/wta-agents/workspaces/research-agent/cm-pages-part2.json'
PROGRESS_FILE = 'C:/MES/wta-agents/workspaces/db-manager/cm-extract-part2-progress.json'

TIMEOUT = 30
MAX_RETRIES = 3

# 임베딩 설정
EMBED_URL = os.environ.get('EMBED_URL', 'http://182.224.6.147:11434/api/embed')
EMBED_MODEL = 'hf.co/Qwen/Qwen3-Embedding-8B-GGUF:Q4_K_M'
EMBED_DIM = 2000
EMBED_BATCH = 8
EMBED_DELAY = 0.5
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

DB_TABLE = 'manual.wta_documents'
CATEGORY = 'Confluence_CM'
DB_CONFIG = {
    'host': 'localhost',
    'port': 55432,
    'user': 'postgres',
    'password': 'your-super-secret-and-long-postgres-password',
    'dbname': 'postgres',
}

logging.basicConfig(
    level=logging.INFO,
    format='[cm-embed] %(asctime)s %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('cm-embed')

# ── 진행 상태 ──
if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, encoding='utf-8') as f:
        progress = json.load(f)
else:
    progress = {'done': [], 'failed': [], 'embedded': []}

done_set = set(progress['done'])
embedded_set = set(progress.get('embedded', []))


def save_progress():
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


# ── 유틸 ──
def safe_dirname(page_id, title):
    safe = re.sub(r'[<>:"/\\|?*]', '_', title)
    return f'{page_id}-{safe.strip()[:60]}'


def get_with_retry(url, stream=False):
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, auth=AUTH, allow_redirects=True, timeout=TIMEOUT, stream=stream)
            return r
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise


# ── ADF → HTML ──
def adf_to_html(node, images_dir_name='images'):
    if not isinstance(node, dict):
        return ''
    ntype = node.get('type', '')
    content = node.get('content', [])

    if ntype == 'doc':
        return '\n'.join(adf_to_html(c, images_dir_name) for c in content)
    elif ntype == 'paragraph':
        inner = ''.join(adf_to_html(c, images_dir_name) for c in content)
        return f'<p>{inner}</p>' if inner.strip() else '<br>'
    elif ntype == 'text':
        text = html_module.escape(node.get('text', ''))
        for mark in node.get('marks', []):
            mt = mark.get('type', '')
            if mt == 'strong': text = f'<strong>{text}</strong>'
            elif mt == 'em': text = f'<em>{text}</em>'
            elif mt == 'code': text = f'<code>{text}</code>'
            elif mt == 'link':
                href = mark.get('attrs', {}).get('href', '#')
                text = f'<a href="{html_module.escape(href)}" target="_blank">{text}</a>'
            elif mt == 'underline': text = f'<u>{text}</u>'
            elif mt == 'strike': text = f'<s>{text}</s>'
        return text
    elif ntype == 'heading':
        level = node.get('attrs', {}).get('level', 2)
        inner = ''.join(adf_to_html(c, images_dir_name) for c in content)
        return f'<h{level}>{inner}</h{level}>'
    elif ntype == 'bulletList':
        items = ''.join(
            f'<li>{"".join(adf_to_html(c, images_dir_name) for c in item.get("content", []))}</li>'
            for item in content if item.get('type') == 'listItem'
        )
        return f'<ul>{items}</ul>'
    elif ntype == 'orderedList':
        items = ''.join(
            f'<li>{"".join(adf_to_html(c, images_dir_name) for c in item.get("content", []))}</li>'
            for item in content if item.get('type') == 'listItem'
        )
        return f'<ol>{items}</ol>'
    elif ntype == 'listItem':
        return ''.join(adf_to_html(c, images_dir_name) for c in content)
    elif ntype in ('mediaSingle', 'mediaGroup'):
        parts = []
        for c in content:
            if c.get('type') == 'media':
                attrs = c.get('attrs', {})
                media_id = attrs.get('id', '')
                alt = html_module.escape(attrs.get('alt', ''))
                if media_id:
                    parts.append(
                        f'<figure><img src="{images_dir_name}/{media_id}" alt="{alt}" '
                        f'style="max-width:100%;border:1px solid #ddd;border-radius:4px;margin:8px 0;">'
                        f'<figcaption style="font-size:12px;color:#666;">{alt}</figcaption></figure>'
                    )
        return '\n'.join(parts)
    elif ntype == 'codeBlock':
        lang = node.get('attrs', {}).get('language', '')
        code = ''.join(c.get('text', '') for c in content if c.get('type') == 'text')
        return f'<pre><code class="language-{lang}">{html_module.escape(code)}</code></pre>'
    elif ntype == 'blockquote':
        inner = '\n'.join(adf_to_html(c, images_dir_name) for c in content)
        return f'<blockquote style="border-left:4px solid #ddd;padding-left:12px;color:#555;">{inner}</blockquote>'
    elif ntype == 'table':
        rows = ''.join(adf_to_html(c, images_dir_name) for c in content)
        return f'<table style="border-collapse:collapse;width:100%;margin:12px 0;">{rows}</table>'
    elif ntype == 'tableRow':
        cells = ''.join(adf_to_html(c, images_dir_name) for c in content)
        return f'<tr>{cells}</tr>'
    elif ntype in ('tableCell', 'tableHeader'):
        tag = 'th' if ntype == 'tableHeader' else 'td'
        inner = ''.join(adf_to_html(c, images_dir_name) for c in content)
        style = 'border:1px solid #ddd;padding:6px 10px;'
        if ntype == 'tableHeader':
            style += 'background:#f4f5f7;font-weight:bold;'
        return f'<{tag} style="{style}">{inner}</{tag}>'
    elif ntype == 'rule':
        return '<hr>'
    elif ntype == 'hardBreak':
        return '<br>'
    elif ntype == 'inlineCard':
        url = node.get('attrs', {}).get('url', '')
        return f'<a href="{html_module.escape(url)}" target="_blank">{html_module.escape(url)}</a>'
    elif ntype == 'panel':
        panel_type = node.get('attrs', {}).get('panelType', 'info')
        colors = {'info': '#deebff', 'note': '#fffae6', 'warning': '#fff3cd', 'error': '#ffebe6', 'success': '#e3fcef'}
        bg = colors.get(panel_type, '#f4f5f7')
        inner = '\n'.join(adf_to_html(c, images_dir_name) for c in content)
        return f'<div style="background:{bg};border-radius:4px;padding:12px 16px;margin:12px 0;">{inner}</div>'
    elif ntype == 'expand':
        title = node.get('attrs', {}).get('title', '')
        inner = '\n'.join(adf_to_html(c, images_dir_name) for c in content)
        return f'<details><summary><strong>{html_module.escape(title)}</strong></summary>{inner}</details>'
    else:
        return '\n'.join(adf_to_html(c, images_dir_name) for c in content)


# ── ADF → 순수 텍스트 (임베딩용) ──
def adf_to_text(node) -> str:
    if not isinstance(node, dict):
        return ''
    ntype = node.get('type', '')
    content = node.get('content', [])

    if ntype == 'text':
        return node.get('text', '')
    if ntype in ('paragraph', 'listItem', 'tableCell', 'tableHeader'):
        return ''.join(adf_to_text(c) for c in content) + '\n'
    if ntype == 'heading':
        return ''.join(adf_to_text(c) for c in content) + '\n'
    if ntype == 'table':
        rows = []
        for row in content:
            cells = [adf_to_text(cell).strip() for cell in row.get('content', [])]
            rows.append(' | '.join(cells))
        return '\n'.join(rows) + '\n'
    if ntype in ('mediaSingle', 'media'):
        alt = node.get('attrs', {}).get('alt', '')
        return f'[이미지: {alt}]\n' if alt else ''
    if ntype == 'codeBlock':
        code = ''.join(c.get('text', '') for c in content if c.get('type') == 'text')
        return code + '\n'
    return ''.join(adf_to_text(c) for c in content)


# ── 청킹 ──
def chunk_text(text: str) -> list[str]:
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
def embed_texts(texts: list[str]) -> list[list[float]] | None:
    try:
        r = requests.post(
            EMBED_URL,
            json={'model': EMBED_MODEL, 'input': texts},
            timeout=120,
        )
        if r.status_code == 200:
            return r.json().get('embeddings', [])
        log.error(f'임베딩 API 오류: {r.status_code} {r.text[:200]}')
    except Exception as e:
        log.error(f'임베딩 오류: {e}')
    return None


# ── DB 저장 ──
def upsert_to_db(conn, rows: list[dict]) -> int:
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
    cache_path = page_dir / 'page-text.txt'
    if cache_path.exists():
        raw_text = cache_path.read_text(encoding='utf-8')
    else:
        log.warning(f'  텍스트 캐시 없음: {page_id}')
        return 0

    safe_title = re.sub(r'[<>:"/\\|?*]', '_', metadata.get('page_title', page_id))[:60]
    source_file = f'confluence-CM/{page_id}-{safe_title}'
    file_hash = hashlib.md5(raw_text.encode()).hexdigest()
    chunks = chunk_text(raw_text)
    if not chunks:
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


# ── 페이지 추출 ──
def extract_page(page_id: str, page_title: str) -> bool:
    dir_name = safe_dirname(page_id, page_title)
    page_dir = BASE_DIR / dir_name
    images_dir = page_dir / 'images'
    page_dir.mkdir(exist_ok=True)
    images_dir.mkdir(exist_ok=True)

    url = f'{BASE}/wiki/rest/api/content/{page_id}?expand=body.atlas_doc_format,version,ancestors'
    try:
        r = get_with_retry(url)
    except Exception as e:
        print(f'  ERR [{page_id}] {page_title}: {e}')
        return False

    if r.status_code != 200:
        print(f'  ERR [{page_id}] HTTP {r.status_code}')
        return False

    page_data = r.json()
    adf_value = page_data.get('body', {}).get('atlas_doc_format', {}).get('value', '{}')
    try:
        adf = json.loads(adf_value)
    except Exception:
        adf = {}

    # 첨부파일 이미지 다운로드
    att_url = f'{BASE}/wiki/rest/api/content/{page_id}/child/attachment?limit=100'
    try:
        att_r = get_with_retry(att_url)
        attachments = att_r.json().get('results', []) if att_r.status_code == 200 else []
    except Exception:
        attachments = []

    media_id_map = {}
    downloaded = 0
    for att in attachments:
        if not att.get('metadata', {}).get('mediaType', '').startswith('image/'):
            continue
        att_id = att['id']
        filename = att['title']
        file_id = att.get('extensions', {}).get('fileId', att_id)
        save_path = images_dir / filename

        if save_path.exists():
            media_id_map[file_id] = filename
            media_id_map[att_id] = filename
            downloaded += 1
            continue

        dl_url = f'{BASE}/wiki/rest/api/content/{page_id}/child/attachment/{att_id}/download'
        try:
            img_r = get_with_retry(dl_url)
            if img_r.status_code == 200 and len(img_r.content) > 0:
                save_path.write_bytes(img_r.content)
                media_id_map[file_id] = filename
                media_id_map[att_id] = filename
                downloaded += 1
        except Exception as e:
            print(f'    WARN 이미지 [{att_id}]: {e}')
        time.sleep(0.1)

    # HTML 생성
    body_html = adf_to_html(adf, 'images')
    for media_id, fname in media_id_map.items():
        body_html = body_html.replace(f'images/{media_id}"', f'images/{fname}"')
    body_html = re.sub(r'images/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"', 'images/not-found"', body_html)
    body_html = re.sub(r'images/att\d+"', 'images/not-found"', body_html)

    ancestors = page_data.get('ancestors', [])
    breadcrumb = ' > '.join(a['title'] for a in ancestors) + (' > ' if ancestors else '') + page_title
    version = page_data.get('version', {}).get('number', '')
    confluence_url = f'https://iwta.atlassian.net/wiki/spaces/CM/pages/{page_id}'

    html_content = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_module.escape(page_title)}</title>
<style>
  body {{ font-family: 'Malgun Gothic', sans-serif; max-width: 1100px; margin: 0 auto; padding: 24px; color: #172B4D; line-height: 1.7; }}
  h1 {{ font-size: 22px; color: #0052CC; border-bottom: 3px solid #0052CC; padding-bottom: 10px; margin-bottom: 20px; }}
  h2 {{ font-size: 17px; color: #253858; border-left: 4px solid #0065FF; padding-left: 10px; margin-top: 28px; }}
  h3 {{ font-size: 15px; color: #253858; margin-top: 20px; }}
  .meta {{ background: #F4F5F7; padding: 10px 14px; border-radius: 4px; font-size: 12px; color: #6B778C; margin-bottom: 20px; }}
  .breadcrumb {{ font-size: 12px; color: #6B778C; margin-bottom: 16px; }}
  img {{ max-width: 100%; height: auto; border: 1px solid #DFE1E6; border-radius: 4px; display: block; margin: 12px 0; }}
  figure {{ margin: 16px 0; }}
  figcaption {{ font-size: 11px; color: #6B778C; margin-top: -8px; }}
  pre {{ background: #F4F5F7; padding: 12px; border-radius: 4px; overflow-x: auto; font-size: 13px; }}
  code {{ background: #F4F5F7; padding: 1px 4px; border-radius: 2px; font-size: 13px; }}
  pre code {{ background: none; padding: 0; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  td, th {{ border: 1px solid #DFE1E6; padding: 6px 10px; }}
  th {{ background: #F4F5F7; }}
  ul, ol {{ padding-left: 20px; }}
  li {{ margin-bottom: 4px; }}
  a {{ color: #0065FF; }}
  .source-link {{ font-size: 12px; color: #0065FF; margin-top: 24px; border-top: 1px solid #DFE1E6; padding-top: 12px; }}
</style>
</head>
<body>
<div class="breadcrumb">{html_module.escape(breadcrumb)}</div>
<h1>{html_module.escape(page_title)}</h1>
<div class="meta">
  <span>📄 페이지 ID: {page_id}</span> &nbsp;
  <span>🔖 버전: {version}</span> &nbsp;
  <span>🖼️ 이미지: {downloaded}개</span>
</div>
{body_html}
<p class="source-link">🔗 원본: <a href="{confluence_url}" target="_blank">{confluence_url}</a></p>
</body>
</html>'''

    (page_dir / 'index.html').write_text(html_content, encoding='utf-8')

    # 임베딩용 텍스트 캐시 저장
    plain_text = adf_to_text(adf).strip()
    (page_dir / 'page-text.txt').write_text(plain_text, encoding='utf-8')

    return True


# ── 메인 ──
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--skip-embed', action='store_true', help='HTML 추출만, 임베딩 건너뜀')
parser.add_argument('--embed-only', action='store_true', help='임베딩만 (추출 건너뜀)')
args = parser.parse_args()

with open(PAGES_FILE, encoding='utf-8') as f:
    pages = json.load(f)

total = len(pages)
success_extract = 0
success_embed = 0
failed = 0

log.info(f'[PART2] {total}개 페이지 처리 시작 (이미 추출: {len(done_set)}개, 임베딩: {len(embedded_set)}개)')

conn = None
if not args.skip_embed:
    conn = psycopg2.connect(**DB_CONFIG)
    log.info('DB 연결 완료')

for i, page in enumerate(pages):
    page_id = str(page['id'])
    page_title = page.get('title', f'page-{page_id}')
    dir_name = safe_dirname(page_id, page_title)
    page_dir = BASE_DIR / dir_name

    print(f'[{i+1}/{total}] {page_id} — {page_title[:50]}')

    # 1. HTML 추출
    if not args.embed_only:
        if page_id in done_set:
            success_extract += 1
        else:
            ok = extract_page(page_id, page_title)
            if ok:
                progress['done'].append(page_id)
                done_set.add(page_id)
                success_extract += 1
            else:
                progress['failed'].append({'id': page_id, 'title': page_title})
                failed += 1
                continue

    # 2. 임베딩
    if not args.skip_embed and page_id not in embedded_set:
        metadata = {
            'page_id': page_id,
            'page_title': page_title,
            'space': 'CM',
            'url': f'https://iwta.atlassian.net/wiki/spaces/CM/pages/{page_id}',
        }
        saved = embed_page(page_id, page_dir, metadata, conn)
        if saved > 0:
            progress['embedded'].append(page_id)
            embedded_set.add(page_id)
            success_embed += 1
            print(f'  → 임베딩 {saved}건 저장')
    elif page_id in embedded_set:
        success_embed += 1

    if (i + 1) % 20 == 0:
        save_progress()
        log.info(f'진행: 추출 {success_extract}건 / 임베딩 {success_embed}건 / 실패 {failed}건 / 전체 {total}건')

    time.sleep(0.3)

save_progress()
if conn:
    conn.close()

print(f'\n=== PART2 완료 ===')
print(f'추출 성공: {success_extract}건, 임베딩 성공: {success_embed}건, 실패: {failed}건')
