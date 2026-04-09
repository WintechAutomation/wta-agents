# -*- coding: utf-8 -*-
"""장비별 중복/프로젝트 누락 품목 정리 HTML 생성
기준: config/erp-inventory-rules.md (2026-04-09)
"""
import sys, io, json
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

KST = timezone(timedelta(hours=9))
now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M')

# --- 데이터 로드 ---
base = r'C:\MES\wta-agents\reports\김근형'

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

items = mp['items']

# --- 제외 품목 코드 수집 (규칙 2-1 ~ 2-3) ---
exclude_cds = set()
# CS성 품목
for it in cs_data.get('items', []):
    exclude_cds.add(it['item_cd'])
# CS전용 품목
if isinstance(cs_only, dict) and 'items' in cs_only:
    for it in cs_only['items']:
        exclude_cds.add(it['item_cd'])
elif isinstance(cs_only, list):
    for it in cs_only:
        exclude_cds.add(it.get('item_cd', ''))
# Cell Press 제외
if isinstance(cell_press, dict) and 'items' in cell_press:
    for it in cell_press['items']:
        exclude_cds.add(it['item_cd'])
elif isinstance(cell_press, list):
    for it in cell_press:
        exclude_cds.add(it.get('item_cd', ''))
# Plan Only
if isinstance(plan_only, dict) and 'items' in plan_only:
    for it in plan_only['items']:
        exclude_cds.add(it['item_cd'])
elif isinstance(plan_only, list):
    for it in plan_only:
        exclude_cds.add(it.get('item_cd', ''))

print(f'제외 품목 수: {len(exclude_cds)}건 (CS성+Cell Press+Plan Only)')

# --- 장비유형 키워드 매핑 (규칙 1-1) ---
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

# 비프로젝트 키워드 (규칙 2-4)
non_project_kw = ['공용자재 구매', '비프로젝트', '무상 자재', '공용자재']

def is_non_project(proj_name):
    return any(kw in proj_name for kw in non_project_kw)

def detect_equip(proj_name):
    if is_non_project(proj_name):
        return set()
    detected = set()
    for equip, keywords in equip_keywords.items():
        for kw in keywords:
            if kw in proj_name:
                detected.add(equip)
    return detected

# 프레스-핸들러 통합 키워드 (규칙 1-4)
handler_part_kw = ['Robot', 'robot', 'Gripper', 'gripper', 'Tool Body', 'tool body',
                   'Pick', 'pick', 'Cylinder', 'cylinder']

def check_press_handler(item, detected):
    """프레스 프로젝트 내 핸들러 부품인지 확인 (규칙 1-4)"""
    if '프레스' in detected and '핸들러' not in detected:
        nm = item.get('item_nm', '')
        if any(kw in nm for kw in handler_part_kw):
            detected.add('핸들러')
    return detected

# 개선/개조 키워드 (규칙 1-3)
improvement_kw = ['개선', '개조', '수리', '보수', '교체', '변경']

# --- 분석 (제외 품목 필터링 적용) ---
# Category 1: 장비별 중복 사용이나 등록 누락
cat1 = []
for item in items:
    if item['item_cd'] in exclude_cds:
        continue
    registered = set(item['equip_types'])
    # 마스크 → 마스크자동기 정규화
    if '마스크' in registered:
        registered.discard('마스크')
        registered.add('마스크자동기')
    if '핸들러' in registered:
        registered.discard('핸들러')  # 핸들러 폐지 - 제거만
    # 연삭핸들러는 독립 장비유형으로 유지
    # 핸들러만 단독이면 제외
    if len(registered) == 0:
        continue

    detected = set()
    for proj in item.get('all_projects', []):
        detected.update(detect_equip(proj))

    missing = detected - registered
    if missing:
        cat1.append({
            'cd': item['item_cd'],
            'nm': item['item_nm'],
            'qty': item['stock_qty'],
            'amt': item['stock_amt'],
            'registered': sorted(registered),
            'missing': sorted(missing),
            'evidence': [p for p in item.get('all_projects', [])
                         if not is_non_project(p) and
                         any(kw in p for eq in missing for kw in equip_keywords.get(eq, []))][:3],
        })

# Category 2: 개선/개조 프로젝트 있으나 분류 누락 (규칙 1-3)
cat2 = []
for item in items:
    if item['item_cd'] in exclude_cds:
        continue
    all_projs = item.get('all_projects', [])
    imp_projs = [p for p in all_projs if not is_non_project(p) and any(kw in p for kw in improvement_kw)]
    if not imp_projs:
        continue
    registered = set(item['equip_types'])
    if '마스크' in registered:
        registered.discard('마스크')
        registered.add('마스크자동기')
    if '핸들러' in registered:
        registered.discard('핸들러')
    # 연삭핸들러는 유지
    if len(registered) == 0:
        continue

    imp_equips = set()
    for p in imp_projs:
        imp_equips.update(detect_equip(p))
    missing = imp_equips - registered
    if missing:
        cat2.append({
            'cd': item['item_cd'],
            'nm': item['item_nm'],
            'qty': item['stock_qty'],
            'amt': item['stock_amt'],
            'registered': sorted(registered),
            'missing': sorted(missing),
            'projects': imp_projs[:3],
        })

