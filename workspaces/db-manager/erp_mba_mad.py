"""MBA210T, MAD111T, SP_MCA207 조사"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()
result = {}

PJT = 'HP3C22601004'
ITEM_CD = 'CKR20-145-1065L'

# 1. MBA210T 구조 및 HP3C22601004 조회
print('=== MBA210T ===')
cur.execute("SELECT TOP 0 * FROM mirae.MBA210T")
mba_cols = [d[0] for d in cur.description]
print(f'컬럼: {mba_cols}')
cur.execute("SELECT COUNT(*) FROM mirae.MBA210T")
print(f'전체: {cur.fetchone()[0]}건')

has_pjt = 'PJT_NO' in mba_cols
if has_pjt:
    cur.execute(f"SELECT COUNT(*) FROM mirae.MBA210T WHERE PJT_NO = '{PJT}'")
    print(f'HP3C22601004: {cur.fetchone()[0]}건')
    cur.execute(f"SELECT COUNT(*) FROM mirae.MBA210T WHERE ITEM_CD = '{ITEM_CD}' AND PJT_NO = '{PJT}'")
    print(f'CKR20-145-1065L AND HP3C22601004: {cur.fetchone()[0]}건')

cur.execute(f"SELECT COUNT(*) FROM mirae.MBA210T WHERE ITEM_CD = '{ITEM_CD}'")
ckr_mba = cur.fetchone()[0]
print(f'CKR20-145-1065L 전체: {ckr_mba}건')

if has_pjt:
    cur.execute(f"""
    SELECT TOP 5 * FROM mirae.MBA210T WHERE ITEM_CD = '{ITEM_CD}'
    ORDER BY PJT_NO DESC
    """)
    rows = cur.fetchall()
    print(f'샘플:')
    for r in rows:
        print(f'  {dict(zip(mba_cols, [str(v) for v in r]))}')

result['mba210t'] = {'columns': mba_cols, 'ckr_count': ckr_mba, 'has_pjt_no': has_pjt}

print()

# 2. MBA200T (헤더) 구조
print('=== MBA200T ===')
cur.execute("SELECT TOP 0 * FROM mirae.MBA200T")
mba200_cols = [d[0] for d in cur.description]
print(f'컬럼: {mba200_cols}')
result['mba200t_cols'] = mba200_cols

print()

# 3. MAD111T 구조
print('=== MAD111T ===')
cur.execute("SELECT TOP 0 * FROM mirae.MAD111T")
mad_cols = [d[0] for d in cur.description]
print(f'컬럼: {mad_cols}')
cur.execute("SELECT COUNT(*) FROM mirae.MAD111T")
print(f'전체: {cur.fetchone()[0]}건')
has_pjt_mad = 'PJT_NO' in mad_cols
if has_pjt_mad:
    cur.execute(f"SELECT COUNT(*) FROM mirae.MAD111T WHERE PJT_NO = '{PJT}'")
    print(f'HP3C22601004: {cur.fetchone()[0]}건')
    cur.execute(f"SELECT COUNT(*) FROM mirae.MAD111T WHERE ITEM_CD = '{ITEM_CD}' AND PJT_NO = '{PJT}'")
    print(f'CKR20-145-1065L AND HP3C22601004: {cur.fetchone()[0]}건')

cur.execute(f"SELECT COUNT(*) FROM mirae.MAD111T WHERE ITEM_CD = '{ITEM_CD}'")
print(f'CKR20-145-1065L 전체: {cur.fetchone()[0]}건')
result['mad111t'] = {'columns': mad_cols, 'has_pjt_no': has_pjt_mad}

print()

# 4. SP_MCA207_SEL1 프로시저 정의 확인 (발주현황조회 현업용 가능성)
print('=== SP_MCA207_SEL1 프로시저 정의 ===')
cur.execute("""
SELECT ROUTINE_DEFINITION
FROM INFORMATION_SCHEMA.ROUTINES
WHERE ROUTINE_SCHEMA = 'mirae' AND ROUTINE_NAME = 'SP_MCA207_SEL1'
""")
row = cur.fetchone()
if row and row[0]:
    print(row[0][:2000])
    result['sp_mca207_sel1_def'] = row[0]
else:
    print('정의 없음 (암호화됨)')
    result['sp_mca207_sel1_def'] = None

# SP_MCA210S 프로시저
print()
print('=== SP_MCA210S 프로시저 정의 ===')
cur.execute("""
SELECT ROUTINE_DEFINITION
FROM INFORMATION_SCHEMA.ROUTINES
WHERE ROUTINE_SCHEMA = 'mirae' AND ROUTINE_NAME = 'SP_MCA210S'
""")
row2 = cur.fetchone()
if row2 and row2[0]:
    print(row2[0][:1500])
    result['sp_mca210s_def'] = row2[0]
else:
    print('정의 없음 (암호화됨)')
    result['sp_mca210s_def'] = None

print()

# 5. MGA100T (337건) - 자재/구매 관련 가능성
print('=== MGA100T ===')
cur.execute("SELECT TOP 0 * FROM mirae.MGA100T")
mga_cols = [d[0] for d in cur.description]
print(f'컬럼: {mga_cols}')
has_pjt_mga = 'PJT_NO' in mga_cols
if has_pjt_mga:
    cur.execute(f"SELECT COUNT(*) FROM mirae.MGA100T WHERE PJT_NO = '{PJT}' AND ITEM_CD = '{ITEM_CD}'")
    print(f'CKR20-145-1065L AND HP3C22601004: {cur.fetchone()[0]}건')
result['mga100t_cols'] = mga_cols

conn.close()
with open('C:/MES/wta-agents/workspaces/db-manager/erp_mba_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)
print('\n저장완료')
