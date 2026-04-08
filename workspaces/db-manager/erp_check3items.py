"""3가지 확인 사항 조회"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()

result = {}

# 1. HP3C22601004 프로젝트 전체 발주 품목
print('=== 1. HP3C22601004 프로젝트 발주 품목 ===')
cur.execute("""
SELECT
    A.ITEM_CD,
    A.PO_NO,
    A.PO_QTY,
    A.PO_PRICE,
    B.PO_DT,
    C.ITEM_NM,
    C.SPEC
FROM mirae.MCA210T A
JOIN mirae.MCA200T B ON A.PO_NO = B.PO_NO
LEFT JOIN mirae.BBA010T C ON A.ITEM_CD = C.ITEM_CD
WHERE A.PJT_NO = 'HP3C22601004'
ORDER BY B.PO_DT DESC, A.ITEM_CD
""")
rows1 = cur.fetchall()
print(f'총 발주 품목라인: {len(rows1)}건')
ckr_found = [r for r in rows1 if r[0] == 'CKR20-145-1065L']
print(f'CKR20-145-1065L 포함 여부: {"포함 " + str(len(ckr_found)) + "건" if ckr_found else "미포함"}')
for r in rows1[:20]:
    marker = ' <<<' if r[0] == 'CKR20-145-1065L' else ''
    print(f'  {r[0]} | {r[5] or ""[:15]} | PO={r[1]} | PO_DT={r[4]} | QTY={r[2]}{marker}')
if len(rows1) > 20:
    print(f'  ... 이하 {len(rows1)-20}건 생략')

result['check1_pjt_po_items'] = {
    'project_no': 'HP3C22601004',
    'total_lines': len(rows1),
    'ckr_included': len(ckr_found) > 0,
    'ckr_records': [{'po_no': r[1], 'po_dt': str(r[4]), 'qty': float(r[2]) if r[2] else 0} for r in ckr_found],
    'all_items': [{'item_cd': r[0], 'item_nm': (r[5] or '')[:30], 'po_no': r[1], 'po_dt': str(r[4])} for r in rows1]
}

print()

# 2. 현재 쿼리 방식(ITEM_CD 단독) vs PO_NO 기반 — 차이 확인
# 기존: stock 품목코드 → PO 테이블에서 ITEM_CD 매칭
# 우려: 같은 PO에서 다른 ITEM_CD로 발주된 경우? → 실제로는 별개 품목이므로 논리적으로 문제 없음
# 확인: CKR20-145-1065L이 속한 PO_NO들에 어떤 품목들이 같이 있는지
print('=== 2. CKR20-145-1065L 발주번호(PO_NO) 내 동반 품목 확인 ===')
cur.execute("""
SELECT DISTINCT A.PO_NO
FROM mirae.MCA210T A
WHERE A.ITEM_CD = 'CKR20-145-1065L'
""")
po_nos = [r[0] for r in cur.fetchall()]
print(f'CKR20-145-1065L이 포함된 PO_NO: {len(po_nos)}건')

if po_nos:
    placeholders = ','.join(["'" + p.replace("'","''") + "'" for p in po_nos[:5]])
    cur.execute(f"""
    SELECT A.PO_NO, A.ITEM_CD, B.PO_DT, A.PJT_NO
    FROM mirae.MCA210T A
    JOIN mirae.MCA200T B ON A.PO_NO = B.PO_NO
    WHERE A.PO_NO IN ({placeholders})
    ORDER BY A.PO_NO, A.ITEM_CD
    """)
    rows2 = cur.fetchall()
    print(f'해당 PO에 포함된 전체 품목라인 (첫 5개 PO): {len(rows2)}건')
    for r in rows2[:30]:
        marker = ' <<<' if r[1] == 'CKR20-145-1065L' else ''
        print(f'  PO={r[0]} | ITEM={r[1]} | PO_DT={r[2]} | PJT={r[3]}{marker}')

result['check2_po_siblings'] = {
    'explanation': 'ITEM_CD 단독 매칭은 정상. 같은 PO에 다른 ITEM_CD는 별개 품목이므로 매칭 방식 문제 없음.',
    'ckr_po_count': len(po_nos),
    'po_nos': po_nos[:10]
}

print()

# 3. CKR20-* 유사 품목코드 발주 조회
print('=== 3. CKR20-* 유사 품목코드 발주 현황 ===')
cur.execute("""
SELECT
    A.ITEM_CD,
    MAX(CASE WHEN ISDATE(B.PO_DT)=1 THEN CONVERT(VARCHAR(10), CAST(B.PO_DT AS DATETIME), 120) ELSE NULL END) AS LAST_PO_DT,
    COUNT(DISTINCT A.PO_NO) AS PO_COUNT,
    SUM(CASE WHEN ISDATE(B.PO_DT)=1 AND CAST(B.PO_DT AS DATETIME) >= '2024-01-01' THEN 1 ELSE 0 END) AS PO_COUNT_2024
FROM mirae.MCA210T A
JOIN mirae.MCA200T B ON A.PO_NO = B.PO_NO
WHERE A.ITEM_CD LIKE 'CKR20-%'
GROUP BY A.ITEM_CD
ORDER BY LAST_PO_DT DESC
""")
rows3 = cur.fetchall()
print(f'CKR20-* 품목코드 발주 현황: {len(rows3)}개 품목')
for r in rows3:
    marker = ' <<<' if r[0] == 'CKR20-145-1065L' else ''
    print(f'  {r[0]} | 마지막발주={r[1]} | 전체PO={r[2]}건 | 2024이후={r[3]}건{marker}')

result['check3_ckr20_variants'] = [
    {'item_cd': r[0], 'last_po_dt': r[1] or '', 'total_po_count': int(r[2]), 'po_count_since_2024': int(r[3])}
    for r in rows3
]

conn.close()

with open('C:/MES/wta-agents/workspaces/db-manager/erp_check3_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print('\n저장완료: erp_check3_result.json')
