"""
qwen3.5:35b-a3b(think:False) vs qwen3.5:35b 엔티티 추출 비교 테스트
"""
import sys, os, json, re, time, logging
from pathlib import Path

import fitz
import requests

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

LOG_FILE = Path('C:/MES/wta-agents/workspaces/db-manager/model-compare.log')
OLLAMA_BASE = 'http://182.224.6.147:11434'
BASE_DIR = Path('C:/MES/wta-agents/data/manuals')

MODELS = [
    {'name': 'qwen3.5:35b-a3b', 'think': False, 'label': 'a3b+think:False'},
    {'name': 'qwen3.5:35b',     'think': None,  'label': '35b_dense'},
]

logging.basicConfig(
    level=logging.INFO,
    format='[compare] %(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_FILE), encoding='utf-8', mode='w'),
    ]
)
log = logging.getLogger('compare')

EXTRACT_PROMPT_TEMPLATE = (
    '다음 기술 매뉴얼에서 엔티티와 관계를 추출하세요.\n'
    '엔티티 타입: Equipment(장비), Component(부품), Process(공정/작업), Issue(문제/에러), Manual(매뉴얼), Tool(도구)\n'
    '관계 타입: USES_COMPONENT(부품사용), HAS_SUBPROCESS(하위공정), HAS_ISSUE(문제발생), MAINTAINS(유지보수), DOCUMENTS(문서화), USES_TOOL(도구사용)\n'
    'JSON 형식으로만 응답: '
    '{{"entities":[{{"id":"eng_id","name":"한국어명","type":"Equipment","properties":{{}}}}],'
    '"relations":[{{"source":"id1","target":"id2","type":"USES_COMPONENT"}}]}}\n'
    '파일명: {filename}\n\n'
    '문서 (앞부분):\n{text}'
)


def parse_pdf_text(pdf_path: Path) -> str:
    texts = []
    try:
        doc = fitz.open(str(pdf_path))
        for page in doc[:5]:
            t = page.get_text('text').strip()
            if t:
                texts.append(t)
        doc.close()
    except Exception as e:
        log.warning(f'파싱 오류: {e}')
    return '\n'.join(texts)


def extract_entities(text: str, filename: str, model: str, use_think_false: bool) -> tuple[dict, float, int]:
    if len(text) < 50:
        return {'entities': [], 'relations': []}, 0.0, 0

    truncated = text[:3000]
    prompt = EXTRACT_PROMPT_TEMPLATE.format(filename=filename, text=truncated)

    payload = {
        'model': model,
        'prompt': prompt,
        'stream': False,
        'options': {'num_predict': 2000, 'temperature': 0.1},
    }
    if use_think_false:
        payload['think'] = False

    t0 = time.time()
    try:
        r = requests.post(f'{OLLAMA_BASE}/api/generate', json=payload, timeout=180)
        elapsed = time.time() - t0
        if r.status_code == 200:
            d = r.json()
            raw = d.get('response', '').strip()
            token_count = d.get('eval_count', 0)
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group()), elapsed, token_count
                except json.JSONDecodeError:
                    pass
            return {'entities': [], 'relations': []}, elapsed, token_count
    except Exception as e:
        log.warning(f'오류 [{model}] [{filename}]: {e}')
    return {'entities': [], 'relations': []}, time.time() - t0, 0


# 테스트 대상 PDF (기존 progress.json에서 로드)
with open('C:/MES/wta-agents/workspaces/db-manager/manual-graphrag-progress.json', encoding='utf-8') as f:
    prog = json.load(f)

done_keys = [d for d in prog['done'] if d not in prog.get('failed', [])]
targets = []
for key in done_keys[:15]:
    parts = key.split('/', 1)
    if len(parts) == 2:
        cat, fname = parts
        p = BASE_DIR / cat / fname
        if p.exists():
            targets.append((cat, p))
    if len(targets) >= 15:
        break

log.info(f'비교 테스트 대상: {len(targets)}개 PDF')
log.info(f'모델: {[m["label"] for m in MODELS]}')

results = {m['label']: {'times': [], 'entity_counts': [], 'rel_counts': [], 'tokens': [], 'samples': []} for m in MODELS}

for i, (cat, pdf_path) in enumerate(targets):
    log.info(f'\n[{i+1}/{len(targets)}] [{cat}] {pdf_path.name[:60]}')
    text = parse_pdf_text(pdf_path)
    if len(text) < 50:
        log.warning(f'  텍스트 없음, 스킵')
        continue
    log.info(f'  텍스트: {len(text)}자')

    for model_cfg in MODELS:
        label = model_cfg['label']
        model = model_cfg['name']
        think_false = model_cfg['think'] is False

        extracted, elapsed, tokens = extract_entities(text, pdf_path.name, model, think_false)
        n_entities = len(extracted.get('entities', []))
        n_rels = len(extracted.get('relations', []))

        results[label]['times'].append(elapsed)
        results[label]['entity_counts'].append(n_entities)
        results[label]['rel_counts'].append(n_rels)
        results[label]['tokens'].append(tokens)

        # 엔티티 샘플
        sample_names = [e.get('name', '') for e in extracted.get('entities', [])[:5]]
        if n_entities > 0:
            results[label]['samples'].append(sample_names)

        log.info(f'  [{label}] 엔티티:{n_entities} 관계:{n_rels} 시간:{elapsed:.1f}초 토큰:{tokens}')
        log.info(f'    샘플: {sample_names[:5]}')


# 최종 비교 출력
log.info('\n\n=== 비교 결과 ===')
for label, data in results.items():
    times = data['times']
    ents = data['entity_counts']
    rels = data['rel_counts']
    if not times:
        continue
    avg_time = sum(times) / len(times)
    avg_ents = sum(ents) / len(ents)
    avg_rels = sum(rels) / len(rels)
    success = sum(1 for e in ents if e > 0)
    log.info(f'\n[{label}]')
    log.info(f'  평균 처리시간: {avg_time:.1f}초')
    log.info(f'  평균 엔티티: {avg_ents:.1f}개/파일')
    log.info(f'  평균 관계: {avg_rels:.1f}개/파일')
    log.info(f'  성공률: {success}/{len(times)} ({100*success//len(times)}%)')
    log.info(f'  평균 토큰: {sum(data["tokens"])/len(data["tokens"]):.0f}')

# JSON 저장
out = {label: {
    'avg_time': sum(d['times'])/len(d['times']) if d['times'] else 0,
    'avg_entities': sum(d['entity_counts'])/len(d['entity_counts']) if d['entity_counts'] else 0,
    'avg_relations': sum(d['rel_counts'])/len(d['rel_counts']) if d['rel_counts'] else 0,
    'success_rate': sum(1 for e in d['entity_counts'] if e > 0) / len(d['entity_counts']) if d['entity_counts'] else 0,
    'sample_entities': d['samples'][:3],
} for label, d in results.items()}

with open('C:/MES/wta-agents/workspaces/db-manager/model-compare-result.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

log.info('\n결과 저장: model-compare-result.json')
