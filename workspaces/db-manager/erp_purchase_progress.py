"""구매진행현황 관련 테이블/프로시저 조사"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()
result = {}

ITEM_CD = 'CKR20-145-1065L'

# 1. mirae 전체 저장프로시저 목록 (MBA*, MDA*, 구매 관련)
print('=== 전체 저장프로시저 목록 ===')
cur.execute("""
SELECT ROUTINE_NAME, ROUTINE_TYPE
FROM INFORMATION_SCHEMA.ROUTINES
WHERE ROUTINE_SCHEMA = 'mirae'
ORDER BY ROUTINE_TYPE, ROUTINE_NAME
""")
all_procs = cur.fetchall()
print(f'전체: {len(all_procs)}개')
for r in all_procs:
    print(f'  {r[1]}: {r[0]}')
result['all_procedures'] = [{'name': r[0], 'type': r[1]} for r in all_procs]

print()

# 2. MBA* 관련 프로시저 정의 확인 (구매진행현황 후보)
print('=== MBA/MDA 관련 프로시저 정의 ===')
mba_procs = [r[0] for r in all_procs if r[0].startswith('SP_MBA') or r[0].startswith('MBA') or r[0].startswith('SP_MDA') or r[0].startswith('MDA')]
print(f'MBA/MDA 프로시저: {mba_procs}')

for proc_name in mba_procs[:5]:  # 첫 5개만
    cur.execute(f"""
    SELECT ROUTINE_DEFINITION FROM INFORMATION_SCHEMA.ROUTINES
    WHERE ROUTINE_SCHEMA = 'mirae' AND ROUTINE_NAME = '{proc_name}'
    """)
    row = cur.fetchone()
    if row and row[0]:
        print(f'\n--- {proc_name} ---')
        print(row[0][:800])
        result[f'proc_{proc_name}'] = row[0]
    else:
        print(f'{proc_name}: 정의 암호화/없음')

print()

# 3. MDA100T 구조 (69건에 CKR20-145-1065L 포함됨)
print('=== MDA100T (69건 포함) ===')
cur.execute("SELECT TOP 0 * FROM mirae.MDA100T")
mda_cols = [d[0] for d in cur.description]
print(f'컬럼: {mda_cols}')
has_pjt = 'PJT_NO' in mda_cols
has_item = 'ITEM_CD' in mda_cols

cur.execute(f"SELECT COUNT(*) FROM mirae.MDA100T WHERE ITEM_CD = '{ITEM_CD}'")
print(f'CKR20-145-1065L: {cur.fetchone()[0]}건')

if has_pjt:
    cur.execute(f"""
    SELECT TOP 10
        {', '.join(mda_cols[:12])}
    FROM mirae.MDA100T
    WHERE ITEM_CD = '{ITEM_CD}'
    ORDER BY {mda_cols[0]} DESC
    """)
    rows = cur.fetchall()
    print('샘플:')
    for r in rows[:5]:
        print(f'  {dict(zip(mda_cols[:12], [str(v) for v in r]))}')

result['mda100t'] = {'columns': mda_cols, 'has_pjt_no': has_pjt}

print()

# 4. MDA200T 구조
print('=== MDA200T ===')
try:
    cur.execute("SELECT TOP 0 * FROM mirae.MDA200T")
    mda200_cols = [d[0] for d in cur.description]
    cur.execute("SELECT COUNT(*) FROM mirae.MDA200T")
    cnt = cur.fetchone()[0]
    print(f'{cnt}건 | 컬럼: {mda200_cols}')
    result['mda200t'] = {'columns': mda200_cols, 'count': cnt}
except Exception as e:
    print(f'오류: {e}')

print()

# 5. MBA200TV (뷰) 구조 및 CKR 조회
print('=== MBA200TV (뷰) ===')
try:
    cur.execute("SELECT TOP 0 * FROM mirae.MBA200TV")
    mba200v_cols = [d[0] for d in cur.description]
    print(f'컬럼: {mba200v_cols}')
    cur.execute("""
    SELECT VIEW_DEFINITION FROM INFORMATION_SCHEMA.VIEWS
    WHERE TABLE_SCHEMA = 'mirae' AND TABLE_NAME = 'MBA200TV'
    """)
    vrow = cur.fetchone()
    if vrow and vrow[0]:
        print(f'뷰 정의: {vrow[0][:600]}')
        result['mba200tv_def'] = vrow[0]
    result['mba200tv_cols'] = mba200v_cols
except Exception as e:
    print(f'오류: {e}')

print()

# 6. 구매진행현황 추정 - MBA210T STS별 의미 + HP3C22601004 구체 샘플
print('=== MBA210T 구매진행현황 샘플 (HP3C22601004, CKR20-145-1065L) ===')
cur.execute(f"""
SELECT TOP 5
    A.PO_PLAN_NO, A.ITEM_CD, A.PJT_NO, A.PLAN_PO_DT,
    A.NEED_QTY, A.PO_PLAN_STS, A.PO_NO,
    B.ITEM_NM, B.SPEC
FROM mirae.MBA210T A
LEFT JOIN mirae.BBA010T B ON A.ITEM_CD = B.ITEM_CD
WHERE A.ITEM_CD = '{ITEM_CD}' AND A.PJT_NO = 'HP3C22601004'
ORDER BY A.PLAN_PO_DT DESC
""")
rows = cur.fetchall()
for r in rows:
    print(f'  PLAN={r[0]} | ITEM={r[1]} | PJT={r[2]} | DT={r[3]} | QTY={r[4]} | STS={r[5]} | PO={r[6]}')
    print(f'    NM={r[7]} | SPEC={r[8]}')
result['mba_ckr_hp3c_sample'] = [
    {'plan_no': r[0], 'item_cd': r[1], 'pjt_no': r[2], 'plan_dt': str(r[3]),
     'need_qty': float(r[4]) if r[4] else 0, 'sts': r[5], 'po_no': r[6]}
    for r in rows
]

conn.close()
with open('C:/MES/wta-agents/workspaces/db-manager/erp_purchase_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)
print('\n저장완료')
