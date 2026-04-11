# -*- coding: utf-8 -*-
"""Phase 2a: 2_sensor rename 실행 (Unknown 제조사 27건 제외, 110건만)"""
import os, sys, io, csv, json
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SRC_DIR = r'C:\MES\wta-agents\data\manuals-ready\2_sensor'
CSV_PATH = r'C:\MES\wta-agents\workspaces\docs-agent\2_sensor_rename_plan.csv'
LOG_PATH = r'C:\MES\wta-agents\workspaces\docs-agent\2_sensor_rename_log_phase2a.json'
UNKNOWN_LIST_PATH = r'C:\MES\wta-agents\workspaces\docs-agent\2_sensor_unknown_27.csv'

KST = timezone(timedelta(hours=9))

def now():
    return datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')

# CSV 로드
with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

targets = [r for r in rows if r['manufacturer'] and r['manufacturer'] != 'Unknown']
skipped = [r for r in rows if not r['manufacturer'] or r['manufacturer'] == 'Unknown']

print(f'총 {len(rows)}건 / rename 대상 {len(targets)}건 / skip {len(skipped)}건')

# 1단계: rename 후보 충돌 검사 (in-place)
#  - 동일 new_filename 가 이미 다른 파일에 존재하면 _vN suffix 부여
existing = set(os.listdir(SRC_DIR))
planned_new = set()
log = []
success = 0
errors = 0
skipped_noop = 0

# 우선 new==old 인 경우(파일명 그대로) skip
for r in targets:
    old = r['old_filename']
    new = r['new_filename']
    old_abs = os.path.join(SRC_DIR, old)
    if not os.path.exists(old_abs):
        log.append({'old': old, 'new': new, 'ts': now(), 'status': 'error', 'reason': 'source missing'})
        errors += 1
        continue
    if old == new:
        log.append({'old': old, 'new': new, 'ts': now(), 'status': 'skip', 'reason': 'identical'})
        skipped_noop += 1
        planned_new.add(new)
        continue
    # 충돌 해결
    final_new = new
    if final_new in planned_new or (final_new in existing and final_new != old):
        base, ext = os.path.splitext(new)
        idx = 2
        while True:
            cand = f'{base}_v{idx}{ext}'
            if cand not in planned_new and cand not in existing:
                final_new = cand
                break
            idx += 1
    planned_new.add(final_new)
    new_abs = os.path.join(SRC_DIR, final_new)
    try:
        os.rename(old_abs, new_abs)
        existing.discard(old)
        existing.add(final_new)
        log.append({'old': old, 'new': final_new, 'ts': now(), 'status': 'success'})
        success += 1
    except Exception as e:
        log.append({'old': old, 'new': final_new, 'ts': now(), 'status': 'error', 'reason': str(e)})
        errors += 1

# 로그 저장
with open(LOG_PATH, 'w', encoding='utf-8') as f:
    json.dump({
        'phase': '2a',
        'executed_at': now(),
        'total_targets': len(targets),
        'success': success,
        'skip_identical': skipped_noop,
        'errors': errors,
        'unknown_skipped': len(skipped),
        'entries': log,
    }, f, ensure_ascii=False, indent=2)

# Unknown 27건 별도 CSV (부서장 수동 보정용)
with open(UNKNOWN_LIST_PATH, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['old_filename','manufacturer','model','doctype','language','notes'])
    w.writeheader()
    for r in skipped:
        w.writerow({
            'old_filename': r['old_filename'],
            'manufacturer': '',
            'model': r.get('model',''),
            'doctype': r.get('doctype',''),
            'language': r.get('language',''),
            'notes': r.get('notes',''),
        })

# 전수 검증
verify_errors = []
for e in log:
    if e['status'] != 'success':
        continue
    old_abs = os.path.join(SRC_DIR, e['old'])
    new_abs = os.path.join(SRC_DIR, e['new'])
    if os.path.exists(old_abs):
        verify_errors.append(f"old still exists: {e['old']}")
    if not os.path.exists(new_abs):
        verify_errors.append(f"new missing: {e['new']}")

print(f'\n=== 실행 결과 ===')
print(f'success: {success}')
print(f'skip(identical): {skipped_noop}')
print(f'errors: {errors}')
print(f'unknown skipped: {len(skipped)}')
print(f'verify errors: {len(verify_errors)}')
for v in verify_errors[:20]:
    print(f'  ! {v}')
print(f'\nlog: {LOG_PATH}')
print(f'unknown list: {UNKNOWN_LIST_PATH}')
