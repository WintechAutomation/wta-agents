"""MCA210TV 뷰 및 POD 테이블 조사"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()

result = {}

# 1. MCA210TV 뷰로 HP3C22601004 조회
print('=== MCA210TV (VIEW) 로 HP3C22601004 조회 ===')
cur.execute("""
SELECT COUNT(*) FROM mirae.MCA210TV WHERE PJT_NO = 'HP3C22601004'
""")
cnt_view = cur.fetchone()[0]
print(f'MCA210TV VIEW: {cnt_view}건')

# MCA210TV 뷰 컬럼 확인
cur.execute("SELECT TOP 0 * FROM mirae.MCA210TV")
view_cols = [d[0] for d in cur.description]
print(f'MCA210TV 컬럼: {view_cols}')

# CKR20-145-1065L in view
cur.execute("""
SELECT COUNT(*) FROM mirae.MCA210TV
WHERE ITEM_CD = 'CKR20-145-1065L' AND PJT_NO = 'HP3C22601004'
""")
ckr_in_view = cur.fetchone()[0]
print(f'CKR20-145-1065L in MCA210TV AND PJT_NO=HP3C22601004: {ckr_in_view}건')

result['mca210tv'] = {
    'count_hp3c22601004': cnt_view,
    'ckr_in_view_and_pjt': ckr_in_view,
    'columns': view_cols
}

print()

# 2. MCA210TV vs MCA210T 차이점 (뷰 정의 확인)
print('=== MCA210TV 뷰 정의 ===')
cur.execute("""
SELECT VIEW_DEFINITION FROM INFORMATION_SCHEMA.VIEWS
WHERE TABLE_SCHEMA = 'mirae' AND TABLE_NAME = 'MCA210TV'
""")
view_def = cur.fetchone()
if view_def:
    print(view_def[0][:2000])
    result['mca210tv_definition'] = view_def[0]

print()

# 3. POD* 테이블 - 발주 관련인지 확인
print('=== POD 테이블군 확인 ===')
for tbl in ['POD010T', 'POD100T', 'POD200T', 'POD210T']:
    try:
        cur.execute(f"SELECT TOP 0 * FROM mirae.{tbl}")
        cols = [d[0] for d in cur.description]
        cur.execute(f"SELECT COUNT(*) FROM mirae.{tbl}")
        cnt = cur.fetchone()[0]
        # PJT_NO 컬럼 있는지 확인
        has_pjt = 'PJT_NO' in cols
        has_item = 'ITEM_CD' in cols
        print(f'{tbl}: {cnt}건 | PJT_NO={has_pjt} | ITEM_CD={has_item} | 컬럼: {cols[:8]}')
        
        if has_pjt:
            cur.execute(f"SELECT COUNT(*) FROM mirae.{tbl} WHERE PJT_NO = 'HP3C22601004'")
            pjt_cnt = cur.fetchone()[0]
            print(f'  → HP3C22601004: {pjt_cnt}건')
        result[f'pod_{tbl}'] = {'total': cnt, 'has_pjt_no': has_pjt, 'has_item_cd': has_item, 'columns': cols}
    except Exception as e:
        print(f'{tbl}: 오류 - {e}')

print()

# 4. MCA210TV에서 HP3C22601004 570건이 되는지 — STS 조건 없이
print('=== MCA210TV STS별 건수 (HP3C22601004) ===')
cur.execute("""
SELECT STS, COUNT(*) FROM mirae.MCA210TV
WHERE PJT_NO = 'HP3C22601004'
GROUP BY STS ORDER BY STS
""")
for r in cur.fetchall():
    print(f'  STS={repr(r[0])}: {r[1]}건')

# 5. MCA210TV에서 CKR20-145-1065L 전체 발주 (날짜 무관)
print()
print('=== MCA210TV에서 CKR20-145-1065L 전체 발주 ===')
cur.execute("""
SELECT TOP 10 PO_NO, PJT_NO, PO_QTY, STS
FROM mirae.MCA210TV
WHERE ITEM_CD = 'CKR20-145-1065L'
ORDER BY PO_NO DESC
""")
for r in cur.fetchall():
    print(f'  PO={r[0]} | PJT={r[1]} | QTY={r[2]} | STS={r[3]}')

conn.close()
with open('C:/MES/wta-agents/workspaces/db-manager/erp_investigate2_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)
print('\n저장완료')
