"""
ERP 현재고현황 + 발주내역 보고서 (전건, v3)
발주계획(MBA210T) + 실제발주(MCA210T) 포함
"""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)

DATA_PATH = Path(r'C:\MES\wta-agents\workspaces\db-manager\erp_inventory_full_v3.json')
OUTPUT = Path(r'C:\MES\wta-agents\reports\김근형\erp_재고현황_발주내역.html')

ITEM_KIND_MAP = {'1': '원자재', '2': '부자재', '3': '반제품', '6': '상품', '7': '기타'}
PLAN_STS_MAP = {'20': '검토', '30': '발주요청', '40': '발주중', '50': '발주완료', '70': '완료'}


def fmt_amt(v):
    if not v:
        return '-'
    return f"{int(v):,}"


def escape_html(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def main():
    data = json.loads(DATA_PATH.read_text(encoding='utf-8'))
    total = len(data)

    # 4-tier classification
    cat_po = [d for d in data if d.get('has_po')]                                    # 실제발주 있음
    cat_plan = [d for d in data if not d.get('has_po') and d.get('has_plan')]         # 발주계획만
    cat_past = [d for d in data if not d.get('has_po') and not d.get('has_plan') and d.get('all_time_last_po_dt')]  # 과거발주만
    cat_none = [d for d in data if not d.get('has_po') and not d.get('has_plan') and not d.get('all_time_last_po_dt')]  # 이력없음

    amt_po = sum(d.get('stock_amt', 0) for d in cat_po)
    amt_plan = sum(d.get('stock_amt', 0) for d in cat_plan)
    amt_past = sum(d.get('stock_amt', 0) for d in cat_past)
    amt_none = sum(d.get('stock_amt', 0) for d in cat_none)
    total_amt = sum(d.get('stock_amt', 0) for d in data)

    # 품목구분 통계
    kind_stats = {}
    for d in data:
        k = ITEM_KIND_MAP.get(d.get('item_kind', ''), d.get('item_kind', ''))
        if k not in kind_stats:
            kind_stats[k] = {'count': 0, 'amt': 0}
        kind_stats[k]['count'] += 1
        kind_stats[k]['amt'] += d.get('stock_amt', 0)

    # JS data array
    js_data = []
    for i, d in enumerate(data):
        kind_label = ITEM_KIND_MAP.get(d.get('item_kind', ''), d.get('item_kind', ''))
        # status: 3=발주완료, 2=발주계획중, 1=과거발주만, 0=이력없음
        if d.get('has_po'):
            status = 3
        elif d.get('has_plan'):
            status = 2
        elif d.get('all_time_last_po_dt'):
            status = 1
        else:
            status = 0

        plan_sts_label = PLAN_STS_MAP.get(d.get('plan_sts', ''), '') if d.get('has_plan') else ''

        js_data.append([
            i + 1,                                          # 0: rank
            escape_html(d.get('item_cd', '')),              # 1: item_cd
            escape_html(d.get('item_nm', '')),              # 2: item_nm
            escape_html(d.get('spec', '') or ''),           # 3: spec
            d.get('stock_qty', 0),                          # 4: qty
            d.get('stock_amt', 0),                          # 5: amt
            status,                                          # 6: status (0~3)
            d.get('last_po_dt', '') or '',                   # 7: last_po_dt (2024~)
            d.get('po_count', 0),                            # 8: po_count
            escape_html(d.get('last_pjt_name', '') or ''),  # 9: po_pjt
            kind_label,                                      # 10: kind
            d.get('all_time_last_po_dt', '') or '',           # 11: all_time_last_po_dt
            d.get('last_plan_dt', '') or '',                  # 12: last_plan_dt
            d.get('plan_count', 0),                          # 13: plan_count
            escape_html(d.get('plan_pjt_name', '') or ''),  # 14: plan_pjt
            plan_sts_label,                                  # 15: plan_sts_label
        ])

    js_str = json.dumps(js_data, ensure_ascii=False)

    # kind cards
    kind_cards_html = ''
    for label in ['원자재', '부자재', '반제품', '상품', '기타']:
        if label in kind_stats:
            s = kind_stats[label]
            kind_cards_html += f"""<div class="kind-card" onclick="filterKind('{label}')">
  <div class="kind-label">{label}</div>
  <div class="kind-count">{s['count']:,}건</div>
  <div class="kind-amt">{fmt_amt(s['amt'])}원</div>
</div>\n"""

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

  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin-bottom: 14px; }}
  .summary-card {{ background: #f8f9ff; border: 1px solid #e0e3f0; border-radius: 8px; padding: 12px; text-align: center; }}
  .summary-card .label {{ font-size: 8.5pt; color: #666; margin-bottom: 3px; }}
  .summary-card .value {{ font-size: 14pt; font-weight: 700; color: #1a237e; }}
  .summary-card .sub-value {{ font-size: 7.5pt; color: #888; margin-top: 2px; }}

  .kind-row {{ display: flex; gap: 6px; margin-bottom: 14px; flex-wrap: wrap; }}
  .kind-card {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 8px 12px; cursor: pointer;
    transition: all 0.2s; min-width: 100px; text-align: center; }}
  .kind-card:hover, .kind-card.active {{ border-color: #1a237e; background: #e8eaf6; }}
  .kind-label {{ font-size: 9pt; font-weight: 700; color: #1a237e; }}
  .kind-count {{ font-size: 11pt; font-weight: 700; }}
  .kind-amt {{ font-size: 7.5pt; color: #666; }}

  .toolbar {{ display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; align-items: center; }}
  .search-box {{ padding: 5px 10px; border: 1px solid #ccc; border-radius: 20px; font-size: 9pt; width: 240px;
    font-family: 'Malgun Gothic', sans-serif; }}
  .filter-btn {{ padding: 4px 10px; border: 1px solid #ccc; background: #fff; border-radius: 20px;
    cursor: pointer; font-size: 8.5pt; font-family: 'Malgun Gothic', sans-serif; transition: all 0.2s; }}
  .filter-btn.active {{ background: #1a237e; color: #fff; border-color: #1a237e; }}
  .filter-btn:hover:not(.active) {{ background: #e8eaf6; }}
  .result-count {{ font-size: 8.5pt; color: #666; margin-left: auto; }}

  .table-wrap {{ max-height: 72vh; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 4px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 8pt; }}
  th {{ background: #e8eaf6; color: #1a237e; padding: 7px 5px; text-align: left; font-weight: 700;
    position: sticky; top: 0; z-index: 5; border-bottom: 2px solid #1a237e; cursor: pointer; white-space: nowrap; font-size: 8pt; }}
  th:hover {{ background: #c5cae9; }}
  td {{ padding: 5px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }}
  tr:hover {{ background: #f5f7ff; }}
  .center {{ text-align: center; }}
  .right {{ text-align: right; font-family: 'Consolas', monospace; }}
  .code {{ font-family: 'Consolas', monospace; font-size: 7.5pt; color: #555; }}
  .spec {{ font-size: 7pt; color: #777; max-width: 130px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .pjt {{ font-size: 7pt; color: #333; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .amt-high {{ color: #c62828; font-weight: 700; }}
  .amt-mid {{ color: #e65100; font-weight: 600; }}

  .badge {{ display: inline-block; padding: 2px 6px; border-radius: 10px; font-size: 7pt; font-weight: 600; white-space: nowrap; }}
  .st-3 {{ background: #e8f5e9; color: #2e7d32; }}
  .st-2 {{ background: #e3f2fd; color: #1565c0; }}
  .st-1 {{ background: #fff3e0; color: #e65100; }}
  .st-0 {{ background: #f5f5f5; color: #888; }}

  .footer {{ font-size: 7.5pt; color: #888; margin-top: 14px; text-align: right; }}
  .legend {{ font-size: 7.5pt; color: #666; margin-bottom: 8px; padding: 6px 10px; background: #fafafa; border-radius: 4px; border: 1px solid #eee; }}
  .legend span {{ margin-right: 12px; }}

  @media print {{
    body {{ padding: 0; background: #fff; }}
    .toolbar, .kind-row {{ display: none; }}
    .table-wrap {{ max-height: none; overflow: visible; }}
  }}
</style>
</head>
<body>
<div class="header">
  <h1>ERP 현재고현황 및 발주내역 분석</h1>
  <div class="sub">(주)윈텍오토메이션 생산관리팀 | 재고량 > 0 전건 ({total:,}건) | 발주계획(MBA210T) + 실제발주(MCA210T) 기준 | {NOW.strftime('%Y-%m-%d')}</div>
</div>
<div class="container">
  <div class="summary">
    <div class="summary-card">
      <div class="label">총 품목</div>
      <div class="value">{total:,}건</div>
      <div class="sub-value">약 {total_amt/100_000_000:.1f}억원</div>
    </div>
    <div class="summary-card">
      <div class="label">발주완료 (24년~)</div>
      <div class="value" style="color:#2e7d32;">{len(cat_po):,}건</div>
      <div class="sub-value">{fmt_amt(amt_po)}원</div>
    </div>
    <div class="summary-card">
      <div class="label">발주계획중</div>
      <div class="value" style="color:#1565c0;">{len(cat_plan):,}건</div>
      <div class="sub-value">{fmt_amt(amt_plan)}원</div>
    </div>
    <div class="summary-card">
      <div class="label">과거발주만</div>
      <div class="value" style="color:#e65100;">{len(cat_past):,}건</div>
      <div class="sub-value">{fmt_amt(amt_past)}원</div>
    </div>
    <div class="summary-card">
      <div class="label">발주이력없음</div>
      <div class="value" style="color:#888;">{len(cat_none):,}건</div>
      <div class="sub-value">{fmt_amt(amt_none)}원</div>
    </div>
  </div>

  <div class="kind-row">
{kind_cards_html}
  </div>

  <div class="legend">
    <span><span class="badge st-3">발주완료</span> 2024년 이후 실제 발주서 발행</span>
    <span><span class="badge st-2">발주계획중</span> 발주계획 등록 (발주서 미발행)</span>
    <span><span class="badge st-1">과거발주</span> 2024년 이전 발주만 있음</span>
    <span><span class="badge st-0">이력없음</span> 발주 이력 전혀 없음</span>
  </div>

  <div class="toolbar">
    <input type="text" class="search-box" id="search" placeholder="품목코드/품목명/규격/프로젝트 검색..." oninput="applyFilters()"/>
    <button class="filter-btn active" data-st="all" onclick="setSt('all')">전체 ({total:,})</button>
    <button class="filter-btn" data-st="3" onclick="setSt('3')">발주완료 ({len(cat_po):,})</button>
    <button class="filter-btn" data-st="2" onclick="setSt('2')">발주계획 ({len(cat_plan):,})</button>
    <button class="filter-btn" data-st="1" onclick="setSt('1')">과거발주 ({len(cat_past):,})</button>
    <button class="filter-btn" data-st="0" onclick="setSt('0')">이력없음 ({len(cat_none):,})</button>
    <span class="result-count" id="result-count"></span>
  </div>

  <div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th class="center" style="width:32px;" onclick="sortBy(0)">#</th>
        <th style="width:120px;" onclick="sortBy(1)">품목코드</th>
        <th onclick="sortBy(2)">품목명</th>
        <th style="width:120px;">규격</th>
        <th class="center" style="width:42px;" onclick="sortBy(10)">구분</th>
        <th class="right" style="width:48px;" onclick="sortBy(4)">수량</th>
        <th class="right" style="width:95px;" onclick="sortBy(5)">재고금액</th>
        <th class="center" style="width:62px;" onclick="sortBy(6)">발주상태</th>
        <th class="center" style="width:72px;" onclick="sortBy(7)">발주일(24~)</th>
        <th class="center" style="width:72px;" onclick="sortBy(12)">계획일</th>
        <th class="center" style="width:48px;">계획상태</th>
        <th class="center" style="width:72px;" onclick="sortBy(11)">최종발주(전체)</th>
        <th style="width:140px;">프로젝트</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
  </div>

  <div class="footer">
    생성: {NOW.strftime('%Y-%m-%d %H:%M')} KST | 발주계획: MBA210T (2024.01~) | 실제발주: MCA210T (2024.01~) | 데이터 출처: ERP
  </div>
</div>

<script>
const DATA = {js_str};
let stFilter = 'all';
let kindFilter = '';
let sortCol = 5;
let sortAsc = false;
let filtered = [...DATA];

function fmtN(v) {{ return v ? Math.round(v).toLocaleString() : '-'; }}
function fmtQ(v) {{ if(!v) return '-'; return (v===Math.floor(v)) ? Math.floor(v).toLocaleString() : v.toLocaleString(); }}

const ST_LABELS = {{3:'발주완료',2:'계획중',1:'과거발주',0:'이력없음'}};
const ST_CLASS = {{3:'st-3',2:'st-2',1:'st-1',0:'st-0'}};

function renderRows(rows) {{
  const tb = document.getElementById('tbody');
  let h = '';
  for (let i = 0; i < rows.length; i++) {{
    const r = rows[i];
    const amt = r[5];
    let ac = '';
    if (amt >= 50000000) ac = ' class="amt-high"';
    else if (amt >= 10000000) ac = ' class="amt-mid"';
    const st = r[6];
    const badge = '<span class="badge '+ST_CLASS[st]+'">'+ST_LABELS[st]+'</span>';
    // project: show plan_pjt if no po_pjt
    let pjt = r[9] || r[14] || '-';
    if (pjt.length > 24) pjt = pjt.substring(0,22)+'..';
    h += '<tr>' +
      '<td class="center">'+(i+1)+'</td>' +
      '<td class="code">'+r[1]+'</td>' +
      '<td>'+r[2]+'</td>' +
      '<td class="spec">'+r[3]+'</td>' +
      '<td class="center" style="font-size:7pt;">'+r[10]+'</td>' +
      '<td class="right">'+fmtQ(r[4])+'</td>' +
      '<td class="right"'+ac+'>'+fmtN(r[5])+'</td>' +
      '<td class="center">'+badge+'</td>' +
      '<td class="center">'+(r[7]||'-')+'</td>' +
      '<td class="center">'+(r[12]||'-')+'</td>' +
      '<td class="center" style="font-size:7pt;">'+(r[15]||'-')+'</td>' +
      '<td class="center">'+(r[11]||'-')+'</td>' +
      '<td class="pjt">'+pjt+'</td></tr>';
  }}
  tb.innerHTML = h;
  document.getElementById('result-count').textContent = rows.length.toLocaleString() + '건';
}}

function applyFilters() {{
  const q = document.getElementById('search').value.toLowerCase();
  filtered = DATA.filter(r => {{
    if (stFilter !== 'all' && r[6] !== parseInt(stFilter)) return false;
    if (kindFilter && r[10] !== kindFilter) return false;
    if (q) {{
      const txt = (r[1]+' '+r[2]+' '+r[3]+' '+r[9]+' '+r[14]).toLowerCase();
      if (!txt.includes(q)) return false;
    }}
    return true;
  }});
  doSort();
  renderRows(filtered);
}}

function setSt(mode) {{
  stFilter = mode;
  document.querySelectorAll('[data-st]').forEach(b => b.classList.toggle('active', b.dataset.st === mode));
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
  else {{ sortCol = col; sortAsc = (col <= 3 || col === 7 || col === 10 || col === 11 || col === 12); }}
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
