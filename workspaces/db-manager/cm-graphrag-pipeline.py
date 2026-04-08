"""
CM 스페이스 GraphRAG 파이프라인 (PART2 — 383건)
단계:
  1. page-text.txt + 이미지 주변 텍스트 통합
  2. 주변 텍스트 부족 이미지 → LLM 비전(qwen3-vl:8b) 설명 생성
  3. 통합 텍스트 → 엔티티/관계 추출 (qwen3.5:35b-a3b)
  4. Neo4j(bolt://localhost:7688) 병합 적재 (Phase4_CM 라벨)
  5. 청크별 벡터 임베딩 (qwen3-embedding:8b, 2000차원) → pgvector

실행:
  python cm-graphrag-pipeline.py               # 전체 (임베딩 + GraphRAG)
  python cm-graphrag-pipeline.py --embed-only  # 임베딩만 (빠름)
  python cm-graphrag-pipeline.py --graph-only  # GraphRAG만 (엔티티+Neo4j)
  python cm-graphrag-pipeline.py --test 5      # 첫 5건만 테스트
"""
import sys, os, json, re, time, hashlib, logging, argparse, base64
from pathlib import Path

import requests
import psycopg2
from psycopg2.extras import execute_values

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── 설정 ──────────────────────────────────────────────────────────
BASE_DIR      = Path('C:/MES/wta-agents/reports/MAX/confluence-CM')
PROGRESS_FILE = Path('C:/MES/wta-agents/workspaces/db-manager/cm-extract-part2-progress.json')
GRAPH_PROG    = Path('C:/MES/wta-agents/workspaces/db-manager/cm-graphrag-progress.json')

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
from dotenv import load_dotenv
load_dotenv('C:/MES/backend/.env')
if os.environ.get('DB_PASSWORD'):
    DB_CONFIG['password'] = os.environ['DB_PASSWORD']

NEO4J_ENV = Path('C:/MES/wta-agents/workspaces/research-agent/neo4j-poc.env')
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
    format='[cm-graphrag] %(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('C:/MES/wta-agents/workspaces/db-manager/cm-graphrag.log',
                            encoding='utf-8'),
    ]
)
log = logging.getLogger('cm-graphrag')

# ── 진행 상태 ──────────────────────────────────────────────────────
def load_progress(path: Path) -> dict:
    if path.exists():
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {'embedded': [], 'graph_done': [], 'failed': []}

def save_progress(prog: dict, path: Path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(prog, f, ensure_ascii=False, indent=2)


# ── 유틸 ──────────────────────────────────────────────────────────
def chunk_text(text: str) -> list[str]:
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
    """page-text.txt에서 이미지 파일명 앞뒤 텍스트 추출"""
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
    """이미지 → LLM 비전 설명 생성 (base64 방식)"""
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
    """LLM으로 엔티티/관계 추출"""
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
                'options': {'num_predict': 600, 'temperature': 0.1},
            },
            timeout=90,
        )
        if r.status_code == 200:
            raw = r.json().get('response', '').strip()
            # JSON 파싱
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                return json.loads(match.group())
    except Exception as e:
        log.warning(f'엔티티 추출 오류 [{title[:30]}]: {e}')
    return {'entities': [], 'relations': []}


# ── Neo4j 적재 ─────────────────────────────────────────────────────
def load_to_neo4j(driver, page_id: str, title: str, extracted: dict):
    """Phase4_CM 라벨로 Neo4j 병합 적재"""
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
            safe_id = f"cm4_{page_id}_{re.sub(r'[^a-zA-Z0-9_]','_', orig_id)}"
            id_map[orig_id] = safe_id
            props = {k: v for k, v in (ent.get('properties') or {}).items()
                     if v is not None and v != ''}
            props.update({'_id': safe_id, '_page_id': page_id, '_space': 'CM'})
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
def embed_texts(texts: list[str]) -> list[list[float]] | None:
    try:
        r = requests.post(
            f'{OLLAMA_BASE}/api/embed',
            json={'model': EMBED_MODEL, 'input': texts},
            timeout=120,
        )
        if r.status_code == 200:
            raw = r.json().get('embeddings', [])
            # 2000차원 슬라이싱
            return [e[:EMBED_DIM] for e in raw]
        log.error(f'임베딩 API 오류: {r.status_code}')
    except Exception as e:
        log.error(f'임베딩 오류: {e}')
    return None


