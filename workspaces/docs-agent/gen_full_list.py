# -*- coding: utf-8 -*-
"""ERP 현재고현황 전체 리스트 — 규칙서(config/erp-inventory-rules.md) 적용
규칙 체크리스트:
  1-4: 핸들러 폐지 → 제거/제외
  1-6: 연삭핸들러 유지
  2-1: CS성 제외 (최근 CS + 3년 내 프로젝트 없음)
  2-2: Cell Press 제외
  2-3: Plan Only 제외
  2-5: 프로젝트 예외 미배정 (장비유형 원본 유지)
  추가: 3년 경과 제외 4건, 사용예정 적용 3건
"""
import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

base = r'C:\MES\wta-agents\reports\김근형'

# --- 데이터 로드 ---
with open(f'{base}/erp_data.json', 'r', encoding='utf-8') as f:
    erp = json.load(f)

with open(f'{base}/cs_type_items.json', 'r', encoding='utf-8') as f:
    cs_type = json.load(f)
with open(f'{base}/cs_only_items.json', 'r', encoding='utf-8') as f:
    cs_only = json.load(f)
with open(f'{base}/cell_press_removed.json', 'r', encoding='utf-8') as f:
    cell_press = json.load(f)
with open(f'{base}/plan_only_items.json', 'r', encoding='utf-8') as f:
    plan_only = json.load(f)

# --- 제외 품목 수집 (규칙 2-1~2-3) ---
exclude_cds = set()
for src in [cs_type, cs_only, cell_press, plan_only]:
    items_list = src.get('items', src) if isinstance(src, dict) else src
    for it in items_list:
        exclude_cds.add(it.get('item_cd', '') if isinstance(it, dict) else '')

# --- 규칙 2-1 추가: 김근형님 확인 CS성 제외 ---
additional_cs_exclude = {'MADHT1505BA1', 'RLHW-70-37'}
exclude_cds.update(additional_cs_exclude)

# --- 3년 경과 제외 품목 (2026-04-09 김근형님 확인) ---
expired_exclude = {'MDDLN45BL', 'E2E-C04S12-WC-C1', '110XI4300DPI+REWIND', 'NUVO-8108GC-XL'}
exclude_cds.update(expired_exclude)

# --- 규칙 2-5: 프로젝트 예외 미배정 (장비유형 원본 유지) ---
exception_items = {'SS-540A-V1', '55348'}

# --- 사용예정 적용 품목 (3년내 발주이력 기반 수량/금액 계산) ---
with open(f'{base}/multi_project_items.json', 'r', encoding='utf-8') as f:
    multi = json.load(f)
multi_dict = {it['item_cd']: it for it in multi['items']}

from datetime import datetime
cutoff_3y = datetime(2023, 4, 9)
cs_kw_strict = ['CS', 'cs', 'C/S', '충돌', '수리', '보수', '교체', '고장', '파손', '무상', 'AS', '긴급', '요청건']

def calc_expected(item_cd):
    """3년내 비CS 발주 수량 합산 → 예정수량/금액 계산"""
    mi = multi_dict.get(item_cd)
    if not mi:
        return None
    total_qty = 0
    for po in mi.get('po_history', []):
        po_dt = po.get('po_dt', '')
        pjt = po.get('pjt_name', '')
        qty = po.get('po_qty', 0) or 0
        try:
            dt = datetime.strptime(po_dt[:10], '%Y-%m-%d')
            within = dt >= cutoff_3y
        except:
            within = False
        is_cs = any(kw in pjt for kw in cs_kw_strict)
        if within and not is_cs:
            total_qty += qty
    if total_qty == 0:
        return None
    # 예정수량은 재고수량 초과 불가
    stock_qty = mi['stock_qty']
    stock_amt = mi['stock_amt']
    use_qty = min(total_qty, stock_qty)
    unit_price = stock_amt // stock_qty if stock_qty > 0 else 0
    est_amt = unit_price * use_qty
    remain_qty = stock_qty - use_qty
    remain_amt = stock_amt - est_amt
    return {'qty': use_qty, 'amt': est_amt, 'remain_qty': remain_qty, 'remain_amt': remain_amt}

# 사용예정 적용 대상 (3년내 장비발주 있으나 프로젝트 미적용)
apply_expected = {'MSMF042L1T2', 'ZT610-600DPI+REWIND', 'EZI-EC-ALL-42L-A-R'}

