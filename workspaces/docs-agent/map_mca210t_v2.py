# -*- coding: utf-8 -*-
"""MCA210T 발주이력 + MAD111T 재고감안을 ERP_현재고_구매진행_전체.html에 매핑
PO 데이터는 별도 JSON 파일, 클릭 시 fetch 로딩
10년치 + 1년치 데이터 병합
"""
import sys, io, json, re, os
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

base = r'C:\MES\wta-agents\reports\김근형'

# MCA210T 10년치 데이터 로드 (1년치 포함)
all_items = []
seen = set()
for fname in ['MCA210T_발주현황_10년.json']:
    fpath = f'{base}/{fname}'
    if not os.path.exists(fpath):
        continue
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for r in data['items']:
        key = (r['po_no'], r['po_seq'], r['item_cd'])
        if key not in seen:
            seen.add(key)
            all_items.append(r)
    print(f'{fname}: {len(data["items"])}건 로드')
# 1년치 파일이 있으면 병합
fname_1y = 'MCA210T_발주현황_1년.json'
if os.path.exists(f'{base}/{fname_1y}'):
    with open(f'{base}/{fname_1y}', 'r', encoding='utf-8') as f:
        data = json.load(f)
    added = 0
    for r in data['items']:
        key = (r['po_no'], r['po_seq'], r['item_cd'])
        if key not in seen:
            seen.add(key)
            all_items.append(r)
            added += 1
    print(f'{fname_1y}: {len(data["items"])}건 로드 (신규 {added}건)')
print(f'MCA210T 총: {len(all_items)}건')

# MAD111T 재고감안 데이터 로드
mad_fname = 'MAD111T_재고감안_10년.json'
with open(f'{base}/{mad_fname}', 'r', encoding='utf-8') as f:
    mad_data = json.load(f)
mad_items = mad_data['items']
print(f'{mad_fname}: {len(mad_items)}건 로드')

# 품목코드별 그룹화 (최신순)
po_groups = defaultdict(list)

# MCA210T 발주
for r in all_items:
    po_groups[r['item_cd']].append({
        'tp': '발주',
        'po_no': r['po_no'],
        'po_dt': r['po_dt'],
        'qty': r['po_unit_qty'],
        'price': r['po_price'],
        'amt': r['po_amt'],
        'pjt': r['pjt_name'] or '',
        'cust': r['cust_name'] or '',
        'dvry': r['dvry_dt'] or '',
        'sts': r['sts_desc'] or '',
        'acpt': r['acpt_qty'],
        'rmk': r['rmk'] or '',
    })

# MAD111T 재고감안
for r in mad_items:
    po_groups[r['item_cd']].append({
        'tp': '재고감안',
        'po_no': r.get('adv_no') or '',
        'po_dt': r.get('adv_dt') or '',
        'qty': r.get('adv_qty') or 0,
        'price': r.get('avg_price') or 0,
        'amt': r.get('amt') or 0,
        'pjt': r.get('pjt_name') or '',
        'cust': '',
        'dvry': r.get('dvry_dt') or '',
        'sts': '재고감안',
        'acpt': 0,
        'rmk': '',
    })

for cd in po_groups:
    po_groups[cd].sort(key=lambda x: x['po_dt'], reverse=True)

po_cnt = len(all_items)
mad_cnt = len(mad_items)
print(f'MCA210T: {po_cnt}건 + MAD111T: {mad_cnt}건 → {len(po_groups)}개 품목')

# po_data.json 불필요 — HTML에서 원본 JSON 직접 fetch
print(f'총 품목: {len(po_groups)}개 (원본 JSON 직접 참조 방식)')

# HTML 로드 (v2 복사본)
with open(f'{base}/ERP_현재고_구매진행_전체_v2.html', 'r', encoding='utf-8') as f:
    html = f.read()

# --- 이전 실행 잔재 제거 ---
html = re.sub(r'<!-- MCA210T 발주이력 모달 -->.*?</div>\s*</div>\s*</div>', '', html, flags=re.DOTALL)
html = re.sub(r'<script>\s*(?:const|let) PO_DATA[\s\S]*?</script>', '', html)
html = re.sub(r'<script>\s*document\.getElementById\(\'tbody\'\)\.addEventListener[\s\S]*?</script>', '', html)

