"""
manuals-v2 PoC10 GraphRAG 교차검증 파이프라인
cm-graphrag-pipeline.py (workspaces/db-manager/) 방식 그대로 재현.
레이블만 Phase4_CM -> ManualsV2_PoC10_QA 로 변경, 나머지 전부 원본 동일.

실행:
  python graphrag_poc10_pipeline.py          # 전체
  python graphrag_poc10_pipeline.py --test 3 # 처음 3건
  python graphrag_poc10_pipeline.py --only 1_robot_c7fe37c1ed98
"""
import sys, json, re, time, logging, argparse
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── 설정 (cm-graphrag-pipeline.py 동일) ────────────────────────────
POC_ROOT     = Path(r'C:\MES\wta-agents\reports\manuals-v2\poc')
WORK_DIR     = Path(r'C:\MES\wta-agents\reports\manuals-v2\work')
STATE_PATH   = WORK_DIR / 'graphrag_poc10_qa_state.json'
LOG_PATH     = WORK_DIR / 'graphrag_poc10_qa.log'
NEO4J_ENV    = Path(r'C:\MES\wta-agents\workspaces\research-agent\neo4j-poc.env')

OLLAMA_BASE   = 'http://182.224.6.147:11434'
EXTRACT_MODEL = 'qwen3.5:35b-a3b'   # cm-graphrag 동일

# PoC 10 확정 file_id 목록
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

# ── 스키마 (cm-graphrag-pipeline.py 와 동일한 타입 세트) ─────────────
VALID_NODE_TYPES = {
    'Customer', 'Equipment', 'Product', 'Component', 'Process',
    'Issue', 'Resolution', 'Person', 'Tool', 'Manual',
}
VALID_REL_TYPES = {
    'OWNS', 'HAS_ISSUE', 'SIMILAR_TO', 'RESOLVED_BY',
    'INVOLVES_COMPONENT', 'USES_COMPONENT', 'INVOLVED_IN',
    'HAS_SUBPROCESS', 'USES_TOOL', 'MAINTAINS', 'DOCUMENTS',
}

# Neo4j 레이블 (원본 Phase4_CM -> 교차검증용)
NEO4J_LABEL = 'ManualsV2_PoC10_QA'

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


# ── Neo4j 연결 ─────────────────────────────────────────────────────
def get_neo4j_driver():
    pwd = ''
    for line in NEO4J_ENV.read_text(encoding='utf-8').splitlines():
        if line.startswith('NEO4J_AUTH=neo4j/'):
            pwd = line.split('/', 1)[1].strip()
            break
    from neo4j import GraphDatabase
    return GraphDatabase.driver('bolt://localhost:7688', auth=('neo4j', pwd))


# ── 체크포인트 ─────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'completed': [], 'failed': []}


def save_state(state: dict):
    tmp = STATE_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(STATE_PATH)


# ── 엔티티/관계 추출 (cm-graphrag-pipeline.py 프롬프트/파라미터 동일) ──
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
    """LLM으로 엔티티/관계 추출 (cm-graphrag-pipeline.py 동일)"""
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
                'think': False,   # qwen3.5:35b-a3b 모델 호환성 픽스 (thinking 모드 비활성화)
                'stream': False,
                'options': {'num_predict': 2000, 'temperature': 0.1},
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


# ── Neo4j 적재 (cm-graphrag-pipeline.py 동일, 레이블만 변경) ──────────
def load_to_neo4j(driver, file_id: str, extracted: dict) -> tuple[int, int]:
    """ManualsV2_PoC10_QA 레이블로 Neo4j 병합 적재"""
    entities = extracted.get('entities', [])
    relations = extracted.get('relations', [])
    if not entities:
        return 0, 0

    id_map: dict[str, str] = {}
    node_count = rel_count = 0

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
            props.update({'_id': safe_id, '_file_id': file_id, '_corpus': 'manuals_v2'})
            try:
                s.run(
                    f"MERGE (n:{NEO4J_LABEL}:{ent_type} {{_id: $_id}}) "
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
                    f"MATCH (a:{NEO4J_LABEL} {{_id: $src}}), (b:{NEO4J_LABEL} {{_id: $tgt}}) "
                    f"MERGE (a)-[r:{rtype}]->(b)",
                    src=src, tgt=tgt,
                )
                rel_count += 1
            except Exception as e:
                log.debug(f'관계 생성 오류: {e}')

    return node_count, rel_count


# ── 메인 ───────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--test', type=int, default=0, help='처음 N건만')
    ap.add_argument('--only', nargs='+', help='특정 file_id만')
    ap.add_argument('--retry', action='store_true', help='실패 재시도')
    args = ap.parse_args()

    state = load_state()
    done_set  = set(state.get('completed', []))
    failed_set = set(state.get('failed', []))

    targets = args.only if args.only else POC10_FILE_IDS
    if args.test > 0:
        targets = targets[:args.test]
        log.info(f'테스트 모드: {len(targets)}건')

    log.info(f'=== GraphRAG PoC10 교차검증 시작 - 대상 {len(targets)}건 ===')
    log.info(f'이미 완료: {len(done_set)}건 / 실패: {len(failed_set)}건')

    try:
        driver = get_neo4j_driver()
        driver.verify_connectivity()
        log.info('Neo4j 연결 완료')
    except Exception as e:
        log.error(f'Neo4j 연결 실패: {e}')
        raise

    total_nodes = total_rels = ok_count = err_count = 0
    t0 = time.time()

    for i, fid in enumerate(targets):
        if fid in done_set and not args.retry:
            log.info(f'[{i+1}/{len(targets)}] {fid} - 이미 완료, 스킵')
            ok_count += 1
            continue
        if fid in failed_set and not args.retry:
            log.info(f'[{i+1}/{len(targets)}] {fid} - 이전 실패, 스킵 (--retry)')
            err_count += 1
            continue

        chunks_path = POC_ROOT / fid / 'chunks.jsonl'
        if not chunks_path.exists():
            log.warning(f'[{i+1}/{len(targets)}] {fid} - chunks.jsonl 없음')
            err_count += 1
            state.setdefault('failed', []).append(fid)
            save_state(state)
            continue

        # 청크 전문 결합 (cm-graphrag의 page_text 에 해당)
        lines = []
        with open(chunks_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        ch = json.loads(line)
                        content = (ch.get('content') or '').strip()
                        if content:
                            lines.append(content)
                    except Exception:
                        pass
        full_text = '\n'.join(lines)

        log.info(f'[{i+1}/{len(targets)}] {fid} - 청크 {len(lines)}개, 텍스트 {len(full_text)}자')
        t1 = time.time()

        try:
            extracted = extract_entities(full_text, fid)
            nodes, rels = load_to_neo4j(driver, fid, extracted)
            total_nodes += nodes
            total_rels  += rels
            ok_count += 1
            state.setdefault('completed', []).append(fid)
            elapsed = round(time.time() - t1, 1)
            log.info(f'   OK nodes={nodes} rels={rels} elapsed={elapsed}s')
        except Exception as e:
            err_count += 1
            state.setdefault('failed', []).append(fid)
            log.error(f'   ERR {fid}: {e}')

        save_state(state)

    driver.close()
    elapsed_total = round(time.time() - t0, 1)
    log.info(f'=== 완료 - ok={ok_count} err={err_count} '
             f'nodes={total_nodes} rels={total_rels} elapsed={elapsed_total}s ===')


if __name__ == '__main__':
    main()
