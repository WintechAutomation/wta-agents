# -*- coding: utf-8 -*-
"""
servo_batch_pipeline.py — db-manager 서보 44건 전체 파이프라인 배치
task_id: tq-db-manager-9299cb

SKILL.md v1.1 준수:
  M1: Neo4j bolt://localhost:7688 직접 쓰기
  M2: qwen3.5:35b-a3b 엔티티 추출
  M3: qwen3-embedding:8b, 2000dim MRL 슬라이싱
  M11: HierarchicalChunker 512+64 (manuals_v2_parse_docling 위임)
  M12: Docling 파서
  M13: state.json + log 2파일 체크포인트
  M16: 800자 + 200 오버랩 윈도우
  M17: MANUALS_V2_EXTRACT_PROMPT
  M18: 엔티티12종 / 관계12종
  M19: :ManualsV2Entity:{Type}, source/run_id/file_id/_team 속성
  M20: num_predict=4096, temperature=0, think=False
  M15: Cloudflare URL 보고

체크포인트: reports/manuals-v2/state/db_manager_servo_state.json
로그:       reports/manuals-v2/state/db_manager_servo.log
"""
import sys, os, json, re, time, logging, hashlib, requests
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = __import__('io').TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ── 환경 ────────────────────────────────────────────────────────────────
KST = timezone(timedelta(hours=9))
RUN_ID = f"run-{datetime.now(KST).strftime('%Y%m%d-%H%M%S')}"
TEAM = 'db-manager'
TASK_ID = 'tq-db-manager-9299cb'

REPORTS_ROOT = Path('C:/MES/wta-agents/reports/manuals-v2')
STATE_DIR = REPORTS_ROOT / 'state'
POC_DIR = REPORTS_ROOT / 'poc'
STATE_FILE = STATE_DIR / 'db_manager_servo_state.json'
LOG_FILE = STATE_DIR / 'db_manager_servo.log'

ALLOC_FILE = REPORTS_ROOT / 'servo_batch_allocation.json'
EXTRACT_JSONL = REPORTS_ROOT / 'extract/manuals_v2_4_servo_extract.jsonl'

OLLAMA_BASE = 'http://182.224.6.147:11434'
EXTRACT_MODEL = 'qwen3.5:35b-a3b'
EMBED_MODEL = 'qwen3-embedding:8b'
EMBED_DIM = 2000

# ── .env 로드 (DB 비밀번호) ─────────────────────────────────────────────
def _load_env():
    env_path = Path('C:/MES/backend/.env')
    env = {}
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
    return env

_ENV = _load_env()

# ── Neo4j 비밀번호 ─────────────────────────────────────────────────────
def _load_neo4j_pass():
    neo4j_env = Path('C:/MES/wta-agents/workspaces/research-agent/neo4j-poc.env')
    if neo4j_env.exists():
        for line in neo4j_env.read_text(encoding='utf-8').splitlines():
            if line.startswith('NEO4J_AUTH=neo4j/'):
                return line.split('/', 1)[1].strip()
    return ''

NEO4J_PASS = _load_neo4j_pass()

# ── 로깅 ───────────────────────────────────────────────────────────────
STATE_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='[servo-batch] %(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_FILE), encoding='utf-8'),
    ]
)
log = logging.getLogger('servo-batch')

# ── v1.1 온톨로지 (M18) ────────────────────────────────────────────────
VALID_ENTITY_TYPES = {
    'Equipment', 'Component', 'Parameter', 'Alarm', 'Process', 'Section',
    'Figure', 'Table', 'Diagram', 'Specification', 'Manual', 'SafetyRule'
}
VALID_REL_TYPES = {
    'PART_OF', 'HAS_PARAMETER', 'SPECIFIES', 'CAUSES', 'RESOLVES',
    'CONNECTS_TO', 'REQUIRES', 'BELONGS_TO', 'REFERENCES', 'DEPICTS',
    'DOCUMENTS', 'WARNS'
}

# ── v1.1 추출 프롬프트 (M17, §5B-4) ────────────────────────────────────
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

# ── 윈도우 생성 (M16, §5B-3) ───────────────────────────────────────────
WINDOW_SIZE = 800
WINDOW_OVERLAP = 200
MIN_WINDOW_LEN = 50


