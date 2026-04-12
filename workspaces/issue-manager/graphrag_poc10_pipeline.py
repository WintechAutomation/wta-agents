"""
manuals-v2 PoC10 GraphRAG 파이프라인 (issue-manager)
원본: workspaces/db-manager/cm-graphrag-pipeline.py (Phase4_CM 383건)
변경: 레이블 Phase4_CM → ManualsV2_PoC10_ISSUE, 입력 Confluence→chunks.jsonl, think:False 추가

실행:
  python graphrag_poc10_pipeline.py                    # PoC10 전체 (graph-only)
  python graphrag_poc10_pipeline.py --test 2           # 첫 2건만
  python graphrag_poc10_pipeline.py --dry              # LLM/Neo4j 없이 건수만 확인
"""
import sys, os, json, re, time, hashlib, logging, argparse
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── 설정 (cm-graphrag-pipeline.py 원본 그대로, 경로만 변경) ──────────────
POC_DIR       = Path('C:/MES/wta-agents/reports/manuals-v2/poc')
PROGRESS_FILE = Path('C:/MES/wta-agents/reports/manuals-v2/work/graphrag_poc10_issue_progress.json')
REPROCESS_STATE = Path('C:/MES/wta-agents/reports/manuals-v2/legacy/manuals_v2_reprocess_state.json')

OLLAMA_BASE   = 'http://182.224.6.147:11434'
EXTRACT_MODEL = 'qwen3.5:35b-a3b'                     # 원본 동일
CHUNK_SIZE    = 800                                    # 원본 동일
CHUNK_OVERLAP = 100                                    # 원본 동일

# ── 변경점: 레이블 / ID prefix ──────────────────────────────────────────
LABEL         = 'ManualsV2_PoC10_ISSUE'                # 원본: Phase4_CM
ID_PREFIX     = 'mv2i'                                 # 원본: cm4

NEO4J_ENV = Path('C:/MES/wta-agents/workspaces/research-agent/neo4j-poc.env')
NEO4J_PASS = ''
for line in NEO4J_ENV.read_text(encoding='utf-8').splitlines():
    if line.startswith('NEO4J_AUTH=neo4j/'):
        NEO4J_PASS = line.split('/', 1)[1].strip()
        break

# ── 원본 그대로: 노드/관계 타입 ──────────────────────────────────────────
VALID_NODE_TYPES = {'Customer','Equipment','Product','Component','Process',
                    'Issue','Resolution','Person','Tool','Manual'}
VALID_REL_TYPES  = {'OWNS','HAS_ISSUE','SIMILAR_TO','RESOLVED_BY',
                    'INVOLVES_COMPONENT','USES_COMPONENT','INVOLVED_IN',
                    'HAS_SUBPROCESS','USES_TOOL','MAINTAINS','DOCUMENTS'}

logging.basicConfig(
    level=logging.INFO,
    format='[mv2-graphrag] %(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('C:/MES/wta-agents/reports/manuals-v2/work/graphrag_poc10_issue.log',
                            encoding='utf-8'),
    ]
)
log = logging.getLogger('mv2-graphrag')

# ── 진행 상태 (원본 그대로) ──────────────────────────────────────────────
def load_progress(path: Path) -> dict:
    if path.exists():
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {'graph_done': [], 'failed': []}

