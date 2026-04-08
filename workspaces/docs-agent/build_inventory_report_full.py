"""
ERP 현재고현황 + 구매진행현황 보고서 (전건, v6)
사용예정수량/금액, 남는재고/금액 컬럼 추가
"""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)

DATA_PATH = Path(r'C:\MES\wta-agents\workspaces\db-manager\erp_inventory_full_v4.json')
OUTPUT = Path(r'C:\MES\wta-agents\reports\김근형\erp_재고현황_발주내역.html')

ITEM_KIND_MAP = {'1': '원자재', '2': '부자재', '3': '반제품', '6': '상품', '7': '기타'}

# 올해 장비별 사용 예정 대수
EQUIP_PLAN = {
    '프레스': 42,
    '소결': 9,
    '연삭핸들러': 1,
    'CVD': 3,
    '포장기': 6,
    '마스크자동기': 3,
    'CBN': 1,
    '검사기': 6,
    '호닝형상': 6,
    'HGM': 4,
}


def fmt_amt(v):
    if not v:
        return '-'
    return f"{int(v):,}"


def escape_html(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def best_date(d):
    candidates = []
    if d.get('last_po_dt'):
        candidates.append(d['last_po_dt'])
    if d.get('last_receipt_dt'):
        candidates.append(d['last_receipt_dt'])
    if d.get('last_plan_dt'):
        candidates.append(d['last_plan_dt'])
    if candidates:
        return max(candidates)
    fb = []
    if d.get('all_time_last_po_dt'):
        fb.append(d['all_time_last_po_dt'])
    if d.get('all_time_last_receipt_dt'):
        fb.append(d['all_time_last_receipt_dt'])
    return max(fb) if fb else ''


def classify(d):
    if d.get('has_po') or d.get('has_receipt') or d.get('has_plan'):
        return 3
    elif d.get('all_time_last_po_dt') or d.get('all_time_last_receipt_dt'):
        return 2
    else:
        return 1


def classify_equip(pjt_names):
    types = set()
    for pjt in pjt_names:
        if not pjt:
            continue
        pu = pjt.upper()
        if '프레스' in pjt:
            types.add('프레스')
        if '소결' in pjt:
            types.add('소결')
        if '핸들러' in pjt and '프레스' not in pjt:
            types.add('연삭핸들러')
        if '연삭' in pjt:
            types.add('연삭핸들러')
        if 'CVD' in pu:
            types.add('CVD')
        if '포장' in pjt:
            types.add('포장기')
        if '마스크' in pjt:
            types.add('마스크자동기')
        if 'CBN' in pu:
            types.add('CBN')
        if '검사' in pjt:
            types.add('검사기')
        if '호닝' in pjt:
            types.add('호닝형상')
        if 'HGM' in pu or 'HIM' in pu:
            types.add('HGM')
    return types


def equip_info(types):
    """장비유형 → (라벨, 사용예정수량 합계)"""
    plan_types = [t for t in types if t in EQUIP_PLAN]
    if not plan_types:
        return '', 0
    total_qty = sum(EQUIP_PLAN[t] for t in plan_types)
    if len(plan_types) == 1:
        t = plan_types[0]
        return f"{t}({EQUIP_PLAN[t]})", total_qty
    else:
        parts = [f"{t}({EQUIP_PLAN[t]})" for t in sorted(plan_types)]
        return '/'.join(parts) + ' 중복', total_qty


def main():
    data = json.loads(DATA_PATH.read_text(encoding='utf-8'))
    total = len(data)

    for d in data:
        d['_cls'] = classify(d)
        d['_best_dt'] = best_date(d)
        pjt_names = [
            d.get('last_pjt_name', ''),
            d.get('plan_pjt_name', ''),
            d.get('receipt_pjt_name', ''),
        ]
        d['_equip_types'] = classify_equip(pjt_names)
        label, eq_qty = equip_info(d['_equip_types'])
        d['_equip_label'] = label
        d['_equip_qty'] = eq_qty  # 사용 예정 수량

        # 단가 계산
        stock_qty = d.get('stock_qty', 0) or 0
        stock_amt = d.get('stock_amt', 0) or 0
        unit_price = stock_amt / stock_qty if stock_qty > 0 else 0

        # 사용 예정 금액 = min(사용예정수량, 재고수량) × 단가
        use_qty = min(eq_qty, stock_qty) if eq_qty > 0 else 0
        d['_use_amt'] = round(use_qty * unit_price)

        # 남는 재고 = max(0, 재고 - 사용예정)
        d['_remain_qty'] = max(0, stock_qty - eq_qty) if eq_qty > 0 else stock_qty
        d['_remain_amt'] = round(d['_remain_qty'] * unit_price)

    cat3 = [d for d in data if d['_cls'] == 3]
    cat2 = [d for d in data if d['_cls'] == 2]
    cat1 = [d for d in data if d['_cls'] == 1]
    amt3 = sum(d.get('stock_amt', 0) for d in cat3)
    amt2 = sum(d.get('stock_amt', 0) for d in cat2)
    amt1 = sum(d.get('stock_amt', 0) for d in cat1)
    total_amt = sum(d.get('stock_amt', 0) for d in data)
    total_use_amt = sum(d['_use_amt'] for d in data)
    total_remain_amt = sum(d['_remain_amt'] for d in data)

    kind_stats = {}
    for d in data:
        k = ITEM_KIND_MAP.get(d.get('item_kind', ''), d.get('item_kind', ''))
        if k not in kind_stats:
            kind_stats[k] = {'count': 0, 'amt': 0}
        kind_stats[k]['count'] += 1
        kind_stats[k]['amt'] += d.get('stock_amt', 0)

    equip_stats = {}
    for d in data:
        for t in d['_equip_types']:
            if t not in equip_stats:
                equip_stats[t] = {'count': 0, 'amt': 0}
            equip_stats[t]['count'] += 1
            equip_stats[t]['amt'] += d.get('stock_amt', 0)

    # JS data
    js_data = []
    for i, d in enumerate(data):
        kind_label = ITEM_KIND_MAP.get(d.get('item_kind', ''), d.get('item_kind', ''))
        pjt = d.get('last_pjt_name', '') or d.get('plan_pjt_name', '') or d.get('receipt_pjt_name', '') or ''

        js_data.append([
            i + 1,                                      # 0: rank
            escape_html(d.get('item_cd', '')),          # 1: item_cd
            escape_html(d.get('item_nm', '')),          # 2: item_nm
            d.get('stock_qty', 0),                      # 3: qty
            d.get('stock_amt', 0),                      # 4: amt
            d['_cls'],                                   # 5: cls (1~3)
            kind_label,                                  # 6: kind
            d['_best_dt'],                               # 7: best_date
            escape_html(pjt),                           # 8: project
            escape_html(d['_equip_label']),             # 9: equip label
            d['_equip_qty'],                             # 10: equip qty (사용예정수량)
            d['_use_amt'],                               # 11: use amt (사용예정금액)
            d['_remain_qty'],                            # 12: remain qty
            d['_remain_amt'],                            # 13: remain amt
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

    equip_cards_html = ''
    for etype, plan_qty in EQUIP_PLAN.items():
        es = equip_stats.get(etype, {'count': 0, 'amt': 0})
        equip_cards_html += f"""<div class="equip-card" onclick="filterEquip('{etype}')">
  <div class="equip-label">{etype}</div>
  <div class="equip-qty">예정 {plan_qty}대</div>
  <div class="equip-count">{es['count']}품목</div>
</div>\n"""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>ERP 현재고현황 및 구매진행현황</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Malgun Gothic', 'Pretendard Variable', sans-serif; background: #f5f5f5; padding: 16px; margin: 0; font-size: 8.5pt; }}
  .header {{ background: #1a237e; color: #fff; padding: 18px 22px; border-radius: 8px 8px 0 0; }}
  .header h1 {{ margin: 0; font-size: 17pt; }}
  .header .sub {{ font-size: 9pt; color: #b3b9e6; margin-top: 4px; }}
  .container {{ background: #fff; border-radius: 0 0 8px 8px; padding: 18px; box-shadow: 0 2px 8px rgba(0,0,0,.1); }}

  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; margin-bottom: 14px; }}
  .summary-card {{ background: #f8f9ff; border: 1px solid #e0e3f0; border-radius: 8px; padding: 10px; text-align: center; }}
  .summary-card .label {{ font-size: 8.5pt; color: #666; margin-bottom: 3px; }}
  .summary-card .value {{ font-size: 14pt; font-weight: 700; }}
  .summary-card .sub-value {{ font-size: 7.5pt; color: #888; margin-top: 2px; }}

  .kind-row {{ display: flex; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }}
  .kind-card {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 6px 10px; cursor: pointer;
    transition: all 0.2s; min-width: 90px; text-align: center; }}
  .kind-card:hover, .kind-card.active {{ border-color: #1a237e; background: #e8eaf6; }}
  .kind-label {{ font-size: 8.5pt; font-weight: 700; color: #1a237e; }}
  .kind-count {{ font-size: 10pt; font-weight: 700; }}
  .kind-amt {{ font-size: 7pt; color: #666; }}

  .equip-row {{ display: flex; gap: 5px; margin-bottom: 12px; flex-wrap: wrap; }}
  .equip-card {{ background: #fff; border: 1px solid #c8e6c9; border-radius: 8px; padding: 5px 9px; cursor: pointer;
    transition: all 0.2s; min-width: 72px; text-align: center; }}
  .equip-card:hover, .equip-card.active {{ border-color: #2e7d32; background: #e8f5e9; }}
  .equip-label {{ font-size: 8pt; font-weight: 700; color: #2e7d32; }}
  .equip-qty {{ font-size: 7.5pt; color: #666; }}
  .equip-count {{ font-size: 7pt; color: #999; }}

  .toolbar {{ display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; align-items: center; }}
  .search-box {{ padding: 5px 12px; border: 1px solid #ccc; border-radius: 20px; font-size: 9pt; width: 240px;
    font-family: 'Malgun Gothic', sans-serif; }}
  .filter-btn {{ padding: 4px 10px; border: 1px solid #ccc; background: #fff; border-radius: 20px;
    cursor: pointer; font-size: 8pt; font-family: 'Malgun Gothic', sans-serif; transition: all 0.2s; }}
  .filter-btn.active {{ background: #1a237e; color: #fff; border-color: #1a237e; }}
  .filter-btn:hover:not(.active) {{ background: #e8eaf6; }}
  .result-count {{ font-size: 8pt; color: #666; margin-left: auto; }}

  .table-wrap {{ max-height: 74vh; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 4px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 8pt; }}
  th {{ background: #e8eaf6; color: #1a237e; padding: 6px 4px; text-align: left; font-weight: 700;
    position: sticky; top: 0; z-index: 5; border-bottom: 2px solid #1a237e; cursor: pointer; white-space: nowrap; font-size: 7.5pt; }}
  th:hover {{ background: #c5cae9; }}
  td {{ padding: 4px 4px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }}
  tr:hover {{ background: #f5f7ff; }}
  .center {{ text-align: center; }}
  .right {{ text-align: right; font-family: 'Consolas', monospace; }}
  .code {{ font-family: 'Consolas', monospace; font-size: 7.5pt; color: #555; }}
  .item-nm {{ font-size: 7.5pt; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .pjt {{ font-size: 7.5pt; color: #333; max-width: 170px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .equip {{ font-size: 7pt; white-space: nowrap; }}
  .equip-used {{ color: #2e7d32; font-weight: 600; }}
  .equip-dup {{ color: #c62828; font-weight: 600; }}
  .amt-high {{ color: #c62828; font-weight: 700; }}
  .amt-mid {{ color: #e65100; font-weight: 600; }}
  .remain-zero {{ color: #c62828; font-weight: 700; }}

  .badge {{ display: inline-block; padding: 2px 6px; border-radius: 10px; font-size: 7pt; font-weight: 600; }}
  .cls-3 {{ background: #e8f5e9; color: #2e7d32; }}
  .cls-2 {{ background: #fff3e0; color: #e65100; }}
  .cls-1 {{ background: #f5f5f5; color: #888; }}

  .footer {{ font-size: 7.5pt; color: #888; margin-top: 14px; text-align: right; }}

  /* 사용예정 헤더 그룹 색상 */
  th.plan-hdr {{ background: #e8f5e9; color: #2e7d32; border-bottom-color: #2e7d32; }}
  th.remain-hdr {{ background: #fff3e0; color: #e65100; border-bottom-color: #e65100; }}

  @media print {{
    body {{ padding: 0; background: #fff; }}
    .toolbar, .kind-row, .equip-row {{ display: none; }}
    .table-wrap {{ max-height: none; overflow: visible; }}
  }}
</style>
</head>
<body>
<div class="header">
  <h1>ERP 현재고현황 및 구매진행현황</h1>
  <div class="sub">(주)윈텍오토메이션 생산관리팀 | 전체 {total:,}건 | {NOW.strftime('%Y-%m-%d')}</div>
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
    <div class="summary-card">
      <div class="label">사용 예정 금액</div>
      <div class="value" style="color:#2e7d32;">-{fmt_amt(total_use_amt)}원</div>
      <div class="sub-value">약 {total_use_amt/100_000_000:.1f}억원</div>
    </div>
    <div class="summary-card">
      <div class="label">예상 잔여 금액</div>
      <div class="value" style="color:#e65100;">{fmt_amt(total_remain_amt)}원</div>
      <div class="sub-value">약 {total_remain_amt/100_000_000:.1f}억원</div>
    </div>
  </div>

  <div class="kind-row">
{kind_cards_html}
  </div>

  <div class="equip-row">
{equip_cards_html}
  </div>

  <div class="toolbar">
    <input type="text" class="search-box" id="search" placeholder="품목코드/품목명/프로젝트 검색..." oninput="applyFilters()"/>
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
        <th class="center" style="width:30px;" onclick="sortBy(0)">#</th>
        <th style="width:110px;" onclick="sortBy(1)">품목코드</th>
        <th style="width:150px;" onclick="sortBy(2)">품목명</th>
        <th class="center" style="width:40px;" onclick="sortBy(6)">구분</th>
        <th class="right" style="width:45px;" onclick="sortBy(3)">수량</th>
        <th class="right" style="width:90px;" onclick="sortBy(4)">재고금액</th>
        <th class="center" style="width:50px;" onclick="sortBy(5)">상태</th>
        <th class="center" style="width:75px;" onclick="sortBy(7)">발주일</th>
        <th style="width:170px;" onclick="sortBy(8)">프로젝트</th>
        <th class="plan-hdr" style="width:100px;" onclick="sortBy(9)">사용 예정</th>
        <th class="plan-hdr right" style="width:45px;" onclick="sortBy(10)">예정수량</th>
        <th class="plan-hdr right" style="width:85px;" onclick="sortBy(11)">예정금액</th>
        <th class="remain-hdr right" style="width:45px;" onclick="sortBy(12)">남는재고</th>
        <th class="remain-hdr right" style="width:85px;" onclick="sortBy(13)">남는금액</th>
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
let equipFilter = '';
let sortCol = 4;
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
    const amt = r[4];
    let ac = '';
    if (amt >= 50000000) ac = ' class="amt-high"';
    else if (amt >= 10000000) ac = ' class="amt-mid"';
    const cls = r[5];
    const badge = '<span class="badge '+CLS_CLASS[cls]+'">'+CLS_LABELS[cls]+'</span>';
    let pjt = r[8] || '-';
    if (pjt.length > 26) pjt = pjt.substring(0,24)+'..';
    const eq = r[9] || '';
    const eqClass = eq.includes('중복') ? 'equip equip-dup' : (eq ? 'equip equip-used' : 'equip');
    const eqQty = r[10] || 0;
    const useAmt = r[11] || 0;
    const remQty = r[12];
    const remAmt = r[13];
    const remClass = (eqQty > 0 && remQty === 0) ? 'right remain-zero' : 'right';
    h += '<tr>' +
      '<td class="center">'+(i+1)+'</td>' +
      '<td class="code">'+r[1]+'</td>' +
      '<td class="item-nm" title="'+r[2]+'">'+r[2]+'</td>' +
      '<td class="center" style="font-size:7pt;">'+r[6]+'</td>' +
      '<td class="right">'+fmtQ(r[3])+'</td>' +
      '<td class="right"'+ac+'>'+fmtN(r[4])+'</td>' +
      '<td class="center">'+badge+'</td>' +
      '<td class="center" style="font-size:7pt;">'+(r[7]||'-')+'</td>' +
      '<td class="pjt" title="'+r[8]+'">'+pjt+'</td>' +
      '<td class="'+eqClass+'">'+eq+'</td>' +
      '<td class="right">'+(eqQty ? fmtQ(eqQty) : '-')+'</td>' +
      '<td class="right" style="color:#2e7d32;">'+(useAmt ? '-'+fmtN(useAmt) : '-')+'</td>' +
      '<td class="'+remClass+'">'+fmtQ(remQty)+'</td>' +
      '<td class="'+remClass+'">'+fmtN(remAmt)+'</td></tr>';
  }}
  tb.innerHTML = h;
  document.getElementById('result-count').textContent = rows.length.toLocaleString() + '건';
}}

function applyFilters() {{
  const q = document.getElementById('search').value.toLowerCase();
  filtered = DATA.filter(r => {{
    if (stFilter !== 'all' && r[5] !== parseInt(stFilter)) return false;
    if (kindFilter && r[6] !== kindFilter) return false;
    if (equipFilter && !r[9].includes(equipFilter)) return false;
    if (q) {{
      const txt = (r[1]+' '+r[2]+' '+r[8]+' '+r[9]).toLowerCase();
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

function filterEquip(equip) {{
  const cards = document.querySelectorAll('.equip-card');
  if (equipFilter === equip) {{
    equipFilter = '';
    cards.forEach(c => c.classList.remove('active'));
  }} else {{
    equipFilter = equip;
    cards.forEach(c => c.classList.toggle('active', c.querySelector('.equip-label').textContent === equip));
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
