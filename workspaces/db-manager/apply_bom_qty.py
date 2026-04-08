"""BOM 단위소요량을 erp_data.json에 추가 (인덱스 [14] = qty_per_unit)"""
import sys, io, json, os, time
import urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from dotenv import load_dotenv
load_dotenv('C:/MES/backend/.env')
import jwt

secret = os.getenv('JWT_SECRET')
payload = {
    'user_id': 10, 'username': 'hjcho', 'is_staff': True,
    'type': 'access', 'iss': 'mes-backend',
    'iat': int(time.time()), 'exp': int(time.time()) + 3600
}
token = jwt.encode(payload, secret, algorithm='HS256')

# ── bom-qty API 호출 ────────────────────────────────────────────
print('bom-qty API 호출 중...')
req = urllib.request.Request(
    'http://localhost:8100/api/erp/inventory/bom-qty',
    headers={'Authorization': f'Bearer {token}'}
)
with urllib.request.urlopen(req, timeout=120) as resp:
    api_data = json.loads(resp.read().decode('utf-8'))

qty_map = api_data['data']['qty_map']
print(f'BOM 단위소요량 품목 수: {len(qty_map):,}')

# 샘플 출력
sample_items = ['03-11-001-2', '03-11-002-0', '01-00-002-0']
for k in sample_items:
    if k in qty_map:
        print(f'  {k}: {qty_map[k]}')

# ── 중간 저장 ───────────────────────────────────────────────────
out_path = 'C:/MES/wta-agents/workspaces/db-manager/bom_qty_map.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(qty_map, f, ensure_ascii=False, indent=2)
print(f'qty_map 저장: {out_path}')

# ── erp_data.json 업데이트 ──────────────────────────────────────
erp_data_path = 'C:/MES/wta-agents/reports/김근형/erp_data.json'
print('erp_data.json 로드 중...')
with open(erp_data_path, encoding='utf-8') as f:
    erp_data = json.load(f)

# 헤더 확인 (현재 길이)
if erp_data['data']:
    print(f'현재 행 길이: {len(erp_data["data"][0])}')

updated = 0
for row in erp_data['data']:
    item_cd = row[1]
    q = qty_map.get(item_cd)
    # [14] = qty_per_unit (max_qty 기준 — 가장 많이 쓰이는 1대당 소요량)
    if len(row) > 14:
        row[14] = q['max_qty'] if q else None
    else:
        row.append(q['max_qty'] if q else None)
    if q:
        updated += 1

print(f'업데이트: {updated:,}건')

with open(erp_data_path, 'w', encoding='utf-8') as f:
    json.dump(erp_data, f, ensure_ascii=False, indent=2)
print(f'저장 완료: {erp_data_path}')
print('완료')
