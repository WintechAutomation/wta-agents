"""TCL0.42x-132I-5M 전체 테이블 스캔"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.utils.erp_utils import create_erp_connection
conn = create_erp_connection()
cur = conn.cursor()

ITEM_CD = 'TCL0.42x-132I-5M'
result = {'item_cd': ITEM_CD, 'found': [], 'not_found': [], 'errors': []}

# ITEM_CD 컬럼 보유 테이블 전체 목록 (이전 스캔 결과)
item_cd_tables = [
    'BBA010T','BBA011T','BBA014T','BBA015T','BBA021T','BBA022T','BBA350T',
    'BBA600T','BBA650T','BBA660T','BBA661T','BBA700T','BBA700T_WIN',
    'BBA800T','BBA810T','CBA100T','CBA110T','CCB100T','CCB200T',
    'IBA010T','iba010t_2020','IBA100T','IBA200T','iba200t_202112',
    'IBA500T_WIN','IBA800T','IBA999T','IBC300T',
    'item_99','item_del','item_r','itemcd',
    'MAD111T','MBA200TV','MBA210T','MCA210T','MCA210TV','MCA260T_SW',
    'MDA100T','MDA200T','MGA100T','MGA200T','MGA400T','MGA500T',
    'MGA800T','MHA300T','MHA400T','MHA400TV','MHA450T','MHA510T',
    'MPA200T','MZA200T',
    'P_BBA010T','P_SCA110T','P_SCA200T','P_SCA300T',
    'P_WCA100T','P_WCA110T','P_WCA200T',
    'SCA500T','SCA600T','SFA400T','STOCK01',
    'TBL020T','TEB020T','temp_base','temp_pord','temp01',
    'tmp901','tmp902','top_code','TR01','tr02','tr02-1','TR3',
    'WBA010T','WBA010T_WIN','WBA010T_SW','WDB200T','WDB300T',
    'WGA100T','WIA200T','WZA010T'
]

safe_cd = ITEM_CD.replace("'", "''")
print(f'{ITEM_CD} 전체 테이블 스캔 시작 ({len(item_cd_tables)}개 테이블)')

for tbl in item_cd_tables:
    try:
        cur.execute(f"SELECT COUNT(*) FROM mirae.{tbl} WHERE ITEM_CD = '{safe_cd}'")
        cnt = cur.fetchone()[0]
        if cnt > 0:
            # 컬럼 정보 및 샘플 가져오기
            cur.execute(f"SELECT TOP 0 * FROM mirae.{tbl}")
            cols = [d[0] for d in cur.description]
            cur.execute(f"SELECT TOP 3 * FROM mirae.{tbl} WHERE ITEM_CD = '{safe_cd}'")
            rows = cur.fetchall()
            samples = [dict(zip(cols, [str(v) for v in r])) for r in rows]
            print(f'  [발견] {tbl}: {cnt}건')
            for s in samples[:2]:
                print(f'    {s}')
            result['found'].append({'table': tbl, 'count': cnt, 'columns': cols, 'samples': samples})
        else:
            result['not_found'].append(tbl)
    except Exception as e:
        result['errors'].append({'table': tbl, 'error': str(e)[:100]})

# BOM 관련 테이블 — CHILD_CD, COMP_CD, P_ITEM_CD, T_ITEM_CD 등 다른 컬럼명 가능성
print('\n=== BOM/T_ITEM_CD/P_ITEM_CD 컬럼 추가 검색 ===')
cur.execute("""
SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'mirae'
AND COLUMN_NAME IN ('T_ITEM_CD','P_ITEM_CD','CHILD_CD','COMP_CD','PARENT_CD','BOM_CD')
ORDER BY TABLE_NAME, COLUMN_NAME
""")
bom_cols = cur.fetchall()
bom_tables = {}
for r in bom_cols:
    bom_tables.setdefault(r[0], []).append(r[1])
print(f'BOM 관련 컬럼 보유 테이블: {dict(bom_tables)}')

for tbl, cols in bom_tables.items():
    for col in cols:
        try:
            cur.execute(f"SELECT COUNT(*) FROM mirae.{tbl} WHERE {col} = '{safe_cd}'")
            cnt = cur.fetchone()[0]
            if cnt > 0:
                cur.execute(f"SELECT TOP 3 * FROM mirae.{tbl} WHERE {col} = '{safe_cd}'")
                all_cols_q = f"SELECT TOP 0 * FROM mirae.{tbl}"
                cur2 = conn.cursor()
                cur2.execute(all_cols_q)
                all_cols = [d[0] for d in cur2.description]
                rows = cur.fetchall()
                samples = [dict(zip(all_cols, [str(v) for v in r])) for r in rows]
                print(f'  [발견] {tbl}.{col}: {cnt}건')
                for s in samples[:1]:
                    print(f'    {s}')
                result['found'].append({'table': tbl, 'column': col, 'count': cnt, 'samples': samples})
        except Exception as e:
            pass

# 생산실적 관련 테이블 (PPB*, WCA*, SFA*)
print('\n=== 생산실적/작업실적 관련 테이블 ===')
cur.execute("""
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'mirae'
AND (TABLE_NAME LIKE 'PPB%' OR TABLE_NAME LIKE 'WCA%'
     OR TABLE_NAME LIKE 'SFA%' OR TABLE_NAME LIKE 'WGA%'
     OR TABLE_NAME LIKE 'WIA%' OR TABLE_NAME LIKE 'WDB%')
ORDER BY TABLE_NAME
""")
prod_tables = [r[0] for r in cur.fetchall()]
print(f'생산관련 테이블: {prod_tables}')

for tbl in prod_tables:
    try:
        cur.execute(f"SELECT TOP 0 * FROM mirae.{tbl}")
        cols = [d[0] for d in cur.description]
        if 'ITEM_CD' in cols:
            cur.execute(f"SELECT COUNT(*) FROM mirae.{tbl} WHERE ITEM_CD = '{safe_cd}'")
            cnt = cur.fetchone()[0]
            if cnt > 0:
                print(f'  [발견] {tbl}: {cnt}건')
                result['found'].append({'table': tbl, 'count': cnt})
    except Exception as e:
        pass

conn.close()
result['summary'] = {
    'found_count': len(result['found']),
    'found_tables': [f['table'] for f in result['found']]
}
print(f'\n=== 요약 ===')
print(f'발견된 테이블: {result["summary"]["found_tables"]}')

with open('C:/MES/wta-agents/workspaces/db-manager/erp_item_scan_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print('저장완료')
