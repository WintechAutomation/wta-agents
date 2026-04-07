"""run-wta-docling-all.py — WTA 매뉴얼 전체 docling 파싱+임베딩 실행.

batch-parse-docling.py를 각 카테고리에 대해 순차 실행.
이미 처리된 파일은 DB hash check로 자동 스킵.

실행:
  py scripts/run-wta-docling-all.py
  py scripts/run-wta-docling-all.py --start-from Press
"""

import subprocess
import sys
import os
import argparse
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SOURCE_DIR = str(BASE_DIR / "data" / "wta-manuals-final")
SCRIPT = str(BASE_DIR / "scripts" / "batch-parse-docling.py")
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-from", help="특정 카테고리부터 시작")
    args = parser.parse_args()

    # wta-manuals-final 하위 폴더 자동 탐색
    cats = sorted(d for d in os.listdir(SOURCE_DIR)
                  if os.path.isdir(os.path.join(SOURCE_DIR, d)))

    if args.start_from:
        if args.start_from not in cats:
            print(f"Unknown category: {args.start_from}")
            sys.exit(1)
        idx = cats.index(args.start_from)
        cats = cats[idx:]
        print(f"Starting from: {args.start_from} ({len(cats)} categories remaining)")

    total_cats = len(cats)
    log_path = LOG_DIR / "wta-docling-all.log"

    print(f"[wta-docling-all] Processing {total_cats} categories")
    print(f"[wta-docling-all] Log: {log_path}")

    with open(log_path, "a", encoding="utf-8") as log_file:
        for i, cat in enumerate(cats, 1):
            cat_dir = os.path.join(SOURCE_DIR, cat)
            files = [f for f in os.listdir(cat_dir) if f.lower().endswith((".pdf", ".docx"))]
            msg = f"[{i}/{total_cats}] Starting: {cat} ({len(files)} files)"
            print(msg)
            log_file.write(f"\n{'='*60}\n{msg}\n")
            log_file.flush()

            start = time.time()
            result = subprocess.run(
                [
                    sys.executable,
                    SCRIPT,
                    "--source-dir", SOURCE_DIR,
                    "--category", cat,
                    "--table", "manual.wta_documents",
                    "--embed-batch", "64",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(BASE_DIR),
            )
            elapsed = time.time() - start

            stdout_tail = result.stdout[-3000:] if result.stdout else ""
            stderr_tail = result.stderr[-500:] if result.stderr else ""

            status = "OK" if result.returncode == 0 else f"ERROR(rc={result.returncode})"
            summary = f"[{i}/{total_cats}] {status} {cat} ({elapsed:.0f}s)"
            print(summary)
            log_file.write(f"{summary}\n")
            log_file.write(stdout_tail)
            if stderr_tail:
                log_file.write(f"\nSTDERR: {stderr_tail}\n")
            log_file.flush()

    print(f"[wta-docling-all] All done. See {log_path}")

if __name__ == "__main__":
    main()
