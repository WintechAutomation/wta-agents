import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wmes.settings')
import django
django.setup()

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
print('STOCK_COUNT=' + str(len(stock_rows)))
print('STOCK_HEADER=ITEM_CD|ITEM_NM|SPEC|STOCK_QTY|AVG_PRICE|STOCK_AMT|UNIT|ITEM_KIND|LOCATION|WH_CD')
for r in stock_rows:
    vals = [str(v) if v is not None else '' for v in r]
    print('STOCK=' + '|'.join(vals))

# 2. 2024-01-01 이후 발주 내역 (재고 있는 품목 한정)
item_codes = [r[0] for r in stock_rows]
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
    po_rows = cur.fetchall()
    print('PO_COUNT=' + str(len(po_rows)))
    print('PO_HEADER=ITEM_CD|LAST_PO_DT|PO_CNT|PJT_NAME|PJT_NO')
    for r in po_rows:
        vals = [str(v) if v is not None else '' for v in r]
        print('PO=' + '|'.join(vals))

conn.close()
