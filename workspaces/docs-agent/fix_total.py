import os

base = os.path.join('C:', os.sep, 'MES', 'wta-agents', 'reports', '김근형')
fpath = os.path.join(base, 'erp_재고현황_발주내역.html')

with open(fpath, 'r', encoding='utf-8') as f:
    html = f.read()

# 총 품목 카드에 id 추가하여 동적 업데이트 가능하게
html = html.replace(
    '<div class="label">총 품목</div>\n      <div class="value" style="color:#1a237e;">4,059건</div>',
    '<div class="label">총 품목</div>\n      <div class="value" style="color:#1a237e;" id="total-count">-</div>'
)

# recalcAll에 총 품목 수 업데이트 추가 - cards[0]에 총 품목 수
old_recalc = "if (cards[2]) { cards[2].querySelector('.value').textContent"
new_recalc = """const totalCount = document.getElementById('total-count');
  if (totalCount) totalCount.textContent = DATA.length.toLocaleString() + '건';
  if (cards[2]) { cards[2].querySelector('.value').textContent"""

html = html.replace(old_recalc, new_recalc)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(html)

print('Total count now dynamic')