def build_windows(chunks: list) -> list:
    full_text_parts = []
    chunk_map = []
    pos = 0
    for ch in chunks:
        content = (ch.get('content') or '').strip()
        if not content:
            continue
        chunk_map.append((pos, ch.get('chunk_id', '')))
        full_text_parts.append(content)
        pos += len(content) + 2
    full_text = '\n\n'.join(full_text_parts)

    windows = []
    start = 0
    while start < len(full_text):
        end = start + WINDOW_SIZE
        win_text = full_text[start:end]
        if len(win_text) < MIN_WINDOW_LEN:
            break
        remaining = len(full_text) - end
        if 0 < remaining < 300:
            win_text = full_text[start:end + remaining]
            end = len(full_text)
        cids = [cid for (p, cid) in chunk_map if p < end and p + 100 > start]
        windows.append({'idx': len(windows), 'text': win_text, 'chunk_ids': cids})
        start = end - WINDOW_OVERLAP
    return windows


# ── 엔티티 추출 (M17, M20) ─────────────────────────────────────────────
def extract_entities(text: str) -> dict:
    if len(text) < MIN_WINDOW_LEN:
        return {'entities': [], 'relations': []}
    prompt = MANUALS_V2_EXTRACT_PROMPT + text
    try:
        r = requests.post(
            f'{OLLAMA_BASE}/api/generate',
            json={
                'model': EXTRACT_MODEL,
                'prompt': prompt,
                'stream': False,
                'think': False,
                'options': {'num_predict': 4096, 'temperature': 0},
            },
            timeout=300,
        )
        if r.status_code == 200:
            raw = r.json().get('response', '').strip()
            raw = re.sub(r'```json\s*', '', raw)
            raw = re.sub(r'```\s*', '', raw)
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    ent_match = re.search(r'"entities"\s*:\s*\[.*?\]', raw, re.DOTALL)
                    if ent_match:
                        try:
                            return json.loads('{' + ent_match.group() + ', "relations": []}')
                        except Exception:
                            pass
    except Exception as e:
        log.warning(f'엔티티 추출 오류: {e}')
    return {'entities': [], 'relations': []}


def filter_extracted(extracted: dict, file_id: str) -> dict:
    entities = [e for e in extracted.get('entities', [])
                if e.get('type') in VALID_ENTITY_TYPES and e.get('id')]
    ent_ids = {e['id'] for e in entities}
    relations = [r for r in extracted.get('relations', [])
                 if r.get('type') in VALID_REL_TYPES
                 and r.get('source') in ent_ids
                 and r.get('target') in ent_ids]
    return {'entities': entities, 'relations': relations}


# ── 임베딩 (M3) ─────────────────────────────────────────────────────────
def embed_texts(texts: list) -> list:
    payload = {'model': EMBED_MODEL, 'input': texts}
    r = requests.post(f'{OLLAMA_BASE}/api/embed', json=payload, timeout=300)
    r.raise_for_status()
    data = r.json()
    if 'embeddings' not in data:
        raise ValueError(f'Embedding error: {data}')
    return [v[:EMBED_DIM] for v in data['embeddings']]


# ── pgvector 적재 (Step 5A) ─────────────────────────────────────────────
def load_pgvector(chunks: list, file_id: str, meta: dict) -> int:
    import psycopg2
    conn = psycopg2.connect(
        host=_ENV.get('DB_HOST', 'localhost'),
        port=int(_ENV.get('DB_PORT', '55432')),
        dbname=_ENV.get('DB_NAME', 'wta'),
        user=_ENV.get('DB_USER', 'postgres'),
        password=_ENV.get('DB_PASSWORD', '')
    )
    conn.autocommit = True
    cur = conn.cursor()

    inserted = 0
    for ch in chunks:
        emb = ch.get('embedding')
        if not emb:
            continue
        emb_slice = emb[:EMBED_DIM] if len(emb) > EMBED_DIM else emb
        try:
            cur.execute("""
                INSERT INTO manual.documents_v2
                    (file_id, chunk_id, category, mfr, model, doctype, lang,
                     section_path, page_start, page_end, content, tokens,
                     source_hash, embedding, figure_refs, table_refs, inline_refs)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector,%s,%s,%s)
                ON CONFLICT (file_id, chunk_id) DO UPDATE SET
                    content=EXCLUDED.content, embedding=EXCLUDED.embedding,
                    tokens=EXCLUDED.tokens
            """, (
                file_id, ch.get('chunk_id', ''),
                meta.get('category', '4_servo'),
                meta.get('mfr', ''), meta.get('model', ''),
                meta.get('doctype', ''), meta.get('lang', ''),
                json.dumps(ch.get('section_path', []), ensure_ascii=False),
                ch.get('page_start'), ch.get('page_end'),
                ch.get('content', ''), ch.get('tokens', 0),
                ch.get('source_hash', ''),
                str(emb_slice),
                json.dumps(ch.get('figure_refs', []), ensure_ascii=False),
                json.dumps(ch.get('table_refs', []), ensure_ascii=False),
                json.dumps(ch.get('inline_refs', []), ensure_ascii=False),
            ))
            inserted += 1
        except Exception as e:
            log.warning(f'pgvector 적재 오류 {ch.get("chunk_id")}: {e}')

    cur.close()
    conn.close()
    return inserted


