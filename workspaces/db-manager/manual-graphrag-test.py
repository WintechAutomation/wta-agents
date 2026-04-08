"""
매뉴얼 GraphRAG 파이프라인 — 테스트 (50개 PDF)
소스: C:/MES/wta-agents/data/manuals (8개 카테고리)
단계:
  1. PDF 파싱 (pymupdf: 텍스트 + 이미지 추출)
  2. 이미지 분석 (qwen3-vl:8b 비전 모델)
  3. 엔티티/관계 추출 (qwen3.5:35b-a3b)
  4. Neo4j 적재 (Phase5_Manual 라벨)
실행:
  python manual-graphrag-test.py
"""
import sys, os, json, re, time, logging, base64
from pathlib import Path
from datetime import datetime, timezone, timedelta

import fitz  # pymupdf
import requests
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

KST = timezone(timedelta(hours=9))

# ── 설정 ───────────────────────────────────────────────────────────
BASE_DIR     = Path('C:/MES/wta-agents/data/manuals')
WORK_DIR     = Path('C:/MES/wta-agents/workspaces/db-manager')
PROGRESS_FILE = WORK_DIR / 'manual-graphrag-progress.json'
LOG_FILE     = WORK_DIR / 'manual-graphrag-test.log'

OLLAMA_BASE   = 'http://182.224.6.147:11434'
VISION_MODEL  = 'qwen3-vl:8b'
EXTRACT_MODEL = 'qwen3.5:35b-a3b'

# Neo4j
NEO4J_URI  = 'bolt://localhost:7688'
NEO4J_USER = 'neo4j'
NEO4J_PASS = 'WtaPoc2026!Graph'

VALID_NODE_TYPES = {'Equipment', 'Component', 'Process', 'Issue', 'Person',
                    'Customer', 'Manual', 'Tool', 'Product', 'Resolution'}
VALID_REL_TYPES  = {'OWNS', 'HAS_ISSUE', 'SIMILAR_TO', 'RESOLVED_BY',
                    'INVOLVES_COMPONENT', 'USES_COMPONENT', 'INVOLVED_IN',
                    'HAS_SUBPROCESS', 'USES_TOOL', 'MAINTAINS', 'DOCUMENTS'}

# 50개 테스트용 카테고리별 할당 (비율 반영)
SAMPLE_COUNTS = {
    '1_robot': 6,
    '2_sensor': 4,
    '3_hmi': 2,
    '4_servo': 8,
    '5_inverter': 1,
    '6_plc': 3,
    '7_pneumatic': 2,
    '8_etc': 24,
}

logging.basicConfig(
    level=logging.INFO,
    format='[manual-graphrag] %(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_FILE), encoding='utf-8'),
    ]
)
log = logging.getLogger('manual-graphrag')


# ── 진행 상태 ─────────────────────────────────────────────────────
def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {'done': [], 'failed': [], 'stats': {}}

def save_progress(prog: dict):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(prog, f, ensure_ascii=False, indent=2)


# ── PDF 파싱 ─────────────────────────────────────────────────────
def parse_pdf(pdf_path: Path) -> tuple[str, list[bytes]]:
    """PDF → (텍스트, 이미지 바이트 목록)"""
    texts = []
    images = []
    try:
        doc = fitz.open(str(pdf_path))
        for page_num, page in enumerate(doc):
            # 텍스트 추출
            text = page.get_text('text').strip()
            if text:
                texts.append(f'[페이지 {page_num+1}]\n{text}')

            # 이미지 추출 (최대 3개/페이지, 최대 5페이지)
            if page_num < 5 and len(images) < 10:
                for img_info in page.get_images(full=False):
                    xref = img_info[0]
                    try:
                        base_img = doc.extract_image(xref)
                        img_bytes = base_img['image']
                        # 100KB 이상 이미지만 (작은 아이콘 제외)
                        if len(img_bytes) > 100 * 1024:
                            images.append((base_img['ext'], img_bytes))
                            if len(images) >= 10:
                                break
                    except Exception:
                        pass
        doc.close()
    except Exception as e:
        log.warning(f'PDF 파싱 오류 {pdf_path.name}: {e}')
    return '\n\n'.join(texts), images


