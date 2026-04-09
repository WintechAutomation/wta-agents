# -*- coding: utf-8 -*-
"""ERP 현재고현황 장비유형 변경 필요 품목 리스트 생성
기준: config/erp-inventory-rules.md (2026-04-09)
"""
import sys, io, json
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

KST = timezone(timedelta(hours=9))
now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M')

base = r'C:\MES\wta-agents\reports\김근형'

# --- 데이터 로드 ---
with open(f'{base}\\erp_data.json', 'r', encoding='utf-8') as f:
    erp = json.load(f)

with open(f'{base}\\multi_project_items.json', 'r', encoding='utf-8') as f:
    mp = json.load(f)

with open(f'{base}\\cs_type_items.json', 'r', encoding='utf-8') as f:
    cs_data = json.load(f)
with open(f'{base}\\cs_only_items.json', 'r', encoding='utf-8') as f:
    cs_only = json.load(f)
with open(f'{base}\\cell_press_removed.json', 'r', encoding='utf-8') as f:
    cell_press = json.load(f)
with open(f'{base}\\plan_only_items.json', 'r', encoding='utf-8') as f:
    plan_only = json.load(f)

erp_data = erp['data']  # list of lists
mp_map = {it['item_cd']: it for it in mp['items']}

# --- 제외 품목 ---
exclude_cds = set()
for src in [cs_data, cs_only, cell_press, plan_only]:
    items_list = src.get('items', src) if isinstance(src, dict) else src
    for it in items_list:
        exclude_cds.add(it.get('item_cd', it) if isinstance(it, dict) else '')

# --- 장비유형 키워드 (규칙 1-1) ---
equip_keywords = {
    '프레스': ['프레스', 'Press', 'press'],
    '소결': ['소결', 'Sintering', 'sintering'],
    'CVD': ['CVD', 'cvd'],
    'PVD': ['PVD', 'pvd', 'UL', 'LUL'],
    '포장기': ['포장기', 'Packing', 'packing', '포장'],
    '검사기': ['검사기', 'Inspection', 'inspection', 'F1', 'F2'],
    '호닝형상': ['호닝', 'HIM', 'Honing', 'honing'],
    '연삭': ['연삭', 'Grinding', 'grinding'],
    'CBN': ['CBN', 'cbn'],
    '마스크자동기': ['마스크', 'Mask', 'mask'],
    '교정': ['교정'],
}

non_project_kw = ['공용자재', '비프로젝트', '무상 자재', '미배정']

def is_non_project(proj_name):
    return any(kw in proj_name for kw in non_project_kw)

def detect_equip(proj_name):
    if not proj_name or is_non_project(proj_name):
        return set()
    detected = set()
    for equip, keywords in equip_keywords.items():
        for kw in keywords:
            if kw in proj_name:
                detected.add(equip)
    return detected

def normalize_equip_types(raw):
    """현재 등록된 장비유형을 정규화 (핸들러 제거, 연삭핸들러 유지)"""
    if isinstance(raw, str):
        result = set()
        if '연삭핸들러' in raw:
            result.add('연삭핸들러')  # 연삭핸들러는 독립 장비유형 유지
        elif '연삭' in raw:
            result.add('연삭')
        if '프레스' in raw and '연삭핸들러' not in raw:
            result.add('프레스')
        if not result and raw.strip():
            result.add(raw)
        return result
    result = set()
    for t in raw:
        if t == '마스크':
            result.add('마스크자동기')
        elif t == '핸들러':
            pass  # 핸들러 제거 (폐지)
        elif t == '연삭핸들러' or '연삭핸들러' in t:
            result.add('연삭핸들러')  # 연삭핸들러는 유지
        else:
            result.add(t)
    return result

def is_handler_only(raw):
    """핸들러만 단독 등록된 품목인지 확인"""
    if isinstance(raw, list):
        return raw == ['핸들러']
    if isinstance(raw, str):
        return raw.strip() == '핸들러'
    return False

def get_raw_changes(raw):
    """핸들러 관련 변경사항 감지"""
    changes = []
    if isinstance(raw, str):
        if '연삭핸들러' in raw:
            changes.append(('형식수정', f'문자열 "{raw}" → 리스트 ["연삭핸들러"]'))
        elif '핸들러' in raw:
            changes.append(('핸들러제거', f'"{raw}" → 핸들러 제거'))
        return changes
    if isinstance(raw, list):
        if '핸들러' in raw and '연삭핸들러' not in raw:
            if raw == ['핸들러']:
                changes.append(('핸들러제외', '핸들러 단독 → 제외 처리'))
            else:
                changes.append(('핸들러제거', '핸들러 제거'))
    return changes