# ── Neo4j 적재 (M19, §5B-1) ─────────────────────────────────────────────
def load_to_neo4j(driver, extracted: dict, file_id: str) -> tuple:
    entities = extracted.get('entities', [])
    relations = extracted.get('relations', [])
    if not entities:
        return 0, 0

    id_map = {}
    node_count, rel_count = 0, 0

    with driver.session() as s:
        for ent in entities:
            ent_type = ent.get('type', '')
            orig_id = ent.get('id', '')
            if not orig_id or ent_type not in VALID_ENTITY_TYPES:
                continue
            safe_id = f"mv2_{file_id}_{re.sub(r'[^a-zA-Z0-9_]', '_', orig_id)}"
            id_map[orig_id] = safe_id
            props = {k: v for k, v in (ent.get('properties') or {}).items()
                     if v is not None and v != ''}
            props.update({
                '_id': safe_id, 'source': 'manuals_v2',
                '_run_id': RUN_ID, '_file_id': file_id, '_team': TEAM,
            })
            try:
                s.run(
                    f"MERGE (n:ManualsV2Entity:{ent_type} {{_id: $_id}}) "
                    f"SET n += $props, n.name = $name",
                    _id=safe_id, props=props, name=ent.get('name', orig_id)
                )
                node_count += 1
            except Exception as e:
                log.debug(f'노드 오류: {e}')

        for rel in relations:
            src = id_map.get(rel.get('source', ''))
            tgt = id_map.get(rel.get('target', ''))
            rtype = rel.get('type', '')
            if not src or not tgt or rtype not in VALID_REL_TYPES:
                continue
            try:
                s.run(
                    f"MATCH (a:ManualsV2Entity {{_id: $src}}), (b:ManualsV2Entity {{_id: $tgt}}) "
                    f"MERGE (a)-[r:{rtype}]->(b)",
                    src=src, tgt=tgt
                )
                rel_count += 1
            except Exception as e:
                log.debug(f'관계 오류: {e}')

    return node_count, rel_count


# ── 체크포인트 (M13) ────────────────────────────────────────────────────
def now_kst():
    return datetime.now(KST).strftime('%Y-%m-%dT%H:%M:%S+09:00')


def load_state(file_list: list) -> dict:
    if STATE_FILE.exists():
        st = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        # items 동기화: 새 파일 추가
        existing_ids = {item['file_id'] for item in st.get('items', [])}
        for f in file_list:
            if f['file_id'] not in existing_ids:
                st['items'].append({
                    'file_id': f['file_id'], 'filename': f['filename'],
                    'mfr': f['mfr'], 'model': f['model'], 'pages': f.get('pages', 0),
                    'step2': 'pending', 'embed': 'pending',
                    'pgvector': 'pending', 'graphrag': 'pending',
                    'status': 'pending', 'chunks': 0, 'nodes': 0, 'rels': 0,
                })
        return st
    return {
        'task_id': TASK_ID,
        'run_id': RUN_ID,
        'status': 'running',
        'total': len(file_list),
        'completed': 0,
        'failed': 0,
        'current': None,
        'last_update': now_kst(),
        'items': [
            {
                'file_id': f['file_id'],            # poc 디렉토리용 (md5[:12])
                'file_id_alloc': f.get('file_id_alloc', f['file_id']),  # 할당 추적용
                'filename': f['filename'],
                'mfr': f['mfr'], 'model': f['model'], 'pages': f.get('pages', 0),
                'step2': 'pending', 'embed': 'pending',
                'pgvector': 'pending', 'graphrag': 'pending',
                'status': 'pending', 'chunks': 0, 'nodes': 0, 'rels': 0,
            }
            for f in file_list
        ],
    }


def save_state(state: dict):
    state['last_update'] = now_kst()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


