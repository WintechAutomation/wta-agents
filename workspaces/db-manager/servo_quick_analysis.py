# -*- coding: utf-8 -*-
"""
servo_quick_analysis.py — 알람 섹션 5윈도우 즉시 품질 분석 (v1.4 프롬프트)
"""
import sys, json
sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/MES/wta-agents/workspaces/db-manager')

from servo_batch_pipeline import (
    build_windows, extract_entities, filter_extracted
)
from pathlib import Path
from collections import defaultdict

chunks_path = Path('C:/MES/wta-agents/reports/manuals-v2/poc/4_servo_7e174cc67cee/chunks.jsonl')
chunks = []
with open(chunks_path, encoding='utf-8') as f:
    for line in f:
        if line.strip():
            chunks.append(json.loads(line))

windows = build_windows(chunks)
# 알람 원인/처치 집중 구간 5개
test_wins = windows[300:305]
print(f'테스트 윈도우: {len(test_wins)}개 (인덱스 300~304)')
print(f'첫 윈도우 텍스트 샘플: {test_wins[0]["text"][:300]}\n')

all_entities = []
all_relations = []
for i, w in enumerate(test_wins):
    print(f'윈도우 {i+1}/5 추출 중...')
    ext = extract_entities(w['text'])
    filtered = filter_extracted(ext, '4_servo_7e174cc67cee')
    all_entities.extend(filtered['entities'])
    all_relations.extend(filtered['relations'])
    print(f'  → 엔티티 {len(filtered["entities"])}건, 관계 {len(filtered["relations"])}건')

# 중복 제거
seen = set()
dedup = []
for e in all_entities:
    if e['id'] not in seen:
        seen.add(e['id'])
        dedup.append(e)
all_entities = dedup

print(f'\n=== 품질 분석 결과 ===')
print(f'총 엔티티: {len(all_entities)}, 관계: {len(all_relations)}')

# 타입 분포
by_type = defaultdict(list)
for e in all_entities:
    by_type[e.get('type', 'unknown')].append(e)
print(f'타입 분포: {dict((t, len(v)) for t, v in by_type.items())}')

# description 보유율
total = len(all_entities)
desc_count = sum(1 for e in all_entities if (e.get('properties') or {}).get('description'))
print(f'description 보유율: {desc_count}/{total} ({desc_count/max(total,1)*100:.0f}%)')

# Alarm 품질
alarms = by_type.get('Alarm', [])
print(f'\n[Alarm 품질] {len(alarms)}건')
if alarms:
    alarm_total = len(alarms)
    def hp(e, k): return bool((e.get('properties') or {}).get(k))
    print(f'  code: {sum(1 for a in alarms if hp(a,"code"))}/{alarm_total}')
    print(f'  cause: {sum(1 for a in alarms if hp(a,"cause"))}/{alarm_total}')
    print(f'  symptom: {sum(1 for a in alarms if hp(a,"symptom"))}/{alarm_total}')
    print(f'  solution: {sum(1 for a in alarms if hp(a,"solution"))}/{alarm_total}')
    print(f'  description: {sum(1 for a in alarms if hp(a,"description"))}/{alarm_total}')
    print()
    for a in alarms[:5]:
        props = a.get('properties', {})
        print(f'  [{a["name"]}]')
        for k in ['code', 'cause', 'symptom', 'solution', 'description']:
            v = props.get(k)
            if v:
                print(f'    {k}: {str(v)[:80]}')
        print()

# Parameter 샘플
params = by_type.get('Parameter', [])[:3]
if params:
    print('[Parameter 샘플]')
    for p in params:
        props = p.get('properties', {})
        print(f'  [{p["name"]}] code={props.get("code")} desc={str(props.get("description",""))[:60]}')

# 관계 타입 분포
if all_relations:
    rel_types = defaultdict(int)
    for r in all_relations:
        rel_types[r.get('type')] += 1
    print(f'\n관계 타입 분포: {dict(rel_types)}')
    print('관계 샘플:')
    for r in all_relations[:5]:
        print(f'  {r.get("source")} --{r.get("type")}--> {r.get("target")}')

print('\n완료')
