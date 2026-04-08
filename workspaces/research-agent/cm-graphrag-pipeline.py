"""
research-agent CM GraphRAG 파이프라인 (439건)
- db-manager 담당(328건) 제외한 나머지 CM 페이지 처리
- HTML → 텍스트 추출 → 엔티티/관계 추출 → Neo4j + pgvector 저장

실행:
  python cm-graphrag-pipeline.py               # 전체
  python cm-graphrag-pipeline.py --graph-only  # GraphRAG(엔티티+Neo4j)만
  python cm-graphrag-pipeline.py --embed-only  # 임베딩만
  python cm-graphrag-pipeline.py --test 5      # 첫 5건만 테스트
"""
import sys, os, json, re, time, hashlib, logging, argparse, base64
from pathlib import Path

import requests
import psycopg2
from psycopg2.extras import execute_values

try:
    from bs4 import BeautifulSoup
    USE_BS4 = True
except ImportError:
    USE_BS4 = False

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── 설정 ──────────────────────────────────────────────────────────
WORKSPACE     = Path('C:/MES/wta-agents/workspaces/research-agent')
PAGES_FILE    = WORKSPACE / 'cm-graphrag-pages.json'
GRAPH_PROG    = WORKSPACE / 'cm-graphrag-progress.json'
ENTITIES_DIR  = WORKSPACE / 'entities'
ENTITIES_DIR.mkdir(exist_ok=True)

BASE_DIR      = Path('C:/MES/wta-agents/reports/MAX/confluence-CM')
OLLAMA_BASE   = 'http://182.224.6.147:11434'
EMBED_MODEL   = 'qwen3-embedding:8b'
VISION_MODEL  = 'qwen3-vl:8b'
EXTRACT_MODEL = 'qwen3.5:35b-a3b'
EMBED_DIM     = 2000
EMBED_BATCH   = 8
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100

DB_TABLE  = 'manual.wta_documents'
CATEGORY  = 'Confluence_CM'
DB_CONFIG = {
    'host': 'localhost', 'port': 55432,
    'user': 'postgres',
    'password': 'your-super-secret-and-long-postgres-password',
    'dbname': 'postgres',
}

NEO4J_ENV = WORKSPACE / 'neo4j-poc.env'
NEO4J_PASS = ''
for line in NEO4J_ENV.read_text().splitlines():
    if line.startswith('NEO4J_AUTH=neo4j/'):
        NEO4J_PASS = line.split('/', 1)[1].strip()
        break

VALID_NODE_TYPES = {'Customer','Equipment','Product','Component','Process',
                    'Issue','Resolution','Person','Tool','Manual'}
VALID_REL_TYPES  = {'OWNS','HAS_ISSUE','SIMILAR_TO','RESOLVED_BY',
                    'INVOLVES_COMPONENT','USES_COMPONENT','INVOLVED_IN',
                    'HAS_SUBPROCESS','USES_TOOL','MAINTAINS','DOCUMENTS'}

logging.basicConfig(
    level=logging.INFO,
    format='[ra-graphrag] %(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(WORKSPACE / 'cm-graphrag.log'), encoding='utf-8'),
    ]
)
log = logging.getLogger('ra-graphrag')

# ── 진행 상태 ──────────────────────────────────────────────────────
def load_progress(path: Path) -> dict:
    if path.exists():
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {'embedded': [], 'graph_done': [], 'failed': []}

