"""CKR20-145-1065L 발주이력 직접 조회"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()

ITEM_CD = 'CKR20-145-1065L'

# MCA200T 컬럼 확인
cur.execute("SELECT TOP 0 * FROM mirae.MCA200T")
cols200 = [d[0] for d in cur.description]
print(f'MCA200T 컬럼: {cols200}')

# MCA210T 컬럼 확인
cur.execute("SELECT TOP 0 * FROM mirae.MCA210T")
cols210 = [d[0] for d in cur.description]
print(f'MCA210T 컬럼: {cols210}')

conn.close()