# ── 파일 목록 준비 ──────────────────────────────────────────────────────
def build_file_list() -> list:
    with open(ALLOC_FILE, encoding='utf-8') as f:
        alloc = json.load(f)
    my_files = alloc['teams']['db-manager']['files']
    my_md5s = {f['md5']: f for f in my_files}

    # extract.jsonl에서 src_path 매핑 (중복 file_id 시 첫 번째만)
    # 주의: parse_docling은 file_id = f'{category}_{md5[:12]}' 를 사용.
    # 할당 파일의 file_id (전체 md5)와 다르므로 별도 보관.
    mapping = {}
    with open(EXTRACT_JSONL, encoding='utf-8') as f:
        for line in f:
            rec = json.loads(line)
            md5 = rec.get('md5')
            if md5 in my_md5s and rec.get('status') == 'ok':
                af = my_md5s[md5]
                fid_alloc = af['file_id']        # 전체 md5 file_id
                fid_poc = f'4_servo_{md5[:12]}'  # parse_docling이 생성하는 실제 file_id
                if fid_alloc not in mapping:
                    mapping[fid_alloc] = {
                        'file_id': fid_poc,      # poc 디렉토리 및 DB 적재에 사용
                        'file_id_alloc': fid_alloc,  # 할당 추적용
                        'src_path': rec.get('src_path', ''),
                        'filename': rec.get('filename', ''),
                        'mfr': af.get('mfr', ''),
                        'model': af.get('model', ''),
                        'doctype': af.get('doctype', ''),
                        'lang': af.get('lang', ''),
                        'pages': int(af.get('pages', 0)),
                        'md5': md5,
                        'category': '4_servo',
                    }

    # 할당 순서 유지
    result = []
    for f in my_files:
        fid_alloc = f['file_id']
        if fid_alloc in mapping:
            result.append(mapping[fid_alloc])
        else:
            log.warning(f'src_path 없음: {fid_alloc}')

    return result


# ── Step 2: Docling 파싱 ─────────────────────────────────────────────────
def run_step2(file_info: dict) -> bool:
    """subprocess로 manuals_v2_parse_docling.py 호출, poc/{file_id}/ 생성"""
    import subprocess
    poc_dir = POC_DIR / file_info['file_id']
    chunks_path = poc_dir / 'chunks.jsonl'
    if chunks_path.exists():
        log.info(f"Step2 이미 완료: {file_info['file_id']}")
        return True

    PY = r'C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe'
    script = r'C:\MES\wta-agents\workspaces\docs-agent\manuals_v2_parse_docling.py'
    src_path = file_info['src_path']

    try:
        result = subprocess.run(
            [PY, script, src_path],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=1800  # 30분
        )
        if result.returncode == 0 or chunks_path.exists():
            log.info(f"Step2 완료: {file_info['file_id']}")
            return True
        else:
            log.warning(f"Step2 실패(rc={result.returncode}): {result.stderr[-300:]}")
            return False
    except subprocess.TimeoutExpired:
        log.warning(f"Step2 타임아웃(30분): {file_info['file_id']}")
        return chunks_path.exists()
    except Exception as e:
        log.error(f"Step2 예외: {file_info['file_id']} → {e}")
        return False


# ── Step 4: 임베딩 ──────────────────────────────────────────────────────
def run_embed(file_info: dict) -> list:
    """chunks.jsonl 읽고 임베딩 추가, 결과 반환"""
    chunks_path = POC_DIR / file_info['file_id'] / 'chunks.jsonl'
    if not chunks_path.exists():
        log.error(f'chunks.jsonl 없음: {file_info["file_id"]}')
        return []

    chunks = []
    with open(chunks_path, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))

    if not chunks:
        return []

    BATCH = 16
    embedded = []
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i+BATCH]
        texts = [c.get('content', '') for c in batch]
        try:
            vecs = embed_texts(texts)
            for c, v in zip(batch, vecs):
                c['embedding'] = v
            embedded.extend(batch)
        except Exception as e:
            log.warning(f'임베딩 오류 배치 {i}: {e}')
            embedded.extend(batch)  # embedding 없이 추가
        time.sleep(0.2)

    return embedded


# ── Step 5B: GraphRAG ───────────────────────────────────────────────────
def run_graphrag(chunks: list, file_info: dict, driver) -> tuple:
    windows = build_windows(chunks)
    total_nodes, total_rels = 0, 0
    for win in windows:
        extracted = extract_entities(win['text'])
        filtered = filter_extracted(extracted, file_info['file_id'])
        n, r = load_to_neo4j(driver, filtered, file_info['file_id'])
        total_nodes += n
        total_rels += r
    return total_nodes, total_rels