# --- 모달 HTML ---
modal_html = '''
<!-- MCA210T 발주이력 모달 -->
<div id="poModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:9999;overflow:auto;">
  <div style="background:#fff;margin:40px auto;padding:20px;border-radius:12px;max-width:900px;max-height:80vh;overflow:auto;box-shadow:0 8px 32px rgba(0,0,0,0.3);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
      <h3 id="poTitle" style="margin:0;font-size:15px;color:#1a237e;"></h3>
      <button onclick="document.getElementById('poModal').style.display='none'" style="background:none;border:none;font-size:20px;cursor:pointer;color:#666;">&times;</button>
    </div>
    <div id="poLoading" style="display:none;text-align:center;padding:40px;color:#666;">발주이력 로딩 중...</div>
    <table id="poTable" style="width:100%;border-collapse:collapse;font-size:11px;">
      <thead>
        <tr style="background:#e8eaf6;">
          <th style="padding:6px;border:1px solid #c5cae9;white-space:nowrap;">구분</th>
          <th style="padding:6px;border:1px solid #c5cae9;white-space:nowrap;">번호</th>
          <th style="padding:6px;border:1px solid #c5cae9;white-space:nowrap;">일자</th>
          <th style="padding:6px;border:1px solid #c5cae9;white-space:nowrap;">수량</th>
          <th style="padding:6px;border:1px solid #c5cae9;white-space:nowrap;">단가</th>
          <th style="padding:6px;border:1px solid #c5cae9;white-space:nowrap;">금액</th>
          <th style="padding:6px;border:1px solid #c5cae9;white-space:nowrap;">입고</th>
          <th style="padding:6px;border:1px solid #c5cae9;white-space:nowrap;">납기</th>
          <th style="padding:6px;border:1px solid #c5cae9;white-space:nowrap;">상태</th>
          <th style="padding:6px;border:1px solid #c5cae9;">프로젝트</th>
          <th style="padding:6px;border:1px solid #c5cae9;">거래처</th>
          <th style="padding:6px;border:1px solid #c5cae9;">비고</th>
        </tr>
      </thead>
      <tbody id="poBody"></tbody>
    </table>
    <div id="poSummary" style="margin-top:8px;font-size:11px;color:#666;"></div>
  </div>
</div>
'''