def save_progress(prog: dict, path: Path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(prog, f, ensure_ascii=False, indent=2)


# ── 유틸: 텍스트 청킹 (원본 그대로) ─────────────────────────────────────
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


# ── 엔티티/관계 추출 (원본 그대로 + think:False 버그픽스) ───────────────
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
    """LLM으로 엔티티/관계 추출 (원본 동일, think:False 추가)"""
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
                'think': False,         # 추가: qwen3.5 사고모드 비활성화
                'options': {'num_predict': 600, 'temperature': 0.1},
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


# ── Neo4j 적재 (원본 그대로, 레이블/ID만 변경) ──────────────────────────
def load_to_neo4j(driver, file_id: str, title: str, extracted: dict):
    """ManualsV2_PoC10_ISSUE 라벨로 Neo4j 병합 적재"""
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
            safe_id = f"{ID_PREFIX}_{file_id}_{re.sub(r'[^a-zA-Z0-9_]','_', orig_id)}"
            id_map[orig_id] = safe_id
            props = {k: v for k, v in (ent.get('properties') or {}).items()
                     if v is not None and v != ''}
            props.update({'_id': safe_id, '_source_id': file_id, '_corpus': 'manuals_v2'})
            try:
                s.run(
                    f"MERGE (n:{LABEL}:{ent_type} {{_id: $_id}}) "
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
                    f"MATCH (a:{LABEL} {{_id: $src}}), (b:{LABEL} {{_id: $tgt}}) "
                    f"MERGE (a)-[r:{rtype}]->(b)",
                    src=src, tgt=tgt
                )
                rel_count += 1
            except Exception as e:
                log.debug(f'관계 생성 오류: {e}')

    return node_count, rel_count


# ── 입력 로더 (변경점: Confluence→chunks.jsonl) ──────────────────────────
def load_poc10_targets() -> list[dict]:
    """PoC10 file_id + 텍스트 로드. 원본의 page_dir/page-text.txt 대신 chunks.jsonl 사용"""
    state = json.loads(REPROCESS_STATE.read_text(encoding='utf-8'))
    targets = []
    for item in state.get('items', []):
        fid = item['id']
        chunks_path = POC_DIR / fid / 'chunks.jsonl'
        if not chunks_path.exists():
            log.warning(f'SKIP {fid}: chunks.jsonl 없음')
            continue
        texts = []
        with chunks_path.open(encoding='utf-8') as f:
            for line in f:
                obj = json.loads(line)
                c = (obj.get('content') or obj.get('text') or '').strip()
                if c:
                    texts.append(c)
        full_text = '\n\n'.join(texts)
        targets.append({
            'file_id': fid,
            'title': f"{fid} ({item.get('lang', obj.get('lang', 'unknown'))})",
            'text': full_text,
            'n_chunks': len(texts),
        })
    # 작은 것부터
    targets.sort(key=lambda t: t['n_chunks'])
    return targets


# ── 메인 (원본 구조 유지, 입력부만 변경) ────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--test', type=int, default=0, help='처음 N건만 처리')
parser.add_argument('--dry', action='store_true', help='LLM/Neo4j 없이 건수만')
args = parser.parse_args()

targets = load_poc10_targets()
if args.test > 0:
    targets = targets[:args.test]
    log.info(f'테스트 모드: {len(targets)}건')

log.info(f'PoC10 대상: {len(targets)}건')
for t in targets:
    # 원본 cm-graphrag의 chunk_text로 800자 청킹 → 각 청크에 extract_entities
    chunks = chunk_text(t['text'])
    log.info(f"  {t['file_id']}  원본청크={t['n_chunks']}  텍스트={len(t['text']):,}자  윈도우(800)={len(chunks)}")

if args.dry:
    log.info('dry run, exit')
    sys.exit(0)

# Neo4j 연결
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7688', auth=('neo4j', NEO4J_PASS))
driver.verify_connectivity()
log.info('Neo4j 연결 완료')

# 진행 상태
prog = load_progress(PROGRESS_FILE)
graph_done_set = set(prog.get('graph_done', []))

total = len(targets)
total_nodes = 0
total_rels = 0

log.info(f'처리 시작: {total}건 (그래프완료:{len(graph_done_set)})')

for i, t in enumerate(targets):
    file_id = t['file_id']
    title = t['title']
    full_text = t['text']

    if file_id in graph_done_set:
        log.info(f'[{i+1}/{total}] {file_id} — 이미 완료, 건너뜀')
        continue

    log.info(f'[{i+1}/{total}] {file_id} — {title}')

    # 원본 패턴 그대로: full_text → chunk_text(800자) → 각 청크에 extract → load_to_neo4j
    chunks = chunk_text(full_text)
    file_nodes = 0
    file_rels = 0
    t0 = time.time()

    for ci, chunk in enumerate(chunks):
        extracted = extract_entities(chunk, title)
        nc, rc = load_to_neo4j(driver, file_id, title, extracted)
        file_nodes += nc
        file_rels += rc
        if ci % 10 == 0 or ci == len(chunks) - 1:
            log.info(f'  chunk {ci+1}/{len(chunks)} nodes+={nc} rels+={rc} subtotal={file_nodes}/{file_rels}')

    elapsed = round(time.time() - t0, 1)
    total_nodes += file_nodes
    total_rels += file_rels
    log.info(f'  DONE {file_id} elapsed={elapsed}s nodes={file_nodes} rels={file_rels}')

    graph_done_set.add(file_id)
    prog['graph_done'] = sorted(graph_done_set)
    save_progress(prog, PROGRESS_FILE)

# 최종 통계
with driver.session() as s:
    final_nodes = s.run(f"MATCH (n:{LABEL}) RETURN count(n) AS c").single()['c']
    final_rels = s.run(f"MATCH (a:{LABEL})-[r]->(b:{LABEL}) RETURN count(r) AS c").single()['c']
log.info(f'=== 최종: 노드={final_nodes} 관계={final_rels} (MERGE 건수: {total_nodes}/{total_rels}) ===')
driver.close()
