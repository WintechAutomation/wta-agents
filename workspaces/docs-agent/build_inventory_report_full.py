"""
ERP 현재고현황 + 구매진행현황 보고서 (전건, v4 간소화)
발주계획/실제발주/입고검수 통합 → 발주일 단일 컬럼
"""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)

DATA_PATH = Path(r'C:\MES\wta-agents\workspaces\db-manager\erp_inventory_full_v4.json')
OUTPUT = Path(r'C:\MES\wta-agents\reports\김근형\erp_재고현황_발주내역.html')

ITEM_KIND_MAP = {'1': '원자재', '2': '부자재', '3': '반제품', '6': '상품', '7': '기타'}


def fmt_amt(v):
    if not v:
        return '-'
    return f"{int(v):,}"


def escape_html(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def best_date(d):
    """실제발주일 > 입고검수일 > 발주계획일 우선순위로 최근 날짜 반환."""
    candidates = []
    if d.get('last_po_dt'):
        candidates.append(d['last_po_dt'])
    if d.get('last_receipt_dt'):
        candidates.append(d['last_receipt_dt'])
    if d.get('last_plan_dt'):
        candidates.append(d['last_plan_dt'])
    if candidates:
        return max(candidates)
    # fallback: 전체기간
    fb = []
    if d.get('all_time_last_po_dt'):
        fb.append(d['all_time_last_po_dt'])
    if d.get('all_time_last_receipt_dt'):
        fb.append(d['all_time_last_receipt_dt'])
    return max(fb) if fb else ''


def classify(d):
    """사용/과거발주/미사용"""
    if d.get('has_po') or d.get('has_receipt') or d.get('has_plan'):
        return 3  # 사용
    elif d.get('all_time_last_po_dt') or d.get('all_time_last_receipt_dt'):
        return 2  # 과거발주
    else:
        return 1  # 미사용


def main():
    data = json.loads(DATA_PATH.read_text(encoding='utf-8'))
    total = len(data)

    for d in data:
        d['_cls'] = classify(d)
        d['_best_dt'] = best_date(d)

    cat3 = [d for d in data if d['_cls'] == 3]
    cat2 = [d for d in data if d['_cls'] == 2]
    cat1 = [d for d in data if d['_cls'] == 1]
    amt3 = sum(d.get('stock_amt', 0) for d in cat3)
    amt2 = sum(d.get('stock_amt', 0) for d in cat2)
    amt1 = sum(d.get('stock_amt', 0) for d in cat1)
    total_amt = sum(d.get('stock_amt', 0) for d in data)

    kind_stats = {}
    for d in data:
        k = ITEM_KIND_MAP.get(d.get('item_kind', ''), d.get('item_kind', ''))
        if k not in kind_stats:
            kind_stats[k] = {'count': 0, 'amt': 0}
        kind_stats[k]['count'] += 1
        kind_stats[k]['amt'] += d.get('stock_amt', 0)

    # JS data — simplified
    js_data = []
    for i, d in enumerate(data):
        kind_label = ITEM_KIND_MAP.get(d.get('item_kind', ''), d.get('item_kind', ''))
        pjt = d.get('last_pjt_name', '') or d.get('plan_pjt_name', '') or d.get('receipt_pjt_name', '') or ''
        po_count = (d.get('po_count', 0) or 0) + (d.get('plan_count', 0) or 0) + (d.get('receipt_count', 0) or 0)

        js_data.append([
            i + 1,                                      # 0: rank
            escape_html(d.get('item_cd', '')),          # 1: item_cd
            escape_html(d.get('item_nm', '')),          # 2: item_nm
            escape_html(d.get('spec', '') or ''),       # 3: spec
            d.get('stock_qty', 0),                      # 4: qty
            d.get('stock_amt', 0),                      # 5: amt
            d['_cls'],                                   # 6: cls (1~3)
            kind_label,                                  # 7: kind
            d['_best_dt'],                               # 8: best_date (발주일)
            po_count,                                    # 9: total count
            escape_html(pjt),                           # 10: project
            escape_html(d.get('location', '') or ''),   # 11: location
        ])

    js_str = json.dumps(js_data, ensure_ascii=False)

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
<title>ERP 현재고현황 및 구매진행현황</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Malgun Gothic', 'Pretendard Variable', sans-serif; background: #f5f5f5; padding: 16px; margin: 0; }}
  .header {{ background: #1a237e; color: #fff; padding: 18px 22px; border-radius: 8px 8px 0 0; }}
  .header h1 {{ margin: 0; font-size: 17pt; }}
  .header .sub {{ font-size: 9pt; color: #b3b9e6; margin-top: 4px; }}
  .container {{ background: #fff; border-radius: 0 0 8px 8px; padding: 18px; box-shadow: 0 2px 8px rgba(0,0,0,.1); }}

  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin-bottom: 14px; }}
  .summary-card {{ background: #f8f9ff; border: 1px solid #e0e3f0; border-radius: 8px; padding: 12px; text-align: center; }}
  .summary-card .label {{ font-size: 9pt; color: #666; margin-bottom: 3px; }}
  .summary-card .value {{ font-size: 15pt; font-weight: 700; }}
  .summary-card .sub-value {{ font-size: 8pt; color: #888; margin-top: 2px; }}

  .kind-row {{ display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }}
  .kind-card {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 8px 12px; cursor: pointer;
    transition: all 0.2s; min-width: 100px; text-align: center; }}
  .kind-card:hover, .kind-card.active {{ border-color: #1a237e; background: #e8eaf6; }}
  .kind-label {{ font-size: 9pt; font-weight: 700; color: #1a237e; }}
  .kind-count {{ font-size: 11pt; font-weight: 700; }}
  .kind-amt {{ font-size: 7.5pt; color: #666; }}

  .toolbar {{ display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; align-items: center; }}
  .search-box {{ padding: 5px 12px; border: 1px solid #ccc; border-radius: 20px; font-size: 9pt; width: 260px;
    font-family: 'Malgun Gothic', sans-serif; }}
  .filter-btn {{ padding: 4px 12px; border: 1px solid #ccc; background: #fff; border-radius: 20px;
    cursor: pointer; font-size: 8.5pt; font-family: 'Malgun Gothic', sans-serif; transition: all 0.2s; }}
  .filter-btn.active {{ background: #1a237e; color: #fff; border-color: #1a237e; }}
  .filter-btn:hover:not(.active) {{ background: #e8eaf6; }}
  .result-count {{ font-size: 8.5pt; color: #666; margin-left: auto; }}

  .table-wrap {{ max-height: 74vh; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 4px; }}
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
  .pjt {{ font-size: 8pt; color: #333; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .amt-high {{ color: #c62828; font-weight: 700; }}
  .amt-mid {{ color: #e65100; font-weight: 600; }}

  .badge {{ display: inline-block; padding: 2px 7px; border-radius: 10px; font-size: 7.5pt; font-weight: 600; }}
  .cls-3 {{ background: #e8f5e9; color: #2e7d32; }}
  .cls-2 {{ background: #fff3e0; color: #e65100; }}
  .cls-1 {{ background: #f5f5f5; color: #888; }}

  .footer {{ font-size: 8pt; color: #888; margin-top: 14px; text-align: right; }}

  @media print {{
    body {{ padding: 0; background: #fff; }}
    .toolbar, .kind-row {{ display: none; }}
    .table-wrap {{ max-height: none; overflow: visible; }}
  }}
</style>
</head>
<body>
<div class="header">
  <h1>ERP 현재고현황 및 구매진행현황</h1>
  <div class="sub">(주)윈텍오토메이션 생산관리팀 | 전체 {total:,}건 | 구매진행현황 기준 | {NOW.strftime('%Y-%m-%d')}</div>
</div>
<div class="container">
  <div class="summary">
    <div class="summary-card">
      <div class="label">총 품목</div>
      <div class="value" style="color:#1a237e;">{total:,}건</div>
      <div class="sub-value">약 {total_amt/100_000_000:.1f}억원</div>
    </div>
    <div class="summary-card">
      <div class="label">사용</div>
      <div class="value" style="color:#2e7d32;">{len(cat3):,}건</div>
      <div class="sub-value">{fmt_amt(amt3)}원</div>
    </div>
    <div class="summary-card">
      <div class="label">과거발주</div>
      <div class="value" style="color:#e65100;">{len(cat2):,}건</div>
      <div class="sub-value">{fmt_amt(amt2)}원</div>
    </div>
    <div class="summary-card">
      <div class="label">미사용</div>
      <div class="value" style="color:#888;">{len(cat1):,}건</div>
      <div class="sub-value">{fmt_amt(amt1)}원</div>
    </div>
  </div>

  <div class="kind-row">
{kind_cards_html}
  </div>

  <div class="toolbar">
    <input type="text" class="search-box" id="search" placeholder="품목코드/품목명/규격/프로젝트 검색..." oninput="applyFilters()"/>
    <button class="filter-btn active" data-st="all" onclick="setSt('all')">전체 ({total:,})</button>
    <button class="filter-btn" data-st="3" onclick="setSt('3')">사용 ({len(cat3):,})</button>
    <button class="filter-btn" data-st="2" onclick="setSt('2')">과거발주 ({len(cat2):,})</button>
    <button class="filter-btn" data-st="1" onclick="setSt('1')">미사용 ({len(cat1):,})</button>
    <span class="result-count" id="result-count"></span>
  </div>

  <div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th class="center" style="width:34px;" onclick="sortBy(0)">#</th>
        <th style="width:120px;" onclick="sortBy(1)">품목코드</th>
        <th onclick="sortBy(2)">품목명</th>
        <th style="width:140px;">규격</th>
        <th class="center" style="width:45px;" onclick="sortBy(7)">구분</th>
        <th class="right" style="width:50px;" onclick="sortBy(4)">수량</th>
        <th class="right" style="width:100px;" onclick="sortBy(5)">재고금액(원)</th>
        <th class="center" style="width:55px;" onclick="sortBy(6)">상태</th>
        <th class="center" style="width:85px;" onclick="sortBy(8)">발주일</th>
        <th class="right" style="width:40px;" onclick="sortBy(9)">건수</th>
        <th style="width:200px;" onclick="sortBy(10)">프로젝트</th>
        <th class="center" style="width:65px;">보관위치</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
  </div>

  <div class="footer">
    생성: {NOW.strftime('%Y-%m-%d %H:%M')} KST | 구매진행현황 (발주계획+실제발주+입고검수 통합) | 기준: 2024.01~ | 데이터 출처: ERP
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

const CLS_LABELS = {{3:'사용',2:'과거발주',1:'미사용'}};
const CLS_CLASS = {{3:'cls-3',2:'cls-2',1:'cls-1'}};

function renderRows(rows) {{
  const tb = document.getElementById('tbody');
  let h = '';
  for (let i = 0; i < rows.length; i++) {{
    const r = rows[i];
    const amt = r[5];
    let ac = '';
    if (amt >= 50000000) ac = ' class="amt-high"';
    else if (amt >= 10000000) ac = ' class="amt-mid"';
    const cls = r[6];
    const badge = '<span class="badge '+CLS_CLASS[cls]+'">'+CLS_LABELS[cls]+'</span>';
    let pjt = r[10] || '-';
    if (pjt.length > 28) pjt = pjt.substring(0,26)+'..';
    h += '<tr>' +
      '<td class="center">'+(i+1)+'</td>' +
      '<td class="code">'+r[1]+'</td>' +
      '<td>'+r[2]+'</td>' +
      '<td class="spec">'+r[3]+'</td>' +
      '<td class="center" style="font-size:7.5pt;">'+r[7]+'</td>' +
      '<td class="right">'+fmtQ(r[4])+'</td>' +
      '<td class="right"'+ac+'>'+fmtN(r[5])+'</td>' +
      '<td class="center">'+badge+'</td>' +
      '<td class="center">'+(r[8]||'-')+'</td>' +
      '<td class="right">'+(r[9]||'-')+'</td>' +
      '<td class="pjt">'+pjt+'</td>' +
      '<td class="center" style="font-size:7.5pt;">'+(r[11]||'-')+'</td></tr>';
  }}
  tb.innerHTML = h;
  document.getElementById('result-count').textContent = rows.length.toLocaleString() + '건';
}}

function applyFilters() {{
  const q = document.getElementById('search').value.toLowerCase();
  filtered = DATA.filter(r => {{
    if (stFilter !== 'all' && r[6] !== parseInt(stFilter)) return false;
    if (kindFilter && r[7] !== kindFilter) return false;
    if (q) {{
      const txt = (r[1]+' '+r[2]+' '+r[3]+' '+r[10]).toLowerCase();
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
  else {{ sortCol = col; sortAsc = (typeof DATA[0][col] === 'string'); }}
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
