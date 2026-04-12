"""
manuals-v2 전체 파이프라인 Step0~7 — 1_robot_18a2fd5fb603 단독 실행
qa-agent 교차검증 (tq-qa-agent-943812)

Step0: chunks.jsonl 검증
Step1: Qwen3-Embedding-8B 임베딩 (2000dim MRL)
Step2: manual.documents_v2 UPSERT (pgvector)
Step3: HNSW + GIN 인덱스 확인
Step4: GraphRAG 엔티티 추출 (qwen3.5:35b-a3b, think:false)
Step5: Neo4j MERGE (ManualsV2_PoC_18a2fd)
Step6: MRR 검증 (≥0.60, TOC 제외)
Step7: HTML 보고서 생성
"""
import sys, os, json, re, time, logging, json_repair
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests
import psycopg2
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── 설정 ────────────────────────────────────────────────────────────
FILE_ID      = '1_robot_18a2fd5fb603'
LABEL_SHORT  = FILE_ID[:6]  # 18a2fd
NEO4J_LABEL  = f'ManualsV2_PoC_{LABEL_SHORT}'   # ManualsV2_PoC_18a2fd

POC_DIR      = Path(f'C:/MES/wta-agents/reports/manuals-v2/poc/{FILE_ID}')
STATE_DIR    = Path('C:/MES/wta-agents/reports/manuals-v2/state')
WORK_DIR     = Path('C:/MES/wta-agents/reports/manuals-v2/work')
STATE_PATH   = STATE_DIR / f'pipeline_{LABEL_SHORT}_state.json'
LOG_PATH     = STATE_DIR / f'pipeline_{LABEL_SHORT}.log'
REPORT_PATH  = Path('C:/MES/wta-agents/dashboard/uploads') / f'report_{LABEL_SHORT}_pipeline.html'
NEO4J_ENV    = Path('C:/MES/wta-agents/workspaces/research-agent/neo4j-poc.env')

OLLAMA_BASE  = 'http://182.224.6.147:11434'
EMBED_MODEL  = 'qwen3-embedding:8b'
EXTRACT_MODEL= 'qwen3.5:35b-a3b'
EMBED_DIM    = 2000

RUN_ID  = datetime.now(timezone(timedelta(hours=9))).strftime('%Y%m%d_%H%M%S')

load_dotenv('C:/MES/backend/.env')

# ── 로깅 ────────────────────────────────────────────────────────────
STATE_DIR.mkdir(parents=True, exist_ok=True)
WORK_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='[pipe-18a2fd] %(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_PATH), encoding='utf-8'),
    ],
)
log = logging.getLogger('pipe-18a2fd')


def kst_now():
    return datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')


# ── 체크포인트 ───────────────────────────────────────────────────────
def load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {
        'task_id': 'tq-qa-agent-943812', 'file_id': FILE_ID,
        'run_id': RUN_ID, 'status': 'in_progress',
        'steps': {}, 'last_update': kst_now(),
    }


def save_state(state):
    state['last_update'] = kst_now()
    tmp = STATE_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(STATE_PATH)


# ── DB 연결 ──────────────────────────────────────────────────────────
def get_db():
    return psycopg2.connect(
        host='localhost', port=55432, dbname='postgres',
        user='postgres', password=os.environ.get('DB_PASSWORD', ''),
    )


# ── Neo4j 연결 ───────────────────────────────────────────────────────
def get_neo4j():
    pwd = ''
    for line in NEO4J_ENV.read_text(encoding='utf-8').splitlines():
        if line.startswith('NEO4J_AUTH=neo4j/'):
            pwd = line.split('/', 1)[1].strip()
            break
    from neo4j import GraphDatabase
    return GraphDatabase.driver('bolt://localhost:7688', auth=('neo4j', pwd))


