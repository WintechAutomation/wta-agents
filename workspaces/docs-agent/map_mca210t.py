# -*- coding: utf-8 -*-
"""MCA210T 발주이력을 ERP_현재고_구매진행_전체.html에 매핑
품목 클릭 시 발주이력 상세 팝업 표시
"""
import sys, io, json, re
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

base = r'C:\MES\wta-agents\reports\김근형'

# MCA210T 데이터 로드
with open(f'{base}/MCA210T_발주현황_1년.json', 'r', encoding='utf-8') as f:
    mca = json.load(f)

# 품목코드별 그룹화 (최신 발주순)
po_groups = defaultdict(list)
for r in mca['items']:
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

# 발주일 내림차순 정렬
for cd in po_groups:
    po_groups[cd].sort(key=lambda x: x['po_dt'], reverse=True)

print(f'MCA210T: {len(mca["items"])}건 → {len(po_groups)}개 품목')

# erp_data의 품목코드만 필터링 (HTML에 있는 것만)
with open(f'{base}/erp_data.json', 'r', encoding='utf-8') as f:
    erp = json.load(f)
erp_cds = {r[1] for r in erp['data']}

po_filtered = {cd: pos for cd, pos in po_groups.items() if cd in erp_cds}
print(f'erp_data 매칭: {len(po_filtered)}개 품목')

# HTML 로드
with open(f'{base}/ERP_현재고_구매진행_전체.html', 'r', encoding='utf-8') as f:
    html = f.read()

# PO_DATA JS 객체 생성
po_data_js = json.dumps(po_filtered, ensure_ascii=False)

# 모달 HTML + JS 코드
modal_html = '''
<!-- MCA210T 발주이력 모달 -->
<div id="poModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:9999;overflow:auto;">
  <div style="background:#fff;margin:40px auto;padding:20px;border-radius:12px;max-width:900px;max-height:80vh;overflow:auto;box-shadow:0 8px 32px rgba(0,0,0,0.3);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
      <h3 id="poTitle" style="margin:0;font-size:15px;color:#1a237e;"></h3>
      <button onclick="document.getElementById('poModal').style.display='none'" style="background:none;border:none;font-size:20px;cursor:pointer;color:#666;">&times;</button>
    </div>
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

modal_js = '''
<script>
const PO_DATA = ''' + po_data_js + ''';

function showPO(itemCd, itemNm) {
  const pos = PO_DATA[itemCd];
  if (!pos || pos.length === 0) {
    alert('발주이력 없음 (최근 1년)');
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
  document.getElementById('poModal').style.display = 'block';
}

// 모달 외부 클릭 시 닫기
document.getElementById('poModal').addEventListener('click', function(e) {
  if (e.target === this) this.style.display = 'none';
});
</script>
'''

# HTML에 모달 삽입 (</body> 앞)
html = html.replace('</body>', modal_html + modal_js + '</body>')

# 품목코드 셀에 클릭 이벤트 추가 — renderRows 함수 수정
# 기존: r[1] 품목코드 표시 부분 찾기
old_render = "r[1]+'</strong>"
new_render = "r[1]+'</strong>"

# 더 정확한 패치: 행 클릭 시 PO 조회
# 기존 tr 태그에 onclick 추가
old_tr = "h += '<tr"
new_tr = "h += '<tr style=\"cursor:pointer\" onclick=\"showPO(\\''+r[1]+'\\',\\''+r[2].replace(/'/g,\"\")+'\\')\""
html = html.replace(old_tr, new_tr, 1)  # 첫 번째만

# 저장
with open(f'{base}/ERP_현재고_구매진행_전체.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f'HTML 매핑 완료: 전체 리스트에 MCA210T 발주이력 팝업 추가')
print(f'매핑 품목: {len(po_filtered)}개, 총 PO: {sum(len(v) for v in po_filtered.values())}건')
