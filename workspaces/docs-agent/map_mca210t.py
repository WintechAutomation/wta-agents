# -*- coding: utf-8 -*-
"""MCA210T 발주이력을 ERP_현재고_구매진행_전체.html에 매핑
PO 데이터는 별도 JSON 파일, 클릭 시 fetch 로딩
10년치 + 1년치 데이터 병합
"""
import sys, io, json, re, os
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

base = r'C:\MES\wta-agents\reports\김근형'

# MCA210T 10년치 + 1년치 데이터 병합 (중복 제거)
all_items = []
seen = set()
for fname in ['MCA210T_발주현황_10년.json', 'MCA210T_발주현황_1년.json']:
    with open(f'{base}/{fname}', 'r', encoding='utf-8') as f:
        data = json.load(f)
    for r in data['items']:
        key = (r['po_no'], r['po_seq'], r['item_cd'])
        if key not in seen:
            seen.add(key)
            all_items.append(r)
    print(f'{fname}: {len(data["items"])}건 로드')
print(f'병합 후 총: {len(all_items)}건 (중복 제거)')

# 품목코드별 그룹화 (최신 발주순)
po_groups = defaultdict(list)
for r in all_items:
    po_groups[r['item_cd']].append({
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

for cd in po_groups:
    po_groups[cd].sort(key=lambda x: x['po_dt'], reverse=True)

print(f'MCA210T: {len(all_items)}건 → {len(po_groups)}개 품목')

# erp_data의 품목코드만 필터링
with open(f'{base}/erp_data.json', 'r', encoding='utf-8') as f:
    erp = json.load(f)
erp_cds = {r[1] for r in erp['data']}

po_filtered = {cd: pos for cd, pos in po_groups.items() if cd in erp_cds}
print(f'erp_data 매칭: {len(po_filtered)}개 품목')

# PO 데이터를 별도 JSON 파일로 저장
po_json_path = f'{base}/po_data.json'
with open(po_json_path, 'w', encoding='utf-8') as f:
    json.dump(po_filtered, f, ensure_ascii=False)
print(f'po_data.json 저장: {os.path.getsize(po_json_path)/1024/1024:.1f} MB')

# HTML 로드
with open(f'{base}/ERP_현재고_구매진행_전체.html', 'r', encoding='utf-8') as f:
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
          <th style="padding:6px;border:1px solid #c5cae9;white-space:nowrap;">발주번호</th>
          <th style="padding:6px;border:1px solid #c5cae9;white-space:nowrap;">발주일</th>
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
    const resp = await fetch('po_data.json');
    PO_DATA = await resp.json();
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
    document.getElementById('poTitle').textContent = itemCd + ' / ' + itemNm + ' — 발주이력 없음';
    document.getElementById('poBody').innerHTML = '<tr><td colspan="11" style="padding:20px;text-align:center;color:#999;">발주이력이 없습니다.</td></tr>';
    return;
  }
  document.getElementById('poTitle').textContent = itemCd + ' / ' + itemNm + ' — 발주이력 (' + pos.length + '건)';
  let h = '';
  let totalQty = 0, totalAmt = 0;
  for (const p of pos) {
    totalQty += p.qty;
    totalAmt += p.amt;
    const pjt = p.pjt.length > 30 ? p.pjt.substring(0,28)+'..' : p.pjt;
    const cust = p.cust.length > 15 ? p.cust.substring(0,13)+'..' : p.cust;
    h += '<tr>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;white-space:nowrap;">' + p.po_no + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;white-space:nowrap;">' + p.po_dt + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;text-align:right;">' + p.qty.toLocaleString() + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;text-align:right;">' + p.price.toLocaleString() + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;text-align:right;">' + p.amt.toLocaleString() + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;text-align:right;">' + p.acpt + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;white-space:nowrap;">' + p.dvry + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;">' + p.sts + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;" title="' + p.pjt + '">' + pjt + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;" title="' + p.cust + '">' + cust + '</td>';
    h += '<td style="padding:4px 6px;border:1px solid #e0e0e0;">' + p.rmk + '</td>';
    h += '</tr>';
  }
  document.getElementById('poBody').innerHTML = h;
  document.getElementById('poSummary').textContent = '합계: ' + totalQty.toLocaleString() + '개, ' + totalAmt.toLocaleString() + '원';
}

document.getElementById('poModal').addEventListener('click', function(e) {
  if (e.target === this) this.style.display = 'none';
});

// 행 클릭 이벤트 위임 (renderRows JS 수정 없이)
document.getElementById('tbody').addEventListener('click', function(e) {
  const tr = e.target.closest('tr');
  if (!tr) return;
  const cells = tr.querySelectorAll('td');
  if (cells.length < 2) return;
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
# TR 커서 포인터 (CSS로)
if '#tbody tr {' in html:
    html = html.replace('#tbody tr {', '#tbody tr { cursor: pointer;')
elif 'cursor: pointer' not in html:
    html = html.replace('</style>', '  #tbody tr { cursor: pointer; }\n</style>')

# 저장
with open(f'{base}/ERP_현재고_구매진행_전체.html', 'w', encoding='utf-8') as f:
    f.write(html)

html_size = os.path.getsize(f'{base}/ERP_현재고_구매진행_전체.html')
po_size = os.path.getsize(po_json_path)
print(f'HTML: {html_size/1024:.0f} KB (PO 데이터 분리)')
print(f'po_data.json: {po_size/1024/1024:.1f} MB')
print(f'매핑 품목: {len(po_filtered)}개, 총 PO: {sum(len(v) for v in po_filtered.values())}건')
