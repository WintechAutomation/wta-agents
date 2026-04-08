"""mirae 스키마 전체 테이블에서 CKR20-145-1065L 존재 여부 스캔"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()
result = {}

ITEM_CD = 'CKR20-145-1065L'

# 1. mirae 스키마 전체 테이블 목록
cur.execute("""
SELECT TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'mirae'
ORDER BY TABLE_TYPE, TABLE_NAME
""")
all_tables = cur.fetchall()
print(f'mirae 스키마 전체: {len(all_tables)}개 (테이블+뷰)')
result['total_objects'] = len(all_tables)

# 2. PUR*, BUY*, ORD*, REQ* 패턴 테이블 확인
print('\n=== 발주/구매 관련 패턴 테이블 ===')
patterns = ['PUR', 'BUY', 'ORD', 'REQ', 'MCA', 'MCB', 'MCC', 'MCD', 'MCE',
            'IBA', 'IBC', 'IBB', 'MBA', 'MBB', 'MBC']
for pat in patterns:
    matches = [r[0] for r in all_tables if r[0].startswith(pat)]
    if matches:
        print(f'  {pat}*: {matches}')
result['pattern_tables'] = {p: [r[0] for r in all_tables if r[0].startswith(p)] for p in patterns if any(r[0].startswith(p) for r in all_tables)}

print()

# 3. ITEM_CD 컬럼을 가진 모든 테이블 목록
print('=== ITEM_CD 컬럼 보유 테이블 ===')
cur.execute("""
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'mirae' AND COLUMN_NAME = 'ITEM_CD'
ORDER BY TABLE_NAME
""")
item_cd_tables = [r[0] for r in cur.fetchall()]
print(f'ITEM_CD 컬럼 보유: {len(item_cd_tables)}개')
print(item_cd_tables)
result['tables_with_item_cd'] = item_cd_tables

print()

# 4. ITEM_CD 보유 테이블에서 CKR20-145-1065L 검색
print(f'=== {ITEM_CD} 존재 테이블 스캔 ===')
found_tables = []
for tbl in item_cd_tables:
    try:
        cur.execute(f"SELECT COUNT(*) FROM mirae.{tbl} WHERE ITEM_CD = '{ITEM_CD.replace(chr(39), chr(39)*2)}'")
        cnt = cur.fetchone()[0]
        if cnt > 0:
            print(f'  ✓ {tbl}: {cnt}건')
            found_tables.append({'table': tbl, 'count': cnt})
        else:
            pass  # 없는 건 조용히
    except Exception as e:
        print(f'  ✗ {tbl}: 오류({str(e)[:50]})')
result['found_in_tables'] = found_tables

print()

# 5. 저장 프로시저/함수 목록 (발주현황 관련)
print('=== 발주현황 관련 저장프로시저 ===')
cur.execute("""
SELECT ROUTINE_NAME, ROUTINE_TYPE
FROM INFORMATION_SCHEMA.ROUTINES
WHERE ROUTINE_SCHEMA = 'mirae'
AND (ROUTINE_NAME LIKE '%PO%' OR ROUTINE_NAME LIKE '%ORDER%'
     OR ROUTINE_NAME LIKE '%PURCH%' OR ROUTINE_NAME LIKE '%MCA%')
ORDER BY ROUTINE_TYPE, ROUTINE_NAME
""")
procs = cur.fetchall()
print(f'발주관련 프로시저/함수: {[r[0] for r in procs]}')
result['po_procedures'] = [{'name': r[0], 'type': r[1]} for r in procs]

# 전체 프로시저 수
cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_SCHEMA = 'mirae'")
total_procs = cur.fetchone()[0]
print(f'mirae 전체 프로시저/함수: {total_procs}개')

conn.close()
with open('C:/MES/wta-agents/workspaces/db-manager/erp_fullscan_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print('\n저장완료')
