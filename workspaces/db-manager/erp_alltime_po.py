"""전체 4059건 품목에 all_time_last_po_dt 추가 조회"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()

# 기존 데이터 로드
with open('C:/MES/wta-agents/workspaces/db-manager/erp_inventory_full.json', encoding='utf-8') as f:
    data = json.load(f)

item_codes = [r['item_cd'] for r in data]
sys.stdout.write(f'품목수: {len(item_codes)}\n')
sys.stdout.flush()

# 전체 기간 마지막 발주일 배치 조회 (날짜 필터 없음)
alltime_map = {}
batch_size = 500
for i in range(0, len(item_codes), batch_size):
    batch = item_codes[i:i+batch_size]
    placeholders = ','.join(["'" + c.replace("'", "''") + "'" for c in batch])
    query = """
    SELECT
        A.ITEM_CD,
        MAX(CASE WHEN ISDATE(B.PO_DT)=1 THEN CONVERT(VARCHAR(10), CAST(B.PO_DT AS DATETIME), 120) ELSE NULL END) AS ALL_TIME_LAST_PO_DT
    FROM mirae.MCA210T A
    JOIN mirae.MCA200T B ON A.PO_NO = B.PO_NO
    WHERE A.ITEM_CD IN (""" + placeholders + """)
    GROUP BY A.ITEM_CD
    """
    cur.execute(query)
    for r in cur.fetchall():
        alltime_map[r[0]] = r[1] or ''
    sys.stdout.write(f'배치 {i//batch_size+1} 완료 ({len(alltime_map)}건 누적)\n')
    sys.stdout.flush()

conn.close()

# 기존 데이터에 필드 추가
for row in data:
    row['all_time_last_po_dt'] = alltime_map.get(row['item_cd'], '')

output_path = 'C:/MES/wta-agents/workspaces/db-manager/erp_inventory_full_v2.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

has_alltime = sum(1 for r in data if r['all_time_last_po_dt'])
sys.stdout.write(f'저장완료: {len(data)}건 -> {output_path}\n')
sys.stdout.write(f'전체기간 발주이력 있음: {has_alltime}건 / 없음: {len(data)-has_alltime}건\n')
sys.stdout.flush()
