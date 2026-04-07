"""
ERP 현재고현황 + 발주내역 보고서 생성
김근형님 요청: 재고량>0, 재고금액 높은 순, 24년1월1일 이후 발주 유무/프로젝트
"""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)

DATA_PATH = Path(r'C:\MES\wta-agents\workspaces\db-manager\erp_inventory_data.json')
OUTPUT = Path(r'C:\MES\wta-agents\reports\김근형\erp_재고현황_발주내역.html')


def fmt_amt(v):
    """금액 포맷 (천원 단위 콤마)"""
    if not v:
        return '-'
    return f"{int(v):,}"


def fmt_qty(v):
    if not v:
        return '-'
    n = int(v) if v == int(v) else v
    return f"{n:,}"


def main():
    data = json.loads(DATA_PATH.read_text(encoding='utf-8'))

    total_items = len(data)
    has_po = [d for d in data if d.get('has_po')]
    no_po = [d for d in data if not d.get('has_po')]
    total_amt = sum(d.get('stock_amt', 0) for d in data)
    po_amt = sum(d.get('stock_amt', 0) for d in has_po)
    no_po_amt = sum(d.get('stock_amt', 0) for d in no_po)

    # Build table rows
    rows = []
    for i, d in enumerate(data, 1):
        po_badge = '<span class="badge po-yes">발주있음</span>' if d.get('has_po') else '<span class="badge po-no">없음</span>'
        po_date = d.get('last_po_dt', '') or '-'
        po_cnt = d.get('po_count', 0)
        pjt = d.get('pjt_name', '') or '-'
        if pjt != '-' and len(pjt) > 30:
            pjt = pjt[:28] + '..'

        amt_class = ''
        amt_val = d.get('stock_amt', 0)
        if amt_val >= 50_000_000:
            amt_class = ' class="amt-high"'
        elif amt_val >= 10_000_000:
            amt_class = ' class="amt-mid"'

        rows.append(f"""<tr>
  <td class="center">{i}</td>
  <td class="code">{d.get('item_cd','')}</td>
  <td>{d.get('item_nm','')}</td>
  <td class="spec">{d.get('spec','') or '-'}</td>
  <td class="right">{fmt_qty(d.get('stock_qty',0))}</td>
  <td class="right"{amt_class}>{fmt_amt(amt_val)}</td>
  <td class="center">{po_badge}</td>
  <td class="center">{po_date}</td>
  <td class="right">{po_cnt if po_cnt else '-'}</td>
  <td class="pjt">{pjt}</td>
</tr>""")

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>ERP 현재고현황 및 발주내역</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Malgun Gothic', 'Pretendard Variable', sans-serif; background: #f5f5f5; padding: 20px; margin: 0; }}
  .header {{ background: #1a237e; color: #fff; padding: 20px 24px; border-radius: 8px 8px 0 0; }}
  .header h1 {{ margin: 0; font-size: 18pt; }}
  .header .sub {{ font-size: 10pt; color: #b3b9e6; margin-top: 4px; }}
  .container {{ background: #fff; border-radius: 0 0 8px 8px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.1); }}

  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 20px; }}
  .summary-card {{ background: #f8f9ff; border: 1px solid #e0e3f0; border-radius: 8px; padding: 16px; text-align: center; }}
  .summary-card .label {{ font-size: 9pt; color: #666; margin-bottom: 4px; }}
  .summary-card .value {{ font-size: 16pt; font-weight: 700; color: #1a237e; }}
  .summary-card .value.green {{ color: #2e7d32; }}
  .summary-card .value.orange {{ color: #e65100; }}
  .summary-card .sub-value {{ font-size: 8pt; color: #888; margin-top: 2px; }}

  .filter-bar {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }}
  .filter-btn {{ padding: 6px 14px; border: 1px solid #ccc; background: #fff; border-radius: 20px;
    cursor: pointer; font-size: 9pt; font-family: 'Malgun Gothic', sans-serif; transition: all 0.2s; }}
  .filter-btn.active {{ background: #1a237e; color: #fff; border-color: #1a237e; }}
  .filter-btn:hover:not(.active) {{ background: #e8eaf6; }}

  table {{ width: 100%; border-collapse: collapse; font-size: 9pt; }}
  th {{ background: #e8eaf6; color: #1a237e; padding: 10px 8px; text-align: left; font-weight: 700;
    position: sticky; top: 0; z-index: 5; border-bottom: 2px solid #1a237e; }}
  td {{ padding: 8px; border-bottom: 1px solid #eee; vertical-align: middle; }}
  tr:hover {{ background: #f5f7ff; }}
  .center {{ text-align: center; }}
  .right {{ text-align: right; font-family: 'Consolas', monospace; }}
  .code {{ font-family: 'Consolas', monospace; font-size: 8pt; color: #555; }}
  .spec {{ font-size: 8pt; color: #777; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .pjt {{ font-size: 8pt; color: #333; max-width: 200px; }}
  .amt-high {{ color: #c62828; font-weight: 700; }}
  .amt-mid {{ color: #e65100; font-weight: 600; }}

  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 8pt; font-weight: 600; }}
  .po-yes {{ background: #e8f5e9; color: #2e7d32; }}
  .po-no {{ background: #fce4ec; color: #c62828; }}

  .footer {{ font-size: 8pt; color: #888; margin-top: 16px; text-align: right; }}

  @media print {{
    body {{ padding: 0; background: #fff; }}
    .filter-bar {{ display: none; }}
    th {{ background: #ddd !important; -webkit-print-color-adjust: exact; }}
  }}
</style>
</head>
<body>
<div class="header">
  <h1>ERP 현재고현황 및 발주내역 분석</h1>
  <div class="sub">(주)윈텍오토메이션 생산관리팀 | 조회기준: 재고량 > 0, 재고금액 높은 순 TOP {total_items} | {NOW.strftime('%Y-%m-%d')}</div>
</div>
<div class="container">
  <div class="summary">
    <div class="summary-card">
      <div class="label">총 품목 수</div>
      <div class="value">{total_items}건</div>
    </div>
    <div class="summary-card">
      <div class="label">총 재고금액</div>
      <div class="value">{fmt_amt(total_amt)}원</div>
    </div>
    <div class="summary-card">
      <div class="label">발주 있음 (2024.01~)</div>
      <div class="value green">{len(has_po)}건</div>
      <div class="sub-value">{fmt_amt(po_amt)}원</div>
    </div>
    <div class="summary-card">
      <div class="label">발주 없음</div>
      <div class="value orange">{len(no_po)}건</div>
      <div class="sub-value">{fmt_amt(no_po_amt)}원</div>
    </div>
  </div>

  <div class="filter-bar">
    <button class="filter-btn active" onclick="filterRows('all')">전체 ({total_items})</button>
    <button class="filter-btn" onclick="filterRows('yes')">발주있음 ({len(has_po)})</button>
    <button class="filter-btn" onclick="filterRows('no')">발주없음 ({len(no_po)})</button>
  </div>

  <div style="overflow-x:auto;">
  <table id="inv-table">
    <thead>
      <tr>
        <th class="center" style="width:40px;">#</th>
        <th style="width:140px;">품목코드</th>
        <th>품목명</th>
        <th style="width:180px;">규격</th>
        <th class="right" style="width:60px;">수량</th>
        <th class="right" style="width:110px;">재고금액(원)</th>
        <th class="center" style="width:70px;">발주</th>
        <th class="center" style="width:90px;">최근발주일</th>
        <th class="right" style="width:50px;">건수</th>
        <th style="width:200px;">프로젝트</th>
      </tr>
    </thead>
    <tbody>
{''.join(rows)}
    </tbody>
  </table>
  </div>

  <div class="footer">
    생성: {NOW.strftime('%Y-%m-%d %H:%M')} KST | 발주 기준: 2024-01-01 이후 | 데이터 출처: ERP 현재고현황
  </div>
</div>

<script>
function filterRows(mode) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  document.querySelectorAll('#inv-table tbody tr').forEach(tr => {{
    const badge = tr.querySelector('.badge');
    if (!badge) return;
    const hasPo = badge.classList.contains('po-yes');
    if (mode === 'all') tr.style.display = '';
    else if (mode === 'yes') tr.style.display = hasPo ? '' : 'none';
    else tr.style.display = hasPo ? 'none' : '';
  }});
}}
</script>
</body>
</html>"""

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding='utf-8')
    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Saved: {OUTPUT} ({size_kb:.0f} KB)")
    print(f"URL: https://agent.mes-wta.com/erp_재고현황_발주내역")


if __name__ == '__main__':
    main()