# --- 분석 ---
changes = []

for row in erp_data:
    item_cd = row[1]
    item_nm = row[2]
    stock_qty = row[3]
    stock_amt = row[4]
    last_proj = row[8]
    raw_equip = row[9]

    if item_cd in exclude_cds:
        continue

    # 핸들러만 단독 등록 → 제외 대상 (별도 집계)
    if is_handler_only(raw_equip):
        continue

    # 현재 등록된 장비유형 정규화
    current = normalize_equip_types(raw_equip)

    # 변경 유형 추적
    change_types = []
    new_equip = set(current)
    details = []

    # 원본 equip_types (정규화 전)
    if isinstance(raw_equip, list):
        orig_set = set(raw_equip)
    elif isinstance(raw_equip, str) and raw_equip.strip():
        orig_set = {raw_equip}
    else:
        orig_set = set()

    # 1. 형식/명칭 수정
    if isinstance(raw_equip, str) and raw_equip.strip():
        change_types.append('형식수정')
        details.append(f'문자열 "{raw_equip}" → 리스트 {sorted(current)}')
    elif isinstance(raw_equip, list):
        for t in raw_equip:
            if t == '마스크':
                change_types.append('명칭변경')
                details.append('마스크 → 마스크자동기')
            elif t == '연삭핸들러' or '연삭핸들러' in t:
                pass  # 연삭핸들러는 유지 (변경 아님)

    # 2. 핸들러 → 프레스 통합 (규칙 1-4)
    raw_handler_changes = get_raw_changes(raw_equip)
    for ct, detail in raw_handler_changes:
        if ct not in change_types:
            change_types.append(ct)
        details.append(detail)

    # 3. 발주이력 기반 장비유형 추가 (multi_project items)
    if item_cd in mp_map:
        mp_item = mp_map[item_cd]
        detected = set()
        for proj in mp_item.get('all_projects', []):
            detected.update(detect_equip(proj))
        missing = detected - current
        if missing:
            change_types.append('장비추가')
            new_equip.update(missing)
            for eq in sorted(missing):
                evidence = [p for p in mp_item.get('all_projects', [])
                           if not is_non_project(p) and
                           any(kw in p for kw2 in equip_keywords.get(eq, []) for kw in [kw2])]
                ev_str = evidence[0][:50] if evidence else ''
                details.append(f'+{eq} (근거: {ev_str})')
    else:
        # 단일 프로젝트 품목
        if last_proj and not is_non_project(last_proj):
            detected = detect_equip(last_proj)
            missing = detected - current
            if missing:
                if len(current) == 0 or current == {''}:
                    change_types.append('신규할당')
                else:
                    change_types.append('장비추가')
                new_equip.update(missing)
                for eq in sorted(missing):
                    details.append(f'+{eq} (근거: {last_proj[:50]})')

    if not change_types:
        continue

    # 빈값 정리
    new_equip.discard('')
    current.discard('')

    changes.append({
        'cd': item_cd,
        'nm': item_nm,
        'qty': stock_qty,
        'amt': stock_amt,
        'current': sorted(current) if current else ['(미분류)'],
        'new': sorted(new_equip),
        'types': change_types,
        'details': details,
    })

# 변경유형별 분류
type_order = ['핸들러제거', '형식수정', '명칭변경', '분리', '신규할당', '장비추가']
type_labels = {
    '핸들러제거': '핸들러 제거',
    '핸들러제외': '핸들러 단독 제외',
    '형식수정': '형식 수정 (문자열→리스트)',
    '명칭변경': '명칭 변경',
    '분리': '장비유형 분리',
    '신규할당': '장비유형 신규 할당',
    '장비추가': '장비유형 추가',
}
type_colors = {
    '핸들러제거': '#6f42c1',
    '핸들러제외': '#6f42c1',
    '형식수정': '#6c757d',
    '명칭변경': '#17a2b8',
    '분리': '#fd7e14',
    '신규할당': '#28a745',
    '장비추가': '#dc3545',
}

