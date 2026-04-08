"""SO_NO 경유 발주 연결 및 MCA260T_SW 조사"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()
result = {}

PJT = 'HP3C22601004'

# 1. SCA* (수주) 테이블에서 해당 프로젝트 SO_NO 확인
print('=== 1. 프로젝트 HP3C22601004 수주번호(SO_NO) 확인 ===')
cur.execute("""
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'mirae' AND TABLE_NAME LIKE 'SCA%'
ORDER BY TABLE_NAME
""")
sca_tables = [r[0] for r in cur.fetchall()]
print(f'SCA* 테이블: {sca_tables}')
result['sca_tables'] = sca_tables

# SCA200T에서 HP3C22601004 관련 SO_NO 조회
cur.execute("""
SELECT TOP 0 * FROM mirae.SCA200T
""")
sca200_cols = [d[0] for d in cur.description]
print(f'SCA200T 컬럼: {sca200_cols}')

# 2. MCA210T의 SO_NO로 HP3C22601004 연결
print('\n=== 2. SO_NO 경유 발주 조회 ===')
# HP3C22601004와 연결된 SO_NO 목록 (SCA 수주 테이블에서)
if 'SCA100T' in sca_tables:
    try:
        cur.execute("SELECT TOP 0 * FROM mirae.SCA100T")
        sca100_cols = [d[0] for d in cur.description]
        print(f'SCA100T 컬럼: {sca100_cols}')
        if 'PJT_NO' in sca100_cols:
            cur.execute(f"SELECT SO_NO FROM mirae.SCA100T WHERE PJT_NO = '{PJT}'")
            so_nos = [r[0] for r in cur.fetchall()]
            print(f'SCA100T에서 {PJT} 연결 SO_NO: {so_nos}')
            result['so_nos_from_sca100t'] = so_nos
    except Exception as e:
        print(f'SCA100T 오류: {e}')

# MCA210T에서 SO_NO가 HP3C22601004 관련인 경우
# (프로젝트 번호 체계: HP3C22601004 → SO_NO가 다를 수 있음)
cur.execute(f"""
SELECT DISTINCT SO_NO FROM mirae.MCA210T
WHERE PJT_NO = '{PJT}' AND SO_NO IS NOT NULL AND SO_NO <> ''
""")
so_in_mca = [r[0] for r in cur.fetchall()]
print(f'MCA210T에서 PJT_NO={PJT}인 행의 SO_NO: {so_in_mca[:10]}')
result['so_nos_in_mca210t'] = so_in_mca[:10]

# SO_NO로 역방향 검색 (해당 SO_NO를 가진 모든 발주)
if so_in_mca:
    placeholders = ','.join(["'"+s.replace("'","''")+"'" for s in so_in_mca[:5]])
    cur.execute(f"""
    SELECT COUNT(*) FROM mirae.MCA210T
    WHERE SO_NO IN ({placeholders})
    """)
    cnt_so = cur.fetchone()[0]
    print(f'해당 SO_NO로 연결된 전체 MCA210T 건수: {cnt_so}건')
    result['count_by_so_no'] = cnt_so

print()

# 3. MCA260T_SW 테이블 확인
print('=== 3. MCA260T_SW 테이블 ===')
try:
    cur.execute("SELECT TOP 0 * FROM mirae.MCA260T_SW")
    sw_cols = [d[0] for d in cur.description]
    cur.execute("SELECT COUNT(*) FROM mirae.MCA260T_SW")
    sw_cnt = cur.fetchone()[0]
    print(f'MCA260T_SW: {sw_cnt}건 | 컬럼: {sw_cols}')
    has_pjt = 'PJT_NO' in sw_cols
    has_item = 'ITEM_CD' in sw_cols
    if has_pjt:
        cur.execute(f"SELECT COUNT(*) FROM mirae.MCA260T_SW WHERE PJT_NO = '{PJT}'")
        print(f'HP3C22601004: {cur.fetchone()[0]}건')
    result['mca260t_sw'] = {'count': sw_cnt, 'columns': sw_cols}
except Exception as e:
    print(f'MCA260T_SW 오류: {e}')

print()

# 4. 발주현황조회 화면이 쓸 법한 BOM 연계 테이블 확인
print('=== 4. BOM 및 자재출고 테이블 ===')
for tbl in ['BOM_LOG', 'BOM_SESSION', 'BOM_USER']:
    try:
        cur.execute(f"SELECT TOP 0 * FROM mirae.{tbl}")
        cols = [d[0] for d in cur.description]
        cur.execute(f"SELECT COUNT(*) FROM mirae.{tbl}")
        cnt = cur.fetchone()[0]
        print(f'{tbl}: {cnt}건 | 컬럼: {cols}')
    except Exception as e:
        print(f'{tbl}: 오류 {e}')

print()

# 5. MCA210T 전체 건수 vs HP3C22601004 건수 재확인
print('=== 5. PJT_NO 패턴 검색 ===')
# HP3C22601004의 변형 (하위 프로젝트 등)
cur.execute(f"""
SELECT PJT_NO, COUNT(*) AS CNT FROM mirae.MCA210T
WHERE PJT_NO LIKE 'HP3C226%'
GROUP BY PJT_NO ORDER BY PJT_NO
""")
pjt_variants = cur.fetchall()
print(f'HP3C226* 프로젝트별 발주건수:')
for r in pjt_variants:
    print(f'  {r[0]}: {r[1]}건')
result['hp3c226_variants'] = [{'pjt_no': r[0], 'count': r[1]} for r in pjt_variants]

total_226 = sum(r[1] for r in pjt_variants)
print(f'HP3C226* 합계: {total_226}건')

# CKR20-145-1065L이 있는 프로젝트
cur.execute("""
SELECT PJT_NO, COUNT(*) AS CNT FROM mirae.MCA210T
WHERE ITEM_CD = 'CKR20-145-1065L'
GROUP BY PJT_NO ORDER BY PJT_NO
""")
ckr_pjts = cur.fetchall()
print(f'\nCKR20-145-1065L 발주 프로젝트:')
for r in ckr_pjts:
    print(f'  {r[0]}: {r[1]}건')
result['ckr_projects'] = [{'pjt_no': r[0], 'count': r[1]} for r in ckr_pjts]

conn.close()
with open('C:/MES/wta-agents/workspaces/db-manager/erp_inv4_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)
print('\n저장완료')
