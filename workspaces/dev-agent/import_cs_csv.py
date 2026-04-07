"""CS 이력 CSV 7개 파일 → csagent.cs_history 테이블 임포트 (psycopg2).

국내 CSV 컬럼: *ID, 상태, 고객사, 장비 프로젝트 이름, 장비 출하일, C/S 접수자,
               관련 부서 선택, 관련 부서 담당자, C/S 제목, C/S 처리자, 등록일, 수정일
해외 CSV 컬럼: *ID, 상태, 장비 프로젝트 이름, 장비 프로젝트 No, C/S 접수자,
               C/S 제목, 이슈관리필요, C/S 처리자, C/S 처리완료일자, 등록일
"""

import csv
import os
import sys
from datetime import datetime, timezone

import psycopg2
from dotenv import load_dotenv

load_dotenv(r"C:\MES\backend\.env")

# .env에서 개별 변수로 연결 문자열 조합
_host = os.getenv("DB_HOST", "localhost")
_port = os.getenv("DB_PORT", "55432")
_user = os.getenv("DB_USER", "postgres")
_pw = os.getenv("DB_PASSWORD", "")
_db = os.getenv("DB_NAME", "postgres")
DATABASE_URL = f"host={_host} port={_port} dbname={_db} user={_user} password={_pw}"

UPLOAD_BASE = r"C:\MES\wta-agents\data\uploads"

DOMESTIC_FILES = [
    r"182541e2-7748-4b0c-ad8c-d37599224448\C_S 이력관리_20260406.csv",
    r"ba11b1a7-7507-4aec-aca7-9eb50ddd082b\C_S 이력관리_20260406 (1).csv",
    r"7b9f5fb0-55f4-4a5f-aa7f-70bcc36ad9eb\C_S 이력관리_20260406 (2).csv",
]

OVERSEAS_FILES = [
    r"5e16c6d6-ea28-4bf1-b0a0-eb418af37470\C_S 이력관리 해외_20260406 (1).csv",
    r"0f1cd3c2-9859-419c-af6c-5bb8b1e835b2\C_S 이력관리 해외_20260406 (2).csv",
    r"ecbbd45f-ff66-4e5f-9157-cc93b9702362\C_S 이력관리 해외_20260406.csv",
    r"54c90657-293b-440b-ad17-bace4d1838d9\C_S 이력관리 해외_20260406 (3).csv",
]


def parse_dt(s: str):
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def read_domestic_csv(filepath: str) -> list[dict]:
    rows = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) < 12 or not row[0].strip():
                continue
            rows.append({
                "csv_source_id": row[0].strip(),
                "status": row[1].strip() or "CS 접수",
                "title": row[8].strip() or row[3].strip(),
                "cs_receiver": row[5].strip() or None,
                "related_dept": row[6].strip() or None,
                "related_dept_contact": row[7].strip() or None,
                "cs_handler": row[9].strip() or None,
                "created_at": parse_dt(row[10]),
                "updated_at": parse_dt(row[11]),
                "region": "국내",
            })
    return rows


def read_overseas_csv(filepath: str) -> list[dict]:
    rows = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) < 10 or not row[0].strip():
                continue
            rows.append({
                "csv_source_id": row[0].strip(),
                "status": row[1].strip() or "CS 접수",
                "title": row[5].strip() or row[2].strip(),
                "cs_receiver": row[4].strip() or None,
                "issue_management_required": row[6].strip() or None,
                "cs_handler": row[7].strip() or None,
                "cs_completed_at": parse_dt(row[8]),
                "created_at": parse_dt(row[9]),
                "region": "해외",
            })
    return rows


