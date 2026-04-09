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

# Z축건 등 CS성 프로젝트 제외 (2026-04-09 김근형님 확인)
cs_project_exclude = {'MBDHT2510BA1'}  # 최근이력 CS, 프로젝트 "Z축건"
exclude_cds.update(cs_project_exclude)

# --- multi_project 로드 (프로젝트 변경용) ---
with open(f'{base}/multi_project_items.json', 'r', encoding='utf-8') as f:
    multi = json.load(f)
multi_dict = {it['item_cd']: it for it in multi['items']}

# JS EXCLUDE_PJT 키워드 (recalcAll에서 사용예정 제외하는 키워드)
JS_EXCLUDE_PJT = ['개발', '판매', '무상', '교체', '개조', '부품', '수리', '소모품', '소모성']
cutoff_3y = datetime(2023, 3, 1)  # 3년+1개월 여유 (경계선 품목 누락 방지)

# --- 수동 오버라이드 (김근형님 확인) ---
# 장비유형 수정
EQUIP_OVERRIDE = {
    '55348': ['호닝형상'],  # 호닝형상 전용 품목, 검사기 분류 오류 수정
    '50-01-07-0': ['PVD', '검사기', '포장기', '프레스'],  # 김근형님 직접 지정 (CVD 제외)
}
# 프로젝트 수동 지정 (multi_project에 없거나 cutoff 경계선)
PROJ_OVERRIDE = {
    'MSMF042L1T2': '아크시스 프레스 #2 (Kob,NSX2-25A)',  # 2023-04-05 발주, cutoff 경계선
}
# 제외 목록에서 빼야 할 품목 (범용 부품이 잘못 제외된 경우)
EXCLUDE_WHITELIST = {
    'EZI-EC-42M-A',  # Cell Press 제외에 잘못 포함, 실제 CVD/PVD/검사기/소결/포장기 범용
}

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

# --- 원본 데이터 + HTML 템플릿 로드 ---
# erp_data.json에서 원본 데이터 로드
with open(f'{base}/erp_data.json', 'r', encoding='utf-8') as f:
    erp_raw = json.load(f)
data = erp_raw['data']

# HTML 템플릿 (기존 생성 파일에서 JS/레이아웃 재사용)
src_html = f'{base}/ERP_현재고_구매진행_전체.html'
with open(src_html, 'r', encoding='utf-8') as f:
    html = f.read()

m = re.search(r'const data = (\[\[.+?\]\]);', html, re.DOTALL)
if not m:
    print("ERROR: data array not found in template HTML")
    sys.exit(1)
print(f'전체 데이터: {len(data)}건')

# --- 규칙 적용 (리스트에서 제거하지 않음, 장비유형만 수정) ---
handler_removed = 0
handler_excluded = 0
exclude_applied = 0
proj_changed = 0

equip_overridden = 0
proj_overridden = 0

for row in data:
    item_cd = row[1]
    equip = row[9]
    proj = row[8] if row[8] else ''

    # 수동 장비유형 오버라이드 (제외보다 먼저)
    if item_cd in EQUIP_OVERRIDE:
        row[9] = EQUIP_OVERRIDE[item_cd]
        equip = row[9]
        equip_overridden += 1

    # 수동 프로젝트 오버라이드
    if item_cd in PROJ_OVERRIDE:
        row[8] = PROJ_OVERRIDE[item_cd]
        proj = row[8]
        proj_overridden += 1

    # 제외 화이트리스트 (잘못 제외된 범용 품목 복원)
    if item_cd in EXCLUDE_WHITELIST:
        pass  # 제외 건너뜀, 장비유형 유지
    # 제외 품목 → 장비유형 빈배열 (JS가 사용예정 0 처리)
    elif item_cd in exclude_cds:
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
print(f'장비유형 오버라이드: {equip_overridden}건, 프로젝트 오버라이드: {proj_overridden}건')
print(f'프로젝트 변경(자동): {proj_changed}건')
print(f'전체 건수 유지: {len(data)}건')

# 재고금액 내림차순 정렬
data.sort(key=lambda x: x[4] if x[4] else 0, reverse=True)

# Re-number
for i, row in enumerate(data):
    row[0] = i + 1

# --- 다수 장비 범용 품목 수집 (JS 프로젝트 필터링 건너뛸 품목) ---
multi_equip_items = set()
for row in data:
    equip = row[9]
    if isinstance(equip, list) and len(equip) >= 2:
        multi_equip_items.add(row[1])
print(f'다수 장비 범용 품목 (JS 필터링 제외): {len(multi_equip_items)}건')

