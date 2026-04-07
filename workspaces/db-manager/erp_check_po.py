"""CKR20-145-1065L 발주이력 직접 조회 - 날짜 제한 없음"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()

ITEM_CD = 'CKR20-145-1065L'

# 1. MCA210T (발주품목) 직접 조회 - 날짜 제한 없음
cur.execute("""
SELECT TOP 20
    A.PO_NO,
    A.ITEM_CD,
    A.PO_QTY,
    A.PO_PRICE,
    A.PJT_NO,
    B.PO_DT,
    B.VENDOR_CD,
    E.PJT_NAME
FROM mirae.MCA210T A
JOIN mirae.MCA200T B ON A.PO_NO = B.PO_NO
LEFT JOIN mirae.SCA200T E ON A.PJT_NO = E.PJT_NO
WHERE A.ITEM_CD = ?
ORDER BY B.PO_DT DESC
""", (ITEM_CD,))
rows = cur.fetchall()
print(f'MCA210T 발주건수: {len(rows)}건')
for r in rows:
    print(f'  PO_NO={r[0]} | PO_DT={r[5]} | QTY={r[2]} | PRICE={r[3]} | PJT={r[7] or r[4]}')

print()

# 2. 2024-01-01 이후로 한정하면 몇 건?
cur.execute("""
SELECT COUNT(*) 
FROM mirae.MCA210T A
JOIN mirae.MCA200T B ON A.PO_NO = B.PO_NO
WHERE A.ITEM_CD = ?
AND ISDATE(B.PO_DT) = 1
AND CAST(B.PO_DT AS DATETIME) >= '2024-01-01'
""", (ITEM_CD,))
cnt_2024 = cur.fetchone()[0]
print(f'2024-01-01 이후 발주건수: {cnt_2024}건')

# 3. PO_DT 값 확인 (NULL/공백/형식 이상 여부)
cur.execute("""
SELECT TOP 10 B.PO_DT, ISDATE(B.PO_DT) AS IS_VALID
FROM mirae.MCA210T A
JOIN mirae.MCA200T B ON A.PO_NO = B.PO_NO
WHERE A.ITEM_CD = ?
ORDER BY B.PO_DT DESC
""", (ITEM_CD,))
dt_rows = cur.fetchall()
print(f'PO_DT 샘플:')
for r in dt_rows:
    print(f'  PO_DT={repr(r[0])} | ISDATE={r[1]}')

# 4. 다른 발주 관련 테이블 있는지 확인 (MCA 시리즈)
cur.execute("""
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = 'mirae' AND TABLE_NAME LIKE 'MCA%'
ORDER BY TABLE_NAME
""")
tables = [r[0] for r in cur.fetchall()]
print(f'\nmirae.MCA* 테이블 목록: {tables}')

conn.close()

result = {
    "item_cd": ITEM_CD,
    "total_po_count": len(rows),
    "po_count_since_2024": cnt_2024,
    "po_records": [
        {"po_no": r[0], "po_dt": str(r[5]) if r[5] else "", "qty": float(r[2]) if r[2] else 0, "pjt": r[7] or r[4] or ""}
        for r in rows
    ],
    "mca_tables": tables
}

with open('C:/MES/wta-agents/workspaces/db-manager/erp_check_po_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print('\n저장완료: erp_check_po_result.json')