# 유형별 카운트
type_counts = {}
for c in changes:
    for t in c['types']:
        type_counts[t] = type_counts.get(t, 0) + 1

# 핸들러 단독 제외 건수
handler_only_count = sum(1 for r in erp_data if is_handler_only(r[9]) and r[1] not in exclude_cds)

changes.sort(key=lambda x: x['amt'], reverse=True)

# --- HTML 생성 ---
lines = []
lines.append('<!DOCTYPE html>')
lines.append('<html lang="ko"><head><meta charset="UTF-8">')
lines.append('<title>ERP 장비유형 변경 필요 품목 리스트</title>')
lines.append('<style>')
lines.append("body { font-family: '맑은 고딕', sans-serif; margin: 20px; background: #f5f5f5; }")
lines.append('.header { background: #4472C4; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }')
lines.append('.header h1 { margin: 0; font-size: 22px; }')
lines.append('.header p { margin: 5px 0 0; opacity: 0.9; font-size: 14px; }')
lines.append('.header .rule-ref { margin-top: 8px; padding: 6px 12px; background: rgba(255,255,255,0.15); border-radius: 4px; font-size: 12px; }')
lines.append('.section { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }')
lines.append('.section h2 { color: #4472C4; border-bottom: 2px solid #4472C4; padding-bottom: 8px; font-size: 18px; }')
lines.append('.summary { display: flex; gap: 15px; margin-bottom: 15px; flex-wrap: wrap; }')
lines.append('.summary-card { padding: 12px 20px; border-radius: 6px; text-align: center; min-width: 130px; }')
lines.append('.summary-card .num { font-size: 28px; font-weight: bold; }')
lines.append('.summary-card .label { font-size: 11px; margin-top: 4px; }')
lines.append('.exclude-info { background: #e8f0fe; padding: 10px 15px; border-radius: 6px; font-size: 13px; color: #4472C4; margin-bottom: 15px; }')
lines.append('table { border-collapse: collapse; width: 100%; font-size: 12px; }')
lines.append('th { background: #4472C4; color: white; padding: 8px; text-align: left; position: sticky; top: 0; }')
lines.append('td { padding: 6px 8px; border-bottom: 1px solid #eee; vertical-align: top; }')
lines.append('tr:hover { background: #f5f8ff; }')
lines.append('.tag { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 11px; margin: 1px; }')
lines.append('.tag-current { background: #e2e3e5; color: #383d41; }')
lines.append('.tag-new { background: #d4edda; color: #155724; }')
lines.append('.tag-added { background: #f8d7da; color: #721c24; font-weight: bold; }')
lines.append('.change-type { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px; color: white; margin: 1px; }')
lines.append('.detail { font-size: 11px; color: #666; }')
lines.append('.amt { text-align: right; }')
lines.append('.qty { text-align: center; }')
lines.append('.arrow { color: #4472C4; font-weight: bold; padding: 0 4px; }')
lines.append('.filter-bar { margin-bottom: 15px; }')
lines.append('.filter-btn { padding: 6px 14px; border: 1px solid #ddd; border-radius: 4px; background: white; cursor: pointer; margin: 2px; font-size: 12px; }')
lines.append('.filter-btn.active { background: #4472C4; color: white; border-color: #4472C4; }')
lines.append('</style>')

# JavaScript for filtering
lines.append('<script>')
lines.append('function filterType(type) {')
lines.append('  var rows = document.querySelectorAll("table.main-table tbody tr");')
lines.append('  var btns = document.querySelectorAll(".filter-btn");')
lines.append('  btns.forEach(function(b) { b.classList.remove("active"); });')
lines.append('  if (type === "all") {')
lines.append('    rows.forEach(function(r) { r.style.display = ""; });')
lines.append('    document.querySelector("[data-type=all]").classList.add("active");')
lines.append('  } else {')
lines.append('    rows.forEach(function(r) {')
lines.append('      r.style.display = r.dataset.types && r.dataset.types.indexOf(type) >= 0 ? "" : "none";')
lines.append('    });')
lines.append('    document.querySelector("[data-type=\'" + type + "\']").classList.add("active");')
lines.append('  }')
lines.append('}')
lines.append('</script>')

lines.append('</head><body>')

