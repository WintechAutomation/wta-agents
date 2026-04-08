import os

base = os.path.join('C:', os.sep, 'MES', 'wta-agents', 'reports', '김근형')
fpath = os.path.join(base, 'erp_재고현황_발주내역.html')

with open(fpath, 'r', encoding='utf-8') as f:
    html = f.read()

old = """  // 합계행
  let sumPlanAmt = 0, sumRemainAmt = 0;
  for (const r of rows) { sumPlanAmt += (r[11]||0); sumRemainAmt += (r[13]||0); }
  const tf = document.getElementById('tfoot');
  tf.innerHTML = '<tr>' +
    '<td colspan="8" style="text-align:right;font-weight:700;font-size:8pt;background:#f5f5f5;border-top:2px solid #1a237e;">합계</td>' +
    '<td style="background:#f5f5f5;border-top:2px solid #1a237e;"></td>' +
    '<td style="background:#f5f5f5;border-top:2px solid #1a237e;"></td>' +
    '<td class="right" style="font-weight:700;color:#2e7d32;font-size:8pt;background:#e8f5e9;border-top:2px solid #2e7d32;">-' + sumPlanAmt.toLocaleString() + '</td>' +
    '<td style="background:#f5f5f5;border-top:2px solid #1a237e;"></td>' +
    '<td class="right" style="font-weight:700;color:#e65100;font-size:8pt;background:#fff3e0;border-top:2px solid #e65100;">' + sumRemainAmt.toLocaleString() + '</td></tr>';"""

new = """  // 합계행
  let sumQty = 0, sumAmt = 0, sumPlanAmt = 0, sumRemainAmt = 0;
  for (const r of rows) { sumQty += (r[3]||0); sumAmt += (r[4]||0); sumPlanAmt += (r[11]||0); sumRemainAmt += (r[13]||0); }
  const tf = document.getElementById('tfoot');
  const ts = 'font-weight:700;font-size:8pt;background:#f5f5f5;border-top:2px solid #1a237e;';
  tf.innerHTML = '<tr>' +
    '<td colspan="2" style="text-align:right;' + ts + '">합계 (' + rows.length.toLocaleString() + '건)</td>' +
    '<td style="' + ts + '"></td>' +
    '<td class="right" style="' + ts + '">' + Math.round(sumQty).toLocaleString() + '</td>' +
    '<td class="right" style="' + ts + 'color:#1a237e;">' + Math.round(sumAmt).toLocaleString() + '</td>' +
    '<td colspan="3" style="' + ts + '"></td>' +
    '<td style="' + ts + '"></td>' +
    '<td style="' + ts + '"></td>' +
    '<td class="right" style="font-weight:700;font-size:8pt;background:#e8f5e9;border-top:2px solid #2e7d32;color:#2e7d32;">예정금액 -' + sumPlanAmt.toLocaleString() + '</td>' +
    '<td style="' + ts + '"></td>' +
    '<td class="right" style="font-weight:700;font-size:8pt;background:#fff3e0;border-top:2px solid #e65100;color:#e65100;">남는금액 ' + sumRemainAmt.toLocaleString() + '</td></tr>';"""

if old in html:
    html = html.replace(old, new)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(html)
    print('Footer updated')
else:
    print('ERROR: old block not found')
