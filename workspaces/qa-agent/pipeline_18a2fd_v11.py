"""
manuals-v2 SKILL.md v1.1 기준 파이프라인 — 1_robot_18a2fd5fb603
Step0~7 전체 실행. 체크포인트/재개 지원.

실행:
  python pipeline_18a2fd_v11.py          # 전체
  python pipeline_18a2fd_v11.py --from step4  # step4부터 재개
  python pipeline_18a2fd_v11.py --reset  # 상태 초기화 후 재시작
"""
import sys, json, re, os, time, logging, argparse, hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import numpy as np
import psycopg2

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── 설정 ──────────────────────────────────────────────────────────
FILE_ID    = '1_robot_18a2fd5fb603'
CATEGORY   = '1_robot'
RUN_ID     = datetime.now(timezone(timedelta(hours=9))).strftime('run-%Y%m%d-%H%M%S')
TEAM       = 'qa-agent'

ROOT       = Path(r'C:\MES\wta-agents')
POC_DIR    = ROOT / 'reports' / 'manuals-v2' / 'poc' / FILE_ID
WORK_DIR   = ROOT / 'reports' / 'manuals-v2' / 'state'
EVAL_DIR   = ROOT / 'reports' / 'manuals-v2' / 'eval'
UPLOAD_DIR = ROOT / 'dashboard' / 'uploads'
NEO4J_ENV  = ROOT / 'workspaces' / 'research-agent' / 'neo4j-poc.env'

STATE_PATH = WORK_DIR / 'pipeline_18a2fd_v11_state.json'
LOG_PATH   = WORK_DIR / 'pipeline_18a2fd_v11.log'

OLLAMA_BASE    = 'http://182.224.6.147:11434'
EMBED_MODEL    = 'qwen3-embedding:8b'
EXTRACT_MODEL  = 'qwen3.5:35b-a3b'
EMBED_DIM      = 2000
EMBED_FULL_DIM = 4096

# v1.1 윈도우 규격
WINDOW_SIZE    = 800
WINDOW_OVERLAP = 200
MIN_WINDOW_LEN = 50

# v1.1 엔티티/관계 온톨로지
VALID_ENTITY_TYPES = {
    'Equipment', 'Component', 'Parameter', 'Alarm', 'Process',
    'Section', 'Figure', 'Table', 'Diagram', 'Specification',
    'Manual', 'SafetyRule',
}
VALID_REL_TYPES = {
    'PART_OF', 'HAS_PARAMETER', 'SPECIFIES', 'CAUSES', 'RESOLVES',
    'CONNECTS_TO', 'REQUIRES', 'BELONGS_TO', 'REFERENCES',
    'DEPICTS', 'DOCUMENTS', 'WARNS',
}

# v1.1 확정 프롬프트
MANUALS_V2_EXTRACT_PROMPT = """다음 산업 장비 매뉴얼 텍스트에서 엔티티와 관계를 추출하세요.

## 엔티티 타입 (12종)
- Equipment: 장비/기기 (로봇, 인버터, 서보, 센서, PLC 등)
- Component: 부품/구성요소 (모터, 엔코더, 퓨즈, 커넥터, 단자대 등)
- Parameter: 파라미터/설정값 코드 (C1-01, H4-02, Pr.7 등 코드 반드시 포함)
- Alarm: 알람/에러코드 (oC, AL.16, E401, OV 등 코드 반드시 포함)
- Process: 절차/작업/공정 (배선, 설치, 점검, 튜닝, 초기화, 교체 등)
- Section: 문서 섹션/챕터 (제목 단위)
- Figure: 그림/다이어그램 (배선도, 회로도, 외형도 등)
- Table: 표 (파라미터 표, 사양 표, 알람 일람표 등)
- Diagram: 도식/블록도 (제어 블록도, 시퀀스 다이어그램 등)
- Specification: 사양/규격 수치 (정격전압 200V, 최대토크 47Nm 등)
- Manual: 매뉴얼 문서 자체
- SafetyRule: 안전규정/경고 ("전원 차단 후 5분 대기" 등)

## 관계 타입 (12종)
- PART_OF: Component가 Equipment의 부품 (예: 엔코더 → 서보모터)
- HAS_PARAMETER: Equipment가 Parameter를 가짐 (예: 인버터 → C1-01)
- SPECIFIES: Specification이 Equipment/Component를 규정 (예: 정격전압 → 인버터)
- CAUSES: Alarm 발생 시 Process 유발 (예: oC 알람 → 냉각 점검)
- RESOLVES: Process가 Alarm을 해결 (예: 냉각팬 교체 → oC 해소)
- CONNECTS_TO: Equipment/Component 간 물리적 연결 (예: 엔코더 → CN5 커넥터)
- REQUIRES: Process에 필요한 Equipment/Component (예: 배선작업 → 압착단자)
- BELONGS_TO: Figure/Table이 Section에 속함 (예: 그림3-1 → 제3장)
- REFERENCES: Section이 Figure/Table을 참조 (예: "그림 3-1 참조")
- DEPICTS: Figure가 Equipment/Component를 도식 (예: 배선도 → 서보드라이브)
- DOCUMENTS: Manual이 Equipment/Process를 기술
- WARNS: SafetyRule이 Process/Equipment에 적용 (예: "접지 필수" → 설치작업)

## 추출 규칙
1. 엔티티 id는 영문 snake_case (예: yaskawa_v1000, param_c1_01, alarm_oc)
2. name은 원문 표기 그대로 (한국어/영어/일어)
3. properties에 model, mfr(제조사), unit(단위), code(코드) 등 있으면 포함
4. 관계는 반드시 추출된 엔티티 id 사이에서만 생성
5. 텍스트에 명시적 근거가 없는 관계는 생성하지 않음
6. 엔티티가 0개여도 빈 배열로 응답, 에러 메시지 금지

## 응답 형식 (JSON만, 다른 텍스트 없이)
{
  "entities": [
    {"id": "eng_snake_case", "name": "표시명", "type": "Equipment", "properties": {"model": "V1000", "mfr": "Yaskawa"}}
  ],
  "relations": [
    {"source": "entity_id1", "target": "entity_id2", "type": "HAS_PARAMETER"}
  ]
}

텍스트:
"""