# Header
lines.append('<div class="header">')
lines.append('  <h1>ERP 현재고현황 장비유형 변경 필요 품목 리스트</h1>')
lines.append(f'  <p>(주)윈텍오토메이션 생산관리팀 | 전체 {len(erp_data)}건 중 변경 필요 {len(changes)}건 | 생성: {now_str}</p>')
lines.append('  <div class="rule-ref">적용 규칙: config/erp-inventory-rules.md (장비유형 분류 표준)</div>')
lines.append('</div>')

# Exclude info
lines.append('<div class="exclude-info">')
lines.append(f'  분석 대상: 전체 {len(erp_data)}건 - 제외 {len(exclude_cds)}건 (CS성/Cell Press/Plan Only) - 핸들러 단독 제외 {handler_only_count}건 = {len(erp_data) - len(exclude_cds) - handler_only_count}건')
lines.append('</div>')

# Summary cards
lines.append('<div class="summary">')
lines.append(f'  <div class="summary-card" style="background:#f0f4fa;"><div class="num" style="color:#4472C4;">{len(changes)}</div><div class="label">전체 변경<br>필요 품목</div></div>')
for t in type_order:
    cnt = type_counts.get(t, 0)
    if cnt > 0:
        color = type_colors[t]
        lines.append(f'  <div class="summary-card" style="background:{color}15;"><div class="num" style="color:{color};">{cnt}</div><div class="label">{type_labels[t]}</div></div>')
lines.append('</div>')

# Filter bar
lines.append('<div class="section">')
lines.append('<h2>변경 필요 품목 상세</h2>')
lines.append('<div class="filter-bar">')
lines.append(f'  <button class="filter-btn active" data-type="all" onclick="filterType(\'all\')">전체 ({len(changes)})</button>')
for t in type_order:
    cnt = type_counts.get(t, 0)
    if cnt > 0:
        lines.append(f'  <button class="filter-btn" data-type="{t}" onclick="filterType(\'{t}\')">{type_labels[t]} ({cnt})</button>')
lines.append('</div>')

# Table
lines.append('<table class="main-table">')
lines.append('<thead><tr><th>#</th><th>품목코드</th><th>품명</th><th class="qty">재고</th><th class="amt">재고금액</th><th>변경유형</th><th>현재</th><th></th><th>변경후</th><th>상세</th></tr></thead>')
lines.append('<tbody>')

for i, item in enumerate(changes):
    cur_tags = ''.join(f'<span class="tag tag-current">{e}</span>' for e in item['current'])
    # 변경후: 추가된 것은 빨간 태그
    new_tags = []
    cur_set = set(item['current'])
    for e in item['new']:
        if e in cur_set and e != '(미분류)':
            new_tags.append(f'<span class="tag tag-new">{e}</span>')
        else:
            new_tags.append(f'<span class="tag tag-added">{e}</span>')
    new_tags_str = ''.join(new_tags)

    type_tags = ''.join(f'<span class="change-type" style="background:{type_colors.get(t,"#999")}">{t}</span>' for t in item['types'])
    detail_str = '<br>'.join(f'<span class="detail">{d[:60]}</span>' for d in item['details'][:3])
    amt = f'{item["amt"]:,}' if item['amt'] else '-'
    types_data = ','.join(item['types'])
    lines.append(f'<tr data-types="{types_data}"><td>{i+1}</td><td>{item["cd"]}</td><td>{item["nm"][:30]}</td><td class="qty">{item["qty"]}</td><td class="amt">{amt}</td><td>{type_tags}</td><td>{cur_tags}</td><td class="arrow">→</td><td>{new_tags_str}</td><td>{detail_str}</td></tr>')

lines.append('</tbody></table></div>')

# Footer
lines.append('<div style="text-align:center;color:#999;font-size:12px;padding:20px;">')
lines.append(f'  (주)윈텍오토메이션 생산관리팀 (AI운영팀) - docs-agent 자동 생성 | {now_str}')
lines.append('</div>')
lines.append('</body></html>')

outpath = f'{base}\\ERP_장비유형_변경필요_품목리스트.html'
with open(outpath, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f'HTML 생성 완료: {outpath}')
print(f'전체 변경 필요: {len(changes)}건')
for t in type_order:
    cnt = type_counts.get(t, 0)
    if cnt > 0:
        print(f'  {type_labels[t]}: {cnt}건')