def embed_and_save(conn, page_id: str, title: str, full_text: str):
    """텍스트 청크화 → 임베딩 → pgvector 저장"""
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
parser.add_argument('--test', type=int, default=0, help='처음 N건만 처리')
args = parser.parse_args()

# part2 완료 페이지 목록 로드
with open(PROGRESS_FILE, encoding='utf-8') as f:
    part2_prog = json.load(f)
done_ids = part2_prog.get('done', [])
log.info(f'PART2 완료 페이지: {len(done_ids)}건')

# pages 메타 로드 (제목 필요)
pages_file = Path('C:/MES/wta-agents/workspaces/research-agent/cm-pages-part2.json')
with open(pages_file, encoding='utf-8') as f:
    pages_list = json.load(f)
pages_meta = {str(p['id']): p.get('title', '') for p in pages_list}

# 처리 대상
targets = [pid for pid in done_ids if pid in pages_meta]
if args.test > 0:
    targets = targets[:args.test]
    log.info(f'테스트 모드: {len(targets)}건')

# GraphRAG 진행 상태
graph_prog = load_progress(GRAPH_PROG)
embedded_set = set(graph_prog.get('embedded', []))
graph_done_set = set(graph_prog.get('graph_done', []))

# DB / Neo4j 연결
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
        log.warning(f'Neo4j 연결 실패 (graph 건너뜀): {e}')
        driver = None

total = len(targets)
embedded_ok = len(embedded_set)
graph_ok = len(graph_done_set)
total_nodes = 0
total_rels  = 0

log.info(f'처리 시작: {total}건 (임베딩완료:{embedded_ok} / 그래프완료:{graph_ok})')

for i, page_id in enumerate(targets):
    title = pages_meta[page_id]
    log.info(f'[{i+1}/{total}] {page_id} — {title[:50]}')

    # 페이지 디렉토리 찾기 (safe_dirname 규칙)
    safe = re.sub(r'[<>:"/\\|?*]', '_', title).strip()[:60]
    page_dir = BASE_DIR / f'{page_id}-{safe}'
    if not page_dir.exists():
        # 정확한 매칭이 안 되면 prefix로 찾기
        matches = list(BASE_DIR.glob(f'{page_id}-*'))
        if matches:
            page_dir = matches[0]
        else:
            log.warning(f'  디렉토리 없음: {page_id}')
            continue

    text_path = page_dir / 'page-text.txt'
    if not text_path.exists() or text_path.stat().st_size == 0:
        log.warning(f'  텍스트 없음: {page_id}')
        continue

    page_text = text_path.read_text(encoding='utf-8').strip()

    # ── 이미지 주변 텍스트 + 비전 설명 통합 ──
    images_dir = page_dir / 'images'
    image_descriptions = []
    if images_dir.exists() and not args.embed_only:
        img_files = list(images_dir.iterdir())
        for img_path in img_files[:5]:  # 페이지당 최대 5개 이미지
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

    # ── 1. 임베딩 ──
    if not args.graph_only and page_id not in embedded_set:
        saved = embed_and_save(conn, page_id, title, full_text)
        if saved > 0:
            graph_prog['embedded'].append(page_id)
            embedded_set.add(page_id)
            embedded_ok += 1
            log.info(f'  임베딩 {saved}청크 저장')
        else:
            log.warning(f'  임베딩 실패: {page_id}')

    # ── 2. 엔티티/관계 추출 + Neo4j 적재 ──
    if not args.embed_only and driver and page_id not in graph_done_set:
        extracted = extract_entities(full_text, title)
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
        log.info(f'중간 저장: 임베딩 {embedded_ok}건 / 그래프 {graph_ok}건 | 누적 {total_nodes}노드')

save_progress(graph_prog, GRAPH_PROG)
if conn:
    conn.close()
if driver:
    driver.close()

log.info(f'\n=== 완료 ===')
log.info(f'임베딩: {embedded_ok}건 / 그래프: {graph_ok}건 / 총 노드: {total_nodes} / 총 관계: {total_rels}')