def save_progress(prog: dict, path: Path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(prog, f, ensure_ascii=False, indent=2)


# ── HTML → 텍스트 추출 ─────────────────────────────────────────────
def html_to_text(html_content: str) -> str:
    if USE_BS4:
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup(['style', 'script', 'meta', 'link']):
            tag.decompose()
        for tag in soup.find_all(class_=['meta', 'breadcrumb', 'source-link']):
            tag.decompose()
        text = soup.get_text(separator='\n')
    else:
        text = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&nbsp;', ' ', text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return '\n'.join(lines)


def get_page_text(page_id: str, page_dir: Path) -> str:
    cache = page_dir / 'page-text.txt'
    if cache.exists() and cache.stat().st_size > 0:
        return cache.read_text(encoding='utf-8').strip()
    html_path = page_dir / 'index.html'
    if not html_path.exists():
        return ''
    html_content = html_path.read_text(encoding='utf-8', errors='replace')
    text = html_to_text(html_content)
    cache.write_text(text, encoding='utf-8')
    return text.strip()


# ── 유틸 ──────────────────────────────────────────────────────────
def chunk_text(text: str) -> list:
    text = text.strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def get_image_context(page_text: str, img_filename: str, context_lines: int = 5) -> str:
    lines = page_text.splitlines()
    img_name = Path(img_filename).stem
    for i, line in enumerate(lines):
        if img_name in line or img_filename in line:
            start = max(0, i - context_lines)
            end = min(len(lines), i + context_lines + 1)
            ctx = [l for l in lines[start:end] if l.strip() and img_filename not in l]
            return '\n'.join(ctx).strip()
    return ''


# ── LLM 비전 이미지 설명 ──────────────────────────────────────────
def describe_image(img_path: Path, context: str = '') -> str:
    if not img_path.exists() or img_path.stat().st_size < 100:
        return ''
    try:
        with open(img_path, 'rb') as f:
            img_b64 = base64.b64encode(f.read()).decode()
        ext = img_path.suffix.lower().lstrip('.')
        if ext == 'jpg':
            ext = 'jpeg'
        prompt = '이 이미지를 한국어로 간결하게 설명하세요. 장비 부품명, 작업 단계, 수치 등 기술적 내용을 중심으로.'
        if context:
            prompt = f'주변 텍스트: {context[:200]}\n\n위 맥락을 참고하여 이미지를 한국어로 설명하세요.'
        r = requests.post(
            f'{OLLAMA_BASE}/api/generate',
            json={
                'model': VISION_MODEL,
                'prompt': prompt,
                'images': [img_b64],
                'stream': False,
                'options': {'num_predict': 150, 'temperature': 0.1},
            },
            timeout=60,
        )
        if r.status_code == 200:
            return r.json().get('response', '').strip()
    except Exception as e:
        log.warning(f'비전 오류 {img_path.name}: {e}')
    return ''


# ── 엔티티/관계 추출 ────────────────────────────────────────────────
EXTRACT_PROMPT = """다음 기술 문서에서 엔티티와 관계를 추출하세요.

엔티티 타입: Equipment(장비), Component(부품), Process(공정/작업), Issue(문제/이슈), Person(담당자), Customer(고객사), Manual(매뉴얼)
관계 타입: OWNS(보유), HAS_ISSUE(문제발생), USES_COMPONENT(부품사용), INVOLVED_IN(관련), HAS_SUBPROCESS(하위공정), MAINTAINS(유지보수), DOCUMENTS(문서화)

JSON 형식으로만 응답하세요:
{
  "entities": [{"id":"eng_id","name":"한국어명","type":"Equipment","properties":{}}],
  "relations": [{"source":"id1","target":"id2","type":"USES_COMPONENT"}]
}

문서:
"""

def extract_entities(text: str, title: str) -> dict:
    if len(text) < 50:
        return {'entities': [], 'relations': []}
    truncated = text[:2000]
    prompt = EXTRACT_PROMPT + f"제목: {title}\n\n{truncated}"
    try:
        r = requests.post(
            f'{OLLAMA_BASE}/api/generate',
            json={
                'model': EXTRACT_MODEL,
                'prompt': prompt,
                'stream': False,
                'think': False,
                'options': {'num_predict': 800, 'temperature': 0.1},
            },
            timeout=90,
        )
        if r.status_code == 200:
            raw = r.json().get('response', '').strip()
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                return json.loads(match.group())
    except Exception as e:
        log.warning(f'엔티티 추출 오류 [{title[:30]}]: {e}')
    return {'entities': [], 'relations': []}


# ── Neo4j 적재 ─────────────────────────────────────────────────────
def load_to_neo4j(driver, page_id: str, title: str, extracted: dict):
    entities = extracted.get('entities', [])
    relations = extracted.get('relations', [])
    if not entities:
        return 0, 0

    id_map = {}
    node_count, rel_count = 0, 0

    with driver.session() as s:
        for ent in entities:
            ent_type = ent.get('type', '')
            if ent_type not in VALID_NODE_TYPES:
                continue
            orig_id = ent.get('id', '')
            if not orig_id:
                continue
            safe_id = f"cm4_{page_id}_{re.sub(r'[^a-zA-Z0-9_]', '_', orig_id)}"
            id_map[orig_id] = safe_id
            props = {k: v for k, v in (ent.get('properties') or {}).items()
                     if v is not None and v != ''}
            props.update({'_id': safe_id, '_page_id': page_id, '_space': 'CM', '_title': title})
            try:
                s.run(
                    f"MERGE (n:Phase4_CM:{ent_type} {{_id: $_id}}) "
                    f"SET n += $props, n.name = $name",
                    _id=safe_id, props=props, name=ent.get('name', orig_id)
                )
                node_count += 1
            except Exception as e:
                log.debug(f'노드 생성 오류: {e}')

        for rel in relations:
            src = id_map.get(rel.get('source', ''))
            tgt = id_map.get(rel.get('target', ''))
            rtype = rel.get('type', '')
            if not src or not tgt or rtype not in VALID_REL_TYPES:
                continue
            try:
                s.run(
                    f"MATCH (a:Phase4_CM {{_id: $src}}), (b:Phase4_CM {{_id: $tgt}}) "
                    f"MERGE (a)-[r:{rtype}]->(b)",
                    src=src, tgt=tgt
                )
                rel_count += 1
            except Exception as e:
                log.debug(f'관계 생성 오류: {e}')

    return node_count, rel_count


# ── 임베딩 ─────────────────────────────────────────────────────────
def embed_texts(texts: list) -> list:
    try:
        r = requests.post(
            f'{OLLAMA_BASE}/api/embed',
            json={'model': EMBED_MODEL, 'input': texts},
            timeout=120,
        )
        if r.status_code == 200:
            raw = r.json().get('embeddings', [])
            return [e[:EMBED_DIM] for e in raw]
        log.error(f'임베딩 API 오류: {r.status_code}')
    except Exception as e:
        log.error(f'임베딩 오류: {e}')
    return None


def embed_and_save(conn, page_id: str, title: str, full_text: str) -> int:
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:60]
    source_file = f'confluence-CM/{page_id}-{safe_title}'
    file_hash = hashlib.md5(full_text.encode()).hexdigest()
    chunks = chunk_text(full_text)
    if not chunks:
        return 0

    rows = []
    for batch_start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[batch_start:batch_start + EMBED_BATCH]
        embeddings = embed_texts(batch)
        if embeddings is None:
            return 0
        for i, (chunk, emb) in enumerate(zip(batch, embeddings)):
            rows.append({
                'source_file': source_file,
                'file_hash': file_hash,
                'chunk_index': batch_start + i,
                'chunk_type': 'text',
                'content': chunk,
                'metadata': {'page_id': page_id, 'page_title': title, 'space': 'CM',
                             'url': f'https://iwta.atlassian.net/wiki/spaces/CM/pages/{page_id}'},
                'embedding': emb,
            })
        if batch_start + EMBED_BATCH < len(chunks):
            time.sleep(0.3)

    if not rows:
        return 0

    cur = conn.cursor()
    cur.execute(f'DELETE FROM {DB_TABLE} WHERE source_file = %s AND category = %s',
                (source_file, CATEGORY))
    execute_values(
        cur,
        f'''INSERT INTO {DB_TABLE}
            (source_file, file_hash, category, chunk_index, chunk_type, page_number,
             content, image_url, metadata, embedding)
            VALUES %s''',
        [(r['source_file'], r['file_hash'], CATEGORY,
          r['chunk_index'], r['chunk_type'], 0,
          r['content'], None,
          json.dumps(r['metadata'], ensure_ascii=False),
          r['embedding']) for r in rows],
        template='(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
    )
    conn.commit()
    cur.close()
    return len(rows)