# --- JS: fetch + 이벤트 위임 (renderRows JS 수정 안 함) ---
modal_js = '''
<script>
let PO_DATA = null;
let poDataLoading = false;

async function loadPOData() {
  if (PO_DATA) return PO_DATA;
  if (poDataLoading) {
    while (poDataLoading) await new Promise(r => setTimeout(r, 100));
    return PO_DATA;
  }
  poDataLoading = true;
  try {
    const [mcaResp, madResp] = await Promise.all([
      fetch('MCA210T_발주현황_10년.json'),
      fetch('MAD111T_재고감안_10년.json')
    ]);
    const mcaData = await mcaResp.json();
    const madData = await madResp.json();
    // 품목코드별 그룹화
    const grouped = {};
    for (const r of mcaData.items) {
      if (!grouped[r.item_cd]) grouped[r.item_cd] = [];
      grouped[r.item_cd].push({
        tp: '발주', po_no: r.po_no, po_dt: r.po_dt,
        qty: r.po_unit_qty, price: r.po_price, amt: r.po_amt,
        pjt: r.pjt_name || '', cust: r.cust_name || '',
        dvry: r.dvry_dt || '', sts: r.sts_desc || '',
        acpt: r.acpt_qty, rmk: r.rmk || ''
      });
    }
    for (const r of madData.items) {
      if (!grouped[r.item_cd]) grouped[r.item_cd] = [];
      grouped[r.item_cd].push({
        tp: '재고감안', po_no: r.adv_no || '', po_dt: r.adv_dt || '',
        qty: r.adv_qty || 0, price: r.avg_price || 0, amt: r.amt || 0,
        pjt: r.pjt_name || '', cust: '',
        dvry: r.dvry_dt || '', sts: '재고감안',
        acpt: 0, rmk: ''
      });
    }
    // 날짜 역순 정렬
    for (const cd in grouped) {
      grouped[cd].sort((a, b) => b.po_dt.localeCompare(a.po_dt));
    }
    PO_DATA = grouped;
  } catch(e) {
    alert('발주이력 데이터 로딩 실패: ' + e.message);
    PO_DATA = {};
  }
  poDataLoading = false;
  return PO_DATA;
}

async function showPO(itemCd, itemNm) {
  document.getElementById('poLoading').style.display = 'block';
  document.getElementById('poTable').style.display = 'none';
  document.getElementById('poSummary').textContent = '';
  document.getElementById('poTitle').textContent = itemCd + ' / ' + itemNm + ' — 로딩 중...';
  document.getElementById('poModal').style.display = 'block';

  const data = await loadPOData();
  const pos = data[itemCd];

  document.getElementById('poLoading').style.display = 'none';
  document.getElementById('poTable').style.display = 'table';

  if (!pos || pos.length === 0) {
    document.getElementById('poTitle').textContent = itemCd + ' / ' + itemNm + ' — 이력 없음';
    document.getElementById('poBody').innerHTML = '<tr><td colspan="12" style="padding:20px;text-align:center;color:#999;">발주/재고감안 이력이 없습니다.</td></tr>';
    return;
  }
  const poCnt = pos.filter(x => x.tp === '발주').length;
  const madCnt = pos.filter(x => x.tp === '재고감안').length;
  let titleParts = [];
  if (poCnt > 0) titleParts.push('발주 ' + poCnt + '건');
  if (madCnt > 0) titleParts.push('재고감안 ' + madCnt + '건');
  document.getElementById('poTitle').textContent = itemCd + ' / ' + itemNm + ' — ' + titleParts.join(' + ') + ' (총 ' + pos.length + '건)';
  let h = '';
  let totalQty = 0, totalAmt = 0;
  for (const p of pos) {
    totalQty += p.qty;
    totalAmt += p.amt;
    const pjt = p.pjt.length > 30 ? p.pjt.substring(0,28)+'..' : p.pjt;
    const cust = p.cust.length > 15 ? p.cust.substring(0,13)+'..' : p.cust;
    const isMad = p.tp === '재고감안';
    const rowBg = isMad ? 'background:#fff8e1;' : '';
    const tpBadge = isMad ? '<span style="color:#e65100;font-weight:bold;">재고</span>' : '<span style="color:#1565c0;">발주</span>';
    h += '<tr style="' + rowBg + '">';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;text-align:center;white-space:nowrap;">' + tpBadge + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;white-space:nowrap;">' + p.po_no + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;white-space:nowrap;">' + p.po_dt + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;text-align:right;">' + p.qty.toLocaleString() + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;text-align:right;">' + (p.price ? p.price.toLocaleString() : '-') + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;text-align:right;">' + (p.amt ? p.amt.toLocaleString() : '-') + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;text-align:right;">' + (isMad ? '-' : p.acpt) + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;white-space:nowrap;">' + p.dvry + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;">' + p.sts + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;" title="' + p.pjt + '">' + pjt + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;" title="' + p.cust + '">' + cust + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;">' + p.rmk + '</td>';
    h += '</tr>';
  }
  document.getElementById('poBody').innerHTML = h;
  document.getElementById('poSummary').textContent = '합계: ' + totalQty.toLocaleString() + '개, ' + totalAmt.toLocaleString() + '원 (발주 ' + poCnt + '건 + 재고감안 ' + madCnt + '건)';
}

document.getElementById('poModal').addEventListener('click', function(e) {
  if (e.target === this) this.style.display = 'none';
});

// 품목코드 셀 더블클릭 시에만 발주이력 팝업 (renderRows JS 수정 없이)
document.getElementById('tbody').addEventListener('dblclick', function(e) {
  const td = e.target.closest('td');
  if (!td) return;
  const tr = td.closest('tr');
  if (!tr) return;
  const cells = tr.querySelectorAll('td');
  if (cells.length < 2 || td !== cells[1]) return;
  const codeEl = cells[1].querySelector('.code');
  const nmEl = cells[1].querySelector('.item-nm');
  if (codeEl && nmEl) showPO(codeEl.textContent, nmEl.textContent.replace(/[()]/g,'').trim());
});
</script>
'''

# --- HTML 수정: 모달 + JS 삽입, CSS 패치 (JS renderRows 안 건드림) ---
html = html.replace('</body>', modal_html + modal_js + '</body>')

# CSS: 품목명 괄호 + 짙은 회색 + 폰트 축소 + 커서
html = html.replace(
    '.item-nm {',
    '.item-nm::before { content: "("; }\n  .item-nm::after { content: ")"; }\n  .item-nm {'
)
html = html.replace(
    'color:#333;font-size:8.5pt;',
    'color:#777;font-size:7.5pt;'
)
# 품목코드 셀에만 커서 포인터 (CSS로)
# 이전 TR 커서 제거
html = html.replace('#tbody tr { cursor: pointer;', '#tbody tr {')
if '#tbody tr td:nth-child(2)' not in html:
    html = html.replace('</style>', '  #tbody tr td:nth-child(2) { cursor: pointer; }\n</style>')

# 저장
outpath = f'{base}/ERP_현재고_구매진행_전체_v2.html'
with open(outpath, 'w', encoding='utf-8') as f:
    f.write(html)

html_size = os.path.getsize(outpath)
print(f'HTML: {html_size/1024:.0f} KB (원본 JSON 직접 fetch 방식)')
print(f'po_data.json 불필요 — 원본 JSON에서 브라우저가 직접 필터링')