cat3 = []  # 핸들러 폐지로 카테고리3 비활성

cat1.sort(key=lambda x: x['amt'], reverse=True)
cat2.sort(key=lambda x: x['amt'], reverse=True)
cat3.sort(key=lambda x: x['amt'], reverse=True)

# cat1과 cat2 중복 제거한 전체 수
all_cds = set(i['cd'] for i in cat1) | set(i['cd'] for i in cat2) | set(i['cd'] for i in cat3)
total_unique = len(all_cds)

# --- HTML 생성 ---
lines = []
lines.append('<!DOCTYPE html>')
lines.append('<html lang="ko"><head><meta charset="UTF-8">')
lines.append('<title>장비별 중복/프로젝트 누락 품목 정리 (v2)</title>')
lines.append('<style>')
lines.append("body { font-family: '맑은 고딕', sans-serif; margin: 20px; background: #f5f5f5; }")
lines.append('.header { background: #4472C4; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }')
lines.append('.header h1 { margin: 0; font-size: 22px; }')
lines.append('.header p { margin: 5px 0 0; opacity: 0.9; font-size: 14px; }')
lines.append('.header .rule-ref { margin-top: 8px; padding: 6px 12px; background: rgba(255,255,255,0.15); border-radius: 4px; font-size: 12px; }')
lines.append('.section { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }')
lines.append('.section h2 { color: #4472C4; border-bottom: 2px solid #4472C4; padding-bottom: 8px; font-size: 18px; }')
lines.append('.section .rule-tag { display: inline-block; background: #e8f0fe; color: #4472C4; padding: 2px 8px; border-radius: 3px; font-size: 11px; margin-left: 8px; }')
lines.append('.summary { display: flex; gap: 15px; margin-bottom: 15px; flex-wrap: wrap; }')
lines.append('.summary-card { background: #f0f4fa; padding: 12px 20px; border-radius: 6px; text-align: center; min-width: 120px; }')
lines.append('.summary-card .num { font-size: 28px; font-weight: bold; color: #4472C4; }')
lines.append('.summary-card .label { font-size: 12px; color: #666; }')
lines.append('.exclude-info { background: #fff3cd; padding: 10px 15px; border-radius: 6px; font-size: 13px; color: #856404; margin-bottom: 15px; }')
lines.append('table { border-collapse: collapse; width: 100%; font-size: 13px; }')
lines.append('th { background: #4472C4; color: white; padding: 8px; text-align: left; position: sticky; top: 0; }')
lines.append('td { padding: 6px 8px; border-bottom: 1px solid #eee; }')
lines.append('tr:hover { background: #f5f8ff; }')
lines.append('.tag { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 11px; margin: 1px; }')
lines.append('.tag-registered { background: #d4edda; color: #155724; }')
lines.append('.tag-missing { background: #f8d7da; color: #721c24; }')
lines.append('.tag-project { background: #fff3cd; color: #856404; font-size: 11px; }')
lines.append('.amt { text-align: right; }')
lines.append('.qty { text-align: center; }')
lines.append('</style></head><body>')

# Header
lines.append('<div class="header">')
lines.append('  <h1>장비별 중복/프로젝트 누락 품목 정리 (v2)</h1>')
lines.append(f'  <p>(주)윈텍오토메이션 생산관리팀 | 기준일: {mp.get("fr_date","")} | 생성: {now_str} | 요청: 김근형</p>')
lines.append('  <div class="rule-ref">적용 규칙: config/erp-inventory-rules.md (장비유형 분류 표준)</div>')
lines.append('</div>')

# Exclude info
lines.append('<div class="exclude-info">')
lines.append(f'  제외 처리: CS성 품목 + Cell Press + Plan Only = {len(exclude_cds)}건 제외 (규칙 2-1~2-3)')
lines.append('</div>')

# Summary
lines.append('<div class="summary">')
lines.append(f'  <div class="summary-card"><div class="num">{len(cat1)}</div><div class="label">장비별 중복 사용<br>등록 누락</div></div>')
lines.append(f'  <div class="summary-card"><div class="num">{len(cat2)}</div><div class="label">개선/개조 프로젝트<br>장비 분류 누락</div></div>')
lines.append(f'  <div class="summary-card"><div class="num">{len(cat3)}</div><div class="label">프레스-핸들러<br>미통합</div></div>')
lines.append(f'  <div class="summary-card"><div class="num">{total_unique}</div><div class="label">전체 해당<br>품목 수</div></div>')
lines.append('</div>')