# ── 메인 ──────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--embed-only', action='store_true')
parser.add_argument('--graph-only', action='store_true')
parser.add_argument('--test', type=int, default=0)
args = parser.parse_args()

with open(PAGES_FILE, encoding='utf-8') as f:
    pages_list = json.load(f)

targets = [(str(p['id']), p.get('title', '')) for p in pages_list]
if args.test > 0:
    targets = targets[:args.test]
    log.info(f'테스트 모드: {len(targets)}건')

graph_prog = load_progress(GRAPH_PROG)
embedded_set   = set(graph_prog.get('embedded', []))
graph_done_set = set(graph_prog.get('graph_done', []))

conn = None
driver = None
if not args.graph_only:
    conn = psycopg2.connect(**DB_CONFIG)
    log.info('PostgreSQL 연결 완료')

if not args.embed_only:
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver('bolt://localhost:7688', auth=('neo4j', NEO4J_PASS))
        driver.verify_connectivity()
        log.info('Neo4j 연결 완료')
    except Exception as e:
        log.warning(f'Neo4j 연결 실패: {e}')
        driver = None

total = len(targets)
embedded_ok = len(embedded_set)
graph_ok    = len(graph_done_set)
total_nodes = 0
total_rels  = 0

log.info(f'처리 시작: {total}건 (임베딩완료:{embedded_ok} / 그래프완료:{graph_ok})')
log.info(f'BeautifulSoup4: {"사용" if USE_BS4 else "미사용"}')

