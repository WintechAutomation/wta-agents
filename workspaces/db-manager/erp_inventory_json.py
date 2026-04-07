"""ERP 현재고현황 + 2024년 이후 발주내역 조회 - JSON 출력"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()

# 1. 현재고현황 재고량>0, 재고금액 높은 순 TOP 100
cur.execute("""
SELECT TOP 100
    A.ITEM_CD,
    B.ITEM_NM,
    B.SPEC,
    A.STOCK_QTY,
    A.AVG_PRICE,
    A.STOCK_AMT,
    B.INV_UNIT,
    B.ITEM_KIND,
    A.LOCATION_NO,
    A.WH_CD
FROM mirae.IBA100T A
JOIN mirae.BBA010T B ON A.ITEM_CD = B.ITEM_CD
WHERE A.STOCK_QTY > 0
ORDER BY A.STOCK_AMT DESC
""")
stock_rows = cur.fetchall()

stock_list = []
for r in stock_rows:
    stock_list.append({
        "item_cd": r[0] or "",
        "item_nm": r[1] or "",
        "spec": r[2] or "",
        "stock_qty": float(r[3]) if r[3] else 0,
        "avg_price": float(r[4]) if r[4] else 0,
        "stock_amt": float(r[5]) if r[5] else 0,
        "unit": r[6] or "",
        "item_kind": r[7] or "",
        "location": r[8] or "",
        "wh_cd": r[9] or "",
    })

# 2. 2024-01-01 이후 발주 내역
item_codes = [r[0] for r in stock_rows]
po_map = {}
if item_codes:
    placeholders = ','.join(["'" + c.replace("'", "''") + "'" for c in item_codes])
    query = """
    SELECT
        A.ITEM_CD,
        MAX(CONVERT(VARCHAR(10), CAST(B.PO_DT AS DATETIME), 120)) AS LAST_PO_DT,
        COUNT(DISTINCT A.PO_NO) AS PO_COUNT,
        MAX(E.PJT_NAME) AS PJT_NAME,
        MAX(A.PJT_NO) AS PJT_NO
    FROM mirae.MCA210T A
    JOIN mirae.MCA200T B ON A.PO_NO = B.PO_NO
    LEFT JOIN mirae.SCA200T E ON A.PJT_NO = E.PJT_NO
    WHERE ISDATE(B.PO_DT) = 1
    AND CAST(B.PO_DT AS DATETIME) >= '2024-01-01'
    AND A.ITEM_CD IN (""" + placeholders + """)
    GROUP BY A.ITEM_CD
    """
    cur.execute(query)
    for r in cur.fetchall():
        po_map[r[0]] = {
            "last_po_dt": r[1] or "",
            "po_count": int(r[2]) if r[2] else 0,
            "pjt_name": r[3] or "",
            "pjt_no": r[4] or "",
        }

conn.close()

# 결합
result = []
for s in stock_list:
    row = dict(s)
    if s["item_cd"] in po_map:
        row["has_po"] = True
        row.update(po_map[s["item_cd"]])
    else:
        row["has_po"] = False
        row["last_po_dt"] = ""
        row["po_count"] = 0
        row["pjt_name"] = ""
        row["pjt_no"] = ""
    result.append(row)

output_path = 'C:/MES/wta-agents/workspaces/db-manager/erp_inventory_data.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"저장완료: {len(result)}건 -> {output_path}")
print(f"발주내역 있는 품목: {sum(1 for r in result if r['has_po'])}건")