# ── 비전 이미지 설명 ─────────────────────────────────────────────
def describe_image(img_ext: str, img_bytes: bytes) -> str:
    """이미지 → 한국어 기술 설명"""
    try:
        img_b64 = base64.b64encode(img_bytes).decode()
        ext = img_ext.lower()
        if ext == 'jpg':
            ext = 'jpeg'
        r = requests.post(
            f'{OLLAMA_BASE}/api/generate',
            json={
                'model': VISION_MODEL,
                'prompt': '이 기술 매뉴얼 이미지를 한국어로 간결하게 설명하세요. 장비명, 부품명, 연결도, 수치, 작업 단계 등 기술적 내용 중심으로.',
                'images': [img_b64],
                'stream': False,
                'options': {'num_predict': 200, 'temperature': 0.1},
            },
            timeout=90,
        )
        if r.status_code == 200:
            return r.json().get('response', '').strip()
    except Exception as e:
        log.warning(f'비전 오류: {e}')
    return ''


# ── 엔티티/관계 추출 ─────────────────────────────────────────────
EXTRACT_PROMPT = """다음 기술 매뉴얼에서 엔티티와 관계를 추출하세요.

엔티티 타입: Equipment(장비), Component(부품), Process(공정/작업), Issue(문제/에러), Manual(매뉴얼), Tool(도구)
관계 타입: USES_COMPONENT(부품사용), HAS_SUBPROCESS(하위공정), HAS_ISSUE(문제발생), MAINTAINS(유지보수), DOCUMENTS(문서화), USES_TOOL(도구사용)

JSON 형식으로만 응답하세요:
{"entities":[{"id":"eng_id","name":"한국어명","type":"Equipment","properties":{}}],"relations":[{"source":"id1","target":"id2","type":"USES_COMPONENT"}]}

문서 (앞부분):
"""

def extract_entities(text: str, filename: str) -> dict:
    if len(text) < 50:
        return {'entities': [], 'relations': []}
    truncated = text[:3000]
    try:
        r = requests.post(
            f'{OLLAMA_BASE}/api/generate',
            json={
                'model': EXTRACT_MODEL,
                'prompt': EXTRACT_PROMPT + f'파일명: {filename}\n\n{truncated}',
                'stream': False,
                'think': False,
                'options': {'num_predict': 2000, 'temperature': 0.1},
            },
            timeout=120,
        )
        if r.status_code == 200:
            raw = r.json().get('response', '').strip()
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                return json.loads(m.group())
    except Exception as e:
        log.warning(f'엔티티 추출 오류 [{filename}]: {e}')
    return {'entities': [], 'relations': []}


# ── Neo4j 적재 ─────────────────────────────────────────────────────
def load_to_neo4j(driver, file_id: str, filename: str, category: str,
                  extracted: dict) -> tuple[int, int]:
    entities = extracted.get('entities', [])
    relations = extracted.get('relations', [])
    if not entities:
        return 0, 0

    id_map = {}
    node_count = rel_count = 0
    safe_cat = category.replace(' ', '_')

    with driver.session() as s:
        for ent in entities:
            etype = ent.get('type', '')
            if etype not in VALID_NODE_TYPES:
                continue
            orig_id = ent.get('id', '')
            if not orig_id:
                continue
            safe_id = f"m5_{file_id}_{re.sub(r'[^a-zA-Z0-9_]', '_', orig_id)}"
            id_map[orig_id] = safe_id
            props = {k: v for k, v in (ent.get('properties') or {}).items()
                     if v is not None and v != ''}
            props.update({
                '_id': safe_id,
                '_file': filename,
                '_category': category,
                '_source': 'manual_pdf',
            })
            try:
                s.run(
                    f"MERGE (n:Phase5_Manual:{etype} {{_id: $_id}}) "
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
                    "MATCH (a:Phase5_Manual {_id: $src}), (b:Phase5_Manual {_id: $tgt}) "
                    f"MERGE (a)-[r:{rtype}]->(b)",
                    src=src, tgt=tgt
                )
                rel_count += 1
            except Exception as e:
                log.debug(f'관계 오류: {e}')

    return node_count, rel_count


# ── 50개 샘플 선택 ────────────────────────────────────────────────
import random
random.seed(42)

