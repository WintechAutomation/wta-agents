"""check-embed-progress.py — manual.documents 임베딩 진행률 실시간 확인.

사용법:
  py scripts/check-embed-progress.py          # 전체 현황
  py scripts/check-embed-progress.py --watch  # 30초마다 갱신
"""
from __future__ import annotations
import argparse
import time
from datetime import datetime, timezone, timedelta

import psycopg2

DB_CONFIG = {
    "host": "localhost", "port": 55432, "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password", "dbname": "postgres",
}
KST = timezone(timedelta(hours=9))
TOTAL_PDF = 892  # manuals-ready 전체 PDF 수


def now_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def fetch_stats(conn) -> dict:
    with conn.cursor() as cur:
        # 전체 레코드 수
        cur.execute("SELECT COUNT(*) FROM manual.documents")
        total_chunks = cur.fetchone()[0]

        # 카테고리별 고유 source_file 수
        cur.execute("""
            SELECT
                COALESCE(NULLIF(category, ''), 'unknown') AS category,
                COUNT(DISTINCT source_file) AS files,
                COUNT(*) AS chunks
            FROM manual.documents
            GROUP BY 1
            ORDER BY 1
        """)
        rows = cur.fetchall()

        # 카테고리별 고유 파일 수 합계
        total_files = sum(r[1] for r in rows)

    return {"total_chunks": total_chunks, "total_files": total_files, "by_cat": rows}


def print_stats(stats: dict) -> None:
    total_chunks = stats["total_chunks"]
    total_files = stats["total_files"]
    by_cat = stats["by_cat"]

    pct = round(total_files / TOTAL_PDF * 100, 1) if TOTAL_PDF else 0

    print(f"\n[임베딩 진행률]  {now_kst()}")
    print(f"  임베딩 완료 파일: {total_files} / {TOTAL_PDF} ({pct}%)")
    print(f"  총 청크 (벡터):  {total_chunks:,}개")
    print()
    print(f"  {'카테고리':<16} {'파일수':>6} {'청크수':>8}")
    print("  " + "-" * 34)
    for cat, files, chunks in by_cat:
        print(f"  {cat:<16} {files:>6} {chunks:>8,}")
    print("  " + "-" * 34)
    print(f"  {'합계':<16} {total_files:>6} {total_chunks:>8,}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="30초마다 자동 갱신")
    parser.add_argument("--interval", type=int, default=30, help="갱신 간격(초), 기본 30")
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        if args.watch:
            print(f"Watch 모드 — {args.interval}초마다 갱신. Ctrl+C로 종료.")
            while True:
                stats = fetch_stats(conn)
                print_stats(stats)
                time.sleep(args.interval)
        else:
            stats = fetch_stats(conn)
            print_stats(stats)
    except KeyboardInterrupt:
        print("\n종료.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
