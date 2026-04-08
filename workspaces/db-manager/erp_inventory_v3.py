"""4059건 재고품목에 MBA210T(발주계획) 데이터 추가 → v3"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()

# 기존 v2 로드
with open('C:/MES/wta-agents/workspaces/db-manager/erp_inventory_full_v2.json', encoding='utf-8') as f:
    data = json.load(f)

item_codes = [r['item_cd'] for r in data]
sys.stdout.write(f'품목수: {len(item_codes)}\n')
sys.stdout.flush()

# MBA210T PLAN_PO_DT 형식 먼저 확인
cur.execute("""
SELECT TOP 5 PLAN_PO_DT, ISDATE(PLAN_PO_DT) AS IS_VALID
FROM mirae.MBA210T
WHERE PLAN_PO_DT IS NOT NULL AND PLAN_PO_DT <> ''
""")
sample_dt = cur.fetchall()
sys.stdout.write(f'PLAN_PO_DT 샘플: {[(str(r[0]), r[1]) for r in sample_dt]}\n')
sys.stdout.flush()

# MBA210T 발주계획 배치 조회 (2024-01-01 이후)
plan_map = {}
batch_size = 500
for i in range(0, len(item_codes), batch_size):
    batch = item_codes[i:i+batch_size]
    placeholders = ','.join(["'" + c.replace("'", "''") + "'" for c in batch])
    query = """
    SELECT
        A.ITEM_CD,
        MAX(CASE WHEN ISDATE(A.PLAN_PO_DT)=1
            THEN CONVERT(VARCHAR(10), CAST(A.PLAN_PO_DT AS DATETIME), 120)
            ELSE NULL END) AS LAST_PLAN_DT,
        COUNT(*) AS PLAN_COUNT,
        MAX(E.PJT_NAME) AS LAST_PJT_NAME,
        MAX(A.PO_PLAN_STS) AS LAST_STS
    FROM mirae.MBA210T A
    LEFT JOIN mirae.SCA200T E ON A.PJT_NO = E.PJT_NO
    WHERE ISDATE(A.PLAN_PO_DT) = 1
    AND CAST(A.PLAN_PO_DT AS DATETIME) >= '2024-01-01'
    AND A.ITEM_CD IN (""" + placeholders + """)
    GROUP BY A.ITEM_CD
    """
    cur.execute(query)
    for r in cur.fetchall():
        plan_map[r[0]] = {
            'last_plan_dt': r[1] or '',
            'plan_count': int(r[2]) if r[2] else 0,
            'plan_pjt_name': r[3] or '',
            'plan_sts': r[4] or '',
        }
    sys.stdout.write(f'발주계획 배치 {i//batch_size+1} 완료 ({len(plan_map)}건 누적)\n')
    sys.stdout.flush()

conn.close()

# 기존 데이터에 발주계획 필드 추가
for row in data:
    icd = row['item_cd']
    if icd in plan_map:
        row['has_plan'] = True
        row['last_plan_dt'] = plan_map[icd]['last_plan_dt']
        row['plan_count'] = plan_map[icd]['plan_count']
        row['plan_pjt_name'] = plan_map[icd]['plan_pjt_name']
        row['plan_sts'] = plan_map[icd]['plan_sts']
    else:
        row['has_plan'] = False
        row['last_plan_dt'] = ''
        row['plan_count'] = 0
        row['plan_pjt_name'] = ''
        row['plan_sts'] = ''

output_path = 'C:/MES/wta-agents/workspaces/db-manager/erp_inventory_full_v3.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

has_plan = sum(1 for r in data if r['has_plan'])
has_po_2024 = sum(1 for r in data if r['has_po'])
both = sum(1 for r in data if r['has_po'] and r['has_plan'])
plan_only = sum(1 for r in data if not r['has_po'] and r['has_plan'])
neither = sum(1 for r in data if not r['has_po'] and not r['has_plan'])

sys.stdout.write(f'저장완료: {len(data)}건 -> {output_path}\n')
sys.stdout.write(f'실제발주(MCA)+발주계획(MBA) 모두있음: {both}건\n')
sys.stdout.write(f'실제발주만 있음: {has_po_2024 - both}건\n')
sys.stdout.write(f'발주계획만 있음(발주서 미발행): {plan_only}건\n')
sys.stdout.write(f'둘 다 없음: {neither}건\n')
sys.stdout.flush()