targets = []
for cat_name, count in SAMPLE_COUNTS.items():
    cat_dir = BASE_DIR / cat_name
    pdfs = sorted(cat_dir.glob('*.pdf'))
    selected = random.sample(pdfs, min(count, len(pdfs)))
    for p in selected:
        targets.append((cat_name, p))

log.info(f'테스트 대상: {len(targets)}개 PDF')
for cat, p in targets[:5]:
    log.info(f'  [{cat}] {p.name}')
log.info('  ...')


# ── 메인 처리 ─────────────────────────────────────────────────────
prog = load_progress()
done_set = set(prog.get('done', []))
failed_set = set(prog.get('failed', []))

# Neo4j 연결
try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    driver.verify_connectivity()
    log.info('Neo4j 연결 완료')
except Exception as e:
    log.error(f'Neo4j 연결 실패: {e}')
    sys.exit(1)

total = len(targets)
done_count = 0
total_nodes = 0
total_rels = 0
timing = []  # 처리 시간 기록

for i, (cat_name, pdf_path) in enumerate(targets):
    file_id = pdf_path.stem[:40]
    file_key = f'{cat_name}/{pdf_path.name}'

    if file_key in done_set:
        log.info(f'[{i+1}/{total}] 스킵 (이미 처리): {pdf_path.name[:50]}')
        done_count += 1
        continue

    log.info(f'[{i+1}/{total}] [{cat_name}] {pdf_path.name[:60]}')
    t_start = time.time()

    # 1. PDF 파싱
    text, images = parse_pdf(pdf_path)
    if not text and not images:
        log.warning(f'  텍스트/이미지 없음: {pdf_path.name}')
        prog['failed'].append(file_key)
        failed_set.add(file_key)
        save_progress(prog)
        continue

    log.info(f'  텍스트: {len(text)}자, 이미지: {len(images)}개')

    # 2. 이미지 분석 (최대 3개)
    image_descs = []
    for ext, img_bytes in images[:3]:
        desc = describe_image(ext, img_bytes)
        if desc:
            image_descs.append(f'[이미지 분석] {desc}')

    full_text = text
    if image_descs:
        full_text += '\n\n' + '\n'.join(image_descs)

    # 3. 엔티티 추출
    extracted = extract_entities(full_text, pdf_path.name)
    n_entities = len(extracted.get('entities', []))
    n_relations = len(extracted.get('relations', []))
    log.info(f'  엔티티: {n_entities}개, 관계: {n_relations}개')

    # 4. Neo4j 적재
    nodes, rels = load_to_neo4j(driver, file_id, pdf_path.name, cat_name, extracted)
    total_nodes += nodes
    total_rels += rels
    if nodes > 0:
        log.info(f'  Neo4j: {nodes}노드, {rels}관계')

    elapsed = time.time() - t_start
    timing.append(elapsed)
    log.info(f'  소요: {elapsed:.1f}초')

    prog['done'].append(file_key)
    done_set.add(file_key)
    done_count += 1

    # 10건마다 저장
    if done_count % 10 == 0:
        prog['stats'] = {
            'done': done_count,
            'total_nodes': total_nodes,
            'total_rels': total_rels,
            'avg_sec': sum(timing) / len(timing) if timing else 0,
        }
        save_progress(prog)
        log.info(f'--- 중간저장: {done_count}건 완료 ---')

# 최종 저장
avg_sec = sum(timing) / len(timing) if timing else 0
prog['stats'] = {
    'done': done_count,
    'total_nodes': total_nodes,
    'total_rels': total_rels,
    'avg_sec': avg_sec,
    'finished_at': datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST'),
}
save_progress(prog)

driver.close()

log.info('=== 테스트 완료 ===')
log.info(f'처리: {done_count}건 / 실패: {len(prog["failed"])}건')
log.info(f'Neo4j 누적: {total_nodes}노드, {total_rels}관계')
log.info(f'평균 처리 시간: {avg_sec:.1f}초/파일')
if timing:
    log.info(f'예상 전체(1865개): {1865 * avg_sec / 3600:.1f}시간')
    log.info(f'예상 야간(7h/일): {1865 * avg_sec / 3600 / 7:.1f}일 소요')