def main():
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    # 1. CSV 파싱 + 중복 제거 (csv_source_id 기준)
    all_rows: dict[str, dict] = {}

    for rel in DOMESTIC_FILES:
        path = os.path.join(UPLOAD_BASE, rel)
        rows = read_domestic_csv(path)
        for r in rows:
            all_rows[r["csv_source_id"]] = r
        print(f"[국내] {os.path.basename(path)}: {len(rows)}건")

    for rel in OVERSEAS_FILES:
        path = os.path.join(UPLOAD_BASE, rel)
        rows = read_overseas_csv(path)
        for r in rows:
            all_rows[r["csv_source_id"]] = r
        print(f"[해외] {os.path.basename(path)}: {len(rows)}건")

    unique_rows = list(all_rows.values())
    print(f"\n중복 제거 후 총 {len(unique_rows)}건")

    # 2. DB 연결
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # csv_source_id 컬럼 존재 확인
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = 'csagent' AND table_name = 'cs_history'
              AND column_name = 'csv_source_id'
        """)
        if cur.fetchone()[0] == 0:
            cur.execute(
                "ALTER TABLE csagent.cs_history ADD COLUMN IF NOT EXISTS csv_source_id VARCHAR(50)"
            )
            conn.commit()
            print("csv_source_id 컬럼 추가됨")

        # 기존 csv_source_id 조회
        cur.execute("SELECT csv_source_id FROM csagent.cs_history WHERE csv_source_id IS NOT NULL")
        existing = {r[0] for r in cur.fetchall()}
        print(f"DB 기존 csv_source_id: {len(existing)}건")

        # 3. INSERT
        inserted = 0
        skipped = 0
        for row in unique_rows:
            sid = row["csv_source_id"]
            if sid in existing:
                skipped += 1
                continue

            cols = ["csv_source_id", "status", "title", "cs_receiver", "cs_handler",
                    "created_at", "updated_at"]
            vals = [sid, row["status"], row["title"], row.get("cs_receiver"),
                    row.get("cs_handler"), row.get("created_at"), row.get("updated_at")]

            if row.get("related_dept"):
                cols.append("related_dept")
                vals.append(row["related_dept"])
            if row.get("related_dept_contact"):
                cols.append("related_dept_contact")
                vals.append(row["related_dept_contact"])
            if row.get("issue_management_required"):
                cols.append("issue_management_required")
                vals.append(row["issue_management_required"])
            if row.get("cs_completed_at"):
                cols.append("cs_completed_at")
                vals.append(row["cs_completed_at"])

            placeholders = ", ".join(["%s"] * len(cols))
            col_str = ", ".join(cols)

            cur.execute(
                f"INSERT INTO csagent.cs_history ({col_str}) VALUES ({placeholders})",
                vals,
            )
            inserted += 1

        conn.commit()
        print(f"\n결과: {inserted}건 INSERT, {skipped}건 중복 스킵")

        # 4. 기존 영문 상태 → 한글 마이그레이션
        cur.execute("UPDATE csagent.cs_history SET status = 'CS 접수' WHERE status = 'pending'")
        r1 = cur.rowcount
        cur.execute("UPDATE csagent.cs_history SET status = 'CS 처리중' WHERE status = 'in_progress'")
        r2 = cur.rowcount
        cur.execute("UPDATE csagent.cs_history SET status = 'CS 종결' WHERE status IN ('completed', 'closed')")
        r3 = cur.rowcount
        conn.commit()
        print(f"\n상태 마이그레이션: pending→CS접수({r1}건), in_progress→CS처리중({r2}건), completed/closed→CS종결({r3}건)")

        # 5. 최종 상태별 건수
        cur.execute(
            "SELECT COALESCE(status, '(없음)') AS st, COUNT(*) AS cnt "
            "FROM csagent.cs_history GROUP BY status ORDER BY cnt DESC"
        )
        print("\n[상태별 건수]")
        for st, cnt in cur.fetchall():
            print(f"  {st:20s} : {cnt}건")

        cur.execute("SELECT COUNT(*) FROM csagent.cs_history")
        total = cur.fetchone()[0]
        print(f"\n총 CS 이력: {total}건")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
