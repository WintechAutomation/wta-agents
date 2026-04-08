import os

base = os.path.join('C:', os.sep, 'MES', 'wta-agents', 'reports', '김근형')
fpath = os.path.join(base, 'erp_재고현황_발주내역.html')

with open(fpath, 'r', encoding='utf-8') as f:
    html = f.read()

# Change: move "합계 N건" to the 수량 column, remove separate qty sum
# Current: '<td colspan="2"...>합계 (N건)</td>' + empty + '<td>sumQty</td>'
# New: '<td colspan="3"...>합계</td>' + '<td>합계 N건</td>'

old = """    '<td colspan="2" style="text-align:right;' + ts + '">합계 (' + rows.length.toLocaleString() + '건)</td>' +
    '<td style="' + ts + '"></td>' +
    '<td class="right" style="' + ts + '">' + Math.round(sumQty).toLocaleString() + '</td>' +"""

new = """    '<td colspan="3" style="text-align:right;' + ts + '">합계</td>' +
    '<td class="right" style="' + ts + '">합계 ' + rows.length.toLocaleString() + '건</td>' +"""

if old in html:
    html = html.replace(old, new)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(html)
    print('Footer updated: 수량열에 합계 N건, 수량총합 제거')
else:
    print('ERROR: old block not found')
