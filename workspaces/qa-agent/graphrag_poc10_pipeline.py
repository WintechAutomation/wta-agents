"""
manuals-v2 PoC10 GraphRAG 파이프라인 - qa-agent 독립 구현
레이블: ManualsV2_PoC10_QA (스킬 M10)
LLM: qwen3.5:35b-a3b / 엔티티 10타입+11관계 / 윈도우 2000자
체크포인트: reports/manuals-v2/work/graphrag_poc10_qa_state.json
"""

import json, re, sys, time, logging, argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests

# ── 경로 상수 ──────────────────────────────────────────────────────
POC_ROOT     = Path(r'C:\MES\wta-agents\reports\manuals-v2\poc')
WORK_DIR     = Path(r'C:\MES\wta-agents\reports\manuals-v2\work')
STATE_PATH   = WORK_DIR / 'graphrag_poc10_qa_state.json'
LOG_PATH     = WORK_DIR / 'graphrag_poc10_qa.log'
NEO4J_ENV    = Path(r'C:\MES\wta-agents\workspaces\research-agent\neo4j-poc.env')

OLLAMA_BASE  = 'http://182.224.6.147:11434'
EXTRACT_MODEL= 'qwen3.5:35b-a3b'

RUN_ID       = datetime.now(timezone(timedelta(hours=9))).strftime('%Y%m%d_%H%M%S')
CORPUS       = 'manuals_v2'
TEAM         = 'qa-agent'
LABEL_MAIN   = 'ManualsV2Entity'
LABEL_RUN    = 'ManualsV2_PoC10_QA'
WINDOW_SIZE  = 2000   # 자

# PoC 10 확정 file_id
POC10_FILE_IDS = [
    '1_robot_0b0c3108c6c9',
    '1_robot_2d70fa79608e',
    '1_robot_2d77a92d4066',
    '1_robot_314928a33268',
    '1_robot_3c1dcc39da41',
    '1_robot_54fdb56329f0',
    '1_robot_c5a220711bc5',
    '1_robot_c7fe37c1ed98',
    '2_sensor_2e6136a51564',
    '5_inverter_c6f52f93cca5',
]

# ── 엔티티/관계 스키마 (10타입 / 11관계) ───────────────────────────
VALID_NODE_TYPES = {
    'Equipment',     # 장비/기기 (로봇, 인버터, 센서 등)
    'Component',     # 부품/구성요소
    'Parameter',     # 파라미터/설정값
    'Alarm',         # 알람/에러코드
    'Process',       # 절차/공정/작업
    'Section',       # 문서 섹션/챕터
    'Figure',        # 그림/다이어그램
    'Table',         # 표
    'Specification', # 사양/규격
    'Manual',        # 매뉴얼 문서
}

VALID_REL_TYPES = {
    'BELONGS_TO',    # Figure/Table → Section
    'REFERENCES',    # Chunk/Section → Figure/Table
    'DEPICTS',       # Figure → Equipment/Component
    'HAS_PARAMETER', # Equipment → Parameter
    'CAUSES',        # Alarm → Process (원인-절차)
    'RESOLVES',      # Process → Alarm
    'CONNECTS_TO',   # Equipment → Equipment/Component
    'REQUIRES',      # Process → Component/Equipment
    'SPECIFIES',     # Specification → Equipment/Component/Parameter
    'PART_OF',       # Component → Equipment
    'DOCUMENTS',     # Manual → Equipment/Process
}

# ── 로깅 ──────────────────────────────────────────────────────────
WORK_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='[poc10-qa] %(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_PATH), encoding='utf-8'),
    ],
)
log = logging.getLogger('poc10-qa')


# ── KST 타임스탬프 ─────────────────────────────────────────────────
def kst_now() -> str:
    return datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')


# ── 체크포인트 ─────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding='utf-8'))
        except Exception as e:
            log.warning(f'state.json 로드 실패 (새로 시작): {e}')
    return {'task_id': 'graphrag_poc10_qa', 'run_id': RUN_ID,
            'status': 'in_progress', 'total': len(POC10_FILE_IDS),
            'completed': 0, 'current': '', 'items': {}, 'last_update': kst_now()}


def save_state(state: dict):
    state['last_update'] = kst_now()
    tmp = STATE_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(STATE_PATH)


# ── Neo4j 연결 ─────────────────────────────────────────────────────
def get_neo4j_driver():
    pwd = ''
    for line in NEO4J_ENV.read_text(encoding='utf-8').splitlines():
        if line.startswith('NEO4J_AUTH=neo4j/'):
            pwd = line.split('/', 1)[1].strip()
            break
    from neo4j import GraphDatabase
    return GraphDatabase.driver('bolt://localhost:7688', auth=('neo4j', pwd))


