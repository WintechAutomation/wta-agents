# -*- coding: utf-8 -*-
"""
servo_sample_test.py — v1.3 프롬프트 품질 검증 (샘플 3건)

검증 파일:
  1. 4_servo_7e174cc67cee — CSD7 아날로그 서보 매뉴얼.pdf (362p, chunks 기존 사용)
  2. 4_servo_bdf916d3cf00 — Functional Specification.pdf / Panasonic SX-DSV02472 (187p)
  3. 4_servo_8f32d3b79d22 — EtherCAT Communication Specifications.pdf / Panasonic (294p)

보고 항목:
  1. Alarm/Parameter/Process 샘플 각 3개 (properties 전체)
  2. description 보유율
  3. Alarm code/cause/symptom/solution 보유율
  4. 관계 타입 제약 준수 여부
  5. CS 질의 시뮬레이션 가능 여부
"""
import sys, os, json, re, time, subprocess, logging, requests
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = __import__('io').TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

KST = timezone(timedelta(hours=9))
REPORTS_ROOT = Path('C:/MES/wta-agents/reports/manuals-v2')
POC_DIR = REPORTS_ROOT / 'poc'
EXTRACT_JSONL = REPORTS_ROOT / 'extract/manuals_v2_4_servo_extract.jsonl'
ALLOC_FILE = REPORTS_ROOT / 'servo_batch_allocation.json'

OLLAMA_BASE = 'http://182.224.6.147:11434'
EXTRACT_MODEL = 'qwen3.5:35b-a3b'
EMBED_MODEL = 'qwen3-embedding:8b'
EMBED_DIM = 2000

logging.basicConfig(
    level=logging.INFO,
    format='[sample-test] %(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger('sample-test')

# ── 프롬프트 임포트 (servo_batch_pipeline.py와 공유) ─────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from servo_batch_pipeline import (
    MANUALS_V2_EXTRACT_PROMPT, VALID_ENTITY_TYPES, VALID_REL_TYPES,
    build_windows, extract_entities, filter_extracted, _load_env, _load_neo4j_pass,
)

_ENV = _load_env()
NEO4J_PASS = _load_neo4j_pass()

# 검증 대상 파일 3건
TEST_FILES = [
    {
        'file_id': '4_servo_7e174cc67cee',
        'filename': 'CSD7 아날로그 서보 매뉴얼.pdf',
        'mfr': 'Unknown', 'model': 'CSD7',
        'has_chunks': True,  # 기존 chunks 사용
        'src_md5': '7e174cc67ceeb6a9662bbdd51cddfcdf',
    },
    {
        'file_id': '4_servo_bdf916d3cf00',
        'filename': 'Functional Specification.pdf',
        'mfr': 'Panasonic', 'model': 'SX-DSV02472',
        'has_chunks': False,
        'src_md5': 'bdf916d3cf00b469651e5ed36ce01763',
    },
    {
        'file_id': '4_servo_8f32d3b79d22',
        'filename': 'EtherCAT Communication Specifications.pdf',
        'mfr': 'Panasonic', 'model': 'SX-DSV02473',
        'has_chunks': False,
        'src_md5': '8f32d3b79d220e96e17d33fcce89476e',
    },
]


def get_src_path(md5: str) -> str:
    """extract.jsonl에서 src_path 조회"""
    with open(EXTRACT_JSONL, encoding='utf-8') as f:
        for line in f:
            rec = json.loads(line)
            if rec.get('md5') == md5 and rec.get('status') == 'ok':
                return rec.get('src_path', '')
    return ''


def run_step2(file_id: str, src_path: str) -> bool:
    """Docling 파싱"""
    poc_dir = POC_DIR / file_id
    chunks_path = poc_dir / 'chunks.jsonl'
    if chunks_path.exists():
        log.info(f'Step2 이미 완료: {file_id}')
        return True
    PY = r'C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe'
    script = r'C:\MES\wta-agents\workspaces\docs-agent\manuals_v2_parse_docling.py'
    log.info(f'Step2 Docling 시작: {file_id}')
    try:
        result = subprocess.run(
            [PY, script, src_path],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=1800,
        )
        if result.returncode == 0 or chunks_path.exists():
            log.info(f'Step2 완료: {file_id}')
            return True
        log.warning(f'Step2 실패(rc={result.returncode}): {result.stderr[-300:]}')
        return False
    except Exception as e:
        log.error(f'Step2 예외: {e}')
        return chunks_path.exists()


def load_chunks(file_id: str) -> list:
    chunks_path = POC_DIR / file_id / 'chunks.jsonl'
    if not chunks_path.exists():
        return []
    chunks = []
    with open(chunks_path, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))
    return chunks


