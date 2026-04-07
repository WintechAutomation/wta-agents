"""CKR20-145-1065L 발주이력 직접 조회 - 날짜 무제한"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()

ITEM_CD = 'CKR20-145-1065L'

# 1. 전체 발주이력 (날짜 제한 없음)
query_all = """
SELECT TOP 30
    A.PO_NO,
    A.ITEM_CD,
    A.PO_QTY,
    A.PO_PRICE,
    A.PJT_NO,
    B.PO_DT,
    B.CUST_CD,
    E.PJT_NAME
FROM mirae.MCA210T A
JOIN mirae.MCA200T B ON A.PO_NO = B.PO_NO
LEFT JOIN mirae.SCA200T E ON A.PJT_NO = E.PJT_NO
WHERE A.ITEM_CD = '""" + ITEM_CD.replace("'", "''") + """'
ORDER BY B.PO_DT DESC
"""
cur.execute(query_all)
rows_all = cur.fetchall()
print(f'전체 발주건수 (날짜무관): {len(rows_all)}건')
for r in rows_all:
    print(f'  PO_NO={r[0]} | PO_DT={r[5]} | QTY={r[2]} | PJT={r[7] or r[4] or "없음"}')

print()

# 2. 2024-01-01 이후
query_2024 = """
SELECT COUNT(*)
FROM mirae.MCA210T A
JOIN mirae.MCA200T B ON A.PO_NO = B.PO_NO
WHERE A.ITEM_CD = '""" + ITEM_CD.replace("'", "''") + """'
AND ISDATE(B.PO_DT) = 1
AND CAST(B.PO_DT AS DATETIME) >= '2024-01-01'
"""
cur.execute(query_2024)
cnt_2024 = cur.fetchone()[0]
print(f'2024-01-01 이후 발주건수: {cnt_2024}건')

print()

# 3. PO_DT 원본값 확인 (날짜형식 이상 여부)
query_dt = """
SELECT TOP 10 B.PO_DT, ISDATE(B.PO_DT) AS IS_VALID_DATE, A.PO_NO
FROM mirae.MCA210T A
JOIN mirae.MCA200T B ON A.PO_NO = B.PO_NO
WHERE A.ITEM_CD = '""" + ITEM_CD.replace("'", "''") + """'
ORDER BY B.PO_DT DESC
"""
cur.execute(query_dt)
dt_rows = cur.fetchall()
print('PO_DT 원본값 샘플:')
for r in dt_rows:
    print(f'  PO_DT={repr(r[0])} | ISDATE={r[1]} | PO_NO={r[2]}')

# 4. 결과 저장
result = {
    "item_cd": ITEM_CD,
    "total_po_count_no_date_limit": len(rows_all),
    "po_count_since_2024": cnt_2024,
    "참조_테이블": {
        "발주품목": "mirae.MCA210T (A.ITEM_CD)",
        "발주헤더": "mirae.MCA200T (B.PO_DT, B.CUST_CD)",
        "프로젝트": "mirae.SCA200T (E.PJT_NAME)",
        "조인조건": "MCA210T.PO_NO = MCA200T.PO_NO, MCA210T.PJT_NO = SCA200T.PJT_NO"
    },
    "날짜필터": "ISDATE(B.PO_DT)=1 AND CAST(B.PO_DT AS DATETIME) >= '2024-01-01'",
    "po_records": [
        {
            "po_no": r[0],
            "po_dt": str(r[5]) if r[5] else "",
            "qty": float(r[2]) if r[2] else 0,
            "pjt_no": r[4] or "",
            "pjt_name": r[7] or ""
        }
        for r in rows_all
    ],
    "po_dt_samples": [
        {"po_dt": str(r[0]), "isdate": r[1], "po_no": r[2]}
        for r in dt_rows
    ]
}

with open('C:/MES/wta-agents/workspaces/db-manager/erp_check_po_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print('\n저장완료: erp_check_po_result.json')

conn.close()
