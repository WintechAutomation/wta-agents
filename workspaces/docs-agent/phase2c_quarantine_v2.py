# -*- coding: utf-8 -*-
"""Phase 2c v2: Unknown 27 + category_valid=false 22 통합 격리 (idempotent)

- 롤백(10건)은 v1에서 이미 완료됨. 이 스크립트는 이동만 재실행.
- 기존 filtered/ 와 충돌 시 _v2/_v3 suffix.
- reason: OCR_Unknown / category_invalid / both
"""
import os, sys, io, csv, json, shutil
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SRC_DIR = r'C:\MES\wta-agents\data\manuals-ready\2_sensor'
DST_DIR = r'C:\MES\wta-agents\data\manuals-filtered\2_sensor'
PLAN_CSV = r'C:\MES\wta-agents\workspaces\docs-agent\2_sensor_rename_plan.csv'
MOVE_LOG = r'C:\MES\wta-agents\workspaces\docs-agent\2_sensor_filtered_move_log.json'
PREV_LOG = r'C:\MES\wta-agents\workspaces\docs-agent\2_sensor_filtered_move_log_v1.json'  # backup old

KST = timezone(timedelta(hours=9))
def now(): return datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')

# 기존 로그 백업
if os.path.exists(MOVE_LOG):
    shutil.copy2(MOVE_LOG, PREV_LOG)

# 계획 로드
with open(PLAN_CSV, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# 타겟 분류
unknown_set = set()        # old_filename (원본명, Unknown_*)
invalid_map = {}           # post-phase2a 이름 -> dict(row)
for r in rows:
    old = r['old_filename']
    new = r['new_filename']
    if not r['manufacturer']:   # Unknown 27
        unknown_set.add(old)
    if r['category_valid'] == 'false':
        # Phase 2a에서 rename되었을 수 있음 → 현재 이름은 new_filename
        key = new if r['manufacturer'] else old
        invalid_map[key] = r

# 통합 타겟 dict: current_filename -> reason
targets = {}
for old in unknown_set:
    targets[old] = 'OCR_Unknown'
for key, r in invalid_map.items():
    if key in targets:
        targets[key] = 'both'
    else:
        targets[key] = 'category_invalid'

print(f'통합 격리 대상: {len(targets)}건 (Unknown {len(unknown_set)} + invalid {len(invalid_map)}, 중복 제거 후)')

ready_files = set(os.listdir(SRC_DIR))
filtered_files = set(os.listdir(DST_DIR))

entries = []
success = 0
skipped = 0
errors = 0

for fname, reason in sorted(targets.items()):
    src = os.path.join(SRC_DIR, fname)
    # 이미 filtered로 이동된 경우
    if fname not in ready_files:
        if fname in filtered_files:
            entries.append({'src': src, 'dst': os.path.join(DST_DIR, fname), 'reason': reason, 'phase':'2c', 'ts': now(), 'status':'already_moved'})
            skipped += 1
        else:
            entries.append({'src': src, 'dst': '', 'reason': reason, 'phase':'2c', 'ts': now(), 'status':'error', 'error':'not found in ready nor filtered'})
            errors += 1
        continue
    # 충돌 해결
    final = fname
    if final in filtered_files:
        base, ext = os.path.splitext(fname)
        idx = 2
        while True:
            cand = f'{base}_v{idx}{ext}'
            if cand not in filtered_files:
                final = cand
                break
            idx += 1
    dst = os.path.join(DST_DIR, final)
    try:
        shutil.move(src, dst)
        ready_files.discard(fname)
        filtered_files.add(final)
        entries.append({'src': src, 'dst': dst, 'reason': reason, 'phase':'2c', 'ts': now(), 'status':'success', 'renamed_to': final if final != fname else None})
        success += 1
    except Exception as e:
        entries.append({'src': src, 'dst': dst, 'reason': reason, 'phase':'2c', 'ts': now(), 'status':'error', 'error':str(e)})
        errors += 1

# 로그 저장
with open(MOVE_LOG, 'w', encoding='utf-8') as f:
    json.dump({
        'phase':'2c-move-v2',
        'executed_at': now(),
        'total_targets': len(targets),
        'unknown_count': len(unknown_set),
        'invalid_count': len(invalid_map),
        'dedup_overlap': len(unknown_set) + len(invalid_map) - len(targets),
        'success': success,
        'already_moved': skipped,
        'errors': errors,
        'entries': entries,
    }, f, ensure_ascii=False, indent=2)

# 최종 검증
src_count = len([f for f in os.listdir(SRC_DIR) if f.lower().endswith('.pdf')])
dst_count = len([f for f in os.listdir(DST_DIR) if f.lower().endswith('.pdf')])
print(f'\n[이동 결과] success={success} / already_moved={skipped} / errors={errors}')
print(f'\n=== 최종 검증 ===')
print(f'ready/2_sensor:    {src_count}개')
print(f'filtered/2_sensor: {dst_count}개')
print(f'\n이동 로그: {MOVE_LOG}')
