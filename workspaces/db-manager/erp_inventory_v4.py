"""4059건 재고품목에 MDA100T(입고검수) 데이터 추가 → v4"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()

# ACPT_DT 형식 먼저 확인
cur.execute("""
SELECT TOP 5 ACPT_DT, ISDATE(ACPT_DT) AS IS_VALID, IN_QTY, BAD_QTY
FROM mirae.MDA100T
WHERE ACPT_DT IS NOT NULL AND ACPT_DT <> ''
ORDER BY ACPT_DT DESC
""")
sys.stdout.write(f'ACPT_DT 샘플: {[(str(r[0]), r[1]) for r in cur.fetchall()]}\n')
sys.stdout.flush()

# v3 로드
with open('C:/MES/wta-agents/workspaces/db-manager/erp_inventory_full_v3.json', encoding='utf-8') as f:
    data = json.load(f)

item_codes = [r['item_cd'] for r in data]
sys.stdout.write(f'품목수: {len(item_codes)}\n')
sys.stdout.flush()

# 배치 조회
receipt_map = {}      # 2024이후
alltime_map = {}      # 전체기간 최근 입고일
batch_size = 500

for i in range(0, len(item_codes), batch_size):
    batch = item_codes[i:i+batch_size]
    placeholders = ','.join(["'" + c.replace("'", "''") + "'" for c in batch])

    # 2024-01-01 이후 입고검수
    q2024 = """
    SELECT
        A.ITEM_CD,
        MAX(CASE WHEN ISDATE(A.ACPT_DT)=1
            THEN CONVERT(VARCHAR(10), CAST(A.ACPT_DT AS DATETIME), 120)
            ELSE NULL END) AS LAST_RECEIPT_DT,
        COUNT(*) AS RECEIPT_COUNT,
        SUM(ISNULL(A.ACPT_QTY, 0)) AS TOT_ACPT_QTY,
        SUM(ISNULL(A.BAD_QTY, 0)) AS TOT_BAD_QTY,
        MAX(E.PJT_NAME) AS LAST_PJT_NAME
    FROM mirae.MDA100T A
    LEFT JOIN mirae.SCA200T E ON A.PJT_NO = E.PJT_NO
    WHERE ISDATE(A.ACPT_DT) = 1
    AND CAST(A.ACPT_DT AS DATETIME) >= '2024-01-01'
    AND A.ITEM_CD IN (""" + placeholders + """)
    GROUP BY A.ITEM_CD
    """
    cur.execute(q2024)
    for r in cur.fetchall():
        receipt_map[r[0]] = {
            'last_receipt_dt': r[1] or '',
            'receipt_count': int(r[2]) if r[2] else 0,
            'total_receipt_qty': float(r[3]) if r[3] else 0,
            'total_bad_qty': float(r[4]) if r[4] else 0,
            'receipt_pjt_name': r[5] or '',
        }

    # 전체기간 최근 입고일
    qall = """
    SELECT
        ITEM_CD,
        MAX(CASE WHEN ISDATE(ACPT_DT)=1
            THEN CONVERT(VARCHAR(10), CAST(ACPT_DT AS DATETIME), 120)
            ELSE NULL END) AS ALL_TIME_LAST_DT
    FROM mirae.MDA100T
    WHERE ITEM_CD IN (""" + placeholders + """)
    GROUP BY ITEM_CD
    """
    cur.execute(qall)
    for r in cur.fetchall():
        alltime_map[r[0]] = r[1] or ''

    sys.stdout.write(f'배치 {i//batch_size+1} 완료 (2024이후={len(receipt_map)}건, 전체={len(alltime_map)}건)\n')
    sys.stdout.flush()

conn.close()

# 데이터 병합
for row in data:
    icd = row['item_cd']
    row['all_time_last_receipt_dt'] = alltime_map.get(icd, '')
    if icd in receipt_map:
        row['has_receipt'] = True
        row.update(receipt_map[icd])
    else:
        row['has_receipt'] = False
        row['last_receipt_dt'] = ''
        row['receipt_count'] = 0
        row['total_receipt_qty'] = 0
        row['total_bad_qty'] = 0
        row['receipt_pjt_name'] = ''

output_path = 'C:/MES/wta-agents/workspaces/db-manager/erp_inventory_full_v4.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

has_receipt = sum(1 for r in data if r['has_receipt'])
has_alltime = sum(1 for r in data if r['all_time_last_receipt_dt'])
total_bad = sum(r['total_bad_qty'] for r in data)

sys.stdout.write(f'저장완료: {len(data)}건 -> {output_path}\n')
sys.stdout.write(f'2024이후 입고검수 있음: {has_receipt}건\n')
sys.stdout.write(f'전체기간 입고이력 있음: {has_alltime}건\n')
sys.stdout.write(f'2024이후 총 불량수량 합계: {total_bad:,.1f}\n')
sys.stdout.flush()
