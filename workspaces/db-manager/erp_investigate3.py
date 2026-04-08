"""MCA210TV 뷰 컬럼 및 POD 테이블 조사 - 안전 버전"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()
result = {}

# 1. MCA210TV 뷰 컬럼 확인
print('=== MCA210TV 컬럼 ===')
cur.execute("SELECT TOP 0 * FROM mirae.MCA210TV")
view_cols = [d[0] for d in cur.description]
print(view_cols)
result['mca210tv_columns'] = view_cols

# 뷰 정의
cur.execute("""
SELECT VIEW_DEFINITION FROM INFORMATION_SCHEMA.VIEWS
WHERE TABLE_SCHEMA = 'mirae' AND TABLE_NAME = 'MCA210TV'
""")
row = cur.fetchone()
vdef = row[0] if row else ''
print(f'\nMCA210TV 뷰 정의 (앞 1000자):\n{vdef[:1000]}')
result['mca210tv_definition'] = vdef

print()

# 2. POD 테이블 컬럼 확인
print('=== POD 테이블 컬럼 ===')
for tbl in ['POD010T', 'POD100T', 'POD200T', 'POD210T', 'POD220T']:
    try:
        cur.execute(f"SELECT TOP 0 * FROM mirae.{tbl}")
        cols = [d[0] for d in cur.description]
        cur.execute(f"SELECT COUNT(*) FROM mirae.{tbl}")
        cnt = cur.fetchone()[0]
        has_pjt = 'PJT_NO' in cols
        has_item = 'ITEM_CD' in cols
        print(f'{tbl} ({cnt}건): PJT_NO={has_pjt}, ITEM_CD={has_item}')
        print(f'  컬럼: {cols}')
        result[tbl] = {'count': cnt, 'columns': cols, 'has_pjt_no': has_pjt, 'has_item_cd': has_item}
    except Exception as e:
        print(f'{tbl}: 오류 {e}')

print()

# 3. MCA220TV 뷰 컬럼
print('=== MCA220TV 컬럼 ===')
try:
    cur.execute("SELECT TOP 0 * FROM mirae.MCA220TV")
    cols220 = [d[0] for d in cur.description]
    print(cols220)
    result['mca220tv_columns'] = cols220
    
    cur.execute("""
    SELECT VIEW_DEFINITION FROM INFORMATION_SCHEMA.VIEWS
    WHERE TABLE_SCHEMA = 'mirae' AND TABLE_NAME = 'MCA220TV'
    """)
    row2 = cur.fetchone()
    print(f'MCA220TV 정의 (앞 500자): {row2[0][:500] if row2 else "없음"}')
except Exception as e:
    print(f'MCA220TV 오류: {e}')

conn.close()
with open('C:/MES/wta-agents/workspaces/db-manager/erp_inv3_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)
print('\n저장완료')
