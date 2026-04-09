# -*- coding: utf-8 -*-
"""erp_재고현황_발주내역.html에서 TOP 100만 추출"""
import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

src = r'C:\MES\wta-agents\reports\김근형\erp_재고현황_발주내역.html'
with open(src, 'r', encoding='utf-8') as f:
    html = f.read()

# Extract data array from "const data = [[...]];"
m = re.search(r'const data = (\[\[.+?\]\]);', html, re.DOTALL)
if not m:
    print("ERROR: data array not found")
    sys.exit(1)

data_str = m.group(1)
data = json.loads(data_str)
print(f'전체 데이터: {len(data)}건')

# Sort by index 4 (재고금액) descending, take top 100
data.sort(key=lambda x: x[4] if x[4] else 0, reverse=True)
top100 = data[:100]

# Re-number
for i, row in enumerate(top100):
    row[0] = i + 1

top100_str = json.dumps(top100, ensure_ascii=False)

# Replace data in HTML
new_html = html.replace(m.group(0), f'const data = {top100_str};')

# Update title and header
new_html = new_html.replace(
    '<title>ERP 현재고현황 및 구매진행현황</title>',
    '<title>ERP 현재고현황 및 구매진행현황 TOP 100</title>'
)
new_html = new_html.replace(
    '<h1>ERP 현재고현황 및 구매진행현황</h1>',
    '<h1>ERP 현재고현황 및 구매진행현황 TOP 100</h1>'
)
new_html = new_html.replace(
    '전체 4,106건',
    f'재고금액 기준 상위 100건 (전체 {len(data)}건 중)'
)

# Update filter button counts (approximate - will be recalculated by JS)
# Just keep the structure, JS will recalculate

outpath = r'C:\MES\wta-agents\reports\김근형\ERP_현재고_구매진행_TOP100.html'
with open(outpath, 'w', encoding='utf-8') as f:
    f.write(new_html)

print(f'HTML 생성 완료: {outpath}')
print(f'TOP 100 재고금액: {top100[0][4]:,} ~ {top100[99][4]:,}')
