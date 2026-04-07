"""
MES DB DDL 실행 스크립트 — db-manager 에이전트 전용
CREATE TABLE, CREATE INDEX, CREATE FUNCTION, CREATE TRIGGER 등 스키마 변경용.
부서장 승인이 완료된 DDL만 실행할 것.

사용법:
  python db-ddl.py <sql_file>
  예: python db-ddl.py create_core_tech_documents.sql
"""
import sys
import os
import psycopg2


def load_mes_password():
    env_path = "C:/MES/backend/.env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("DB_PASSWORD="):
                    return line.strip().split("=", 1)[1]
    return None


def execute_ddl(sql: str):
    password = load_mes_password()
    if not password:
        print("[오류] MES DB 비밀번호를 찾을 수 없습니다.")
        sys.exit(1)

    conn = psycopg2.connect(
        host="localhost",
        port=55432,
        user="postgres",
        password=password,
        dbname="postgres",
    )
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute(sql)
        print("[완료] DDL 실행 성공")
    except Exception as e:
        print(f"[오류] {e}")
        sys.exit(1)
    finally:
        conn.close()


def main():
    if len(sys.argv) < 2:
        print("사용법: python db-ddl.py <sql_file>")
        sys.exit(1)

    sql_file = sys.argv[1]
    if not os.path.exists(sql_file):
        print(f"[오류] 파일 없음: {sql_file}")
        sys.exit(1)

    with open(sql_file, "r", encoding="utf-8") as f:
        sql = f.read()

    execute_ddl(sql)


if __name__ == "__main__":
    main()
