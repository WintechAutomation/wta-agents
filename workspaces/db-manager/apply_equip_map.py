"""erp_data.json에 equip_map 추가 (BOM 기반 품목별 프로젝트 이력 → 장비유형 추출)"""
import sys, io, json, os, time
import urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from dotenv import load_dotenv
load_dotenv('C:/MES/backend/.env')
import jwt

# ── JWT 토큰 생성 ──────────────────────────────────────────────
secret = os.getenv('JWT_SECRET')
payload = {
    'user_id': 10, 'username': 'hjcho', 'is_staff': True,
    'type': 'access', 'iss': 'mes-backend',
    'iat': int(time.time()), 'exp': int(time.time()) + 3600
}
token = jwt.encode(payload, secret, algorithm='HS256')

# ── equip-map API 호출 ─────────────────────────────────────────
print('equip-map API 호출 중...')
req = urllib.request.Request(
    'http://localhost:8100/api/erp/inventory/equip-map',
    headers={'Authorization': f'Bearer {token}'}
)
with urllib.request.urlopen(req, timeout=180) as resp:
    api_data = json.loads(resp.read().decode('utf-8'))

equip_map_raw = api_data['data']['equip_map']
print(f'equip-map 품목 수: {len(equip_map_raw):,}')

# ── 장비유형 키워드 → 분류 매핑 ──────────────────────────────────
EQUIP_TYPES = {
    '프레스': ['프레스', 'Press', 'PRESS', 'Dorst', 'dorst', 'EP16', 'Kob', 'kob', '기후 프레스'],
    '교정': ['교정기', '교정'],
    '핸들러': ['핸들러', 'Handler', 'HIM'],
    'CVD': ['CVD'],
    'PVD': ['PVD'],
    '검사기': ['검사기', 'F2 #', 'F검사기'],
    '소결': ['소결취출기', '소결 #', '소결#', ' 소결'],
    '포장기': ['포장기'],
    '트랙크코더': ['트랙크코더', '트랙크', 'Traque'],
    'CBN': ['CBN'],
    '알사기': ['알사기', '알사'],
    '호닝형상': ['호닝', '형상기'],
}

def extract_equip_types(pjt_names):
    """프로젝트명 목록에서 장비유형 추출"""
    found = set()
    for pjt in pjt_names:
        if not pjt:
            continue
        for etype, keywords in EQUIP_TYPES.items():
            for kw in keywords:
                if kw in pjt:
                    found.add(etype)
                    break
    return sorted(found)

# ── item_cd → [장비유형, ...] 변환 ──────────────────────────────
equip_map = {}
for item_cd, pjt_names in equip_map_raw.items():
    etypes = extract_equip_types(pjt_names)
    if etypes:
        equip_map[item_cd] = etypes

print(f'장비유형 매핑된 품목 수: {len(equip_map):,}')

# 샘플 출력
sample = list(equip_map.items())[:5]
for k, v in sample:
    print(f'  {k}: {v}')

# ── 중간 저장 (equip_map만) ──────────────────────────────────────
out_map = 'C:/MES/wta-agents/workspaces/db-manager/equip_map.json'
with open(out_map, 'w', encoding='utf-8') as f:
    json.dump(equip_map, f, ensure_ascii=False, indent=2)
print(f'equip_map 저장: {out_map}')

# ── erp_data.json 로드 및 업데이트 ──────────────────────────────
erp_data_path = 'C:/MES/wta-agents/reports/김근형/erp_data.json'
print(f'erp_data.json 로드 중...')
with open(erp_data_path, encoding='utf-8') as f:
    erp_data = json.load(f)

updated = 0
not_found = 0
for row in erp_data['data']:
    item_cd = row[1]  # [1] = item_cd
    if item_cd in equip_map:
        row[9] = equip_map[item_cd]  # [9] = 장비유형 (기존 단일값 → 배열)
        updated += 1
    else:
        not_found += 1

print(f'업데이트: {updated:,}건, 미매핑: {not_found:,}건')

# ── 저장 ─────────────────────────────────────────────────────────
with open(erp_data_path, 'w', encoding='utf-8') as f:
    json.dump(erp_data, f, ensure_ascii=False, indent=2)
print(f'저장 완료: {erp_data_path}')
print('완료')
