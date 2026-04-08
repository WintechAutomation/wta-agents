"""
ERP 현재고현황 + 발주내역 보고서 (전건)
김근형님 요청: 재고량>0 전체, 재고금액 높은 순, 발주이력 전건 확인
"""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)

DATA_PATH = Path(r'C:\MES\wta-agents\workspaces\db-manager\erp_inventory_full_v2.json')
OUTPUT = Path(r'C:\MES\wta-agents\reports\김근형\erp_재고현황_발주내역.html')

ITEM_KIND_MAP = {
    '1': '원자재',
    '2': '부자재',
    '3': '반제품',
    '6': '상품',
    '7': '기타',
}


def fmt_amt(v):
    if not v:
        return '-'
    return f"{int(v):,}"


def fmt_qty(v):
    if not v:
        return '-'
    n = int(v) if v == int(v) else v
    return f"{n:,}"


def escape_html(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def main():
    data = json.loads(DATA_PATH.read_text(encoding='utf-8'))

    total_items = len(data)
    has_po_list = [d for d in data if d.get('has_po')]
    past_po_list = [d for d in data if not d.get('has_po') and d.get('all_time_last_po_dt')]
    never_po_list = [d for d in data if not d.get('has_po') and not d.get('all_time_last_po_dt')]
    no_po_list = past_po_list + never_po_list
    total_amt = sum(d.get('stock_amt', 0) for d in data)
    po_amt = sum(d.get('stock_amt', 0) for d in has_po_list)
    past_po_amt = sum(d.get('stock_amt', 0) for d in past_po_list)
    never_po_amt = sum(d.get('stock_amt', 0) for d in never_po_list)
    no_po_amt = past_po_amt + never_po_amt

    # 품목구분별 통계
    kind_stats = {}
    for d in data:
        k = d.get('item_kind', '')
        label = ITEM_KIND_MAP.get(k, k)
        if label not in kind_stats:
            kind_stats[label] = {'count': 0, 'amt': 0, 'po': 0}
        kind_stats[label]['count'] += 1
        kind_stats[label]['amt'] += d.get('stock_amt', 0)
        if d.get('has_po'):
            kind_stats[label]['po'] += 1

    # Build JSON data for client-side rendering (much smaller than full HTML table)
    js_data = []
    for i, d in enumerate(data):
        kind_label = ITEM_KIND_MAP.get(d.get('item_kind', ''), d.get('item_kind', ''))
        # po_status: 2=24년이후있음, 1=과거있음, 0=이력없음
        if d.get('has_po'):
            po_status = 2
        elif d.get('all_time_last_po_dt'):
            po_status = 1
        else:
            po_status = 0
        js_data.append([
            i + 1,                                    # 0: rank
            escape_html(d.get('item_cd', '')),        # 1: item_cd
            escape_html(d.get('item_nm', '')),        # 2: item_nm
            escape_html(d.get('spec', '') or ''),     # 3: spec
            d.get('stock_qty', 0),                    # 4: qty
            d.get('stock_amt', 0),                    # 5: amt
            po_status,                                # 6: po_status (0/1/2)
            d.get('last_po_dt', '') or '',             # 7: last_po_dt (2024~)
            d.get('po_count', 0),                     # 8: po_count
            escape_html(d.get('last_pjt_name', '') or ''),  # 9: pjt
            kind_label,                               # 10: kind
            escape_html(d.get('location', '') or ''), # 11: location
            d.get('all_time_last_po_dt', '') or '',   # 12: all_time_last_po_dt
        ])

    js_data_str = json.dumps(js_data, ensure_ascii=False)

    # 품목구분 카드
    kind_cards = []
    for label in ['원자재', '부자재', '반제품', '상품', '기타']:
        if label in kind_stats:
            s = kind_stats[label]
            kind_cards.append(f"""<div class="kind-card" onclick="filterKind('{label}')">
  <div class="kind-label">{label}</div>
  <div class="kind-count">{s['count']:,}건</div>
  <div class="kind-amt">{fmt_amt(s['amt'])}원</div>
  <div class="kind-po">발주: {s['po']}건</div>
</div>""")

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>ERP 현재고현황 및 발주내역 (전체)</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Malgun Gothic', 'Pretendard Variable', sans-serif; background: #f5f5f5; padding: 20px; margin: 0; }}
  .header {{ background: #1a237e; color: #fff; padding: 20px 24px; border-radius: 8px 8px 0 0; }}
  .header h1 {{ margin: 0; font-size: 18pt; }}
  .header .sub {{ font-size: 10pt; color: #b3b9e6; margin-top: 4px; }}
  .container {{ background: #fff; border-radius: 0 0 8px 8px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.1); }}

  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 16px; }}
  .summary-card {{ background: #f8f9ff; border: 1px solid #e0e3f0; border-radius: 8px; padding: 14px; text-align: center; }}
  .summary-card .label {{ font-size: 9pt; color: #666; margin-bottom: 4px; }}
  .summary-card .value {{ font-size: 15pt; font-weight: 700; color: #1a237e; }}
  .summary-card .value.green {{ color: #2e7d32; }}
  .summary-card .value.orange {{ color: #e65100; }}
  .summary-card .sub-value {{ font-size: 8pt; color: #888; margin-top: 2px; }}

  .kind-row {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }}
  .kind-card {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 10px 14px; cursor: pointer;
    transition: all 0.2s; min-width: 120px; text-align: center; }}
  .kind-card:hover, .kind-card.active {{ border-color: #1a237e; background: #e8eaf6; }}
  .kind-label {{ font-size: 10pt; font-weight: 700; color: #1a237e; }}
  .kind-count {{ font-size: 12pt; font-weight: 700; }}
  .kind-amt {{ font-size: 8pt; color: #666; }}
  .kind-po {{ font-size: 8pt; color: #2e7d32; }}

  .toolbar {{ display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; align-items: center; }}
  .search-box {{ padding: 6px 12px; border: 1px solid #ccc; border-radius: 20px; font-size: 9pt; width: 260px;
    font-family: 'Malgun Gothic', sans-serif; }}
  .filter-btn {{ padding: 5px 12px; border: 1px solid #ccc; background: #fff; border-radius: 20px;
    cursor: pointer; font-size: 9pt; font-family: 'Malgun Gothic', sans-serif; transition: all 0.2s; }}
  .filter-btn.active {{ background: #1a237e; color: #fff; border-color: #1a237e; }}
  .filter-btn:hover:not(.active) {{ background: #e8eaf6; }}
  .result-count {{ font-size: 9pt; color: #666; margin-left: auto; }}

  table {{ width: 100%; border-collapse: collapse; font-size: 8.5pt; }}
  th {{ background: #e8eaf6; color: #1a237e; padding: 8px 6px; text-align: left; font-weight: 700;
    position: sticky; top: 0; z-index: 5; border-bottom: 2px solid #1a237e; cursor: pointer; white-space: nowrap; }}
  th:hover {{ background: #c5cae9; }}
  td {{ padding: 6px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }}
  tr:hover {{ background: #f5f7ff; }}
  .center {{ text-align: center; }}
  .right {{ text-align: right; font-family: 'Consolas', monospace; }}
  .code {{ font-family: 'Consolas', monospace; font-size: 8pt; color: #555; }}
  .spec {{ font-size: 7.5pt; color: #777; max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .pjt {{ font-size: 7.5pt; color: #333; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .amt-high {{ color: #c62828; font-weight: 700; }}
  .amt-mid {{ color: #e65100; font-weight: 600; }}

  .badge {{ display: inline-block; padding: 2px 7px; border-radius: 10px; font-size: 7.5pt; font-weight: 600; }}
  .po-yes {{ background: #e8f5e9; color: #2e7d32; }}
  .po-past {{ background: #fff3e0; color: #e65100; }}
  .po-no {{ background: #f5f5f5; color: #888; }}

  .footer {{ font-size: 8pt; color: #888; margin-top: 16px; text-align: right; }}
  .table-wrap {{ max-height: 70vh; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 4px; }}

  @media print {{
    body {{ padding: 0; background: #fff; }}
    .toolbar, .kind-row {{ display: none; }}
    .table-wrap {{ max-height: none; overflow: visible; }}
    th {{ background: #ddd !important; -webkit-print-color-adjust: exact; }}
  }}
</style>
</head>
<body>
<div class="header">
  <h1>ERP 현재고현황 및 발주내역 분석 (전체)</h1>
  <div class="sub">(주)윈텍오토메이션 생산관리팀 | 재고량 > 0 전건 ({total_items:,}건) | 재고금액 높은 순 | {NOW.strftime('%Y-%m-%d')}</div>
</div>
<div class="container">
  <div class="summary">
    <div class="summary-card">
      <div class="label">총 품목 수</div>
      <div class="value">{total_items:,}건</div>
    </div>
    <div class="summary-card">
      <div class="label">총 재고금액</div>
      <div class="value">{fmt_amt(total_amt)}원</div>
      <div class="sub-value">약 {total_amt/100_000_000:.1f}억원</div>
    </div>
    <div class="summary-card">
      <div class="label">2024년 이후 발주 있음</div>
      <div class="value green">{len(has_po_list):,}건</div>
      <div class="sub-value">{fmt_amt(po_amt)}원</div>
    </div>
    <div class="summary-card">
      <div class="label">과거 발주만 있음</div>
      <div class="value orange">{len(past_po_list):,}건</div>
      <div class="sub-value">{fmt_amt(past_po_amt)}원</div>
    </div>
    <div class="summary-card">
      <div class="label">발주이력 없음</div>
      <div class="value" style="color:#888;">{len(never_po_list):,}건</div>
      <div class="sub-value">{fmt_amt(never_po_amt)}원</div>
    </div>
  </div>

  <div class="kind-row">
{''.join(kind_cards)}
  </div>

  <div class="toolbar">
    <input type="text" class="search-box" id="search" placeholder="품목코드/품목명/규격/프로젝트 검색..." oninput="applyFilters()"/>
    <button class="filter-btn active" data-po="all" onclick="setPo('all')">전체 ({total_items:,})</button>
    <button class="filter-btn" data-po="2" onclick="setPo('2')">24년이후 발주 ({len(has_po_list):,})</button>
    <button class="filter-btn" data-po="1" onclick="setPo('1')">과거발주만 ({len(past_po_list):,})</button>
    <button class="filter-btn" data-po="0" onclick="setPo('0')">발주이력없음 ({len(never_po_list):,})</button>
    <span class="result-count" id="result-count"></span>
  </div>

  <div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th class="center" style="width:36px;" onclick="sortBy(0)">#</th>
        <th style="width:130px;" onclick="sortBy(1)">품목코드</th>
        <th onclick="sortBy(2)">품목명</th>
        <th style="width:140px;">규격</th>
        <th class="center" style="width:50px;" onclick="sortBy(10)">구분</th>
        <th class="right" style="width:55px;" onclick="sortBy(4)">수량</th>
        <th class="right" style="width:105px;" onclick="sortBy(5)">재고금액(원)</th>
        <th class="center" style="width:70px;" onclick="sortBy(6)">발주상태</th>
        <th class="center" style="width:78px;" onclick="sortBy(7)">최근발주(24~)</th>
        <th class="center" style="width:78px;" onclick="sortBy(12)">최근발주(전체)</th>
        <th class="right" style="width:36px;">건수</th>
        <th style="width:170px;">프로젝트</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
  </div>

  <div class="footer">
    생성: {NOW.strftime('%Y-%m-%d %H:%M')} KST | 발주 기준: 2024-01-01 이후 | 데이터 출처: ERP 현재고현황 전건
  </div>
</div>

<script>
const DATA = {js_data_str};
let poFilter = 'all';
let kindFilter = '';
let sortCol = 5;
let sortAsc = false;
let filtered = [...DATA];

function fmtN(v) {{ return v ? Math.round(v).toLocaleString() : '-'; }}
function fmtQ(v) {{ return v ? (v === Math.floor(v) ? Math.floor(v).toLocaleString() : v.toLocaleString()) : '-'; }}

function renderRows(rows) {{
  const tb = document.getElementById('tbody');
  let html = '';
  for (let i = 0; i < rows.length; i++) {{
    const r = rows[i];
    const amt = r[5];
    let ac = '';
    if (amt >= 50000000) ac = ' class="amt-high"';
    else if (amt >= 10000000) ac = ' class="amt-mid"';
    let badge;
    if (r[6]===2) badge='<span class="badge po-yes">24년이후 발주</span>';
    else if (r[6]===1) badge='<span class="badge po-past">과거발주</span>';
    else badge='<span class="badge po-no">이력없음</span>';
    const pjt = r[9].length > 26 ? r[9].substring(0,24)+'..' : r[9];
    html += '<tr>' +
      '<td class="center">'+(i+1)+'</td>' +
      '<td class="code">'+r[1]+'</td>' +
      '<td>'+r[2]+'</td>' +
      '<td class="spec">'+r[3]+'</td>' +
      '<td class="center" style="font-size:7.5pt;">'+r[10]+'</td>' +
      '<td class="right">'+fmtQ(r[4])+'</td>' +
      '<td class="right"'+ac+'>'+fmtN(r[5])+'</td>' +
      '<td class="center">'+badge+'</td>' +
      '<td class="center">'+(r[7]||'-')+'</td>' +
      '<td class="center">'+(r[12]||'-')+'</td>' +
      '<td class="right">'+(r[8]||'-')+'</td>' +
      '<td class="pjt">'+(pjt||'-')+'</td></tr>';
  }}
  tb.innerHTML = html;
  document.getElementById('result-count').textContent = rows.length.toLocaleString() + '건 표시';
}}

function applyFilters() {{
  const q = document.getElementById('search').value.toLowerCase();
  filtered = DATA.filter(r => {{
    if (poFilter !== 'all' && r[6] !== parseInt(poFilter)) return false;
    if (kindFilter && r[10] !== kindFilter) return false;
    if (q) {{
      const txt = (r[1]+' '+r[2]+' '+r[3]+' '+r[9]).toLowerCase();
      if (!txt.includes(q)) return false;
    }}
    return true;
  }});
  doSort();
  renderRows(filtered);
}}

function setPo(mode) {{
  poFilter = mode;
  document.querySelectorAll('[data-po]').forEach(b => b.classList.toggle('active', b.dataset.po === mode));
  applyFilters();
}}

function filterKind(kind) {{
  const cards = document.querySelectorAll('.kind-card');
  if (kindFilter === kind) {{
    kindFilter = '';
    cards.forEach(c => c.classList.remove('active'));
  }} else {{
    kindFilter = kind;
    cards.forEach(c => c.classList.toggle('active', c.querySelector('.kind-label').textContent === kind));
  }}
  applyFilters();
}}

function sortBy(col) {{
  if (sortCol === col) sortAsc = !sortAsc;
  else {{ sortCol = col; sortAsc = (col <= 3 || col === 7 || col === 10); }}
  doSort();
  renderRows(filtered);
}}

function doSort() {{
  filtered.sort((a, b) => {{
    let va = a[sortCol], vb = b[sortCol];
    if (typeof va === 'string') {{ va = va.toLowerCase(); vb = (vb||'').toLowerCase(); }}
    if (va < vb) return sortAsc ? -1 : 1;
    if (va > vb) return sortAsc ? 1 : -1;
    return 0;
  }});
}}

applyFilters();
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