def run_graphrag_sample(chunks: list, file_id: str, max_windows: int = 30) -> dict:
    """처음 max_windows 윈도우만 추출해서 품질 분석"""
    windows = build_windows(chunks)
    windows = windows[:max_windows]

    all_entities = []
    all_relations = []

    for i, win in enumerate(windows):
        log.info(f'  윈도우 {i+1}/{len(windows)} 추출...')
        extracted = extract_entities(win['text'])
        filtered = filter_extracted(extracted, file_id)
        all_entities.extend(filtered['entities'])
        all_relations.extend(filtered['relations'])
        time.sleep(0.3)

    # 중복 id 제거 (전체 파일 수준)
    seen = set()
    dedup = []
    for e in all_entities:
        if e['id'] not in seen:
            seen.add(e['id'])
            dedup.append(e)
    all_entities = dedup

    return {'entities': all_entities, 'relations': all_relations}


def analyze_quality(extracted: dict, file_id: str, filename: str) -> dict:
    entities = extracted['entities']
    relations = extracted['relations']

    total = len(entities)
    if total == 0:
        return {'file_id': file_id, 'filename': filename, 'total': 0}

    by_type = defaultdict(list)
    for e in entities:
        by_type[e.get('type', 'unknown')].append(e)

    # description 보유율
    desc_count = sum(1 for e in entities if (e.get('properties') or {}).get('description'))
    desc_rate = desc_count / total * 100

    # Alarm 품질
    alarms = by_type.get('Alarm', [])
    alarm_metrics = {}
    if alarms:
        alarm_total = len(alarms)
        def has_prop(e, key): return bool((e.get('properties') or {}).get(key))
        alarm_metrics = {
            'total': alarm_total,
            'code_rate': sum(1 for e in alarms if has_prop(e, 'code')) / alarm_total * 100,
            'cause_rate': sum(1 for e in alarms if has_prop(e, 'cause')) / alarm_total * 100,
            'symptom_rate': sum(1 for e in alarms if has_prop(e, 'symptom')) / alarm_total * 100,
            'solution_rate': sum(1 for e in alarms if has_prop(e, 'solution')) / alarm_total * 100,
            'desc_rate': sum(1 for e in alarms if has_prop(e, 'description')) / alarm_total * 100,
        }

    # 관계 타입 제약 위반 확인
    ent_type_map = {e['id']: e.get('type') for e in entities}

    REL_TYPE_CONSTRAINTS = {
        'PART_OF': ({'Component'}, {'Equipment'}),
        'HAS_PARAMETER': ({'Equipment'}, {'Parameter'}),
        'SPECIFIES': ({'Specification'}, {'Equipment', 'Component'}),
        'CAUSES': ({'Alarm'}, {'Process'}),
        'RESOLVES': ({'Process'}, {'Alarm'}),
        'CONNECTS_TO': ({'Equipment', 'Component'}, {'Equipment', 'Component'}),
        'REQUIRES': ({'Process'}, {'Equipment', 'Component'}),
        'BELONGS_TO': ({'Figure', 'Table', 'Diagram'}, {'Section'}),
        'REFERENCES': ({'Section'}, {'Figure', 'Table', 'Diagram'}),
        'DEPICTS': ({'Figure', 'Diagram'}, {'Equipment', 'Component'}),
        'DOCUMENTS': ({'Manual'}, {'Equipment', 'Process'}),
        'WARNS': ({'SafetyRule'}, {'Process', 'Equipment'}),
    }

    violations = []
    for r in relations:
        rtype = r.get('type')
        src_type = ent_type_map.get(r.get('source'))
        tgt_type = ent_type_map.get(r.get('target'))
        if rtype in REL_TYPE_CONSTRAINTS:
            allowed_src, allowed_tgt = REL_TYPE_CONSTRAINTS[rtype]
            if src_type and src_type not in allowed_src:
                violations.append(f"{rtype}: src={src_type}(허용:{allowed_src})")
            if tgt_type and tgt_type not in allowed_tgt:
                violations.append(f"{rtype}: tgt={tgt_type}(허용:{allowed_tgt})")

    rel_violation_rate = len(violations) / max(len(relations), 1) * 100

    # CS 질의 가능 여부: Alarm이 있고 CAUSES/RESOLVES 관계 존재하면 YES
    alarm_rels = [r for r in relations if r.get('type') in ('CAUSES', 'RESOLVES')]
    cs_queryable = len(alarms) > 0 and len(alarm_rels) > 0

    # 샘플 3개씩
    def samples(lst, n=3):
        return lst[:n]

    return {
        'file_id': file_id,
        'filename': filename,
        'total_entities': total,
        'total_relations': len(relations),
        'type_distribution': {t: len(v) for t, v in by_type.items()},
        'description_rate': round(desc_rate, 1),
        'alarm_metrics': alarm_metrics,
        'rel_violation_count': len(violations),
        'rel_violation_rate': round(rel_violation_rate, 1),
        'violations_sample': violations[:5],
        'cs_queryable': cs_queryable,
        'alarm_samples': samples(alarms),
        'param_samples': samples(by_type.get('Parameter', [])),
        'process_samples': samples(by_type.get('Process', [])),
        'relation_samples': samples(relations),
    }