# ── 청크 윈도잉 (2000자 묶음) ──────────────────────────────────────
def build_windows(chunks: list[dict]) -> list[dict]:
    """chunks 리스트를 2000자 단위로 묶어 윈도우 텍스트 생성"""
    windows = []
    buf, buf_ids, buf_lang = [], [], 'ko'
    buf_len = 0

    for ch in chunks:
        content = (ch.get('content') or '').strip()
        if not content:
            continue
        buf.append(content)
        buf_ids.append(ch.get('chunk_id', ''))
        buf_lang = ch.get('lang', 'ko') or 'ko'
        buf_len += len(content)

        if buf_len >= WINDOW_SIZE:
            windows.append({
                'text': '\n'.join(buf),
                'chunk_ids': buf_ids[:],
                'lang': buf_lang,
            })
            buf, buf_ids, buf_len = [], [], 0

    if buf:
        windows.append({'text': '\n'.join(buf), 'chunk_ids': buf_ids, 'lang': buf_lang})

    return windows


# ── 엔티티 추출 프롬프트 ───────────────────────────────────────────
EXTRACT_PROMPT = """다음 산업 매뉴얼 텍스트에서 엔티티와 관계를 추출하세요.

엔티티 타입:
- Equipment: 장비/기기 (로봇, 인버터, 서보, 센서 등)
- Component: 부품/구성요소 (모터, 단자, 퓨즈, 엔코더 등)
- Parameter: 파라미터/설정값 (C1-01, H4-02 등 파라미터 코드 포함)
- Alarm: 알람/에러코드 (oC, AL.16, E401 등)
- Process: 절차/작업/공정 (배선, 설치, 점검, 튜닝 등)
- Section: 문서 섹션/챕터 (제목 단위)
- Figure: 그림/다이어그램 (배선도, 회로도 등)
- Table: 표 (파라미터 표, 사양 표 등)
- Specification: 사양/규격 (전압, 전류, 토크 등 수치)
- Manual: 매뉴얼 문서

관계 타입:
- BELONGS_TO: Figure/Table이 Section에 속함
- REFERENCES: Section이 Figure/Table을 참조
- DEPICTS: Figure가 Equipment/Component를 나타냄
- HAS_PARAMETER: Equipment가 Parameter를 가짐
- CAUSES: Alarm이 Process를 유발 (원인-복구 절차)
- RESOLVES: Process가 Alarm을 해결
- CONNECTS_TO: Equipment/Component 간 연결
- REQUIRES: Process가 Component/Equipment를 필요로 함
- SPECIFIES: Specification이 Equipment/Component/Parameter를 규정
- PART_OF: Component가 Equipment의 부품
- DOCUMENTS: Manual이 Equipment/Process를 기술

JSON 형식으로만 응답하세요 (다른 텍스트 없이):
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


def extract_entities(text: str, source_id: str, lang: str) -> dict:
    if len(text.strip()) < 30:
        return {'entities': [], 'relations': []}
    prompt = EXTRACT_PROMPT + f"[출처: {source_id}, 언어: {lang}]\n\n{text}"
    try:
        r = requests.post(
            f'{OLLAMA_BASE}/api/generate',
            json={
                'model': EXTRACT_MODEL,
                'prompt': prompt,
                'stream': False,
                'options': {'num_predict': 800, 'temperature': 0},
            },
            timeout=120,
        )
        if r.status_code == 200:
            raw = r.json().get('response', '').strip()
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                return json.loads(m.group())
    except Exception as e:
        log.warning(f'엔티티 추출 오류 [{source_id}]: {e}')
    return {'entities': [], 'relations': []}


# ── Neo4j 적재 ─────────────────────────────────────────────────────
def load_to_neo4j(driver, file_id: str, window_idx: int,
                  extracted: dict, chunk_ids: list[str], lang: str) -> tuple[int, int]:
    entities = extracted.get('entities', [])
    relations = extracted.get('relations', [])
    if not entities:
        return 0, 0

    id_map: dict[str, str] = {}
    node_count = rel_count = 0
    source_id = f"{file_id}_w{window_idx:04d}"

    with driver.session() as s:
        for ent in entities:
            ent_type = ent.get('type', '')
            if ent_type not in VALID_NODE_TYPES:
                continue
            orig_id = ent.get('id', '')
            if not orig_id:
                continue
            safe_id = f"mv2_{file_id}_{re.sub(r'[^a-zA-Z0-9_]', '_', orig_id)}"
            id_map[orig_id] = safe_id

            props = {k: v for k, v in (ent.get('properties') or {}).items()
                     if v is not None and v != ''}
            props.update({
                '_id':        safe_id,
                '_source_id': source_id,
                '_run_id':    RUN_ID,
                '_corpus':    CORPUS,
                '_lang':      lang,
                '_team':      TEAM,
                '_file_id':   file_id,
                '_chunk_ids': json.dumps(chunk_ids),
            })
            try:
                s.run(
                    f"MERGE (n:{LABEL_MAIN}:{LABEL_RUN}:{ent_type} {{_id: $_id}}) "
                    f"SET n += $props, n.name = $name",
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
                    f"MATCH (a:{LABEL_MAIN} {{_id: $src}}), (b:{LABEL_MAIN} {{_id: $tgt}}) "
                    f"MERGE (a)-[r:{rtype}]->(b) "
                    f"ON CREATE SET r._run_id=$run_id, r._corpus=$corpus",
                    src=src, tgt=tgt, run_id=RUN_ID, corpus=CORPUS,
                )
                rel_count += 1
            except Exception as e:
                log.debug(f'관계 생성 오류: {e}')

    return node_count, rel_count


# ── 단일 file_id 처리 ──────────────────────────────────────────────
def process_file(driver, file_id: str, state: dict, args) -> dict:
    chunks_path = POC_ROOT / file_id / 'chunks.jsonl'
    if not chunks_path.exists():
        log.warning(f'[{file_id}] chunks.jsonl 없음 - 스킵')
        return {'status': 'skipped', 'reason': 'no chunks.jsonl'}

    chunks = []
    with open(chunks_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    if not chunks:
        return {'status': 'skipped', 'reason': 'empty chunks'}

    lang = chunks[0].get('lang', 'ko') or 'ko'
    windows = build_windows(chunks)
    log.info(f'  [{file_id}] 청크={len(chunks)}, 윈도우={len(windows)}, lang={lang}')

    total_nodes = total_rels = 0
    win_done = state.get('items', {}).get(file_id, {}).get('windows_done', 0)

    for idx, win in enumerate(windows):
        if idx < win_done:
            continue  # 재개 시 완료된 윈도우 스킵

        extracted = extract_entities(win['text'], f"{file_id}_w{idx:04d}", lang)
        nodes, rels = load_to_neo4j(driver, file_id, idx,
                                    extracted, win['chunk_ids'], lang)
        total_nodes += nodes
        total_rels  += rels
        win_done = idx + 1

        # 윈도우 단위 중간 저장
        state['items'].setdefault(file_id, {})['windows_done'] = win_done
        save_state(state)
        log.info(f'    w{idx:04d} ents={nodes} rels={rels}')

        if args.dry_run:
            log.info('  --dry-run: 첫 윈도우만 처리')
            break

    return {
        'status':       'done',
        'chunks':       len(chunks),
        'windows':      len(windows),
        'total_nodes':  total_nodes,
        'total_rels':   total_rels,
        'lang':         lang,
    }


# ── 메인 ───────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file-id',   help='단일 file_id만 처리')
    ap.add_argument('--dry-run',   action='store_true', help='첫 윈도우만 처리 (검증용)')
    ap.add_argument('--retry-error', action='store_true', help='error 상태 재시도')
    args = ap.parse_args()

    state = load_state()
    state['run_id'] = RUN_ID
    save_state(state)

    targets = [args.file_id] if args.file_id else POC10_FILE_IDS

    log.info(f'=== GraphRAG PoC10 QA 시작 - 대상 {len(targets)}건, run_id={RUN_ID} ===')

    try:
        driver = get_neo4j_driver()
    except Exception as e:
        log.error(f'Neo4j 연결 실패: {e}')
        sys.exit(1)

    total_nodes = total_rels = ok_count = err_count = 0
    t0 = time.time()

    for fid in targets:
        prev = state['items'].get(fid, {})
        if prev.get('status') == 'done' and not args.retry_error:
            log.info(f'[{fid}] 이미 완료 - 스킵')
            state['completed'] += 0  # 이미 집계됨
            continue
        if prev.get('status') == 'error' and not args.retry_error:
            log.info(f'[{fid}] 이전 error - 스킵 (--retry-error 로 재시도)')
            continue

        state['current'] = fid
        save_state(state)
        log.info(f'>> [{fid}]')
        t1 = time.time()

        try:
            result = process_file(driver, fid, state, args)
            result['elapsed'] = round(time.time() - t1, 1)
            state['items'][fid] = result
            if result['status'] == 'done':
                ok_count += 1
                state['completed'] = ok_count
                total_nodes += result.get('total_nodes', 0)
                total_rels  += result.get('total_rels', 0)
                log.info(f'   OK nodes={result["total_nodes"]} rels={result["total_rels"]} elapsed={result["elapsed"]}s')
            else:
                log.info(f'   SKIP reason={result.get("reason")}')
        except Exception as e:
            err_count += 1
            state['items'][fid] = {'status': 'error', 'error': str(e)}
            log.error(f'   ERR {fid}: {e}')

        save_state(state)

    elapsed_total = round(time.time() - t0, 1)
    state['status'] = 'done'
    state['summary'] = {
        'ok': ok_count, 'error': err_count,
        'total_nodes': total_nodes, 'total_rels': total_rels,
        'elapsed_s': elapsed_total,
    }
    save_state(state)
    driver.close()

    log.info(f'=== 완료 - ok={ok_count} err={err_count} nodes={total_nodes} rels={total_rels} elapsed={elapsed_total}s ===')


if __name__ == '__main__':
    main()
