"""
ERP 현재고현황 + 구매진행현황 보고서 (전건, v4)
발주계획(MBA210T) + 실제발주(MCA210T) + 입고검수(MDA100T) 포함
"""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)

DATA_PATH = Path(r'C:\MES\wta-agents\workspaces\db-manager\erp_inventory_full_v4.json')
OUTPUT = Path(r'C:\MES\wta-agents\reports\김근형\erp_재고현황_발주내역.html')

ITEM_KIND_MAP = {'1': '원자재', '2': '부자재', '3': '반제품', '6': '상품', '7': '기타'}
PLAN_STS_MAP = {'20': '검토', '30': '발주요청', '40': '발주중', '50': '발주완료', '70': '완료'}


def fmt_amt(v):
    if not v:
        return '-'
    return f"{int(v):,}"


def escape_html(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def classify(d):
    """품목 분류: 4=활성, 3=발주계획중, 2=과거활동, 1=장기미활동"""
    has_po = d.get('has_po', False)
    has_receipt = d.get('has_receipt', False)
    has_plan = d.get('has_plan', False)
    has_past = bool(d.get('all_time_last_po_dt') or d.get('all_time_last_receipt_dt'))

    if has_po or has_receipt:
        return 4  # 활성
    elif has_plan:
        return 3  # 발주계획중
    elif has_past:
        return 2  # 과거활동
    else:
        return 1  # 장기미활동


def main():
    data = json.loads(DATA_PATH.read_text(encoding='utf-8'))
    total = len(data)

    # Classify
    for d in data:
        d['_cls'] = classify(d)

    cat4 = [d for d in data if d['_cls'] == 4]
    cat3 = [d for d in data if d['_cls'] == 3]
    cat2 = [d for d in data if d['_cls'] == 2]
    cat1 = [d for d in data if d['_cls'] == 1]

    amt4 = sum(d.get('stock_amt', 0) for d in cat4)
    amt3 = sum(d.get('stock_amt', 0) for d in cat3)
    amt2 = sum(d.get('stock_amt', 0) for d in cat2)
    amt1 = sum(d.get('stock_amt', 0) for d in cat1)
    total_amt = sum(d.get('stock_amt', 0) for d in data)

    # 품목구분 통계
    kind_stats = {}
    for d in data:
        k = ITEM_KIND_MAP.get(d.get('item_kind', ''), d.get('item_kind', ''))
        if k not in kind_stats:
            kind_stats[k] = {'count': 0, 'amt': 0}
        kind_stats[k]['count'] += 1
        kind_stats[k]['amt'] += d.get('stock_amt', 0)

    # JS data
    js_data = []
    for i, d in enumerate(data):
        kind_label = ITEM_KIND_MAP.get(d.get('item_kind', ''), d.get('item_kind', ''))
        plan_sts_label = PLAN_STS_MAP.get(d.get('plan_sts', ''), '') if d.get('has_plan') else ''

        # best project: po > plan > receipt
        pjt = d.get('last_pjt_name', '') or d.get('plan_pjt_name', '') or d.get('receipt_pjt_name', '') or ''

        js_data.append([
            i + 1,                                          # 0: rank
            escape_html(d.get('item_cd', '')),              # 1: item_cd
            escape_html(d.get('item_nm', '')),              # 2: item_nm
            escape_html(d.get('spec', '') or ''),           # 3: spec
            d.get('stock_qty', 0),                          # 4: qty
            d.get('stock_amt', 0),                          # 5: amt
            d['_cls'],                                       # 6: classification (1~4)
            kind_label,                                      # 7: kind
            # 발주계획
            d.get('last_plan_dt', '') or '',                  # 8: plan_dt
            d.get('plan_count', 0),                          # 9: plan_count
            plan_sts_label,                                  # 10: plan_sts
            # 실제발주
            d.get('last_po_dt', '') or '',                   # 11: po_dt (2024~)
            d.get('po_count', 0),                            # 12: po_count
            d.get('all_time_last_po_dt', '') or '',           # 13: all_time_po
            # 입고검수
            d.get('last_receipt_dt', '') or '',               # 14: receipt_dt (2024~)
            d.get('receipt_count', 0),                        # 15: receipt_count
            d.get('total_receipt_qty', 0),                    # 16: receipt_qty
            d.get('total_bad_qty', 0),                        # 17: bad_qty
            d.get('all_time_last_receipt_dt', '') or '',       # 18: all_time_receipt
            # 프로젝트
            escape_html(pjt),                                # 19: project
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
<title>ERP 현재고현황 및 구매진행현황</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Malgun Gothic', 'Pretendard Variable', sans-serif; background: #f5f5f5; padding: 16px; margin: 0; }}
  .header {{ background: #1a237e; color: #fff; padding: 18px 22px; border-radius: 8px 8px 0 0; }}
  .header h1 {{ margin: 0; font-size: 17pt; }}
  .header .sub {{ font-size: 9pt; color: #b3b9e6; margin-top: 4px; }}
  .container {{ background: #fff; border-radius: 0 0 8px 8px; padding: 18px; box-shadow: 0 2px 8px rgba(0,0,0,.1); }}

  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; margin-bottom: 12px; }}
  .summary-card {{ background: #f8f9ff; border: 1px solid #e0e3f0; border-radius: 8px; padding: 10px; text-align: center; }}
  .summary-card .label {{ font-size: 8pt; color: #666; margin-bottom: 2px; }}
  .summary-card .value {{ font-size: 13pt; font-weight: 700; }}
  .summary-card .sub-value {{ font-size: 7pt; color: #888; margin-top: 1px; }}

  .kind-row {{ display: flex; gap: 5px; margin-bottom: 10px; flex-wrap: wrap; }}
  .kind-card {{ background: #fff; border: 1px solid #ddd; border-radius: 6px; padding: 6px 10px; cursor: pointer;
    transition: all 0.2s; min-width: 90px; text-align: center; }}
  .kind-card:hover, .kind-card.active {{ border-color: #1a237e; background: #e8eaf6; }}
  .kind-label {{ font-size: 8.5pt; font-weight: 700; color: #1a237e; }}
  .kind-count {{ font-size: 10pt; font-weight: 700; }}
  .kind-amt {{ font-size: 7pt; color: #666; }}

  .toolbar {{ display: flex; gap: 5px; margin-bottom: 8px; flex-wrap: wrap; align-items: center; }}
  .search-box {{ padding: 4px 10px; border: 1px solid #ccc; border-radius: 20px; font-size: 8.5pt; width: 220px;
    font-family: 'Malgun Gothic', sans-serif; }}
  .filter-btn {{ padding: 3px 9px; border: 1px solid #ccc; background: #fff; border-radius: 20px;
    cursor: pointer; font-size: 8pt; font-family: 'Malgun Gothic', sans-serif; transition: all 0.2s; }}
  .filter-btn.active {{ background: #1a237e; color: #fff; border-color: #1a237e; }}
  .filter-btn:hover:not(.active) {{ background: #e8eaf6; }}
  .result-count {{ font-size: 8pt; color: #666; margin-left: auto; }}

  .legend {{ font-size: 7pt; color: #666; margin-bottom: 6px; padding: 5px 8px; background: #fafafa; border-radius: 4px; border: 1px solid #eee; }}
  .legend span {{ margin-right: 10px; }}

  .table-wrap {{ max-height: 72vh; overflow: auto; border: 1px solid #e0e0e0; border-radius: 4px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 7.5pt; white-space: nowrap; }}
  th {{ background: #e8eaf6; color: #1a237e; padding: 6px 4px; text-align: left; font-weight: 700;
    position: sticky; top: 0; z-index: 5; border-bottom: 2px solid #1a237e; cursor: pointer; font-size: 7.5pt; }}
  th:hover {{ background: #c5cae9; }}
  .th-group {{ background: #d1d9f0; text-align: center; font-size: 7pt; padding: 3px; border-bottom: 1px solid #9fa8da; }}
  td {{ padding: 4px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }}
  tr:hover {{ background: #f5f7ff; }}
  .center {{ text-align: center; }}
  .right {{ text-align: right; font-family: 'Consolas', monospace; }}
  .code {{ font-family: 'Consolas', monospace; font-size: 7pt; color: #555; }}
  .spec {{ font-size: 6.5pt; color: #777; max-width: 110px; overflow: hidden; text-overflow: ellipsis; }}
  .pjt {{ font-size: 6.5pt; color: #333; max-width: 130px; overflow: hidden; text-overflow: ellipsis; }}
  .amt-high {{ color: #c62828; font-weight: 700; }}
  .amt-mid {{ color: #e65100; font-weight: 600; }}

  .badge {{ display: inline-block; padding: 1px 5px; border-radius: 8px; font-size: 6.5pt; font-weight: 600; }}
  .cls-4 {{ background: #e8f5e9; color: #2e7d32; }}
  .cls-3 {{ background: #e3f2fd; color: #1565c0; }}
  .cls-2 {{ background: #fff3e0; color: #e65100; }}
  .cls-1 {{ background: #f5f5f5; color: #888; }}
  .bad {{ color: #c62828; font-weight: 700; }}

  .footer {{ font-size: 7pt; color: #888; margin-top: 12px; text-align: right; }}

  @media print {{
    body {{ padding: 0; background: #fff; font-size: 7pt; }}
    .toolbar, .kind-row {{ display: none; }}
    .table-wrap {{ max-height: none; overflow: visible; }}
  }}
</style>
</head>
<body>
<div class="header">
  <h1>ERP 현재고현황 및 구매진행현황</h1>
  <div class="sub">(주)윈텍오토메이션 생산관리팀 | 전체 {total:,}건 | 발주계획(MBA) + 실제발주(MCA) + 입고검수(MDA) | {NOW.strftime('%Y-%m-%d')}</div>
</div>
<div class="container">
  <div class="summary">
    <div class="summary-card">
      <div class="label">총 품목</div>
      <div class="value" style="color:#1a237e;">{total:,}건</div>
      <div class="sub-value">약 {total_amt/100_000_000:.1f}억원</div>
    </div>
    <div class="summary-card">
      <div class="label">활성 (발주+입고)</div>
      <div class="value" style="color:#2e7d32;">{len(cat4):,}건</div>
      <div class="sub-value">{fmt_amt(amt4)}원</div>
    </div>
    <div class="summary-card">
      <div class="label">발주계획중</div>
      <div class="value" style="color:#1565c0;">{len(cat3):,}건</div>
      <div class="sub-value">{fmt_amt(amt3)}원</div>
    </div>
    <div class="summary-card">
      <div class="label">과거활동</div>
      <div class="value" style="color:#e65100;">{len(cat2):,}건</div>
      <div class="sub-value">{fmt_amt(amt2)}원</div>
    </div>
    <div class="summary-card">
      <div class="label">장기미활동</div>
      <div class="value" style="color:#888;">{len(cat1):,}건</div>
      <div class="sub-value">{fmt_amt(amt1)}원</div>
    </div>
  </div>

  <div class="kind-row">
{kind_cards_html}
  </div>

  <div class="legend">
    <span><span class="badge cls-4">활성</span> 2024년 이후 실제발주 또는 입고 있음</span>
    <span><span class="badge cls-3">발주계획</span> 발주계획 등록 (발주서 미발행)</span>
    <span><span class="badge cls-2">과거활동</span> 2024년 이전 이력만 있음</span>
    <span><span class="badge cls-1">미활동</span> 발주/입고 이력 없음</span>
  </div>

  <div class="toolbar">
    <input type="text" class="search-box" id="search" placeholder="품목코드/품목명/규격/프로젝트 검색..." oninput="applyFilters()"/>
    <button class="filter-btn active" data-st="all" onclick="setSt('all')">전체 ({total:,})</button>
    <button class="filter-btn" data-st="4" onclick="setSt('4')">활성 ({len(cat4):,})</button>
    <button class="filter-btn" data-st="3" onclick="setSt('3')">발주계획 ({len(cat3):,})</button>
    <button class="filter-btn" data-st="2" onclick="setSt('2')">과거활동 ({len(cat2):,})</button>
    <button class="filter-btn" data-st="1" onclick="setSt('1')">미활동 ({len(cat1):,})</button>
    <span class="result-count" id="result-count"></span>
  </div>

  <div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th rowspan="2" class="center" style="width:28px;" onclick="sortBy(0)">#</th>
        <th rowspan="2" style="width:105px;" onclick="sortBy(1)">품목코드</th>
        <th rowspan="2" onclick="sortBy(2)">품목명</th>
        <th rowspan="2" style="width:100px;">규격</th>
        <th rowspan="2" class="center" style="width:36px;" onclick="sortBy(7)">구분</th>
        <th rowspan="2" class="right" style="width:42px;" onclick="sortBy(4)">수량</th>
        <th rowspan="2" class="right" style="width:88px;" onclick="sortBy(5)">재고금액</th>
        <th rowspan="2" class="center" style="width:50px;" onclick="sortBy(6)">상태</th>
        <th colspan="3" class="th-group">발주계획 (MBA)</th>
        <th colspan="3" class="th-group">실제발주 (MCA)</th>
        <th colspan="3" class="th-group">입고검수 (MDA)</th>
        <th rowspan="2" style="width:120px;">프로젝트</th>
      </tr>
      <tr>
        <th class="center" style="width:68px;" onclick="sortBy(8)">계획일</th>
        <th class="right" style="width:30px;">건</th>
        <th class="center" style="width:42px;">상태</th>
        <th class="center" style="width:68px;" onclick="sortBy(11)">발주일</th>
        <th class="right" style="width:30px;">건</th>
        <th class="center" style="width:68px;" onclick="sortBy(13)">최종(전체)</th>
        <th class="center" style="width:68px;" onclick="sortBy(14)">입고일</th>
        <th class="right" style="width:30px;">건</th>
        <th class="right" style="width:42px;">불량</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
  </div>

  <div class="footer">
    생성: {NOW.strftime('%Y-%m-%d %H:%M')} KST | 발주계획: MBA210T | 실제발주: MCA210T | 입고검수: MDA100T | 기준: 2024.01~ (전체기간 포함) | 데이터 출처: ERP
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

const CLS_LABELS = {{4:'활성',3:'계획중',2:'과거',1:'미활동'}};
const CLS_CLASS = {{4:'cls-4',3:'cls-3',2:'cls-2',1:'cls-1'}};

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
    let pjt = r[19] || '-';
    if (pjt.length > 20) pjt = pjt.substring(0,18)+'..';
    const badHtml = r[17] > 0 ? '<span class="bad">'+r[17]+'</span>' : (r[15]>0?'0':'-');
    h += '<tr>' +
      '<td class="center">'+(i+1)+'</td>' +
      '<td class="code">'+r[1]+'</td>' +
      '<td>'+r[2]+'</td>' +
      '<td class="spec">'+r[3]+'</td>' +
      '<td class="center" style="font-size:6.5pt;">'+r[7]+'</td>' +
      '<td class="right">'+fmtQ(r[4])+'</td>' +
      '<td class="right"'+ac+'>'+fmtN(r[5])+'</td>' +
      '<td class="center">'+badge+'</td>' +
      // 발주계획
      '<td class="center">'+(r[8]||'-')+'</td>' +
      '<td class="right">'+(r[9]||'-')+'</td>' +
      '<td class="center" style="font-size:6.5pt;">'+(r[10]||'-')+'</td>' +
      // 실제발주
      '<td class="center">'+(r[11]||'-')+'</td>' +
      '<td class="right">'+(r[12]||'-')+'</td>' +
      '<td class="center">'+(r[13]||'-')+'</td>' +
      // 입고검수
      '<td class="center">'+(r[14]||'-')+'</td>' +
      '<td class="right">'+(r[15]||'-')+'</td>' +
      '<td class="right">'+badHtml+'</td>' +
      '<td class="pjt">'+pjt+'</td></tr>';
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
      const txt = (r[1]+' '+r[2]+' '+r[3]+' '+r[19]).toLowerCase();
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
