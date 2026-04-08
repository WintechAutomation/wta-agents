"""erp_data.json 프로젝트명/발주일 검증 및 수정
우선순위: 실발주(last_po_dt) > 재고감안(issue) > 비공용자재실발주(real_po) > 계획(plan)
"""
import sys, io, os, time, json, urllib.request, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from dotenv import load_dotenv
load_dotenv('C:/MES/backend/.env')
import jwt

secret = os.getenv('JWT_SECRET')
token = jwt.encode({'user_id':10,'username':'hjcho','is_staff':True,'type':'access',
    'iss':'mes-backend','iat':int(time.time()),'exp':int(time.time())+3600}, secret, algorithm='HS256')

# ── full-status API 재호출 (최신 데이터) ─────────────────────────
print('full-status API 호출 중...')
req = urllib.request.Request(
    'http://localhost:8100/api/erp/inventory/full-status',
    headers={'Authorization': f'Bearer {token}'}
)
with urllib.request.urlopen(req, timeout=180) as resp:
    api_data = json.loads(resp.read().decode('utf-8'))

full_items = {it['item_cd']: it for it in api_data['data']['items']}
print(f'full-status 조회: {len(full_items):,}건')

# ── erp_data.json 로드 ────────────────────────────────────────────
erp_path = 'C:/MES/wta-agents/reports/김근형/erp_data.json'
with open(erp_path, encoding='utf-8') as f:
    erp_data = json.load(f)
print(f'erp_data.json: {len(erp_data["data"]):,}건')

# ── 우선순위 기반 날짜/프로젝트명 결정 ────────────────────────────
def pick_pjt(it):
    """실발주 우선 → 비공용자재실발주 vs 계획(최신기준) → 재고감안 → 계획 폴백
    - 1순위: frDate 이후 실발주
    - 2순위: 비공용자재 실발주 vs 구매계획 중 날짜가 더 최신인 것
    - 3순위: 재고감안 (MAD111T)
    - 4순위: 구매계획 폴백
    이유: plan_dt가 real_po_dt보다 최신이면 현재 재고의 용도가 계획 기준이 맞음
    """
    # 1순위: 실발주 (frDate 이후, 최신 기준)
    if it.get('has_po') and it.get('last_po_dt'):
        return it['last_po_dt'], it.get('last_pjt_name') or it.get('last_pjt_no')

    # 2순위: 비공용자재 실발주 vs 구매계획 — 날짜 최신 기준
    real_dt   = it.get('real_po_dt') or ''
    real_pjt  = it.get('real_pjt_name') if it.get('real_po_dt') else None
    plan_dt   = it.get('last_plan_dt') or ''
    plan_pjt  = it.get('plan_pjt_name') if it.get('has_plan') else None

    if real_pjt and plan_pjt:
        # 둘 다 있으면 날짜 최신 우선
        if plan_dt >= real_dt:
            return plan_dt, plan_pjt
        else:
            return real_dt, real_pjt
    elif real_pjt:
        return real_dt, real_pjt
    elif plan_pjt:
        return plan_dt, plan_pjt

    # 3순위: 재고감안 (MAD111T — 공용자재 보조)
    if it.get('has_issue') and it.get('issue_pjt_name'):
        return plan_dt, it['issue_pjt_name']

    return '', None

changed = 0
no_match = 0
priority_stats = {'po':0, 'issue':0, 'real_po':0, 'plan':0, 'none':0}

for row in erp_data['data']:
    item_cd = row[1]
    it = full_items.get(item_cd)
    if not it:
        no_match += 1
        continue

    dt, pjt = pick_pjt(it)

    # 우선순위 통계
    if it.get('has_po') and it.get('last_po_dt'):
        priority_stats['po'] += 1
    elif it.get('has_issue') and it.get('issue_pjt_name'):
        priority_stats['issue'] += 1
    elif it.get('real_po_dt') and it.get('real_pjt_name'):
        priority_stats['real_po'] += 1
    elif it.get('has_plan') and it.get('plan_pjt_name'):
        priority_stats['plan'] += 1
    else:
        priority_stats['none'] += 1

    old_dt  = row[7] if len(row) > 7 else None
    old_pjt = row[8] if len(row) > 8 else None

    if old_dt != dt or old_pjt != pjt:
        # 길이 보정
        while len(row) <= 8:
            row.append(None)
        row[7] = dt
        row[8] = pjt
        changed += 1

print(f'\n업데이트: {changed:,}건, 미매칭: {no_match:,}건')
print('우선순위 분포:')
for k, v in priority_stats.items():
    print(f'  {k}: {v:,}건')

# MCDHT3520BA1 확인
for row in erp_data['data']:
    if row[1] == 'MCDHT3520BA1':
        print(f'\nMCDHT3520BA1 검증: [7]={row[7]}, [8]={row[8]}')
        it = full_items.get('MCDHT3520BA1', {})
        print(f'  has_po={it.get("has_po")}, last_po_dt={it.get("last_po_dt")}')
        print(f'  has_issue={it.get("has_issue")}, issue_pjt={it.get("issue_pjt_name")}')
        print(f'  real_po_dt={it.get("real_po_dt")}, real_pjt={it.get("real_pjt_name")}')
        print(f'  has_plan={it.get("has_plan")}, plan_pjt={it.get("plan_pjt_name")}')

with open(erp_path, 'w', encoding='utf-8') as f:
    json.dump(erp_data, f, ensure_ascii=False, indent=2)
print('\nerp_data.json 저장 완료')
