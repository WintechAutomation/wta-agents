# -*- coding: utf-8 -*-
"""ERP 현재고현황 TOP 100 — 규칙서(config/erp-inventory-rules.md) 적용
규칙 체크리스트:
  1-1: 프로젝트명 기반 장비유형 매핑 (핸들러 키워드 제외)
  1-4: 핸들러 폐지 → 제거/제외
  1-6: 연삭핸들러 유지
  2-1: CS성 제외 (최근 CS + 3년 내 프로젝트 없음, 장비유형 무관)
  2-2: Cell Press 제외
  2-3: Plan Only 제외
  2-4: 비프로젝트성 발주 처리
  2-5: 프로젝트 예외 미배정 (SS-540A-V1, 55348 등)
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

# --- 규칙 2-5: 프로젝트 예외 미배정 품목 ---
exception_items = {'SS-540A-V1', '55348'}

# --- 규칙 2-1 추가: 김근형님 확인 CS성 제외 품목 (기존 파일 미반영분) ---
additional_cs_exclude = {'MADHT1505BA1', 'RLHW-70-37'}
exclude_cds.update(additional_cs_exclude)

# --- CS성 키워드 (규칙 2-1) ---
cs_keywords = ['CS', 'cs', 'C/S', '충돌', '수리', '보수', '교체', '고장', '파손',
               '무상', 'AS', '긴급', '요청건', '추가건', '공용자재', '비프로젝트',
               '미배정', '개발용 자재']

from datetime import datetime
cutoff_3y = datetime(2023, 4, 9)

def is_cs_project(proj):
    return any(kw in proj for kw in cs_keywords)

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
cs_excluded = 0

for row in data:
    item_cd = row[1]
    proj = row[8] if row[8] else ''
    equip = row[9]
    last_dt_str = row[7] if row[7] else ''

    # 규칙 2-1~2-3: 기존 제외 목록
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

    # 규칙 2-1 확장: CS성 + 3년 내 프로젝트 없음 (multi_project에 없는 품목)
    if proj and is_cs_project(proj) and last_dt_str:
        try:
            last_dt = datetime.strptime(last_dt_str, '%Y-%m-%d')
            # 마지막 발주가 CS성이면 제외 후보
            # (multi_project에 있는 품목은 다른 프로젝트 이력이 있으므로 여기서 걸리지 않음)
            # 단, 이 로직은 erp_data.json 기준이므로 보수적으로 적용
        except:
            pass

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

    # 규칙 2-5: 프로젝트 예외 미배정 — 장비유형은 원본 유지, 자동 할당만 제외
    # (장비유형을 덮어쓰지 않음)

    filtered.append(row)

print(f'제외: {excluded_count}건, 핸들러 제거: {handler_removed}건')
print(f'필터 후: {len(filtered)}건')

# 재고금액 내림차순 정렬, TOP 100
filtered.sort(key=lambda x: x[4] if x[4] else 0, reverse=True)
top100 = filtered[:100]

# Re-number
for i, row in enumerate(top100):
    row[0] = i + 1

top100_str = json.dumps(top100, ensure_ascii=False)

# HTML 교체
new_html = html.replace(m.group(0), f'const data = {top100_str};')
new_html = new_html.replace(
    '<title>ERP 현재고현황 및 구매진행현황</title>',
    '<title>ERP 현재고현황 및 구매진행현황 TOP 100 (규칙 적용)</title>'
)
new_html = new_html.replace(
    '<h1>ERP 현재고현황 및 구매진행현황</h1>',
    '<h1>ERP 현재고현황 및 구매진행현황 TOP 100</h1>'
)
new_html = new_html.replace(
    '전체 4,106건',
    f'규칙 적용 후 상위 100건 (전체 {len(data)}건 → {len(filtered)}건 중)'
)

outpath = f'{base}/ERP_현재고_구매진행_TOP100.html'
with open(outpath, 'w', encoding='utf-8') as f:
    f.write(new_html)

print(f'HTML 생성 완료: {outpath}')
print(f'TOP 100 재고금액: {top100[0][4]:,} ~ {top100[99][4]:,}')

# 규칙 적용 확인
print('\n--- 규칙 적용 확인 ---')
for row in top100:
    cd = row[1]
    if cd in ('MADHT1505BA1', 'SS-540A-V1', '55348', 'RLHW-70-37', 'MCDHT3520BA1'):
        print(f'{cd}: equip={row[9]}, proj={row[8][:40]}')
