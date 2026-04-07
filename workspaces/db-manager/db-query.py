"""
MES/ERP DB 조회 전용 스크립트 — db-manager 에이전트 전용
읽기 전용(SELECT) 쿼리만 허용. INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE 차단.

사용법:
  python db-query.py mes "SELECT * FROM api_project LIMIT 5"
  python db-query.py erp "SELECT TOP 5 * FROM mirae.dbo.some_table"
"""
import sys
import os
import re
import json

# ── DB 접속 정보 ──
MES_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "dbname": "postgres",
}
# .env에서 비밀번호 로드
def load_mes_password():
    env_path = "C:/MES/backend/.env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("DB_PASSWORD="):
                    return line.strip().split("=", 1)[1]
    return None

ERP_CONFIG = {
    "server": "192.168.1.201,1433",
    "database": "mirae",
    "user": "sa",
}
def load_erp_password():
    env_path = "C:/MES/backend/.env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("ERP_PASSWORD="):
                    return line.strip().split("=", 1)[1]
    return None

# ── 차단 패턴 (읽기 전용 강제) ──
BLOCKED_PATTERNS = [
    r'\bINSERT\b', r'\bUPDATE\b', r'\bDELETE\b',
    r'\bDROP\b', r'\bALTER\b', r'\bTRUNCATE\b',
    r'\bCREATE\b', r'\bGRANT\b', r'\bREVOKE\b',
    r'\bEXEC\b', r'\bEXECUTE\b',
]

def validate_query(sql):
    """SELECT만 허용"""
    sql_upper = sql.upper().strip()
    # SELECT 또는 WITH로 시작하는지 확인
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        return False, "SELECT 또는 WITH 문만 허용됩니다."
    # 차단 패턴 검사
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, sql_upper):
            return False, f"차단된 키워드 감지: {pattern}"
    return True, "OK"


def query_mes(sql):
    """MES PostgreSQL 조회"""
    import psycopg2
    password = load_mes_password()
    if not password:
        return {"error": "MES DB 비밀번호를 찾을 수 없습니다."}

    conn = psycopg2.connect(
        host=MES_CONFIG["host"],
        port=MES_CONFIG["port"],
        user=MES_CONFIG["user"],
        password=password,
        dbname=MES_CONFIG["dbname"],
    )
    try:
        # 읽기 전용 트랜잭션 강제
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()
        return {
            "columns": columns,
            "rows": [list(map(str, row)) for row in rows],
            "count": len(rows),
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


def query_erp(sql):
    """ERP SQL Server 조회 (읽기 전용)"""
    import pymssql
    password = load_erp_password()
    if not password:
        return {"error": "ERP DB 비밀번호를 찾을 수 없습니다."}

    conn = pymssql.connect(
        server=ERP_CONFIG["server"],
        user=ERP_CONFIG["user"],
        password=password,
        database=ERP_CONFIG["database"],
        charset="utf8",
    )
    try:
        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()
        return {
            "columns": columns,
            "rows": [list(map(str, row)) for row in rows],
            "count": len(rows),
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


def format_result(result):
    """결과를 읽기 쉬운 텍스트로 출력"""
    if "error" in result:
        print(f"[오류] {result['error']}")
        return

    columns = result["columns"]
    rows = result["rows"]
    count = result["count"]

    if not rows:
        print("(결과 없음)")
        return

    # 헤더
    print(" | ".join(columns))
    print("-" * min(len(" | ".join(columns)) + 20, 120))
    # 데이터 (최대 100행)
    for row in rows[:100]:
        print(" | ".join(row))

    if count > 100:
        print(f"\n... 외 {count - 100}건 (총 {count}건)")
    else:
        print(f"\n총 {count}건")


def main():
    if len(sys.argv) < 3:
        print("사용법: python db-query.py <mes|erp> \"SQL 쿼리\"")
        print("예: python db-query.py mes \"SELECT COUNT(*) FROM api_project\"")
        sys.exit(1)

    db_type = sys.argv[1].lower()

    # SQL을 stdin으로 읽기 지원 (Windows argv 파싱 문제 우회)
    if sys.argv[2] == "-":
        import io
        sql = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8").read().strip()
    else:
        sql = " ".join(sys.argv[2:])

    # 쿼리 검증
    valid, msg = validate_query(sql)
    if not valid:
        print(f"[차단] {msg}")
        print("읽기 전용: SELECT 쿼리만 허용됩니다.")
        sys.exit(1)

    # 실행
    if db_type == "mes":
        result = query_mes(sql)
    elif db_type == "erp":
        result = query_erp(sql)
    else:
        print(f"[오류] 지원하지 않는 DB: {db_type} (mes 또는 erp)")
        sys.exit(1)

    format_result(result)


if __name__ == "__main__":
    main()