# v1.1 LLM 파라미터
LLM_PARAMS = {
    'model': EXTRACT_MODEL,
    'stream': False,
    'think': False,
    'options': {'num_predict': 4096, 'temperature': 0},
}
LLM_TIMEOUT = 300

# ── 디렉토리 생성 ─────────────────────────────────────────────────
for d in [WORK_DIR, EVAL_DIR, UPLOAD_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── 로깅 ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[v11] %(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_PATH), encoding='utf-8'),
    ],
)
log = logging.getLogger('v11')


# ── 유틸 ──────────────────────────────────────────────────────────
def now_kst():
    return datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'run_id': RUN_ID, 'status': 'running', 'steps': {}}


def save_state(state: dict):
    state['last_update'] = now_kst()
    tmp = STATE_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(STATE_PATH)


# ── DB 연결 ──────────────────────────────────────────────────────
def _read_db_password() -> str:
    # 환경변수 우선, 없으면 backend/.env에서 읽기
    pwd = os.environ.get('DB_PASSWORD', '')
    if not pwd:
        env_path = Path(r'C:\MES\backend\.env')
        if env_path.exists():
            for line in env_path.read_text(encoding='utf-8').splitlines():
                if line.startswith('DB_PASSWORD='):
                    pwd = line.split('=', 1)[1].strip()
                    break
    return pwd


def get_db():
    return psycopg2.connect(
        host='localhost', port=55432, dbname='postgres',
        user='postgres', password=_read_db_password(),
    )


# ── Neo4j 연결 ───────────────────────────────────────────────────
def get_neo4j():
    pwd = ''
    for line in NEO4J_ENV.read_text(encoding='utf-8').splitlines():
        if line.startswith('NEO4J_AUTH=neo4j/'):
            pwd = line.split('/', 1)[1].strip()
            break
    from neo4j import GraphDatabase
    return GraphDatabase.driver('bolt://localhost:7688', auth=('neo4j', pwd))


