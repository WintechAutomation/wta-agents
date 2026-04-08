# -*- coding: utf-8 -*-
"""장비별 중복/프로젝트 누락 품목 정리 HTML 생성"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(r'C:\MES\wta-agents\reports\김근형\multi_project_items.json', 'r', encoding='utf-8') as f:
    mp = json.load(f)

items = mp['items']

equip_keywords = {
    '프레스': ['프레스', 'Press', 'press'],
    '핸들러': ['핸들러', 'Handler', 'handler'],
    '소결': ['소결', 'Sintering', 'sintering'],
    'CVD': ['CVD', 'cvd'],
    'PVD': ['PVD', 'pvd', 'UL', 'LUL'],
    '포장기': ['포장기', 'Packing', 'packing', '포장'],
    '검사기': ['검사기', 'Inspection', 'inspection', 'F1', 'F2'],
    '호닝형상': ['호닝', 'HIM', 'Honing', 'honing'],
    '연삭': ['연삭', 'Grinding', 'grinding'],
    'CBN': ['CBN', 'cbn'],
    '마스크': ['마스크', 'Mask', 'mask'],
}

def detect_equip(proj_name):
    detected = set()
    for equip, keywords in equip_keywords.items():
        for kw in keywords:
            if kw in proj_name:
                detected.add(equip)
    return detected

# Category 1: 장비별 중복 사용이나 등록 누락
cat1 = []
for item in items:
    registered = set(item['equip_types'])
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
                         if any(kw in p for eq in missing for kw in equip_keywords.get(eq, []))][:3],
        })

# Category 2: 개선/개조 프로젝트 있으나 분류 누락
improvement_kw = ['개선', '개조', '수리', '보수', '교체', '변경']
cat2 = []
for item in items:
    all_projs = item.get('all_projects', [])
    imp_projs = [p for p in all_projs if any(kw in p for kw in improvement_kw)]
    if not imp_projs:
        continue
    registered = set(item['equip_types'])
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

cat1.sort(key=lambda x: x['amt'], reverse=True)
cat2.sort(key=lambda x: x['amt'], reverse=True)

total_unique = len(set(i['cd'] for i in cat1) | set(i['cd'] for i in cat2))

# Generate HTML
lines = []
lines.append('<!DOCTYPE html>')
lines.append('<html lang="ko"><head><meta charset="UTF-8">')
lines.append('<title>장비별 중복/프로젝트 누락 품목 정리</title>')
lines.append('<style>')
lines.append("body { font-family: '맑은 고딕', sans-serif; margin: 20px; background: #f5f5f5; }")
lines.append('.header { background: #4472C4; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }')
lines.append('.header h1 { margin: 0; font-size: 22px; }')
lines.append('.header p { margin: 5px 0 0; opacity: 0.9; font-size: 14px; }')
lines.append('.section { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }')
lines.append('.section h2 { color: #4472C4; border-bottom: 2px solid #4472C4; padding-bottom: 8px; font-size: 18px; }')
lines.append('.summary { display: flex; gap: 20px; margin-bottom: 15px; }')
lines.append('.summary-card { background: #f0f4fa; padding: 12px 20px; border-radius: 6px; text-align: center; }')
lines.append('.summary-card .num { font-size: 28px; font-weight: bold; color: #4472C4; }')
lines.append('.summary-card .label { font-size: 12px; color: #666; }')
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
lines.append('  <h1>장비별 중복/프로젝트 누락 품목 정리</h1>')
lines.append(f'  <p>(주)윈텍오토메이션 생산관리팀 | 기준일: {mp.get("fr_date","")} | 요청: 김근형</p>')
lines.append('</div>')

# Summary
lines.append('<div class="summary">')
lines.append(f'  <div class="summary-card"><div class="num">{len(cat1)}</div><div class="label">장비별 중복 사용<br>등록 누락 품목</div></div>')
lines.append(f'  <div class="summary-card"><div class="num">{len(cat2)}</div><div class="label">개선/개조 프로젝트<br>장비 분류 누락</div></div>')
lines.append(f'  <div class="summary-card"><div class="num">{total_unique}</div><div class="label">전체 해당<br>품목 수</div></div>')
lines.append('</div>')

# Cat 1
lines.append('<div class="section">')
lines.append(f'<h2>1. 장비별 중복 사용이나 등록 누락 품목 ({len(cat1)}건)</h2>')
lines.append('<p style="color:#666;font-size:13px;">발주이력상 복수 장비에 사용되었으나, BOM 등록 장비유형에 누락된 품목입니다.</p>')
lines.append('<table>')
lines.append('<tr><th>#</th><th>품목코드</th><th>품명</th><th class="qty">재고</th><th class="amt">재고금액</th><th>등록 장비</th><th>누락 장비</th><th>근거 프로젝트</th></tr>')

for i, item in enumerate(cat1):
    reg_tags = ''.join(f'<span class="tag tag-registered">{e}</span>' for e in item['registered'])
    miss_tags = ''.join(f'<span class="tag tag-missing">{e}</span>' for e in item['missing'])
    proj_tags = '<br>'.join(f'<span class="tag tag-project">{p[:45]}</span>' for p in item['evidence'][:2])
    amt = f'{item["amt"]:,}' if item['amt'] else '-'
    lines.append(f'<tr><td>{i+1}</td><td>{item["cd"]}</td><td>{item["nm"][:30]}</td><td class="qty">{item["qty"]}</td><td class="amt">{amt}</td><td>{reg_tags}</td><td>{miss_tags}</td><td>{proj_tags}</td></tr>')

lines.append('</table></div>')

# Cat 2
lines.append('<div class="section">')
lines.append(f'<h2>2. 개선/개조 프로젝트 발주 있으나 장비 분류 누락 ({len(cat2)}건)</h2>')
lines.append('<p style="color:#666;font-size:13px;">개선/개조/교체 프로젝트로 발주되었으나, 해당 장비유형이 BOM에 등록되지 않은 품목입니다.</p>')
lines.append('<table>')
lines.append('<tr><th>#</th><th>품목코드</th><th>품명</th><th class="qty">재고</th><th class="amt">재고금액</th><th>등록 장비</th><th>누락 장비</th><th>개선/개조 프로젝트</th></tr>')

for i, item in enumerate(cat2):
    reg_tags = ''.join(f'<span class="tag tag-registered">{e}</span>' for e in item['registered'])
    miss_tags = ''.join(f'<span class="tag tag-missing">{e}</span>' for e in item['missing'])
    proj_tags = '<br>'.join(f'<span class="tag tag-project">{p[:50]}</span>' for p in item['projects'][:2])
    amt = f'{item["amt"]:,}' if item['amt'] else '-'
    lines.append(f'<tr><td>{i+1}</td><td>{item["cd"]}</td><td>{item["nm"][:30]}</td><td class="qty">{item["qty"]}</td><td class="amt">{amt}</td><td>{reg_tags}</td><td>{miss_tags}</td><td>{proj_tags}</td></tr>')

lines.append('</table></div>')

lines.append('<div style="text-align:center;color:#999;font-size:12px;padding:20px;">')
lines.append('  (주)윈텍오토메이션 생산관리팀 (AI운영팀) - docs-agent 자동 생성')
lines.append('</div>')
lines.append('</body></html>')

outpath = r'C:\MES\wta-agents\reports\김근형\장비중복_프로젝트누락_품목정리.html'
with open(outpath, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f'HTML 생성 완료: {outpath}')
print(f'카테고리1 (장비 중복 누락): {len(cat1)}건')
print(f'카테고리2 (개선 프로젝트 누락): {len(cat2)}건')
print(f'전체 해당 품목: {total_unique}건')
