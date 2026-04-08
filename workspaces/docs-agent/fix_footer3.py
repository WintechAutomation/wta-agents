import os

base = os.path.join('C:', os.sep, 'MES', 'wta-agents', 'reports', '김근형')
fpath = os.path.join(base, 'erp_재고현황_발주내역.html')

with open(fpath, 'r', encoding='utf-8') as f:
    html = f.read()

# Add "재고금액" label before the amount
old = """'<td class="right" style="' + ts + 'color:#1a237e;">' + Math.round(sumAmt).toLocaleString() + '</td>'"""
new = """'<td class="right" style="' + ts + 'color:#1a237e;">재고금액 ' + Math.round(sumAmt).toLocaleString() + '</td>'"""

if old in html:
    html = html.replace(old, new)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(html)
    print('Added 재고금액 label')
else:
    print('ERROR: not found')
