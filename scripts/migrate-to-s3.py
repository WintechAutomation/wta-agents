"""migrate-to-s3.py — Supabase Storage → AWS S3 마이그레이션.

방식: MES 서버에서 Supabase 다운로드 → SSH pipe → EC2에서 S3 업로드

실행:
  py migrate-to-s3.py --dry-run       # 대상 파일 목록만 출력
  py migrate-to-s3.py                  # S3 업로드 + DB URL 업데이트
  py migrate-to-s3.py --db-only        # DB URL만 업데이트 (S3 업로드 건너뜀)
  py migrate-to-s3.py --skip-db        # S3 업로드만 (DB 업데이트 안 함)
"""

import argparse
import logging
import subprocess
import sys

import psycopg2
import requests

# ── 설정 ──
SUPABASE_URL = "http://localhost:8000"
SUPABASE_STORAGE_BASE = f"{SUPABASE_URL}/storage/v1/object/public/vector"

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password",
    "dbname": "postgres",
}

S3_BUCKET = "wta-manuals"
S3_REGION = "ap-northeast-2"
S3_PUBLIC_URL = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com"
SSH_HOST = "my-ec2"

logging.basicConfig(
    level=logging.INFO,
    format="[migrate-s3] %(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("migrate-s3")


def _content_type(path: str) -> str:
    """파일 확장자 기반 Content-Type."""
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(ext, "application/octet-stream")


def list_unique_paths(conn) -> list[str]:
    """DB에서 고유 파일 경로 추출 (vector 버킷 기준 상대 경로)."""
    cur = conn.cursor()
    paths = set()

    for table in ("manual.documents", "manual.wta_documents"):
        cur.execute(f"""
            SELECT DISTINCT SUBSTRING(pdf_url FROM 'object/public/vector/(.+)')
            FROM {table}
            WHERE pdf_url IS NOT NULL AND pdf_url != ''
        """)
        for row in cur.fetchall():
            if row[0]:
                paths.add(row[0])

    cur.close()
    return sorted(paths)


def check_s3_exists(path: str) -> bool:
    """SSH 경유로 S3 파일 존재 확인."""
    result = subprocess.run(
        ["ssh", SSH_HOST, f"aws s3api head-object --bucket {S3_BUCKET} --key '{path}' 2>/dev/null && echo EXISTS"],
        capture_output=True, text=True, timeout=15,
    )
    return "EXISTS" in result.stdout


def upload_via_pipe(path: str) -> bool:
    """Supabase 다운로드 → SSH pipe → S3 업로드."""
    url = f"{SUPABASE_STORAGE_BASE}/{path}"
    try:
        resp = requests.get(url, timeout=120)
        if resp.status_code != 200:
            log.warning("다운로드 실패 (%d): %s", resp.status_code, path)
            return False
    except Exception as e:
        log.warning("다운로드 오류: %s — %s", path, e)
        return False

    ct = _content_type(path)
    s3_uri = f"s3://{S3_BUCKET}/{path}"
    try:
        proc = subprocess.run(
            ["ssh", SSH_HOST, f"aws s3 cp - '{s3_uri}' --content-type '{ct}'"],
            input=resp.content, capture_output=True, timeout=120,
        )
        if proc.returncode == 0:
            return True
        log.error("S3 업로드 실패: %s — %s", path, proc.stderr.decode()[:200])
        return False
    except Exception as e:
        log.error("SSH/S3 오류: %s — %s", path, e)
        return False


def update_db_urls(conn):
    """DB의 pdf_url을 S3 URL로 일괄 치환."""
    old_base = f"{SUPABASE_URL}/storage/v1/object/public/vector/"
    new_base = f"{S3_PUBLIC_URL}/"
    cur = conn.cursor()
    total = 0

    for table in ("manual.documents", "manual.wta_documents"):
        cur.execute(f"""
            UPDATE {table}
            SET pdf_url = REPLACE(pdf_url, %s, %s)
            WHERE pdf_url LIKE %s
        """, (old_base, new_base, f"{old_base}%"))
        count = cur.rowcount
        total += count
        log.info("%s 업데이트: %d행", table, count)

    conn.commit()
    cur.close()
    return total


def main():
    parser = argparse.ArgumentParser(description="Supabase → S3 PDF 마이그레이션")
    parser.add_argument("--dry-run", action="store_true", help="대상 목록만 출력")
    parser.add_argument("--db-only", action="store_true", help="DB URL만 업데이트")
    parser.add_argument("--skip-db", action="store_true", help="S3 업로드만")
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONFIG)
    paths = list_unique_paths(conn)
    log.info("이전 대상: %d개 파일", len(paths))

    if args.dry_run:
        for p in paths:
            print(f"  {p}")
        log.info("총 %d개 (dry-run)", len(paths))
        conn.close()
        return

    # S3 업로드
    if not args.db_only:
        uploaded = 0
        skipped = 0
        failed = 0

        for i, path in enumerate(paths):
            if check_s3_exists(path):
                skipped += 1
            elif upload_via_pipe(path):
                uploaded += 1
            else:
                failed += 1

            if (i + 1) % 50 == 0 or (i + 1) == len(paths):
                log.info("진행: %d/%d (업로드=%d, 건너뜀=%d, 실패=%d)",
                         i + 1, len(paths), uploaded, skipped, failed)

        log.info("S3 업로드 완료: 업로드=%d, 건너뜀=%d, 실패=%d", uploaded, skipped, failed)

    # DB URL 업데이트
    if not args.skip_db:
        total = update_db_urls(conn)
        log.info("DB URL 업데이트 완료: 총 %d행", total)

    conn.close()
    log.info("마이그레이션 완료")


if __name__ == "__main__":
    main()
