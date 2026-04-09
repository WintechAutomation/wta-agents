# -*- coding: utf-8 -*-
"""ERP 현재고현황 전체 리스트 — 규칙서(config/erp-inventory-rules.md) 적용
핵심: 품목을 리스트에서 제거하지 않음! 장비유형(r[9])만 수정.
JS recalcAll()이 장비유형 기반으로 사용예정/수량/금액을 동적 계산함.
"""
import sys, io, json, re
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

for row in data:
    item_cd = row[1]
    equip = row[9]

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

    # 규칙 2-5: 프로젝트 예외 미배정 — 장비유형 원본 유지

print(f'제외(사용예정 비움): {exclude_applied}건, 핸들러 단독: {handler_excluded}건, 핸들러 제거: {handler_removed}건')
print(f'전체 건수 유지: {len(data)}건')

# 재고금액 내림차순 정렬
data.sort(key=lambda x: x[4] if x[4] else 0, reverse=True)

# Re-number
for i, row in enumerate(data):
    row[0] = i + 1

data_str = json.dumps(data, ensure_ascii=False)

# HTML 교체 (데이터만 교체, 건수/금액은 원본 유지)
new_html = html.replace(m.group(0), f'const data = {data_str};')

# 제목만 변경
new_html = new_html.replace(
    '<title>ERP 현재고현황 및 구매진행현황</title>',
    '<title>ERP 현재고현황 및 구매진행현황 (규칙 적용)</title>'
)

outpath = f'{base}/ERP_현재고_구매진행_전체.html'
with open(outpath, 'w', encoding='utf-8') as f:
    f.write(new_html)

print(f'HTML 생성 완료: {outpath}')

# --- 적용 확인 ---
print('\n--- 규칙 적용 확인 ---')

# 제외 확인 (장비유형 빈배열)
check_excluded = ['MADHT1505BA1', 'RLHW-70-37', 'MDDLN45BL', 'E2E-C04S12-WC-C1', '110XI4300DPI+REWIND', 'NUVO-8108GC-XL']
for cd in check_excluded:
    for r in data:
        if r[1] == cd:
            status = '장비유형 비움 ✓' if r[9] == [] else f'오류: {r[9]}'
            print(f'제외 {cd}: {status}')

# 사용예정 유지 품목
check_apply = ['MSMF042L1T2', 'ZT610-600DPI+REWIND', 'EZI-EC-ALL-42L-A-R']
for cd in check_apply:
    for r in data:
        if r[1] == cd:
            print(f'유지 #{r[0]} {cd}: 장비={r[9]}')

# 예외 미배정
for cd in ['SS-540A-V1', '55348']:
    for r in data:
        if r[1] == cd:
            print(f'예외 #{r[0]} {cd}: 장비={r[9]}, 프로젝트={r[8][:40]}')
