# -*- coding: utf-8 -*-
"""Phase 2c: Phase 2b rollback + Unknown 27건 filtered 폴더로 격리"""
import os, sys, io, csv, json, shutil
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SRC_DIR = r'C:\MES\wta-agents\data\manuals-ready\2_sensor'
DST_DIR = r'C:\MES\wta-agents\data\manuals-filtered\2_sensor'
OCR_LOG = r'C:\MES\wta-agents\workspaces\docs-agent\2_sensor_ocr_rescan_log.json'
UNKNOWN_CSV = r'C:\MES\wta-agents\workspaces\docs-agent\2_sensor_unknown_27.csv'
ROLLBACK_LOG = r'C:\MES\wta-agents\workspaces\docs-agent\2_sensor_phase2b_rollback_log.json'
MOVE_LOG = r'C:\MES\wta-agents\workspaces\docs-agent\2_sensor_filtered_move_log.json'

KST = timezone(timedelta(hours=9))
def now(): return datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')

os.makedirs(DST_DIR, exist_ok=True)

# === 1단계: Phase 2b high 10건 롤백 ===
with open(OCR_LOG, 'r', encoding='utf-8') as f:
    ocr_log = json.load(f)

rollback_entries = []
rb_success = 0
rb_error = 0
for entry in ocr_log['entries']:
    if entry.get('status') != 'success':
        continue
    # 현재 파일명은 entry['new'], 원래는 entry['old']
    current = os.path.join(SRC_DIR, entry['new'])
    original = os.path.join(SRC_DIR, entry['old'])
    if not os.path.exists(current):
        rollback_entries.append({'current': entry['new'], 'original': entry['old'], 'ts': now(), 'status':'error', 'reason':'current missing'})
        rb_error += 1
        continue
    if os.path.exists(original) and entry['new'] != entry['old']:
        rollback_entries.append({'current': entry['new'], 'original': entry['old'], 'ts': now(), 'status':'error', 'reason':'original name collision'})
        rb_error += 1
        continue
    try:
        os.rename(current, original)
        rollback_entries.append({'current': entry['new'], 'original': entry['old'], 'ts': now(), 'status':'success'})
        rb_success += 1
    except Exception as e:
        rollback_entries.append({'current': entry['new'], 'original': entry['old'], 'ts': now(), 'status':'error', 'reason':str(e)})
        rb_error += 1

with open(ROLLBACK_LOG, 'w', encoding='utf-8') as f:
    json.dump({
        'phase':'2c-rollback',
        'executed_at': now(),
        'total': len(rollback_entries),
        'success': rb_success,
        'errors': rb_error,
        'entries': rollback_entries,
    }, f, ensure_ascii=False, indent=2)

print(f'[1단계 롤백] success={rb_success} / errors={rb_error}')

# === 2단계: Unknown 27건 filtered 폴더로 이동 ===
with open(UNKNOWN_CSV, 'r', encoding='utf-8-sig') as f:
    unknown_rows = list(csv.DictReader(f))

move_entries = []
mv_success = 0
mv_error = 0
for r in unknown_rows:
    fname = r['old_filename']
    src = os.path.join(SRC_DIR, fname)
    dst = os.path.join(DST_DIR, fname)
    if not os.path.exists(src):
        move_entries.append({'src': src, 'dst': dst, 'reason':'OCR Unknown', 'phase':'2c', 'ts': now(), 'status':'error', 'error':'src missing'})
        mv_error += 1
        continue
    if os.path.exists(dst):
        move_entries.append({'src': src, 'dst': dst, 'reason':'OCR Unknown', 'phase':'2c', 'ts': now(), 'status':'error', 'error':'dst exists'})
        mv_error += 1
        continue
    try:
        shutil.move(src, dst)
        move_entries.append({'src': src, 'dst': dst, 'reason':'OCR Unknown', 'phase':'2c', 'ts': now(), 'status':'success'})
        mv_success += 1
    except Exception as e:
        move_entries.append({'src': src, 'dst': dst, 'reason':'OCR Unknown', 'phase':'2c', 'ts': now(), 'status':'error', 'error':str(e)})
        mv_error += 1

with open(MOVE_LOG, 'w', encoding='utf-8') as f:
    json.dump({
        'phase':'2c-move',
        'executed_at': now(),
        'total': len(move_entries),
        'success': mv_success,
        'errors': mv_error,
        'entries': move_entries,
    }, f, ensure_ascii=False, indent=2)

print(f'[2단계 이동] success={mv_success} / errors={mv_error}')

# === 3단계: 최종 검증 ===
src_count = len([f for f in os.listdir(SRC_DIR) if f.lower().endswith('.pdf')])
dst_count = len([f for f in os.listdir(DST_DIR) if f.lower().endswith('.pdf')])
print(f'\n=== 최종 검증 ===')
print(f'2_sensor (ready):    {src_count}개 (기대 110)')
print(f'2_sensor (filtered): {dst_count}개 (기대 27)')
print(f'합계: {src_count + dst_count} (기대 137)')
print(f'\n롤백 로그: {ROLLBACK_LOG}')
print(f'이동 로그: {MOVE_LOG}')
