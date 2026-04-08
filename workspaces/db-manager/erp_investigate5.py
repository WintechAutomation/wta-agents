"""SO_NO='CMA2601001' 기반 최종 확인"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()
result = {}

# 1. SO_NO='CMA2601001' 기반 발주 - CKR20-145-1065L 포함 여부
print('=== SO_NO=CMA2601001 기반 발주 조회 ===')
cur.execute("""
SELECT COUNT(*) FROM mirae.MCA210T WHERE SO_NO = 'CMA2601001'
""")
cnt_so = cur.fetchone()[0]
print(f'SO_NO=CMA2601001 전체 발주라인: {cnt_so}건')

cur.execute("""
SELECT COUNT(*) FROM mirae.MCA210T
WHERE SO_NO = 'CMA2601001' AND ITEM_CD = 'CKR20-145-1065L'
""")
ckr_so = cur.fetchone()[0]
print(f'SO_NO=CMA2601001 AND ITEM_CD=CKR20-145-1065L: {ckr_so}건')
result['so_cma2601001'] = {'total': cnt_so, 'ckr_count': ckr_so}

if ckr_so > 0:
    cur.execute("""
    SELECT TOP 10 A.PO_NO, A.PJT_NO, A.PO_QTY, B.PO_DT
    FROM mirae.MCA210T A
    JOIN mirae.MCA200T B ON A.PO_NO = B.PO_NO
    WHERE A.SO_NO = 'CMA2601001' AND A.ITEM_CD = 'CKR20-145-1065L'
    ORDER BY B.PO_DT DESC
    """)
    for r in cur.fetchall():
        print(f'  PO={r[0]} | PJT={r[1]} | QTY={r[2]} | PO_DT={r[3]}')

print()

# 2. HP3C22601004 관련 전체 SO_NO 목록과 각 SO_NO별 건수
print('=== HP3C2260* 프로젝트들의 SO_NO 분포 ===')
cur.execute("""
SELECT SO_NO, PJT_NO, COUNT(*) AS CNT
FROM mirae.MCA210T
WHERE PJT_NO LIKE 'HP3C22601%'
GROUP BY SO_NO, PJT_NO
ORDER BY SO_NO, PJT_NO
""")
so_dist = cur.fetchall()
for r in so_dist:
    print(f'  SO_NO={r[0]} | PJT={r[1]}: {r[2]}건')
result['so_distribution'] = [{'so_no': r[0], 'pjt_no': r[1], 'count': r[2]} for r in so_dist]

print()

# 3. 화면의 '발주현황조회' 필터 조건 추정:
# ERP 화면은 SCA100T(수주)의 PJT_NO로 SO_NO를 얻고,
# 그 SO_NO로 MCA210T를 조회할 가능성 → SCA100T 확인
print('=== SCA100T 컬럼 및 HP3C22601004 수주 ===')
try:
    cur.execute("SELECT TOP 0 * FROM mirae.SCA100T")
    sca100_cols = [d[0] for d in cur.description]
    print(f'SCA100T 컬럼: {sca100_cols}')
    result['sca100t_cols'] = sca100_cols
    
    if 'PJT_NO' in sca100_cols:
        cur.execute("SELECT * FROM mirae.SCA100T WHERE PJT_NO = 'HP3C22601004'")
        sca_rows = cur.fetchall()
        print(f'SCA100T HP3C22601004: {len(sca_rows)}건')
        for r in sca_rows[:5]:
            print(f'  {dict(zip(sca100_cols, r))}')
except Exception as e:
    print(f'SCA100T 오류: {e}')

print()

# 4. HP3C22601001~004 합산 건수 및 CKR20-145-1065L 포함 여부
print('=== HP3C22601001~004 합산 발주 ===')
cur.execute("""
SELECT COUNT(*) FROM mirae.MCA210T
WHERE PJT_NO IN ('HP3C22601001','HP3C22601002','HP3C22601003','HP3C22601004')
""")
cnt_group = cur.fetchone()[0]
print(f'HP3C22601001~004 합산: {cnt_group}건')

cur.execute("""
SELECT PJT_NO, COUNT(*) FROM mirae.MCA210T
WHERE PJT_NO IN ('HP3C22601001','HP3C22601002','HP3C22601003','HP3C22601004')
AND ITEM_CD = 'CKR20-145-1065L'
GROUP BY PJT_NO
""")
ckr_group = cur.fetchall()
print(f'CKR20-145-1065L in 001~004: {[dict(pjt_no=r[0], count=r[1]) for r in ckr_group]}')
result['group_total'] = cnt_group
result['ckr_in_group'] = [{'pjt_no': r[0], 'count': r[1]} for r in ckr_group]

conn.close()
with open('C:/MES/wta-agents/workspaces/db-manager/erp_inv5_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)
print('\n저장완료')