# ── 메인 ────────────────────────────────────────────────────────────────
def main():
    import subprocess

    log.info(f'=== 서보 배치 파이프라인 시작 | run_id={RUN_ID} ===')

    file_list = build_file_list()
    log.info(f'처리 대상: {len(file_list)}건')

    state = load_state(file_list)
    save_state(state)

    # Neo4j 연결
    try:
        from neo4j import GraphDatabase
        neo4j_driver = GraphDatabase.driver(
            'bolt://localhost:7688',
            auth=('neo4j', NEO4J_PASS)
        )
        neo4j_driver.verify_connectivity()
        log.info('Neo4j 연결 성공')
    except Exception as e:
        log.error(f'Neo4j 연결 실패: {e}')
        neo4j_driver = None

    completed_total = sum(1 for it in state['items'] if it['status'] == 'done')

    for item in state['items']:
        if item['status'] == 'done':
            log.info(f"[SKIP] {item['file_id']} (이미 완료)")
            continue

        file_info = next((f for f in file_list if f['file_id'] == item['file_id']), None)
        if not file_info:
            log.warning(f"파일 정보 없음: {item['file_id']}")
            item['status'] = 'failed'
            state['failed'] += 1
            save_state(state)
            continue

        state['current'] = item['file_id']
        save_state(state)
        log.info(f"\n[{completed_total+1}/{state['total']}] {item['file_id']} | {item['mfr']} {item['model']} | {item['pages']}p")

        try:
            # Step 2: Docling 파싱
            if item['step2'] != 'done':
                log.info(f'  Step2: Docling 파싱...')
                ok = run_step2(file_info)
                item['step2'] = 'done' if ok else 'failed'
                save_state(state)
                if not ok:
                    item['status'] = 'failed'
                    state['failed'] += 1
                    save_state(state)
                    continue

            # Step 4: 임베딩
            chunks = []
            if item['embed'] != 'done':
                log.info(f'  Step4: 임베딩...')
                chunks = run_embed(file_info)
                item['chunks'] = len(chunks)
                item['embed'] = 'done' if chunks else 'failed'
                save_state(state)
            else:
                # 이미 임베딩 완료 — chunks.jsonl 재로드 (pgvector/graphrag 재처리 위해)
                chunks_path = POC_DIR / file_info['file_id'] / 'chunks.jsonl'
                if chunks_path.exists():
                    with open(chunks_path, encoding='utf-8') as f:
                        chunks = [json.loads(line) for line in f if line.strip()]

            if not chunks:
                item['status'] = 'failed'
                state['failed'] += 1
                save_state(state)
                continue

            # Step 5A: pgvector 적재
            if item['pgvector'] != 'done':
                log.info(f'  Step5A: pgvector 적재 ({len(chunks)}청크)...')
                n_inserted = load_pgvector(chunks, file_info['file_id'], file_info)
                log.info(f'  적재: {n_inserted}건')
                item['pgvector'] = 'done'
                save_state(state)

            # Step 5B: GraphRAG
            if item['graphrag'] != 'done' and neo4j_driver:
                log.info(f'  Step5B: GraphRAG 엔티티 추출...')
                nodes, rels = run_graphrag(chunks, file_info, neo4j_driver)
                log.info(f'  노드: {nodes}, 관계: {rels}')
                item['nodes'] = nodes
                item['rels'] = rels
                item['graphrag'] = 'done'
                save_state(state)
            elif not neo4j_driver:
                log.warning(f'  Step5B: Neo4j 미연결, 건너뜀')
                item['graphrag'] = 'skip'

            item['status'] = 'done'
            state['completed'] += 1
            completed_total += 1
            save_state(state)
            log.info(f'  완료 [{completed_total}/{state["total"]}]')

        except Exception as e:
            log.error(f'처리 오류 {item["file_id"]}: {e}')
            import traceback; traceback.print_exc()
            item['status'] = 'failed'
            state['failed'] += 1
            save_state(state)

        # 10건마다 중간 보고 (send_message MCP 미사용 — 대신 파일에 기록)
        if completed_total > 0 and completed_total % 10 == 0:
            log.info(f'=== 중간 체크포인트: {completed_total}/{state["total"]} 완료 ===')
            # 보고 파일 기록 (메인 프로세스가 확인)
            report_path = STATE_DIR / 'db_manager_servo_progress.json'
            report_path.write_text(json.dumps({
                'completed': completed_total,
                'total': state['total'],
                'failed': state['failed'],
                'timestamp': now_kst(),
            }, ensure_ascii=False), encoding='utf-8')

    # 완료
    state['status'] = 'done' if state['failed'] == 0 else 'partial'
    state['current'] = None
    save_state(state)

    log.info(f'\n=== 배치 완료: {state["completed"]}/{state["total"]} 성공, {state["failed"]} 실패 ===')
    if neo4j_driver:
        neo4j_driver.close()


if __name__ == '__main__':
    main()
