import os

base = os.path.join('C:', os.sep, 'MES', 'wta-agents', 'reports', '김근형')

for fname in ['erp_재고현황_발주내역.html', 'erp_현재고_TOP20.html']:
    fpath = os.path.join(base, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        html = f.read()

    # body 기본 폰트: 8.5pt → 10pt
    html = html.replace('font-size: 8.5pt; }', 'font-size: 10pt; }')

    # table 폰트: 8pt → 9.5pt
    html = html.replace('table { width: 100%; border-collapse: collapse; font-size: 8pt;',
                         'table { width: 100%; border-collapse: collapse; font-size: 9.5pt;')

    # th 폰트: 7.5pt → 9pt
    html = html.replace('font-size: 7.5pt; }', 'font-size: 9pt; }')

    # code 폰트: 7.5pt → 9pt
    html = html.replace(".code { font-family: 'Consolas', monospace; font-size: 7.5pt;",
                         ".code { font-family: 'Consolas', monospace; font-size: 9pt;")

    # item-nm 폰트: 7.5pt → 8.5pt
    html = html.replace('.item-nm { font-size: 7.5pt;', '.item-nm { font-size: 8.5pt;')

    # pjt 폰트: 7.5pt → 8.5pt
    html = html.replace('.pjt { font-size: 7.5pt;', '.pjt { font-size: 8.5pt;')

    # equip 폰트: 7pt → 8.5pt
    html = html.replace('.equip { font-size: 7pt;', '.equip { font-size: 8.5pt;')

    # badge 폰트: 7pt → 8pt
    html = html.replace('.badge { display: inline-block; padding: 2px 6px; border-radius: 10px; font-size: 7pt;',
                         '.badge { display: inline-block; padding: 2px 6px; border-radius: 10px; font-size: 8pt;')

    # inline style font-size:7pt → 8.5pt (발주일, 품목명 등)
    html = html.replace('font-size:7pt;', 'font-size:8.5pt;')
    html = html.replace('font-size:7.5pt;', 'font-size:8.5pt;')

    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'{fname}: font sizes updated')