# --- 전체 리스트 HTML ---
data_str = json.dumps(data, ensure_ascii=False)
new_html = html.replace(m.group(0), f'const data = {data_str};')
new_html = new_html.replace(
    '<title>ERP 현재고현황 및 구매진행현황</title>',
    '<title>ERP 현재고현황 및 구매진행현황 (규칙 적용)</title>'
)

# JS 패치: 다수 장비 범용 품목은 프로젝트 기반 필터링 건너뜀
multi_equip_js = json.dumps(sorted(multi_equip_items), ensure_ascii=False)
js_patch_old = '// 프로젝트명에서 장비유형 추출 → BOM 유형과 교차 (실제 사용처만 반영)'
js_patch_new = f'const MULTI_EQUIP = new Set({multi_equip_js});\n    // 프로젝트명에서 장비유형 추출 → BOM 유형과 교차 (다수 장비 범용 품목 제외)'
new_html = new_html.replace(js_patch_old, js_patch_new)

# 프로젝트 필터링 조건에 MULTI_EQUIP 체크 추가
new_html = new_html.replace(
    'if (types.length > 1 && r[8]) {',
    'if (types.length > 1 && r[8] && !MULTI_EQUIP.has(r[1])) {'
)

# 네비게이션 버튼 정의
btn_style = "background:#fff;color:#1a237e;border:none;padding:6px 14px;border-radius:20px;font-size:9pt;cursor:pointer;font-weight:700;font-family:'Malgun Gothic',sans-serif;margin-left:4px;"
orig_btn = """<button onclick="location.href='erp_현재고_TOP20'" style="background:#fff;color:#1a237e;border:none;padding:6px 14px;border-radius:20px;font-size:9pt;cursor:pointer;font-weight:700;font-family:'Malgun Gothic',sans-serif;">TOP 20 &rarr;</button>"""
nav_full = f'<button onclick="location.href=\'erp_현재고_TOP20\'" style="{btn_style}">TOP 20 &rarr;</button><button onclick="location.href=\'ERP_현재고_구매진행_TOP200\'" style="{btn_style}">TOP 200 &rarr;</button>'
nav_top200 = f'<button onclick="location.href=\'ERP_현재고_구매진행_전체\'" style="{btn_style}">&larr; 전체</button><button onclick="location.href=\'erp_현재고_TOP20\'" style="{btn_style}">TOP 20 &rarr;</button>'
nav_top20 = f'<button onclick="location.href=\'ERP_현재고_구매진행_전체\'" style="{btn_style}">&larr; 전체</button><button onclick="location.href=\'ERP_현재고_구매진행_TOP200\'" style="{btn_style}">&larr; TOP 200</button>'

new_html = new_html.replace(orig_btn, nav_full)

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

# --- TOP 20 리스트 HTML ---
top20 = data[:20]
top20_str = json.dumps(top20, ensure_ascii=False)
top20_html = html.replace(m.group(0), f'const data = {top20_str};')
top20_html = top20_html.replace(
    '<title>ERP 현재고현황 및 구매진행현황</title>',
    '<title>ERP 현재고현황 및 구매진행현황 TOP 20 (규칙 적용)</title>'
)
top20_html = top20_html.replace(
    '<h1>ERP 현재고현황 및 구매진행현황</h1>',
    '<h1>ERP 현재고현황 및 구매진행현황 TOP 20</h1>'
)

outpath20 = f'{base}/ERP_현재고_구매진행_TOP20.html'
with open(outpath20, 'w', encoding='utf-8') as f:
    f.write(top20_html)
# 버튼 링크 호환용 별칭 파일
with open(f'{base}/erp_현재고_TOP20.html', 'w', encoding='utf-8') as f:
    f.write(top20_html)
print(f'TOP 20 HTML 생성: {outpath20}')
print(f'TOP 20 재고금액: {top20[0][4]:,} ~ {top20[19][4]:,}')

# --- 적용 확인 ---
print('\n--- 규칙 적용 확인 ---')

# 프로젝트 변경 확인
proj_check = ['ZT610-600DPI+REWIND', 'EZI-EC-42M-A', 'EZI-EC-ALL-42XL-A-R', 'ZT610-300DPI+REWIND', 'HTR1010AC7S-172']
for cd in proj_check:
    for r in data:
        if r[1] == cd:
            print(f'프로젝트변경 #{r[0]} {cd}: proj={r[8][:45]}, 장비={r[9]}')

# 오버라이드 확인
for cd in ['MSMF042L1T2', 'EZI-EC-ALL-42L-A-R', '55348']:
    for r in data:
        if r[1] == cd:
            print(f'확인 #{r[0]} {cd}: proj={r[8][:45]}, 장비={r[9]}')

# 예외 미배정
for cd in ['SS-540A-V1', '55348']:
    for r in data:
        if r[1] == cd:
            print(f'예외 #{r[0]} {cd}: 장비={r[9]}, proj={r[8][:40]}')
