# -*- coding: utf-8 -*-
"""ERP 현재고현황 전체 리스트 — 규칙서(config/erp-inventory-rules.md) 적용
핵심: 품목을 리스트에서 제거하지 않음! 장비유형(r[9])만 수정.
JS recalcAll()이 장비유형 기반으로 사용예정/수량/금액을 동적 계산함.
추가: 프로젝트 제외 키워드(개조/개발/판매/무상 등)에 걸리는 품목 → 비제외 프로젝트로 변경
"""
import sys, io, json, re
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

base = r'C:\MES\wta-agents\reports\김근형'

# --- 제외 품목 수집 (규칙 2-1~2-3: 사용예정에서 제외, 리스트 유지) ---
with open(f'{base}/cs_type_items.json', 'r', encoding='utf-8') as f:
    cs_type = json.load(f)
with open(f'{base}/cs_only_items.json', 'r', encoding='utf-8') as f:
    cs_only = json.load(f)
with open(f'{base}/cell_press_removed.json', 'r', encoding='utf-8') as f:
    cell_press = json.load(f)
with open(f'{base}/plan_only_items.json', 'r', encoding='utf-8') as f:
    plan_only = json.load(f)

exclude_cds = set()
for src in [cs_type, cs_only, cell_press, plan_only]:
    items_list = src.get('items', src) if isinstance(src, dict) else src
    for it in items_list:
        exclude_cds.add(it.get('item_cd', '') if isinstance(it, dict) else '')

# 규칙 2-1 추가 CS성 제외
additional_cs_exclude = {'MADHT1505BA1', 'RLHW-70-37'}
exclude_cds.update(additional_cs_exclude)

# 3년 경과 제외 (2026-04-09 김근형님 확인)
expired_exclude = {'MDDLN45BL', 'E2E-C04S12-WC-C1', '110XI4300DPI+REWIND', 'NUVO-8108GC-XL'}
exclude_cds.update(expired_exclude)

# --- multi_project 로드 (프로젝트 변경용) ---
with open(f'{base}/multi_project_items.json', 'r', encoding='utf-8') as f:
    multi = json.load(f)
multi_dict = {it['item_cd']: it for it in multi['items']}

# JS EXCLUDE_PJT 키워드 (recalcAll에서 사용예정 제외하는 키워드)
JS_EXCLUDE_PJT = ['개발', '판매', '무상', '교체', '개조', '부품', '수리', '소모품', '소모성']
cutoff_3y = datetime(2023, 4, 9)

def find_alt_project(item_cd):
    """JS 제외 키워드에 안 걸리는 3년내 최신 프로젝트 찾기"""
    mi = multi_dict.get(item_cd)
    if not mi:
        return None
    for po in mi.get('po_history', []):
        pjt = po.get('pjt_name', '')
        po_dt = po.get('po_dt', '')
        if any(kw in pjt for kw in JS_EXCLUDE_PJT):
            continue
        # 공용자재/비프로젝트도 제외
        if any(kw in pjt for kw in ['공용자재', '비프로젝트', '미배정']):
            continue
        try:
            dt = datetime.strptime(po_dt[:10], '%Y-%m-%d')
            if dt >= cutoff_3y:
                return pjt
        except:
            pass
    return None

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

# --- 규칙 적용 (리스트에서 제거하지 않음, 장비유형만 수정) ---
handler_removed = 0
handler_excluded = 0
exclude_applied = 0
proj_changed = 0

