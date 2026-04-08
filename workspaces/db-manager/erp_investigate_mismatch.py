"""발주현황 불일치 원인 조사"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()

result = {}

# 1. mirae 스키마 내 MCA 관련 테이블/뷰 전체 확인
print('=== 1. mirae.MCA* 테이블/뷰 전체 목록 ===')
cur.execute("""
SELECT TABLE_NAME, TABLE_TYPE
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'mirae' AND TABLE_NAME LIKE 'MCA%'
ORDER BY TABLE_TYPE, TABLE_NAME
""")
mca_tables = cur.fetchall()
for r in mca_tables:
    print(f'  {r[0]} ({r[1]})')

# 뷰도 확인
cur.execute("""
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.VIEWS
WHERE TABLE_SCHEMA = 'mirae' AND TABLE_NAME LIKE '%PO%'
OR TABLE_SCHEMA = 'mirae' AND TABLE_NAME LIKE '%ORDER%'
OR TABLE_SCHEMA = 'mirae' AND TABLE_NAME LIKE '%PURCH%'
""")
views = cur.fetchall()
print(f'발주관련 뷰: {[r[0] for r in views]}')
result['mca_tables'] = [{'name': r[0], 'type': r[1]} for r in mca_tables]
result['po_views'] = [r[0] for r in views]

print()

# 2. HP3C22601004 발주 건수 — 여러 조건 비교
print('=== 2. HP3C22601004 발주건수 조건별 비교 ===')

# 2a. 현재 쿼리 방식 (PJT_NO 직접 매칭)
cur.execute("""
SELECT COUNT(*) FROM mirae.MCA210T WHERE PJT_NO = 'HP3C22601004'
""")
cnt_direct = cur.fetchone()[0]
print(f'MCA210T.PJT_NO = HP3C22601004 직접: {cnt_direct}건')

# 2b. SO_NO 경유 가능성 (수주번호로 연결될 수 있음)
cur.execute("""
SELECT COUNT(*) FROM mirae.MCA210T A
JOIN mirae.MCA200T B ON A.PO_NO = B.PO_NO
WHERE A.PJT_NO = 'HP3C22601004'
""")
cnt_join = cur.fetchone()[0]
print(f'MCA210T JOIN MCA200T WHERE PJT_NO: {cnt_join}건')

# 2c. T_ITEM_CD 또는 P_ITEM_CD 컬럼 의미 확인 (대체품목 등)
cur.execute("""
SELECT TOP 5 T_ITEM_CD, P_ITEM_CD, ITEM_CD, PO_NO
FROM mirae.MCA210T
WHERE PJT_NO = 'HP3C22601004'
""")
sample = cur.fetchall()
print(f'T_ITEM_CD/P_ITEM_CD 샘플:')
for r in sample:
    print(f'  T={r[0]} | P={r[1]} | ITEM={r[2]} | PO={r[3]}')

# 2d. STS(상태) 컬럼별 건수
cur.execute("""
SELECT STS, COUNT(*) as CNT
FROM mirae.MCA210T
WHERE PJT_NO = 'HP3C22601004'
GROUP BY STS ORDER BY STS
""")
sts_rows = cur.fetchall()
print(f'STS별 건수:')
for r in sts_rows:
    print(f'  STS={repr(r[0])} | {r[1]}건')
result['check2'] = {
    'mca210t_direct': cnt_direct,
    'with_join_mca200t': cnt_join,
    'sts_breakdown': [{'sts': r[0], 'count': r[1]} for r in sts_rows]
}

# 2e. STS 조건 없이 전체 vs 일부 상태만?
cur.execute("""
SELECT COUNT(*) FROM mirae.MCA210T
WHERE PJT_NO = 'HP3C22601004' AND (STS IS NULL OR STS <> '9')
""")
cnt_no9 = cur.fetchone()[0]
print(f'STS<>9 (취소 제외?): {cnt_no9}건')

print()

# 3. CKR20-145-1065L을 품목명/규격으로도 발주 테이블 검색
print('=== 3. 품목명/규격 기반 검색 ===')

# 먼저 품목마스터에서 해당 품목 정보 확인
cur.execute("""
SELECT ITEM_CD, ITEM_NM, SPEC FROM mirae.BBA010T
WHERE ITEM_CD = 'CKR20-145-1065L'
""")
item_info = cur.fetchone()
if item_info:
    item_nm = item_info[1] or ''
    item_spec = item_info[2] or ''
    print(f'품목마스터: NM={item_nm} | SPEC={item_spec}')
    
    # 품목명으로 발주 테이블 검색 (JOIN 통해)
    if item_nm:
        cur.execute("""
        SELECT A.ITEM_CD, A.PO_NO, A.PJT_NO, B.PO_DT
        FROM mirae.MCA210T A
        JOIN mirae.BBA010T C ON A.ITEM_CD = C.ITEM_CD
        JOIN mirae.MCA200T B ON A.PO_NO = B.PO_NO
        WHERE C.ITEM_NM LIKE ?
        AND A.PJT_NO = 'HP3C22601004'
        """, ('%' + item_nm[:10] + '%',))
        nm_rows = cur.fetchall()
        print(f'품목명 유사 검색 (HP3C22601004): {len(nm_rows)}건')

result['check3_item_info'] = {
    'item_cd': 'CKR20-145-1065L',
    'item_nm': item_nm if item_info else '',
    'spec': item_spec if item_info else ''
}

print()

# 4. MCA210T 외 발주 관련 테이블 확인
print('=== 4. mirae 스키마 발주/자재 관련 전체 테이블 ===')
cur.execute("""
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'mirae'
AND (TABLE_NAME LIKE '%PO%' OR TABLE_NAME LIKE '%PUR%' 
     OR TABLE_NAME LIKE '%BOM%' OR TABLE_NAME LIKE '%ISSUE%'
     OR TABLE_NAME LIKE '%MAT%' OR TABLE_NAME LIKE '%MCA%'
     OR TABLE_NAME LIKE '%MCB%' OR TABLE_NAME LIKE '%MCC%')
ORDER BY TABLE_NAME
""")
related = cur.fetchall()
print(f'관련 테이블: {[r[0] for r in related]}')
result['check4_related_tables'] = [r[0] for r in related]

# 5. HP3C22601004에서 CKR20-145-1065L 검색 — 조인 없이 MCA210T만
print()
print('=== 5. CKR20-145-1065L in HP3C22601004 직접 검색 ===')
cur.execute("""
SELECT COUNT(*) FROM mirae.MCA210T
WHERE ITEM_CD = 'CKR20-145-1065L' AND PJT_NO = 'HP3C22601004'
""")
cnt5 = cur.fetchone()[0]
print(f'MCA210T WHERE ITEM_CD=CKR20-145-1065L AND PJT_NO=HP3C22601004: {cnt5}건')

# T_ITEM_CD, P_ITEM_CD로도 검색
cur.execute("""
SELECT COUNT(*) FROM mirae.MCA210T
WHERE (T_ITEM_CD = 'CKR20-145-1065L' OR P_ITEM_CD = 'CKR20-145-1065L')
AND PJT_NO = 'HP3C22601004'
""")
cnt5b = cur.fetchone()[0]
print(f'T_ITEM_CD 또는 P_ITEM_CD = CKR20-145-1065L AND PJT_NO=HP3C22601004: {cnt5b}건')

result['check5'] = {'by_item_cd': cnt5, 'by_t_p_item_cd': cnt5b}

conn.close()

with open('C:/MES/wta-agents/workspaces/db-manager/erp_mismatch_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print('\n저장완료: erp_mismatch_result.json')
