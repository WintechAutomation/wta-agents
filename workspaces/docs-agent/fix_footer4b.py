import os

base = os.path.join('C:', os.sep, 'MES', 'wta-agents', 'reports', '김근형')
fpath = os.path.join(base, 'erp_재고현황_발주내역.html')

with open(fpath, 'r', encoding='utf-8') as f:
    html = f.read()

old = ">합계 ' + rows.length.toLocaleString() + '건</td>"
new = ">' + rows.length.toLocaleString() + '건</td>"

if old in html:
    html = html.replace(old, new)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(html)
    print('Fixed')
else:
    print('ERROR: not found')