for row in data:
    item_cd = row[1]
    equip = row[9]
    proj = row[8] if row[8] else ''

    # 제외 품목 → 장비유형 빈배열 (JS가 사용예정 0 처리)
    if item_cd in exclude_cds:
        row[9] = []
        exclude_applied += 1
        continue

    # 규칙 1-4: 핸들러 단독 → 장비유형 빈배열
    if isinstance(equip, list) and equip == ['핸들러']:
        row[9] = []
        handler_excluded += 1
        continue
    if isinstance(equip, str) and equip.strip() == '핸들러':
        row[9] = []
        handler_excluded += 1
        continue

    # 규칙 1-4: 핸들러 제거 (복합 등록)
    if isinstance(equip, list) and '핸들러' in equip:
        new_equip = [e for e in equip if e != '핸들러']
        if not new_equip:
            row[9] = []
            handler_excluded += 1
            continue
        row[9] = new_equip
        handler_removed += 1

    # 규칙 1-6: 연삭핸들러 형식 수정
    if isinstance(equip, str) and '연삭핸들러' in equip:
        row[9] = ['연삭핸들러']

    # 프로젝트 제외 키워드 → 비제외 프로젝트로 변경
    if proj and any(kw in proj for kw in JS_EXCLUDE_PJT):
        cur_equip = row[9]
        if cur_equip and cur_equip != []:
            alt = find_alt_project(item_cd)
            if alt:
                row[8] = alt
                proj_changed += 1

    # 규칙 2-5: 프로젝트 예외 미배정 — 장비유형 원본 유지

print(f'제외(사용예정 비움): {exclude_applied}건, 핸들러 단독: {handler_excluded}건, 핸들러 제거: {handler_removed}건')
print(f'프로젝트 변경: {proj_changed}건')
print(f'전체 건수 유지: {len(data)}건')

# 재고금액 내림차순 정렬
data.sort(key=lambda x: x[4] if x[4] else 0, reverse=True)

# Re-number
for i, row in enumerate(data):
    row[0] = i + 1

# --- 전체 리스트 HTML ---
data_str = json.dumps(data, ensure_ascii=False)
new_html = html.replace(m.group(0), f'const data = {data_str};')
new_html = new_html.replace(
    '<title>ERP 현재고현황 및 구매진행현황</title>',
    '<title>ERP 현재고현황 및 구매진행현황 (규칙 적용)</title>'
)

outpath = f'{base}/ERP_현재고_구매진행_전체.html'
with open(outpath, 'w', encoding='utf-8') as f:
    f.write(new_html)
print(f'전체 HTML 생성: {outpath}')

# --- TOP 200 리스트 HTML ---
top200 = data[:200]
top200_str = json.dumps(top200, ensure_ascii=False)
top200_html = html.replace(m.group(0), f'const data = {top200_str};')
top200_html = top200_html.replace(
    '<title>ERP 현재고현황 및 구매진행현황</title>',
    '<title>ERP 현재고현황 및 구매진행현황 TOP 200 (규칙 적용)</title>'
)
top200_html = top200_html.replace(
    '<h1>ERP 현재고현황 및 구매진행현황</h1>',
    '<h1>ERP 현재고현황 및 구매진행현황 TOP 200</h1>'
)

outpath200 = f'{base}/ERP_현재고_구매진행_TOP200.html'
with open(outpath200, 'w', encoding='utf-8') as f:
    f.write(top200_html)
print(f'TOP 200 HTML 생성: {outpath200}')
print(f'TOP 200 재고금액: {top200[0][4]:,} ~ {top200[199][4]:,}')

# --- 적용 확인 ---
print('\n--- 규칙 적용 확인 ---')

# 프로젝트 변경 확인
proj_check = ['ZT610-600DPI+REWIND', 'EZI-EC-42M-A', 'EZI-EC-ALL-42XL-A-R', 'ZT610-300DPI+REWIND', 'HTR1010AC7S-172']
for cd in proj_check:
    for r in data:
        if r[1] == cd:
            print(f'프로젝트변경 #{r[0]} {cd}: proj={r[8][:45]}, 장비={r[9]}')

# 사용예정 유지 품목
for cd in ['MSMF042L1T2', 'EZI-EC-ALL-42L-A-R']:
    for r in data:
        if r[1] == cd:
            print(f'유지 #{r[0]} {cd}: 장비={r[9]}')

# 예외 미배정
for cd in ['SS-540A-V1', '55348']:
    for r in data:
        if r[1] == cd:
            print(f'예외 #{r[0]} {cd}: 장비={r[9]}, proj={r[8][:40]}')