for i, (page_id, title) in enumerate(targets):
    need_embed = not args.graph_only and page_id not in embedded_set
    need_graph = not args.embed_only and page_id not in graph_done_set
    if not need_embed and not need_graph:
        continue

    log.info(f'[{i+1}/{total}] {page_id} — {title[:50]}')

    # 페이지 디렉토리 찾기
    safe = re.sub(r'[<>:"/\\|?*]', '_', title).strip()[:60]
    page_dir = BASE_DIR / f'{page_id}-{safe}'
    if not page_dir.exists():
        matches = list(BASE_DIR.glob(f'{page_id}-*'))
        page_dir = matches[0] if matches else None
    if not page_dir:
        log.warning(f'  디렉토리 없음: {page_id}')
        graph_prog.setdefault('failed', []).append(page_id)
        continue

    page_text = get_page_text(page_id, page_dir)
    if not page_text:
        log.warning(f'  텍스트 없음: {page_id}')
        continue

    # 이미지 분석
    image_descriptions = []
    if not args.embed_only:
        images_dir = page_dir / 'images'
        if images_dir.exists():
            for img_path in list(images_dir.iterdir())[:5]:
                if img_path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.gif', '.webp'}:
                    continue
                context = get_image_context(page_text, img_path.name)
                if len(context) < 30:
                    desc = describe_image(img_path, context)
                    if desc:
                        image_descriptions.append(f'[이미지: {img_path.name}] {desc}')
                else:
                    image_descriptions.append(f'[이미지 맥락: {img_path.name}] {context}')

    full_text = page_text
    if image_descriptions:
        full_text += '\n\n' + '\n'.join(image_descriptions)

    # 임베딩
    if need_embed:
        saved = embed_and_save(conn, page_id, title, full_text)
        if saved > 0:
            graph_prog['embedded'].append(page_id)
            embedded_set.add(page_id)
            embedded_ok += 1
            log.info(f'  임베딩 {saved}청크')

    # 엔티티 추출 + Neo4j
    if need_graph and driver:
        extracted = extract_entities(full_text, title)
        # 엔티티 파일 저장 (컨텍스트 컴팩팅 대응)
        entity_file = ENTITIES_DIR / f'cm_{page_id}.json'
        with open(entity_file, 'w', encoding='utf-8') as ef:
            json.dump({'page_id': page_id, 'title': title, **extracted},
                      ef, ensure_ascii=False, indent=2)
        nodes, rels = load_to_neo4j(driver, page_id, title, extracted)
        total_nodes += nodes
        total_rels  += rels
        graph_prog['graph_done'].append(page_id)
        graph_done_set.add(page_id)
        graph_ok += 1
        if nodes > 0:
            log.info(f'  Neo4j: {nodes}노드, {rels}관계')

    if (i + 1) % 10 == 0:
        save_progress(graph_prog, GRAPH_PROG)
        log.info(f'중간저장: 임베딩 {embedded_ok}건 / 그래프 {graph_ok}건 | 누적 {total_nodes}노드')

    time.sleep(0.2)

save_progress(graph_prog, GRAPH_PROG)
if conn:
    conn.close()
if driver:
    driver.close()

log.info(f'=== 완료 === 임베딩: {embedded_ok}건 / 그래프: {graph_ok}건 / 노드: {total_nodes} / 관계: {total_rels}')
