import os

base = os.path.join('C:', os.sep, 'MES', 'wta-agents', 'reports', '김근형')
fpath = os.path.join(base, 'erp_재고현황_발주내역.html')

with open(fpath, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. CSS: sub-value를 인라인으로 (별도 줄 → value 옆에)
html = html.replace(
    ".summary-card .sub-value { font-size: 7.5pt; color: #888; margin-top: 2px; }",
    ".summary-card .sub-value { font-size: 7.5pt; color: #888; display: inline; margin-left: 4px; }"
)

# 2. value도 인라인으로
html = html.replace(
    ".summary-card .value { font-size: 12pt; font-weight: 700; }",
    ".summary-card .value { font-size: 12pt; font-weight: 700; display: inline; }"
)

# 3. HTML: sub-value를 value와 같은 div에 넣기 (현재고 총액)
html = html.replace(
    '<div class="value" style="color:#1a237e;">2,564,610,860원</div>\n      <div class="sub-value">약 25.6억원</div>',
    '<div><span class="value" style="color:#1a237e;">2,564,610,860원</span><span class="sub-value">(약 25.6억원)</span></div>'
)

# 4. 사용 예정 금액
html = html.replace(
    '<div class="value" style="color:#2e7d32;">-962,265,371원</div>\n      <div class="sub-value">약 9.6억원</div>',
    '<div><span class="value" style="color:#2e7d32;">-962,265,371원</span><span class="sub-value">(약 9.6억원)</span></div>'
)

# 5. 예상 잔여 금액
html = html.replace(
    '<div class="value" style="color:#e65100;">1,602,345,489원</div>\n      <div class="sub-value">약 16.0억원</div>',
    '<div><span class="value" style="color:#e65100;">1,602,345,489원</span><span class="sub-value">(약 16.0억원)</span></div>'
)

# 6. JS에서 동적 업데이트도 같은 패턴으로 수정
# cards[2] - 사용예정금액
html = html.replace(
    "if (cards[2]) { cards[2].querySelector('.value').textContent = '-' + totalUseAmt.toLocaleString() + '원'; cards[2].querySelector('.sub-value').textContent = '약 ' + (totalUseAmt/100000000).toFixed(1) + '억원'; }",
    "if (cards[2]) { cards[2].querySelector('.value').textContent = '-' + totalUseAmt.toLocaleString() + '원'; cards[2].querySelector('.sub-value').textContent = '(약 ' + (totalUseAmt/100000000).toFixed(1) + '억원)'; }"
)

# cards[3] - 잔여금액
html = html.replace(
    "if (cards[3]) { cards[3].querySelector('.value').textContent = totalRemainAmt.toLocaleString() + '원'; cards[3].querySelector('.sub-value').textContent = '약 ' + (totalRemainAmt/100000000).toFixed(1) + '억원'; }",
    "if (cards[3]) { cards[3].querySelector('.value').textContent = totalRemainAmt.toLocaleString() + '원'; cards[3].querySelector('.sub-value').textContent = '(약 ' + (totalRemainAmt/100000000).toFixed(1) + '억원)'; }"
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(html)

print('Summary cards: inline sub-value applied')
