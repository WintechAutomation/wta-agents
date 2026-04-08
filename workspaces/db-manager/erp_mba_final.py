"""MBA210T(발주계획) HP3C22601004 및 CKR20-145-1065L 최종 확인"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()
result = {}

PJT = 'HP3C22601004'
ITEM_CD = 'CKR20-145-1065L'

# 1. MBA210T HP3C22601004 건수
print('=== MBA210T (발주계획) HP3C22601004 ===')
cur.execute(f"SELECT COUNT(*) FROM mirae.MBA210T WHERE PJT_NO = '{PJT}'")
cnt_mba_pjt = cur.fetchone()[0]
print(f'MBA210T WHERE PJT_NO=HP3C22601004: {cnt_mba_pjt}건')

cur.execute(f"""
SELECT COUNT(*) FROM mirae.MBA210T
WHERE PJT_NO = '{PJT}' AND ITEM_CD = '{ITEM_CD}'
""")
ckr_mba_pjt = cur.fetchone()[0]
print(f'CKR20-145-1065L AND HP3C22601004: {ckr_mba_pjt}건')

# PO_PLAN_STS별 분포
cur.execute(f"""
SELECT PO_PLAN_STS, COUNT(*) FROM mirae.MBA210T
WHERE PJT_NO = '{PJT}'
GROUP BY PO_PLAN_STS ORDER BY PO_PLAN_STS
""")
sts_dist = cur.fetchall()
print(f'PO_PLAN_STS별:')
for r in sts_dist:
    print(f'  STS={repr(r[0])}: {r[1]}건')

result['mba210t_pjt'] = {
    'total': cnt_mba_pjt,
    'ckr_count': ckr_mba_pjt,
    'sts_breakdown': [{'sts': r[0], 'count': r[1]} for r in sts_dist]
}

print()

# 2. MCA210T + MBA210T 합산 (발주 + 발주계획) → 570건 여부
print('=== MCA210T + MBA210T 합산 ===')
cur.execute(f"SELECT COUNT(*) FROM mirae.MCA210T WHERE PJT_NO = '{PJT}'")
cnt_mca = cur.fetchone()[0]
total_combined = cnt_mca + cnt_mba_pjt
print(f'MCA210T: {cnt_mca}건 + MBA210T: {cnt_mba_pjt}건 = 합산: {total_combined}건')

result['combined_total'] = total_combined

print()

# 3. CKR20-145-1065L MBA210T 전체 발주계획 이력
print(f'=== MBA210T CKR20-145-1065L 전체 ===')
cur.execute(f"""
SELECT TOP 20
    A.PO_PLAN_NO, A.PJT_NO, A.SO_NO, A.NEED_QTY,
    A.PLAN_PO_DT, A.PO_PLAN_STS, A.PO_NO
FROM mirae.MBA210T A
WHERE A.ITEM_CD = '{ITEM_CD}'
ORDER BY A.PLAN_PO_DT DESC
""")
rows = cur.fetchall()
print(f'MBA210T CKR20-145-1065L 전체: {len(rows)}건 (TOP 20)')
pjt_set = set()
for r in rows:
    print(f'  PLAN_NO={r[0]} | PJT={r[1]} | NEED_QTY={r[3]} | PLAN_DT={r[4]} | STS={r[5]} | PO_NO={r[6]}')
    if r[1]: pjt_set.add(r[1])

# HP3C22601004 있는지
hp3c_found = [r for r in rows if r[1] == PJT]
print(f'HP3C22601004 포함: {len(hp3c_found)}건')
result['mba_ckr_records'] = [
    {'plan_no': r[0], 'pjt_no': r[1], 'need_qty': float(r[3]) if r[3] else 0,
     'plan_dt': str(r[4]), 'sts': r[5], 'po_no': r[6]}
    for r in rows
]

print()

# 4. MAD111T HP3C22601004 건수
print('=== MAD111T (출고예약?) HP3C22601004 ===')
cur.execute(f"SELECT COUNT(*) FROM mirae.MAD111T WHERE PJT_NO = '{PJT}'")
mad_cnt = cur.fetchone()[0]
print(f'MAD111T HP3C22601004: {mad_cnt}건')
cur.execute(f"SELECT COUNT(*) FROM mirae.MAD111T WHERE PJT_NO = '{PJT}' AND ITEM_CD = '{ITEM_CD}'")
mad_ckr = cur.fetchone()[0]
print(f'CKR20-145-1065L AND HP3C22601004: {mad_ckr}건')
result['mad111t_pjt'] = {'total': mad_cnt, 'ckr_count': mad_ckr}

# MAD111T ADV_KIND 설명
cur.execute("SELECT DISTINCT ADV_KIND FROM mirae.MAD111T")
adv_kinds = [r[0] for r in cur.fetchall()]
print(f'MAD111T ADV_KIND 종류: {adv_kinds}')

conn.close()
with open('C:/MES/wta-agents/workspaces/db-manager/erp_mba_final_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)
print('\n저장완료')