# Cat 1
lines.append('<div class="section">')
lines.append(f'<h2>1. 장비별 중복 사용이나 등록 누락 품목 ({len(cat1)}건) <span class="rule-tag">규칙 1-1, 1-2</span></h2>')
lines.append('<p style="color:#666;font-size:13px;">발주이력상 복수 장비에 사용되었으나, 등록 장비유형에 누락된 품목입니다. (비프로젝트성 발주 제외)</p>')
lines.append('<table>')
lines.append('<tr><th>#</th><th>품목코드</th><th>품명</th><th class="qty">재고</th><th class="amt">재고금액</th><th>등록 장비</th><th>누락 장비</th><th>근거 프로젝트</th></tr>')

for i, item in enumerate(cat1):
    reg_tags = ''.join(f'<span class="tag tag-registered">{e}</span>' for e in item['registered'])
    miss_tags = ''.join(f'<span class="tag tag-missing">{e}</span>' for e in item['missing'])
    proj_tags = '<br>'.join(f'<span class="tag tag-project">{p[:50]}</span>' for p in item['evidence'][:3])
    amt = f'{item["amt"]:,}' if item['amt'] else '-'
    lines.append(f'<tr><td>{i+1}</td><td>{item["cd"]}</td><td>{item["nm"][:35]}</td><td class="qty">{item["qty"]}</td><td class="amt">{amt}</td><td>{reg_tags}</td><td>{miss_tags}</td><td>{proj_tags}</td></tr>')

lines.append('</table></div>')

# Cat 2
lines.append('<div class="section">')
lines.append(f'<h2>2. 개선/개조 프로젝트 발주 있으나 장비 분류 누락 ({len(cat2)}건) <span class="rule-tag">규칙 1-3</span></h2>')
lines.append('<p style="color:#666;font-size:13px;">개선/개조/교체/수리/보수/변경 프로젝트로 발주되었으나, 해당 장비유형이 등록되지 않은 품목입니다.</p>')
lines.append('<table>')
lines.append('<tr><th>#</th><th>품목코드</th><th>품명</th><th class="qty">재고</th><th class="amt">재고금액</th><th>등록 장비</th><th>누락 장비</th><th>개선/개조 프로젝트</th></tr>')

for i, item in enumerate(cat2):
    reg_tags = ''.join(f'<span class="tag tag-registered">{e}</span>' for e in item['registered'])
    miss_tags = ''.join(f'<span class="tag tag-missing">{e}</span>' for e in item['missing'])
    proj_tags = '<br>'.join(f'<span class="tag tag-project">{p[:55]}</span>' for p in item['projects'][:3])
    amt = f'{item["amt"]:,}' if item['amt'] else '-'
    lines.append(f'<tr><td>{i+1}</td><td>{item["cd"]}</td><td>{item["nm"][:35]}</td><td class="qty">{item["qty"]}</td><td class="amt">{amt}</td><td>{reg_tags}</td><td>{miss_tags}</td><td>{proj_tags}</td></tr>')

lines.append('</table></div>')

# Cat 3
if cat3:
    lines.append('<div class="section">')
    lines.append(f'<h2>3. 프레스-핸들러 미통합 품목 ({len(cat3)}건) <span class="rule-tag">규칙 1-4</span></h2>')
    lines.append('<p style="color:#666;font-size:13px;">프레스에만 등록되어 있으나, 품명이 핸들러 부품(Robot, Gripper, Tool Body 등)인 품목입니다.</p>')
    lines.append('<table>')
    lines.append('<tr><th>#</th><th>품목코드</th><th>품명</th><th class="qty">재고</th><th class="amt">재고금액</th><th>등록 장비</th><th>추가 필요</th></tr>')

    for i, item in enumerate(cat3):
        reg_tags = ''.join(f'<span class="tag tag-registered">{e}</span>' for e in item['registered'])
        amt = f'{item["amt"]:,}' if item['amt'] else '-'
        lines.append(f'<tr><td>{i+1}</td><td>{item["cd"]}</td><td>{item["nm"][:35]}</td><td class="qty">{item["qty"]}</td><td class="amt">{amt}</td><td>{reg_tags}</td><td><span class="tag tag-missing">핸들러</span></td></tr>')

    lines.append('</table></div>')

# Footer
lines.append('<div style="text-align:center;color:#999;font-size:12px;padding:20px;">')
lines.append(f'  (주)윈텍오토메이션 생산관리팀 (AI운영팀) - docs-agent 자동 생성 | {now_str}')
lines.append('</div>')
lines.append('</body></html>')

outpath = f'{base}\\장비중복_프로젝트누락_품목정리.html'
with open(outpath, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f'HTML 생성 완료: {outpath}')
print(f'카테고리1 (장비 중복 누락): {len(cat1)}건')
print(f'카테고리2 (개선 프로젝트 누락): {len(cat2)}건')
print(f'카테고리3 (프레스-핸들러 미통합): {len(cat3)}건')
print(f'전체 해당 품목: {total_unique}건')
