# -*- coding: utf-8 -*-
"""ERP 현재고현황 및 구매진행현황 TOP 100 (재고금액 기준)"""
import sys, io, json
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

KST = timezone(timedelta(hours=9))
now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M')

base = r'C:\MES\wta-agents\reports\김근형'

with open(f'{base}\\erp_data.json', 'r', encoding='utf-8') as f:
    erp = json.load(f)

data = erp['data']
# 재고금액(index 4) 내림차순 정렬, TOP 100
sorted_data = sorted(data, key=lambda x: x[4] if x[4] else 0, reverse=True)[:100]

lines = []
lines.append('<!DOCTYPE html>')
lines.append('<html lang="ko"><head><meta charset="UTF-8">')
lines.append('<title>ERP 현재고현황 및 구매진행현황 TOP 100</title>')
lines.append('<style>')
lines.append("body { font-family: '맑은 고딕', sans-serif; margin: 20px; background: #f5f5f5; }")
lines.append('.header { background: #4472C4; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }')
lines.append('.header h1 { margin: 0; font-size: 22px; }')
lines.append('.header p { margin: 5px 0 0; opacity: 0.9; font-size: 14px; }')
lines.append('.section { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }')
lines.append('table { border-collapse: collapse; width: 100%; font-size: 13px; }')
lines.append('th { background: #4472C4; color: white; padding: 8px; text-align: left; position: sticky; top: 0; }')
lines.append('td { padding: 6px 8px; border-bottom: 1px solid #eee; }')
lines.append('tr:hover { background: #f5f8ff; }')
lines.append('.tag { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 11px; margin: 1px; background: #d4edda; color: #155724; }')
lines.append('.tag-empty { background: #f8d7da; color: #721c24; }')
lines.append('.amt { text-align: right; }')
lines.append('.qty { text-align: center; }')
lines.append('</style></head><body>')

lines.append('<div class="header">')
lines.append('  <h1>ERP 현재고현황 및 구매진행현황 TOP 100</h1>')
lines.append(f'  <p>(주)윈텍오토메이션 생산관리팀 | 재고금액 기준 상위 100건 | 생성: {now_str}</p>')
lines.append('</div>')

lines.append('<div class="section">')
lines.append('<table>')
lines.append('<tr><th>#</th><th>품목코드</th><th>품명</th><th>품목유형</th><th class="qty">재고수량</th><th class="amt">재고금액</th><th>최종발주일</th><th>프로젝트</th><th>장비유형</th></tr>')

for i, r in enumerate(sorted_data):
    item_cd = r[1]
    item_nm = r[2]
    qty = r[3]
    amt = r[4]
    item_type = r[6]
    last_dt = r[7] if r[7] else '-'
    proj = r[8] if r[8] else '-'
    equip = r[9]

    amt_str = f'{amt:,}' if amt else '-'

    if isinstance(equip, list) and len(equip) > 0:
        equip_tags = ''.join(f'<span class="tag">{e}</span>' for e in equip)
    elif isinstance(equip, str) and equip.strip():
        equip_tags = f'<span class="tag">{equip}</span>'
    else:
        equip_tags = '<span class="tag tag-empty">미분류</span>'

    proj_display = proj[:45] if proj else '-'
    lines.append(f'<tr><td>{i+1}</td><td>{item_cd}</td><td>{item_nm[:35]}</td><td>{item_type}</td><td class="qty">{qty}</td><td class="amt">{amt_str}</td><td>{last_dt}</td><td>{proj_display}</td><td>{equip_tags}</td></tr>')

lines.append('</table></div>')

lines.append('<div style="text-align:center;color:#999;font-size:12px;padding:20px;">')
lines.append(f'  (주)윈텍오토메이션 생산관리팀 (AI운영팀) - docs-agent 자동 생성 | {now_str}')
lines.append('</div>')
lines.append('</body></html>')

outpath = f'{base}\\ERP_현재고_구매진행_TOP100.html'
with open(outpath, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f'HTML 생성 완료: {outpath}')
print(f'TOP 100 재고금액 범위: {sorted_data[0][4]:,} ~ {sorted_data[99][4]:,}')