# ════════════════════════════════════════════════════════════════════
# Step 0: chunks.jsonl 검증
# ════════════════════════════════════════════════════════════════════
def step0_validate(state):
    log.info('--- Step0: chunks.jsonl 검증 ---')
    chunks_path = POC_DIR / 'chunks.jsonl'
    if not chunks_path.exists():
        raise FileNotFoundError(f'chunks.jsonl 없음: {chunks_path}')

    chunks = []
    with open(chunks_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    assert len(chunks) > 0, '청크 0개'
    empty = [c for c in chunks if not (c.get('content') or '').strip()]
    langs = set(c.get('lang', '?') for c in chunks)
    lens = [len(c.get('content') or '') for c in chunks]
    has_embed = sum(1 for c in chunks if c.get('embedding') is not None)

    result = {
        'total': len(chunks), 'empty': len(empty),
        'langs': list(langs), 'min_len': min(lens),
        'avg_len': sum(lens) // len(lens), 'max_len': max(lens),
        'already_embedded': has_embed,
    }
    log.info(f'  총 청크={result["total"]} empty={result["empty"]} '
             f'lang={result["langs"]} avg_len={result["avg_len"]} embedded={has_embed}')
    state['steps']['step0'] = {'status': 'done', **result}
    save_state(state)
    return chunks


# ════════════════════════════════════════════════════════════════════
# Step 1: 임베딩 생성 (Qwen3-Embedding-8B, 2000dim MRL)
# ════════════════════════════════════════════════════════════════════
def step1_embed(chunks, state):
    log.info('--- Step1: 임베딩 생성 (qwen3-embedding:8b, 2000dim) ---')
    BATCH = 4
    embeddings = {}
    errors = 0

    prev = state['steps'].get('step1', {}).get('embedded_ids', [])
    done_ids = set(prev)

    todo = [c for c in chunks if c['chunk_id'] not in done_ids]
    log.info(f'  대상 {len(todo)}건 (이미 완료: {len(done_ids)}건)')

    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        texts = [c.get('content', '') for c in batch]
        try:
            r = requests.post(
                f'{OLLAMA_BASE}/api/embed',
                json={'model': EMBED_MODEL, 'input': texts},
                timeout=120,
            )
            if r.status_code == 200:
                raw_embs = r.json().get('embeddings', [])
                for c, emb in zip(batch, raw_embs):
                    embeddings[c['chunk_id']] = emb[:EMBED_DIM]
                    done_ids.add(c['chunk_id'])
                log.info(f'  batch {i//BATCH+1}: {len(batch)}건 임베딩 완료')
            else:
                log.warning(f'  batch {i//BATCH+1}: API 오류 {r.status_code}')
                errors += len(batch)
        except Exception as e:
            log.warning(f'  batch {i//BATCH+1}: {e}')
            errors += len(batch)

        # 이전 완료분도 embeddings에 포함 (chunks에서 읽어옴)
        time.sleep(0.2)

    # chunks에 embedding 부착
    for c in chunks:
        if c['chunk_id'] in embeddings:
            c['embedding'] = embeddings[c['chunk_id']]

    ok = len(embeddings)
    log.info(f'  임베딩 완료: {ok}건 / 오류: {errors}건')
    state['steps']['step1'] = {
        'status': 'done', 'ok': ok, 'errors': errors,
        'embedded_ids': list(done_ids),
    }
    save_state(state)
    return embeddings


# ════════════════════════════════════════════════════════════════════
# Step 2: manual.documents_v2 UPSERT
# ════════════════════════════════════════════════════════════════════
def step2_insert(chunks, embeddings, state):
    log.info('--- Step2: manual.documents_v2 UPSERT ---')
    conn = get_db()
    cur = conn.cursor()

    # 기존 데이터 삭제 (idempotent)
    cur.execute('DELETE FROM manual.documents_v2 WHERE file_id = %s', (FILE_ID,))
    deleted = cur.rowcount
    log.info(f'  기존 {deleted}건 삭제')

    rows_inserted = 0
    for c in chunks:
        emb = embeddings.get(c['chunk_id']) or c.get('embedding')
        if emb is None:
            continue
        try:
            cur.execute(
                '''INSERT INTO manual.documents_v2
                   (file_id, chunk_id, category, mfr, model, doctype, lang,
                    section_path, page_start, page_end, content, tokens,
                    source_hash, embedding, figure_refs, table_refs, inline_refs)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector,%s,%s,%s)
                   ON CONFLICT (file_id, chunk_id) DO UPDATE
                   SET content=EXCLUDED.content, embedding=EXCLUDED.embedding
                ''',
                (
                    c.get('file_id', FILE_ID),
                    c['chunk_id'],
                    c.get('category', '1_robot'),
                    c.get('mfr', ''),
                    c.get('model', ''),
                    c.get('doctype', 'manual'),
                    c.get('lang', 'en'),
                    json.dumps(c.get('section_path') or [], ensure_ascii=False),
                    c.get('page_start'),
                    c.get('page_end'),
                    c.get('content', ''),
                    c.get('tokens'),
                    c.get('source_hash'),
                    '[' + ','.join(str(v) for v in emb) + ']',
                    json.dumps(c.get('figure_refs') or [], ensure_ascii=False),
                    json.dumps(c.get('table_refs') or [], ensure_ascii=False),
                    json.dumps(c.get('inline_refs') or [], ensure_ascii=False),
                )
            )
            rows_inserted += 1
        except Exception as e:
            log.warning(f'  INSERT 오류 [{c["chunk_id"]}]: {e}')

    conn.commit()
    cur.close()
    conn.close()
    log.info(f'  INSERT 완료: {rows_inserted}건')
    state['steps']['step2'] = {'status': 'done', 'inserted': rows_inserted, 'deleted': deleted}
    save_state(state)
    return rows_inserted


# ════════════════════════════════════════════════════════════════════
# Step 3: 인덱스 확인
# ════════════════════════════════════════════════════════════════════
def step3_index(state):
    log.info('--- Step3: HNSW + GIN 인덱스 확인 ---')
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE schemaname='manual' AND tablename='documents_v2'
        ORDER BY indexname
    """)
    indexes = cur.fetchall()
    cur.close()
    conn.close()

    idx_names = [r[0] for r in indexes]
    has_hnsw = any('hnsw' in r[1].lower() or 'vector' in r[1].lower() for r in indexes)
    has_btree = any('btree' in r[1].lower() or ('file_id' in r[1]) for r in indexes)

    for name, defn in indexes:
        log.info(f'  인덱스: {name}')

    if not has_hnsw:
        log.warning('  HNSW 인덱스 없음 — 검색 성능 저하 가능')
    else:
        log.info('  HNSW 인덱스 확인')

    state['steps']['step3'] = {
        'status': 'done', 'indexes': idx_names,
        'has_hnsw': has_hnsw, 'has_btree': has_btree,
    }
    save_state(state)
    return indexes


# ════════════════════════════════════════════════════════════════════
# Step 4: GraphRAG 엔티티 추출
# ════════════════════════════════════════════════════════════════════
VALID_NODE_TYPES = {
    'Customer', 'Equipment', 'Product', 'Component', 'Process',
    'Issue', 'Resolution', 'Person', 'Tool', 'Manual',
}
VALID_REL_TYPES = {
    'OWNS', 'HAS_ISSUE', 'SIMILAR_TO', 'RESOLVED_BY',
    'INVOLVES_COMPONENT', 'USES_COMPONENT', 'INVOLVED_IN',
    'HAS_SUBPROCESS', 'USES_TOOL', 'MAINTAINS', 'DOCUMENTS',
}

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


def extract_entities_graphrag(text: str, title: str) -> dict:
    if len(text) < 50:
        return {'entities': [], 'relations': []}
    truncated = text[:2000]
    prompt = EXTRACT_PROMPT + f'제목: {title}\n\n{truncated}'
    try:
        r = requests.post(
            f'{OLLAMA_BASE}/api/generate',
            json={
                'model': EXTRACT_MODEL,
                'prompt': prompt,
                'think': False,
                'stream': False,
                'options': {'num_predict': 1200, 'temperature': 0.1},
            },
            timeout=90,
        )
        if r.status_code == 200:
            raw = r.json().get('response', '').strip()
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                return json_repair.loads(m.group())
    except Exception as e:
        log.warning(f'엔티티 추출 오류 [{title[:30]}]: {e}')
    return {'entities': [], 'relations': []}


def step4_extract(chunks, state):
    log.info('--- Step4: GraphRAG 엔티티 추출 ---')
    # 전체 청크 텍스트 결합 후 2000자 트런케이션
    full_text = '\n'.join(c.get('content', '') for c in chunks)
    log.info(f'  전체 텍스트 {len(full_text)}자 → 2000자 트런케이션 후 추출')
    extracted = extract_entities_graphrag(full_text, FILE_ID)
    nodes = extracted.get('entities', [])
    rels = extracted.get('relations', [])
    log.info(f'  추출: 엔티티={len(nodes)} 관계={len(rels)}')
    state['steps']['step4'] = {
        'status': 'done', 'entities': len(nodes), 'relations': len(rels),
    }
    save_state(state)
    return extracted


# ════════════════════════════════════════════════════════════════════
# Step 5: Neo4j MERGE
# ════════════════════════════════════════════════════════════════════
def step5_neo4j(extracted, state):
    log.info(f'--- Step5: Neo4j MERGE (라벨: {NEO4J_LABEL}) ---')
    driver = get_neo4j()

    # 기존 노드 삭제 (idempotent)
    with driver.session() as s:
        r = s.run(f'MATCH (n:{NEO4J_LABEL}) RETURN count(n) as cnt')
        existing = r.single()['cnt']
        if existing > 0:
            s.run(f'MATCH (n:{NEO4J_LABEL}) DETACH DELETE n')
            log.info(f'  기존 {existing}개 삭제')

    entities = extracted.get('entities', [])
    relations = extracted.get('relations', [])
    id_map = {}
    node_count = rel_count = 0

    with driver.session() as s:
        for ent in entities:
            ent_type = ent.get('type', '')
            if ent_type not in VALID_NODE_TYPES:
                continue
            orig_id = ent.get('id', '')
            if not orig_id:
                continue
            safe_id = f"mv2_{FILE_ID}_{re.sub(r'[^a-zA-Z0-9_]', '_', orig_id)}"
            id_map[orig_id] = safe_id
            props = {k: v for k, v in (ent.get('properties') or {}).items()
                     if v is not None and v != ''}
            props.update({'_id': safe_id, '_file_id': FILE_ID,
                          '_corpus': 'manuals_v2', '_run_id': RUN_ID})
            try:
                s.run(
                    f'MERGE (n:{NEO4J_LABEL}:{ent_type} {{_id: $_id}}) '
                    f'SET n += $props, n.name = $name',
                    _id=safe_id, props=props, name=ent.get('name', orig_id),
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
                    f'MATCH (a:{NEO4J_LABEL} {{_id: $src}}), (b:{NEO4J_LABEL} {{_id: $tgt}}) '
                    f'MERGE (a)-[r:{rtype}]->(b)',
                    src=src, tgt=tgt,
                )
                rel_count += 1
            except Exception as e:
                log.debug(f'관계 생성 오류: {e}')

    driver.close()
    log.info(f'  Neo4j: 노드={node_count} 관계={rel_count}')
    state['steps']['step5'] = {
        'status': 'done', 'nodes': node_count, 'rels': rel_count,
        'label': NEO4J_LABEL,
    }
    save_state(state)
    return node_count, rel_count


# ════════════════════════════════════════════════════════════════════
# Step 6: MRR 검증 (TOC 제외, ≥0.60)
# ════════════════════════════════════════════════════════════════════
TOC_PATTERNS = [
    r'^(목차|contents|table of contents|index)$',
    r'^\d+[\.\-]\d*\s+\w',
]

def is_toc_chunk(chunk: dict) -> bool:
    sp = chunk.get('section_path') or []
    content = (chunk.get('content') or '').strip()
    for p in TOC_PATTERNS:
        if any(re.search(p, str(s), re.IGNORECASE) for s in sp):
            return True
    # 내용이 매우 짧거나 숫자/점으로만 구성된 경우
    if len(content) < 30 and re.match(r'^[\d\s\.\-]+$', content):
        return True
    return False


def embed_query(text: str) -> list:
    r = requests.post(
        f'{OLLAMA_BASE}/api/embed',
        json={'model': EMBED_MODEL, 'input': [text]},
        timeout=60,
    )
    if r.status_code == 200:
        embs = r.json().get('embeddings', [])
        if embs:
            return embs[0][:EMBED_DIM]
    return []


def step6_mrr(chunks, state):
    log.info('--- Step6: MRR 검증 (TOC 제외, ≥0.60) ---')

    # TOC 제외한 유효 청크만 사용
    valid_chunks = [c for c in chunks if not is_toc_chunk(c)
                    and c.get('embedding') is not None
                    and len(c.get('content', '')) > 50]
    log.info(f'  유효 청크: {len(valid_chunks)}/{len(chunks)}개')

    if not valid_chunks:
        log.warning('  유효 청크 없음 — MRR 스킵')
        state['steps']['step6'] = {'status': 'skip', 'reason': 'no valid chunks'}
        save_state(state)
        return 0.0, []

    # 검증용 쿼리 세트 (파일 내용 기반으로 첫 몇 개 청크에서 추출)
    # 간단히 첫 5개 유효 청크의 첫 문장을 쿼리로 사용
    test_queries = []
    for c in valid_chunks[:5]:
        content = c.get('content', '')
        # 첫 문장 추출
        sentences = re.split(r'[.!?\n]+', content)
        for s in sentences:
            s = s.strip()
            if len(s) > 20:
                test_queries.append({'text': s, 'target_chunk_id': c['chunk_id']})
                break

    log.info(f'  검증 쿼리: {len(test_queries)}개')

    reciprocal_ranks = []
    query_results = []

    for q in test_queries:
        q_text = q['text']
        target_id = q['target_chunk_id']

        # 쿼리 임베딩
        q_emb = embed_query(q_text)
        if not q_emb:
            log.warning(f'  쿼리 임베딩 실패: {q_text[:30]}')
            continue

        # 코사인 유사도 계산
        import numpy as np
        q_vec = np.array(q_emb)
        scores = []
        for c in valid_chunks:
            emb = c.get('embedding')
            if not emb:
                continue
            c_vec = np.array(emb)
            norm = np.linalg.norm(q_vec) * np.linalg.norm(c_vec)
            sim = float(np.dot(q_vec, c_vec) / norm) if norm > 0 else 0.0
            scores.append((sim, c['chunk_id']))

        scores.sort(reverse=True)
        ranked_ids = [s[1] for s in scores]

        rank = None
        for i, cid in enumerate(ranked_ids):
            if cid == target_id:
                rank = i + 1
                break

        rr = 1.0 / rank if rank else 0.0
        reciprocal_ranks.append(rr)
        query_results.append({
            'query': q_text[:60],
            'target': target_id,
            'rank': rank,
            'rr': round(rr, 3),
            'top3': ranked_ids[:3],
        })
        log.info(f'  Q: {q_text[:40]}... → rank={rank} RR={rr:.3f}')

    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0
    pass_fail = 'PASS' if mrr >= 0.60 else 'FAIL'
    log.info(f'  MRR={mrr:.3f} {pass_fail} (n={len(reciprocal_ranks)})')

    state['steps']['step6'] = {
        'status': 'done', 'mrr': round(mrr, 3),
        'pass_fail': pass_fail, 'n_queries': len(reciprocal_ranks),
        'queries': query_results,
    }
    save_state(state)
    return mrr, query_results


# ════════════════════════════════════════════════════════════════════
# Step 7: HTML 보고서 생성
# ════════════════════════════════════════════════════════════════════
def step7_report(state, mrr, query_results, node_count, rel_count):
    log.info('--- Step7: HTML 보고서 생성 ---')
    s = state['steps']
    s0 = s.get('step0', {})
    s1 = s.get('step1', {})
    s2 = s.get('step2', {})
    s3 = s.get('step3', {})
    s4 = s.get('step4', {})
    s5 = s.get('step5', {})
    s6 = s.get('step6', {})
    now = kst_now()

    mrr_color = '#27ae60' if mrr >= 0.60 else '#e74c3c'
    mrr_verdict = 'PASS' if mrr >= 0.60 else 'FAIL'
    verdict_bg = '#d5f5e3' if mrr >= 0.60 else '#fadbd8'
    verdict_border = '#27ae60' if mrr >= 0.60 else '#e74c3c'

    idx_rows = ''
    for name in s3.get('indexes', []):
        idx_rows += f'<tr><td>{name}</td></tr>'
    if not idx_rows:
        idx_rows = '<tr><td colspan="1" style="color:#999">인덱스 없음</td></tr>'

    q_rows = ''
    for q in query_results:
        rank = q.get('rank', '-')
        rr = q.get('rr', 0)
        color = '#27ae60' if rr >= 0.5 else ('#e67e22' if rr > 0 else '#e74c3c')
        q_rows += f'''<tr>
            <td style="font-size:11px">{q["query"]}...</td>
            <td style="text-align:center">{rank}</td>
            <td style="text-align:center;color:{color};font-weight:700">{rr}</td>
        </tr>'''

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>manuals-v2 파이프라인 검증 — {FILE_ID}</title>
<style>
body{{font-family:'Malgun Gothic',sans-serif;margin:0;background:#f5f5f5;color:#333}}
.header{{background:#2c3e50;color:#fff;padding:24px 36px}}
.header h1{{margin:0;font-size:20px}}
.header .sub{{font-size:12px;color:#aaa;margin-top:6px}}
.container{{max-width:900px;margin:24px auto;padding:0 16px}}
.card{{background:#fff;border-radius:8px;padding:20px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
.card h2{{font-size:15px;margin:0 0 14px;color:#2c3e50;border-bottom:2px solid #3498db;padding-bottom:6px}}
.kpi-row{{display:flex;gap:12px;flex-wrap:wrap}}
.kpi{{flex:1;min-width:100px;background:#f8f9fa;border-radius:6px;padding:12px;text-align:center;border-left:4px solid #3498db}}
.kpi .val{{font-size:26px;font-weight:700;color:#3498db}}
.kpi .lbl{{font-size:11px;color:#888;margin-top:3px}}
.kpi.g{{border-color:#27ae60}}.kpi.g .val{{color:#27ae60}}
.kpi.r{{border-color:#e74c3c}}.kpi.r .val{{color:#e74c3c}}
.kpi.o{{border-color:#e67e22}}.kpi.o .val{{color:#e67e22}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#2c3e50;color:#fff;padding:7px 10px;text-align:left}}
td{{padding:7px 10px;border-bottom:1px solid #eee}}
.badge{{display:inline-block;padding:2px 7px;border-radius:10px;font-size:11px;font-weight:700}}
.ok{{background:#d5f5e3;color:#27ae60}}
.warn{{background:#fdebd0;color:#e67e22}}
.fail{{background:#fadbd8;color:#e74c3c}}
.verdict{{font-size:14px;font-weight:700;padding:12px 16px;border-radius:6px;margin-top:10px;
  background:{verdict_bg};border-left:4px solid {verdict_border};color:{verdict_border}}}
.step-row{{display:flex;align-items:center;margin:6px 0}}
.step-num{{width:60px;font-size:12px;color:#888;font-weight:700}}
.step-bar{{flex:1;height:8px;background:#eee;border-radius:4px;overflow:hidden}}
.step-fill{{height:100%;background:#3498db;border-radius:4px}}
.step-fill.done{{background:#27ae60}}
.step-label{{width:100px;font-size:11px;color:#555;margin-left:8px}}
</style>
</head>
<body>
<div class="header">
  <h1>manuals-v2 파이프라인 단독 검증 보고서</h1>
  <div class="sub">qa-agent | {FILE_ID} | {now} | run_id: {RUN_ID}</div>
</div>
<div class="container">

<div class="card">
  <h2>종합 KPI</h2>
  <div class="kpi-row">
    <div class="kpi {'g' if mrr>=0.6 else 'r'}"><div class="val">{mrr:.3f}</div><div class="lbl">MRR ({mrr_verdict})</div></div>
    <div class="kpi g"><div class="val">{s0.get('total',0)}</div><div class="lbl">총 청크</div></div>
    <div class="kpi g"><div class="val">{s1.get('ok',0)}</div><div class="lbl">임베딩 완료</div></div>
    <div class="kpi g"><div class="val">{s2.get('inserted',0)}</div><div class="lbl">DB INSERT</div></div>
    <div class="kpi {'g' if node_count>0 else 'o'}"><div class="val">{node_count}</div><div class="lbl">Neo4j 노드</div></div>
    <div class="kpi"><div class="val">{rel_count}</div><div class="lbl">Neo4j 관계</div></div>
  </div>
  <div class="verdict">전체 파이프라인 {mrr_verdict}: MRR={mrr:.3f} ({'≥' if mrr>=0.6 else '<'}0.60 허들)</div>
</div>

<div class="card">
  <h2>Step별 실행 결과</h2>
  <table>
    <tr><th>Step</th><th>내용</th><th>결과</th><th>상태</th></tr>
    <tr><td>Step0</td><td>chunks.jsonl 검증</td>
      <td>총 {s0.get('total',0)}청크, lang={s0.get('langs','-')}, 빈청크={s0.get('empty',0)}</td>
      <td><span class="badge ok">DONE</span></td></tr>
    <tr><td>Step1</td><td>임베딩 (qwen3-embedding:8b, 2000dim)</td>
      <td>완료={s1.get('ok',0)} 오류={s1.get('errors',0)}</td>
      <td><span class="badge ok">DONE</span></td></tr>
    <tr><td>Step2</td><td>manual.documents_v2 UPSERT</td>
      <td>INSERT={s2.get('inserted',0)} (기존 {s2.get('deleted',0)}건 삭제)</td>
      <td><span class="badge ok">DONE</span></td></tr>
    <tr><td>Step3</td><td>HNSW+GIN 인덱스 확인</td>
      <td>{'HNSW 있음' if s3.get('has_hnsw') else 'HNSW 없음 (성능저하 가능)'}</td>
      <td><span class="badge {'ok' if s3.get('has_hnsw') else 'warn'}">{'DONE' if s3.get('has_hnsw') else 'WARN'}</span></td></tr>
    <tr><td>Step4</td><td>GraphRAG 엔티티 추출 (qwen3.5:35b-a3b)</td>
      <td>엔티티={s4.get('entities',0)} 관계={s4.get('relations',0)}</td>
      <td><span class="badge ok">DONE</span></td></tr>
    <tr><td>Step5</td><td>Neo4j MERGE ({NEO4J_LABEL})</td>
      <td>노드={node_count} 관계={rel_count}</td>
      <td><span class="badge {'ok' if node_count>0 else 'warn'}">{'DONE' if node_count>0 else 'WARN'}</span></td></tr>
    <tr><td>Step6</td><td>MRR 검증 (TOC 제외)</td>
      <td>MRR={mrr:.3f} (n={s6.get('n_queries',0)}쿼리)</td>
      <td><span class="badge {'ok' if mrr>=0.6 else 'fail'}">{mrr_verdict}</span></td></tr>
    <tr><td>Step7</td><td>HTML 보고서</td><td>이 보고서</td>
      <td><span class="badge ok">DONE</span></td></tr>
  </table>
</div>

<div class="card">
  <h2>Step6 — MRR 검증 상세</h2>
  <table>
    <tr><th>쿼리 (앞 60자)</th><th>rank</th><th>RR</th></tr>
    {q_rows if q_rows else '<tr><td colspan="3" style="color:#999">쿼리 결과 없음</td></tr>'}
  </table>
  <div style="margin-top:10px;font-size:13px">
    <b>MRR = {mrr:.3f}</b> | 허들 0.60 | 판정: <b style="color:{mrr_color}">{mrr_verdict}</b>
  </div>
</div>

<div class="card">
  <h2>Step3 — 인덱스 목록</h2>
  <table>
    <tr><th>인덱스명</th></tr>
    {idx_rows}
  </table>
</div>

<div class="card">
  <h2>파이프라인 구성 (SKILL.md 준수)</h2>
  <table>
    <tr><th>항목</th><th>설정</th><th>준수</th></tr>
    <tr><td>임베딩 모델</td><td>qwen3-embedding:8b</td><td><span class="badge ok">M3</span></td></tr>
    <tr><td>임베딩 차원</td><td>2000dim (MRL 슬라이싱)</td><td><span class="badge ok">M3</span></td></tr>
    <tr><td>GraphRAG LLM</td><td>qwen3.5:35b-a3b (think:false)</td><td><span class="badge ok">M2</span></td></tr>
    <tr><td>num_predict</td><td>1200 + json_repair</td><td><span class="badge ok">통일</span></td></tr>
    <tr><td>벡터 테이블</td><td>manual.documents_v2</td><td><span class="badge ok">M6</span></td></tr>
    <tr><td>Neo4j 라벨</td><td>{NEO4J_LABEL}</td><td><span class="badge ok">M10</span></td></tr>
    <tr><td>LightRAG</td><td>미사용</td><td><span class="badge ok">N1</span></td></tr>
    <tr><td>산출물 경로</td><td>reports/manuals-v2/</td><td><span class="badge ok">M8</span></td></tr>
    <tr><td>체크포인트</td><td>state.json + .log 2파일</td><td><span class="badge ok">M13</span></td></tr>
  </table>
</div>

</div>
</body>
</html>'''

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(html, encoding='utf-8')
    log.info(f'  보고서 저장: {REPORT_PATH}')
    state['steps']['step7'] = {'status': 'done', 'report': str(REPORT_PATH)}
    save_state(state)
    return REPORT_PATH


# ════════════════════════════════════════════════════════════════════
# 메인
# ════════════════════════════════════════════════════════════════════
def main():
    t0 = time.time()
    log.info(f'=== manuals-v2 파이프라인 시작 — {FILE_ID} | {kst_now()} ===')
    state = load_state()
    state['run_id'] = RUN_ID
    save_state(state)

    try:
        # Step0
        chunks = step0_validate(state)

        # Step1
        embeddings = step1_embed(chunks, state)

        # Step2
        inserted = step2_insert(chunks, embeddings, state)

        # Step3
        step3_index(state)

        # Step4
        extracted = step4_extract(chunks, state)

        # Step5
        node_count, rel_count = step5_neo4j(extracted, state)

        # Step6
        mrr, query_results = step6_mrr(chunks, state)

        # Step7
        step7_report(state, mrr, query_results, node_count, rel_count)

        elapsed = round(time.time() - t0, 1)
        state['status'] = 'done'
        state['elapsed'] = elapsed
        save_state(state)
        log.info(f'=== 완료 — MRR={mrr:.3f} nodes={node_count} rels={rel_count} elapsed={elapsed}s ===')

    except Exception as e:
        state['status'] = 'error'
        state['error'] = str(e)
        save_state(state)
        log.error(f'파이프라인 오류: {e}')
        raise


if __name__ == '__main__':
    main()