def print_report(result: dict):
    print('\n' + '='*70)
    print(f"파일: {result['filename']}")
    print(f"file_id: {result['file_id']}")
    total = result.get('total_entities', 0)
    if total == 0:
        print('  [오류] 추출 결과 없음')
        return
    print(f"총 엔티티: {total}, 관계: {result['total_relations']}")
    print(f"타입 분포: {result['type_distribution']}")
    print(f"description 보유율: {result['description_rate']}%")

    am = result.get('alarm_metrics', {})
    if am:
        print(f"\n[Alarm 품질] 총 {am['total']}건")
        print(f"  code: {am['code_rate']:.0f}% | cause: {am['cause_rate']:.0f}% | "
              f"symptom: {am['symptom_rate']:.0f}% | solution: {am['solution_rate']:.0f}% | "
              f"description: {am['desc_rate']:.0f}%")

    print(f"\n관계 제약 위반: {result['rel_violation_count']}건 ({result['rel_violation_rate']}%)")
    if result['violations_sample']:
        for v in result['violations_sample']:
            print(f"  위반: {v}")

    print(f"CS 질의 가능(Alarm+CAUSES/RESOLVES): {'YES' if result['cs_queryable'] else 'NO'}")

    # Alarm 샘플
    if result['alarm_samples']:
        print('\n[Alarm 샘플]')
        for e in result['alarm_samples']:
            props = e.get('properties', {})
            print(f"  name: {e['name']}")
            for k, v in props.items():
                print(f"    {k}: {v}")
            print()

    # Parameter 샘플
    if result['param_samples']:
        print('[Parameter 샘플]')
        for e in result['param_samples']:
            props = e.get('properties', {})
            print(f"  name: {e['name']}")
            for k, v in props.items():
                print(f"    {k}: {v}")
            print()

    # Process 샘플
    if result['process_samples']:
        print('[Process 샘플]')
        for e in result['process_samples']:
            props = e.get('properties', {})
            print(f"  name: {e['name']}")
            for k, v in props.items():
                print(f"    {k}: {v}")
            print()

    # 관계 샘플
    if result['relation_samples']:
        print('[관계 샘플]')
        for r in result['relation_samples']:
            print(f"  {r.get('source')} --{r.get('type')}--> {r.get('target')}")


def main():
    print(f"=== 서보 샘플 3건 품질 검증 (v1.3 프롬프트) ===")
    print(f"시작: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')}\n")

    results = []

    for tf in TEST_FILES:
        file_id = tf['file_id']
        filename = tf['filename']
        log.info(f'\n--- {filename} ---')

        # Step2: chunks 준비
        if not tf['has_chunks']:
            src_path = get_src_path(tf['src_md5'])
            if not src_path:
                log.warning(f'src_path 없음: {file_id}')
                continue
            log.info(f'src_path: {src_path}')
            ok = run_step2(file_id, src_path)
            if not ok:
                log.warning(f'Step2 실패, 건너뜀: {file_id}')
                continue

        chunks = load_chunks(file_id)
        if not chunks:
            log.warning(f'chunks 없음: {file_id}')
            continue
        log.info(f'청크: {len(chunks)}건, 최대 30 윈도우 추출')

        # GraphRAG (최대 30 윈도우)
        extracted = run_graphrag_sample(chunks, file_id, max_windows=30)
        log.info(f'추출: 엔티티 {len(extracted["entities"])}건, 관계 {len(extracted["relations"])}건')

        # 품질 분석
        result = analyze_quality(extracted, file_id, filename)
        results.append(result)
        print_report(result)

    # 전체 요약
    print('\n' + '='*70)
    print('=== 전체 요약 ===')
    for r in results:
        am = r.get('alarm_metrics', {})
        alarm_count = am.get('total', 0) if am else 0
        print(f"  {r['filename'][:40]}: 엔티티 {r.get('total_entities',0)}, "
              f"Alarm {alarm_count}, desc율 {r.get('description_rate',0)}%, "
              f"CS질의 {'O' if r.get('cs_queryable') else 'X'}")

    # JSON 보고서 저장
    report_path = REPORTS_ROOT / 'state' / 'sample_test_report.json'
    report_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n보고서 저장: {report_path}')
    print(f"완료: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')}")


if __name__ == '__main__':
    main()