# --- 원본 HTML 로드 ---
src_html = f'{base}/erp_재고현황_발주내역.html'
with open(src_html, 'r', encoding='utf-8') as f:
    html = f.read()

m = re.search(r'const data = (\[\[.+?\]\]);', html, re.DOTALL)
if not m:
    print("ERROR: data array not found")
    sys.exit(1)

data = json.loads(m.group(1))
print(f'전체 데이터: {len(data)}건')

# --- 규칙 적용 ---
filtered = []
excluded_count = 0
handler_removed = 0

for row in data:
    item_cd = row[1]
    equip = row[9]

    # 제외 목록 (규칙 2-1~2-3 + CS추가 + 3년경과)
    if item_cd in exclude_cds:
        excluded_count += 1
        continue

    # 규칙 1-4: 핸들러 단독 → 제외
    if isinstance(equip, list) and equip == ['핸들러']:
        excluded_count += 1
        continue
    if isinstance(equip, str) and equip.strip() == '핸들러':
        excluded_count += 1
        continue

    # 규칙 1-4: 핸들러 제거 (복합 등록)
    if isinstance(equip, list) and '핸들러' in equip:
        new_equip = [e for e in equip if e != '핸들러']
        if not new_equip:
            excluded_count += 1
            continue
        row[9] = new_equip
        handler_removed += 1

    # 규칙 1-6: 연삭핸들러 형식 수정
    if isinstance(equip, str) and '연삭핸들러' in equip:
        row[9] = ['연삭핸들러']

    # 규칙 2-5: 장비유형 원본 유지 (자동 할당만 제외)

    # 사용예정 수량/금액 적용
    if item_cd in apply_expected:
        result = calc_expected(item_cd)
        if result:
            row[10] = result['qty']
            row[11] = result['amt']
            row[12] = result['remain_qty']
            row[13] = result['remain_amt']

    filtered.append(row)

print(f'제외: {excluded_count}건, 핸들러 제거: {handler_removed}건')
print(f'필터 후: {len(filtered)}건')

# 재고금액 내림차순 정렬
filtered.sort(key=lambda x: x[4] if x[4] else 0, reverse=True)

# Re-number
for i, row in enumerate(filtered):
    row[0] = i + 1

filtered_str = json.dumps(filtered, ensure_ascii=False)

# HTML 교체
new_html = html.replace(m.group(0), f'const data = {filtered_str};')
new_html = new_html.replace(
    '<title>ERP 현재고현황 및 구매진행현황</title>',
    '<title>ERP 현재고현황 및 구매진행현황 (규칙 적용)</title>'
)
new_html = new_html.replace(
    '<h1>ERP 현재고현황 및 구매진행현황</h1>',
    '<h1>ERP 현재고현황 및 구매진행현황 (규칙 적용)</h1>'
)
new_html = new_html.replace(
    '전체 4,106건',
    f'규칙 적용 후 {len(filtered):,}건 (전체 {len(data):,}건 중 {excluded_count}건 제외)'
)

outpath = f'{base}/ERP_현재고_구매진행_전체.html'
with open(outpath, 'w', encoding='utf-8') as f:
    f.write(new_html)

print(f'HTML 생성 완료: {outpath}')

# --- 적용 확인 ---
print('\n--- 규칙 적용 확인 ---')

# 제외 확인
check_excluded = ['MADHT1505BA1', 'RLHW-70-37', 'MDDLN45BL', 'E2E-C04S12-WC-C1', '110XI4300DPI+REWIND', 'NUVO-8108GC-XL']
for cd in check_excluded:
    found = any(r[1] == cd for r in filtered)
    print(f'제외 {cd}: {"미제외(오류!)" if found else "정상 제외 ✓"}')

# 사용예정 적용 확인
check_apply = ['MSMF042L1T2', 'ZT610-600DPI+REWIND', 'EZI-EC-ALL-42L-A-R']
for cd in check_apply:
    for r in filtered:
        if r[1] == cd:
            print(f'적용 #{r[0]} {cd}: 장비={r[9]}, 예정수량={r[10]}, 예정금액={r[11]:,}, 남는재고={r[12]}, 남는금액={r[13]:,}')

# 예외 미배정 확인
for cd in ['SS-540A-V1', '55348']:
    for r in filtered:
        if r[1] == cd:
            print(f'예외 #{r[0]} {cd}: equip={r[9]}, proj={r[8][:45]}')