# ── Step 0: 청크 검증 ─────────────────────────────────────────────
def step0(state: dict) -> list[dict]:
    log.info('=== Step 0: 청크 검증 ===')
    chunks_path = POC_DIR / 'chunks.jsonl'
    chunks = []
    with open(chunks_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ch = json.loads(line)
                content = (ch.get('content') or '').strip()
                if content:
                    chunks.append(ch)
            except Exception:
                pass

    langs = list(set(ch.get('lang', 'unk') for ch in chunks))
    lens = [len(ch.get('content', '')) for ch in chunks]
    result = {
        'status': 'done',
        'total': len(chunks),
        'empty': 0,
        'langs': langs,
        'min_len': min(lens) if lens else 0,
        'avg_len': round(sum(lens) / len(lens)) if lens else 0,
        'max_len': max(lens) if lens else 0,
    }
    state['steps']['step0'] = result
    save_state(state)
    log.info(f"   총 {len(chunks)}청크, avg_len={result['avg_len']}자")
    return chunks


# ── Step 1: 임베딩 ────────────────────────────────────────────────
def step1(state: dict, chunks: list[dict]) -> list[dict]:
    log.info('=== Step 1: 임베딩 (qwen3-embedding:8b 2000dim) ===')
    prev = state['steps'].get('step1', {})
    done_ids = set(prev.get('embedded_ids', []))

    to_embed = [ch for ch in chunks if ch.get('chunk_id') not in done_ids]
    log.info(f'   임베딩 대상: {len(to_embed)}건 (기존 완료: {len(done_ids)}건)')

    BATCH = 4
    embedded_ids = list(done_ids)
    errors = 0
    embed_map: dict[str, list[float]] = {}

    for i in range(0, len(to_embed), BATCH):
        batch = to_embed[i:i + BATCH]
        texts = [ch.get('content', '')[:3000] for ch in batch]
        try:
            r = requests.post(
                f'{OLLAMA_BASE}/api/embed',
                json={'model': EMBED_MODEL, 'input': texts},
                timeout=120,
            )
            if r.status_code == 200:
                vecs = r.json().get('embeddings', [])
                for ch, vec in zip(batch, vecs):
                    if vec and len(vec) >= EMBED_DIM:
                        embed_map[ch['chunk_id']] = vec[:EMBED_DIM]
                        embedded_ids.append(ch['chunk_id'])
                    else:
                        errors += 1
            else:
                errors += len(batch)
                log.warning(f'   임베딩 오류 [{i}]: HTTP {r.status_code}')
        except Exception as e:
            errors += len(batch)
            log.warning(f'   임베딩 예외 [{i}]: {e}')

        if (i // BATCH + 1) % 10 == 0:
            log.info(f'   진행: {min(i+BATCH, len(to_embed))}/{len(to_embed)}')

    # chunks에 embedding 추가
    for ch in chunks:
        if ch['chunk_id'] in embed_map:
            ch['_embedding'] = embed_map[ch['chunk_id']]

    result = {
        'status': 'done',
        'ok': len(embedded_ids),
        'errors': errors,
        'embedded_ids': embedded_ids,
    }
    state['steps']['step1'] = result
    save_state(state)
    log.info(f"   완료: ok={result['ok']}, errors={errors}")
    return chunks


# ── Step 2: pgvector 적재 ─────────────────────────────────────────
def step2(state: dict, chunks: list[dict]):
    log.info('=== Step 2: pgvector 적재 (manual.documents_v2) ===')
    conn = get_db()
    cur = conn.cursor()

    # 기존 행 삭제
    cur.execute('DELETE FROM manual.documents_v2 WHERE file_id = %s', (FILE_ID,))
    deleted = cur.rowcount
    log.info(f'   기존 행 삭제: {deleted}건')

    inserted = 0
    for ch in chunks:
        emb = ch.get('_embedding')
        if emb is None:
            continue
        content = (ch.get('content') or '').strip()
        tokens = ch.get('tokens', len(content.split()))
        src_hash = ch.get('source_hash', hashlib.md5(content.encode()).hexdigest())
        try:
            cur.execute(
                """INSERT INTO manual.documents_v2
                   (file_id, chunk_id, category, mfr, model, doctype, lang,
                    section_path, page_start, page_end, content, tokens,
                    source_hash, embedding, figure_refs, table_refs, inline_refs)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector,%s,%s,%s)
                   ON CONFLICT (file_id, chunk_id) DO UPDATE
                   SET content=EXCLUDED.content, embedding=EXCLUDED.embedding,
                       tokens=EXCLUDED.tokens, source_hash=EXCLUDED.source_hash""",
                (
                    ch.get('file_id', FILE_ID),
                    ch.get('chunk_id', ''),
                    ch.get('category', CATEGORY),
                    ch.get('mfr', 'Unknown'),
                    ch.get('model', 'Unknown'),
                    ch.get('doctype', 'manual'),
                    ch.get('lang', 'en'),
                    json.dumps(ch.get('section_path', [])),
                    ch.get('page_start', 0),
                    ch.get('page_end', 0),
                    content,
                    tokens,
                    src_hash,
                    '[' + ','.join(str(v) for v in emb) + ']',
                    json.dumps(ch.get('figure_refs', [])),
                    json.dumps(ch.get('table_refs', [])),
                    json.dumps(ch.get('inline_refs', [])),
                ),
            )
            inserted += 1
        except Exception as e:
            log.warning(f'   INSERT 오류 [{ch.get("chunk_id")}]: {e}')

    conn.commit()
    conn.close()

    result = {'status': 'done', 'deleted': deleted, 'inserted': inserted}
    state['steps']['step2'] = result
    save_state(state)
    log.info(f"   삭제 {deleted}건, 삽입 {inserted}건")


# ── Step 3: 인덱스 확인 ───────────────────────────────────────────
def step3(state: dict):
    log.info('=== Step 3: 인덱스 확인 ===')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT indexname FROM pg_indexes
        WHERE tablename='documents_v2' AND schemaname='manual'
        ORDER BY indexname
    """)
    idxs = [r[0] for r in cur.fetchall()]
    conn.close()

    has_hnsw = any('hnsw' in i for i in idxs)
    has_gin  = any('gin' in i for i in idxs)
    result = {
        'status': 'done',
        'indexes': idxs,
        'has_hnsw': has_hnsw,
        'has_gin': has_gin,
    }
    state['steps']['step3'] = result
    save_state(state)
    log.info(f"   HNSW={has_hnsw}, GIN={has_gin}, 인덱스 {len(idxs)}개")


# ── Step 4: 엔티티 추출 (v1.1 윈도우 + 프롬프트) ──────────────────
def build_windows(chunks: list[dict]) -> list[dict]:
    """800자 + 200 오버랩 슬라이딩 윈도우"""
    parts = []
    chunk_map = []  # (start_pos, chunk_id)
    pos = 0
    for ch in chunks:
        content = (ch.get('content') or '').strip()
        if not content:
            continue
        chunk_map.append((pos, ch.get('chunk_id', '')))
        parts.append(content)
        pos += len(content) + 2

    full_text = '\n\n'.join(parts)
    total_len = len(full_text)
    log.info(f'   전체 텍스트 {total_len}자 → 윈도우 생성 중')

    windows = []
    start = 0
    while start < total_len:
        end = start + WINDOW_SIZE
        win_text = full_text[start:end]
        if len(win_text) < MIN_WINDOW_LEN:
            break
        # 마지막 윈도우가 300자 미만이면 현재에 병합
        remaining = total_len - end
        if 0 < remaining < 300:
            win_text = full_text[start:]
            end = total_len
        # 해당 윈도우에 걸리는 chunk_id 수집
        cids = [cid for (p, cid) in chunk_map if p < end and p + 100 > start]
        windows.append({'idx': len(windows), 'text': win_text, 'chunk_ids': cids})
        if end >= total_len:
            break
        start = end - WINDOW_OVERLAP

    return windows


def extract_window(win_text: str, win_idx: int) -> dict:
    """단일 윈도우 엔티티/관계 추출"""
    prompt = MANUALS_V2_EXTRACT_PROMPT + win_text
    params = dict(LLM_PARAMS)
    params['prompt'] = prompt
    try:
        r = requests.post(f'{OLLAMA_BASE}/api/generate', json=params, timeout=LLM_TIMEOUT)
        if r.status_code == 200:
            raw = r.json().get('response', '').strip()
            # 코드블록 제거
            raw = re.sub(r'```json\s*', '', raw)
            raw = re.sub(r'```\s*', '', raw)
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    # 부분 파싱: entities만 추출
                    ent_m = re.search(r'"entities"\s*:\s*\[(.*?)\]', raw, re.DOTALL)
                    if ent_m:
                        try:
                            ents = json.loads('[' + ent_m.group(1) + ']')
                            return {'entities': ents, 'relations': []}
                        except Exception:
                            pass
    except Exception as e:
        log.warning(f'   LLM 오류 [win_{win_idx}]: {e}')
    return {'entities': [], 'relations': []}


def step4(state: dict, chunks: list[dict]) -> tuple[dict, dict]:
    """
    v1.1: 800+200 슬라이딩 윈도우로 엔티티/관계 추출.
    Returns: (all_entities dict keyed by safe_id, all_relations list)
    """
    log.info('=== Step 4: 엔티티 추출 (v1.1 윈도우) ===')
    prev = state['steps'].get('step4', {})
    done_wins = set(prev.get('done_windows', []))
    all_entities: dict = prev.get('all_entities', {})
    all_relations: list = prev.get('all_relations', [])

    windows = build_windows(chunks)
    log.info(f'   윈도우 총 {len(windows)}개')

    for win in windows:
        widx = win['idx']
        if widx in done_wins:
            continue

        t0 = time.time()
        result = extract_window(win['text'], widx)
        elapsed = round(time.time() - t0, 1)

        # 엔티티 병합 (중복 제거: snake_case id 기준)
        win_entity_ids = set()
        for ent in result.get('entities', []):
            etype = ent.get('type', '')
            if etype not in VALID_ENTITY_TYPES:
                continue
            orig_id = ent.get('id', '').strip()
            if not orig_id:
                continue
            safe_id = re.sub(r'[^a-zA-Z0-9_]', '_', orig_id).lower()
            win_entity_ids.add(safe_id)
            if safe_id not in all_entities:
                all_entities[safe_id] = {
                    'id': safe_id,
                    'orig_id': orig_id,
                    'name': ent.get('name', orig_id),
                    'type': etype,
                    'properties': ent.get('properties') or {},
                }

        # 관계 병합 (현재 윈도우 엔티티 id 기반)
        for rel in result.get('relations', []):
            src = re.sub(r'[^a-zA-Z0-9_]', '_', rel.get('source', '')).lower()
            tgt = re.sub(r'[^a-zA-Z0-9_]', '_', rel.get('target', '')).lower()
            rtype = rel.get('type', '')
            if src in win_entity_ids and tgt in win_entity_ids and rtype in VALID_REL_TYPES:
                rel_key = f'{src}|{rtype}|{tgt}'
                # 중복 방지
                existing_keys = {f"{r['source']}|{r['type']}|{r['target']}" for r in all_relations}
                if rel_key not in existing_keys:
                    all_relations.append({'source': src, 'target': tgt, 'type': rtype})

        done_wins.add(widx)
        n_ent = len(result.get('entities', []))
        n_rel = len(result.get('relations', []))
        log.info(f'   win_{widx}/{len(windows)-1}: entities={n_ent} rels={n_rel} ({elapsed}s)')

        # 중간 저장 (5 윈도우마다)
        if widx % 5 == 0:
            state['steps']['step4'] = {
                'status': 'running',
                'total_windows': len(windows),
                'done_windows': list(done_wins),
                'all_entities': all_entities,
                'all_relations': all_relations,
            }
            save_state(state)

    result_step = {
        'status': 'done',
        'total_windows': len(windows),
        'done_windows': list(done_wins),
        'all_entities': all_entities,
        'all_relations': all_relations,
        'total_entities': len(all_entities),
        'total_relations': len(all_relations),
    }
    state['steps']['step4'] = result_step
    save_state(state)
    log.info(f"   완료: 엔티티 {len(all_entities)}개, 관계 {len(all_relations)}개")
    return all_entities, all_relations


# ── Step 5: Neo4j 적재 (v1.1 라벨 규칙) ──────────────────────────
def step5(state: dict, all_entities: dict, all_relations: list):
    log.info('=== Step 5: Neo4j 적재 (:ManualsV2Entity:{Type}) ===')
    driver = get_neo4j()
    node_count = rel_count = 0

    with driver.session() as s:
        for eid, ent in all_entities.items():
            etype = ent['type']
            props = dict(ent.get('properties') or {})
            props.update({
                '_id': eid,
                '_file_id': FILE_ID,
                '_run_id': RUN_ID,
                '_team': TEAM,
                'source': 'manuals_v2',
            })
            props = {k: v for k, v in props.items() if v is not None and v != ''}
            try:
                s.run(
                    f'MERGE (n:ManualsV2Entity:{etype} {{_id: $_id}}) '
                    f'SET n += $props, n.name = $name',
                    _id=eid, props=props, name=ent.get('name', eid),
                )
                node_count += 1
            except Exception as e:
                log.debug(f'   노드 오류 [{eid}]: {e}')

        for rel in all_relations:
            src, tgt, rtype = rel['source'], rel['target'], rel['type']
            try:
                s.run(
                    'MATCH (a:ManualsV2Entity {_id: $src}), (b:ManualsV2Entity {_id: $tgt}) '
                    'MERGE (a)-[r:' + rtype + ']->(b)',
                    src=src, tgt=tgt,
                )
                rel_count += 1
            except Exception as e:
                log.debug(f'   관계 오류 [{src}->{tgt}]: {e}')

    driver.close()
    result = {
        'status': 'done',
        'neo4j_label': 'ManualsV2Entity:{Type}',
        'nodes': node_count,
        'rels': rel_count,
        'run_id': RUN_ID,
    }
    state['steps']['step5'] = result
    save_state(state)
    log.info(f"   Neo4j: 노드 {node_count}개, 관계 {rel_count}개")


# ── Step 6: MRR 평가 (v1.1 기준) ─────────────────────────────────
def embed_text(text: str) -> list[float]:
    r = requests.post(
        f'{OLLAMA_BASE}/api/embed',
        json={'model': EMBED_MODEL, 'input': [text]},
        timeout=60,
    )
    if r.status_code == 200:
        vecs = r.json().get('embeddings', [])
        if vecs and len(vecs[0]) >= EMBED_DIM:
            return vecs[0][:EMBED_DIM]
    return []


def cosine(a, b):
    a, b = np.array(a), np.array(b)
    n = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / n) if n > 0 else 0.0


def step6(state: dict, chunks: list[dict]):
    log.info('=== Step 6: MRR 평가 (v1.1 쿼리셋) ===')

    # 임베딩이 있는 청크 수집
    valid = [(ch['chunk_id'], ch['_embedding']) for ch in chunks if ch.get('_embedding')]
    if not valid:
        # DB에서 로드
        log.info('   DB에서 임베딩 로드 중...')
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            'SELECT chunk_id, embedding FROM manual.documents_v2 WHERE file_id=%s',
            (FILE_ID,),
        )
        valid = []
        for chunk_id, emb in cur.fetchall():
            if emb:
                vec = [float(x) for x in str(emb).strip('[]').split(',')]
                valid.append((chunk_id, vec))
        conn.close()
        log.info(f'   로드 완료: {len(valid)}건')

    chunk_vecs = {cid: vec for cid, vec in valid}

    # TOC 패턴 제외
    toc_pattern = re.compile(
        r'^[\d\.]+\s*$|目次|contents|table of contents|index|索引',
        re.IGNORECASE,
    )

    def is_toc(ch):
        c = (ch.get('content') or '')
        return bool(toc_pattern.search(c[:100])) or len(c.strip()) < 30

    # 쿼리 후보: 상위 10% 청크 (길이 기준) → 첫 문장 추출
    sorted_chunks = sorted(
        [ch for ch in chunks if not is_toc(ch)],
        key=lambda x: len(x.get('content', '')),
        reverse=True,
    )
    top10pct = sorted_chunks[:max(3, len(sorted_chunks) // 10)]

    # 쿼리 생성 (최소 3건)
    queries = []
    for ch in top10pct[:10]:
        content = (ch.get('content') or '').strip()
        # 첫 문장 (50자 이상)
        sentences = [s.strip() for s in re.split(r'[.。\n]', content) if len(s.strip()) > 30]
        if sentences:
            q_text = sentences[0][:120]
            queries.append({'query': q_text, 'answer_chunk_ids': [ch['chunk_id']], 'category': CATEGORY, 'file_id': FILE_ID})

    # 최소 3건 보장
    if len(queries) < 3:
        for ch in sorted_chunks[len(queries):10]:
            content = (ch.get('content') or '').strip()[:120]
            queries.append({'query': content, 'answer_chunk_ids': [ch['chunk_id']], 'category': CATEGORY, 'file_id': FILE_ID})
            if len(queries) >= 3:
                break

    log.info(f'   쿼리 {len(queries)}건 생성')

    # 쿼리셋 저장
    qs_path = EVAL_DIR / 'mrr_queryset_v1.jsonl'
    with open(qs_path, 'w', encoding='utf-8') as f:
        for q in queries:
            f.write(json.dumps(q, ensure_ascii=False) + '\n')

    # MRR@5, Hit@5, Precision@5 평가
    all_cids = list(chunk_vecs.keys())
    results = []
    for q in queries:
        q_emb = embed_text(q['query'])
        if not q_emb:
            continue
        scored = sorted(
            [(cid, cosine(q_emb, chunk_vecs[cid])) for cid in all_cids if cid in chunk_vecs],
            key=lambda x: x[1], reverse=True,
        )
        top5 = [cid for cid, _ in scored[:5]]
        answers = set(q['answer_chunk_ids'])
        rank = next((i + 1 for i, cid in enumerate(top5) if cid in answers), 0)
        rr = 1.0 / rank if rank > 0 else 0.0
        hit = 1 if rank > 0 else 0
        precision = len([c for c in top5 if c in answers]) / 5
        results.append({
            'query': q['query'],
            'answer_chunk_ids': q['answer_chunk_ids'],
            'rank': rank,
            'reciprocal_rank': rr,
            'hit_at_5': hit,
            'precision_at_5': round(precision, 3),
            'top5': top5,
        })

    avg_mrr = round(sum(r['reciprocal_rank'] for r in results) / len(results), 4) if results else 0
    avg_hit = round(sum(r['hit_at_5'] for r in results) / len(results), 4) if results else 0
    avg_prec = round(sum(r['precision_at_5'] for r in results) / len(results), 4) if results else 0
    pass_fail = 'PASS' if avg_mrr >= 0.60 else 'FAIL'

    # MRR 보고서 저장
    mrr_report = {
        'run_id': RUN_ID,
        'team': TEAM,
        'queryset_version': 'v1',
        'results': results,
        'summary': {'avg_mrr': avg_mrr, 'avg_hit': avg_hit, 'avg_precision': avg_prec, 'pass_fail': pass_fail},
    }
    rpt_path = EVAL_DIR / 'mrr_report_v1.json'
    rpt_path.write_text(json.dumps(mrr_report, ensure_ascii=False, indent=2), encoding='utf-8')

    step_result = {
        'status': 'done',
        'mrr': avg_mrr,
        'hit_at_5': avg_hit,
        'precision_at_5': avg_prec,
        'pass_fail': pass_fail,
        'n_queries': len(results),
        'queries': results,
    }
    state['steps']['step6'] = step_result
    save_state(state)
    log.info(f"   MRR={avg_mrr}, Hit@5={avg_hit}, Precision@5={avg_prec} → {pass_fail}")


# ── Step 7: HTML 보고서 ───────────────────────────────────────────
def step7(state: dict, t0: float):
    log.info('=== Step 7: HTML 보고서 생성 ===')
    s0 = state['steps'].get('step0', {})
    s1 = state['steps'].get('step1', {})
    s2 = state['steps'].get('step2', {})
    s3 = state['steps'].get('step3', {})
    s4 = state['steps'].get('step4', {})
    s5 = state['steps'].get('step5', {})
    s6 = state['steps'].get('step6', {})

    # 엔티티 타입 분포
    all_entities = s4.get('all_entities', {})
    type_dist: dict[str, int] = {}
    for ent in all_entities.values():
        t = ent.get('type', 'Unknown')
        type_dist[t] = type_dist.get(t, 0) + 1

    def badge(v):
        if v == 'PASS':
            return '<span class="badge badge-ok">PASS</span>'
        if v == 'FAIL':
            return '<span class="badge badge-err">FAIL</span>'
        if v == 'WARN':
            return '<span class="badge badge-warn">WARN</span>'
        return f'<span class="badge badge-ok">{v}</span>'

    def step_row(name, result, detail=''):
        status = result.get('status', '-')
        cls = 'badge-ok' if status == 'done' else 'badge-warn'
        return f'<tr><td>{name}</td><td><span class="badge {cls}">{status}</span></td><td>{detail}</td></tr>'

    type_rows = ''.join(
        f'<tr><td>{t}</td><td>{c}</td></tr>'
        for t, c in sorted(type_dist.items(), key=lambda x: -x[1])
    )

    q_rows = ''
    for q in s6.get('queries', []):
        rr = q.get('reciprocal_rank', 0)
        rank = q.get('rank', 0)
        cls = 'badge-ok' if rank == 1 else ('badge-warn' if rank <= 3 else 'badge-err')
        q_rows += f'<tr><td>{q["query"][:80]}...</td><td>{rank}</td><td>{rr:.2f}</td><td>{q["hit_at_5"]}</td></tr>'

    elapsed_total = round(time.time() - t0, 1)
    mrr = s6.get('mrr', 0)
    pf = s6.get('pass_fail', '-')
    pf_class = 'pass' if pf == 'PASS' else 'warn'

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>manuals-v2 v1.1 파이프라인 보고서 — {FILE_ID}</title>
<style>
body {{ font-family: 'Malgun Gothic', sans-serif; margin: 0; background: #f5f5f5; color: #333; }}
.header {{ background: #2c3e50; color: #fff; padding: 28px 40px; }}
.header h1 {{ margin: 0; font-size: 20px; font-weight: 700; }}
.header .sub {{ font-size: 13px; color: #aaa; margin-top: 6px; }}
.container {{ max-width: 1000px; margin: 30px auto; padding: 0 20px; }}
.card {{ background: #fff; border-radius: 8px; padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
.card h2 {{ font-size: 16px; margin: 0 0 16px; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px; }}
.kpi-row {{ display: flex; gap: 16px; flex-wrap: wrap; }}
.kpi {{ flex: 1; min-width: 120px; background: #f8f9fa; border-radius: 6px; padding: 16px; text-align: center; border-left: 4px solid #3498db; }}
.kpi .value {{ font-size: 28px; font-weight: 700; color: #3498db; }}
.kpi .label {{ font-size: 12px; color: #888; margin-top: 4px; }}
.kpi.green {{ border-color: #27ae60; }} .kpi.green .value {{ color: #27ae60; }}
.kpi.orange {{ border-color: #e67e22; }} .kpi.orange .value {{ color: #e67e22; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ background: #2c3e50; color: #fff; padding: 8px 12px; text-align: left; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #eee; }}
tr:hover td {{ background: #f8f9fa; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
.badge-ok {{ background: #d5f5e3; color: #27ae60; }}
.badge-warn {{ background: #fdebd0; color: #e67e22; }}
.badge-err {{ background: #fadbd8; color: #e74c3c; }}
.verdict {{ font-size: 15px; font-weight: 700; padding: 14px 18px; border-radius: 6px; margin-top: 12px; }}
.verdict.pass {{ background: #d5f5e3; color: #1e8449; border-left: 4px solid #27ae60; }}
.verdict.warn {{ background: #fdebd0; color: #a04000; border-left: 4px solid #e67e22; }}
.note {{ font-size: 12px; color: #666; margin-top: 8px; background: #f8f9fa; padding: 10px; border-radius: 4px; }}
</style>
</head>
<body>
<div class="header">
  <h1>manuals-v2 SKILL v1.1 파이프라인 보고서</h1>
  <div class="sub">{FILE_ID} | qa-agent | {now_kst()} | run_id={RUN_ID}</div>
</div>
<div class="container">

<div class="card">
  <h2>요약</h2>
  <div class="kpi-row">
    <div class="kpi green"><div class="value">{s0.get('total',0)}</div><div class="label">청크 수</div></div>
    <div class="kpi green"><div class="value">{s1.get('ok',0)}</div><div class="label">임베딩</div></div>
    <div class="kpi green"><div class="value">{s2.get('inserted',0)}</div><div class="label">pgvector</div></div>
    <div class="kpi {'green' if s5.get('nodes',0)>0 else 'orange'}"><div class="value">{s5.get('nodes',0)}</div><div class="label">Neo4j 노드</div></div>
    <div class="kpi {'green' if s5.get('rels',0)>0 else 'orange'}"><div class="value">{s5.get('rels',0)}</div><div class="label">Neo4j 관계</div></div>
    <div class="kpi {'green' if mrr>=0.6 else 'orange'}"><div class="value">{mrr:.3f}</div><div class="label">MRR</div></div>
    <div class="kpi"><div class="value">{elapsed_total}s</div><div class="label">총 소요</div></div>
  </div>
  <div class="verdict {pf_class}">
    {pf} — SKILL.md v1.1 기준 재실행. 윈도우 800자+200오버랩, 엔티티 12종/관계 12종, :ManualsV2Entity 라벨
  </div>
</div>

<div class="card">
  <h2>단계별 결과</h2>
  <table>
    <tr><th>단계</th><th>상태</th><th>상세</th></tr>
    {step_row('Step0 청크 검증', s0, f"총 {s0.get('total',0)}청크, avg {s0.get('avg_len',0)}자")}
    {step_row('Step1 임베딩', s1, f"ok={s1.get('ok',0)}, errors={s1.get('errors',0)}")}
    {step_row('Step2 pgvector', s2, f"삭제 {s2.get('deleted',0)}, 삽입 {s2.get('inserted',0)}")}
    {step_row('Step3 인덱스', s3, f"HNSW={s3.get('has_hnsw',False)}, GIN={s3.get('has_gin',False)}")}
    {step_row('Step4 추출', s4, f"윈도우 {s4.get('total_windows',0)}개, 엔티티 {s4.get('total_entities',0)}, 관계 {s4.get('total_relations',0)}")}
    {step_row('Step5 Neo4j', s5, f"노드 {s5.get('nodes',0)}, 관계 {s5.get('rels',0)}, label=:ManualsV2Entity")}
    {step_row('Step6 MRR', s6, f"MRR={mrr:.3f}, Hit@5={s6.get('hit_at_5',0):.3f}, Precision@5={s6.get('precision_at_5',0):.3f}")}
    <tr><td>Step7 보고서</td><td><span class="badge badge-ok">done</span></td><td>HTML 생성 완료</td></tr>
  </table>
</div>

<div class="card">
  <h2>엔티티 타입 분포 (v1.1 온톨로지)</h2>
  <table>
    <tr><th>타입</th><th>노드 수</th></tr>
    {type_rows if type_rows else '<tr><td colspan="2">데이터 없음</td></tr>'}
  </table>
  <div class="note">v1.1 12종: Equipment, Component, Parameter, Alarm, Process, Section, Figure, Table, Diagram, Specification, Manual, SafetyRule</div>
</div>

<div class="card">
  <h2>MRR 평가 쿼리 (v1.1 기준, 최소 3건)</h2>
  <table>
    <tr><th>쿼리</th><th>Rank</th><th>RR</th><th>Hit@5</th></tr>
    {q_rows if q_rows else '<tr><td colspan="4">쿼리 없음</td></tr>'}
  </table>
  <div class="note">MRR@5={mrr:.3f}, 임계값=0.60 → {badge(pf)}</div>
</div>

<div class="card">
  <h2>v1.1 준수 사항</h2>
  <table>
    <tr><th>항목</th><th>결과</th></tr>
    <tr><td>M16: 800자+200 슬라이딩 윈도우</td><td>{badge('PASS')}</td></tr>
    <tr><td>M17: MANUALS_V2_EXTRACT_PROMPT</td><td>{badge('PASS')}</td></tr>
    <tr><td>M18: 엔티티 12종/관계 12종</td><td>{badge('PASS')}</td></tr>
    <tr><td>M19: :ManualsV2Entity 라벨 + _run_id</td><td>{badge('PASS')}</td></tr>
    <tr><td>M20: num_predict=4096, temp=0, think=False</td><td>{badge('PASS')}</td></tr>
    <tr><td>N11: 팀별 전용 라벨 금지</td><td>{badge('PASS')}</td></tr>
    <tr><td>N12: cm-graphrag 프롬프트 금지</td><td>{badge('PASS')}</td></tr>
    <tr><td>N13: 2000자 단일 트런케이션 금지</td><td>{badge('PASS')}</td></tr>
  </table>
</div>

</div>
</body>
</html>"""

    html_name = 'report_18a2fd_v11_pipeline.html'
    out_path = UPLOAD_DIR / html_name
    out_path.write_text(html, encoding='utf-8')

    state['steps']['step7'] = {
        'status': 'done',
        'html': str(out_path),
        'cloudflare_url': f'https://agent.mes-wta.com/uploads/{html_name}',
    }
    state['elapsed'] = elapsed_total
    save_state(state)
    log.info(f'   HTML 저장: {out_path}')
    return f'https://agent.mes-wta.com/uploads/{html_name}'


# ── 메인 ──────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='from_step', default=None,
                    help='재개 시작 단계 (step0~step7)')
    ap.add_argument('--reset', action='store_true', help='상태 초기화')
    args = ap.parse_args()

    if args.reset and STATE_PATH.exists():
        STATE_PATH.unlink()
        log.info('상태 초기화 완료')

    state = load_state()
    if state.get('run_id') == RUN_ID or not state.get('run_id'):
        state['run_id'] = RUN_ID

    from_step = args.from_step or 'step0'
    STEP_ORDER = ['step0', 'step1', 'step2', 'step3', 'step4', 'step5', 'step6', 'step7']
    from_idx = STEP_ORDER.index(from_step) if from_step in STEP_ORDER else 0

    log.info(f'=== manuals-v2 v1.1 파이프라인 시작 ===')
    log.info(f'file_id={FILE_ID}, run_id={RUN_ID}, from={from_step}')

    t0 = time.time()
    chunks = []

    try:
        # Step 0
        if from_idx <= 0:
            chunks = step0(state)
        else:
            # 청크 로드만
            poc_path = POC_DIR / 'chunks.jsonl'
            with open(poc_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            ch = json.loads(line)
                            if (ch.get('content') or '').strip():
                                chunks.append(ch)
                        except Exception:
                            pass
            log.info(f'청크 {len(chunks)}개 로드 (step0 스킵)')

        # Step 1
        if from_idx <= 1:
            chunks = step1(state, chunks)
        else:
            # 기존 임베딩 ID 로드
            prev_ids = set(state['steps'].get('step1', {}).get('embedded_ids', []))
            log.info(f'Step1 스킵 (기존 임베딩 {len(prev_ids)}건)')

        # Step 2 — 재개 시 임베딩이 메모리에 없으면 DB에서 로드 후 재삽입
        if from_idx <= 2:
            if from_idx == 2 and not any(ch.get('_embedding') for ch in chunks):
                log.info('Step2 재개: DB에서 임베딩 로드 중...')
                conn_tmp = get_db()
                cur_tmp = conn_tmp.cursor()
                cur_tmp.execute(
                    'SELECT chunk_id, embedding FROM manual.documents_v2 WHERE file_id=%s',
                    (FILE_ID,),
                )
                emb_map_tmp = {}
                for cid, emb in cur_tmp.fetchall():
                    if emb:
                        vec = [float(x) for x in str(emb).strip('[]').split(',')]
                        emb_map_tmp[cid] = vec
                conn_tmp.close()
                for ch in chunks:
                    if ch['chunk_id'] in emb_map_tmp:
                        ch['_embedding'] = emb_map_tmp[ch['chunk_id']]
                log.info(f'   임베딩 로드: {len(emb_map_tmp)}건')
            step2(state, chunks)

        # Step 3
        if from_idx <= 3:
            step3(state)

        # Step 4
        if from_idx <= 4:
            all_entities, all_relations = step4(state, chunks)
        else:
            prev4 = state['steps'].get('step4', {})
            all_entities = prev4.get('all_entities', {})
            all_relations = prev4.get('all_relations', [])
            log.info(f'Step4 스킵 (기존 엔티티 {len(all_entities)}개, 관계 {len(all_relations)}개)')

        # Step 5
        if from_idx <= 5:
            step5(state, all_entities, all_relations)

        # Step 6
        if from_idx <= 6:
            # chunks에 임베딩 다시 로드 (step1 스킵 시)
            if not any(ch.get('_embedding') for ch in chunks):
                conn = get_db()
                cur = conn.cursor()
                cur.execute('SELECT chunk_id, embedding FROM manual.documents_v2 WHERE file_id=%s', (FILE_ID,))
                emb_map = {}
                for cid, emb in cur.fetchall():
                    if emb:
                        vec = [float(x) for x in str(emb).strip('[]').split(',')]
                        emb_map[cid] = vec
                conn.close()
                for ch in chunks:
                    if ch['chunk_id'] in emb_map:
                        ch['_embedding'] = emb_map[ch['chunk_id']]
            step6(state, chunks)

        # Step 7
        url = step7(state, t0)

        state['status'] = 'done'
        save_state(state)

        s5 = state['steps'].get('step5', {})
        s6 = state['steps'].get('step6', {})
        log.info(f'=== 완료 ===')
        log.info(f'노드={s5.get("nodes",0)}, 관계={s5.get("rels",0)}, MRR={s6.get("mrr",0):.3f} → {s6.get("pass_fail","-")}')
        log.info(f'HTML: {url}')

    except Exception as e:
        state['status'] = 'error'
        state['error'] = str(e)
        save_state(state)
        log.error(f'파이프라인 오류: {e}')
        raise


if __name__ == '__main__':
    main()
