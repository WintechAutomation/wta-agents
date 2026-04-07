"""run-parts-embed-all.py — 부품 매뉴얼 전체 카테고리 순차 임베딩 (Qwen3 사용).

batch-parse.py를 각 카테고리에 대해 순차 실행.
이미 처리된 파일은 DB hash check로 자동 스킵.
Qwen3-Embedding-8B(4096→2000차원) 사용.

실행:
  py scripts/run-parts-embed-all.py
"""

import subprocess
import sys
import os
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SOURCE_DIR = str(BASE_DIR / "data" / "manuals-ready")
SCRIPT = str(BASE_DIR / "scripts" / "batch-parse.py")
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

CATEGORIES = [
    "1_robot",
    "2_sensor",
    "3_hmi",
    "4_servo",
    "5_inverter",
    "6_plc",
    "7_pneumatic",
    "8_etc",
]

def main():
    log_path = LOG_DIR / "parts-embed-all.log"
    print(f"[parts-embed-all] Processing {len(CATEGORIES)} categories via Qwen3")
    print(f"[parts-embed-all] Log: {log_path}")

    with open(log_path, "a", encoding="utf-8") as log_file:
        for i, cat in enumerate(CATEGORIES, 1):
            cat_dir = os.path.join(SOURCE_DIR, cat)
            if not os.path.isdir(cat_dir):
                msg = f"[{i}/{len(CATEGORIES)}] SKIP {cat} (directory not found)"
                print(msg); log_file.write(msg + "\n")
                continue

            files = [f for f in os.listdir(cat_dir) if f.lower().endswith((".pdf", ".docx"))]
            msg = f"[{i}/{len(CATEGORIES)}] Starting: {cat} ({len(files)} files)"
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
                    "--table", "documents",
                    "--embed-url", "http://182.224.6.147:11434/api/embed",
                    "--embed-batch", "128",
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
            summary = f"[{i}/{len(CATEGORIES)}] {status} {cat} ({elapsed:.0f}s)"
            print(summary)
            log_file.write(f"{summary}\n{stdout_tail}")
            if stderr_tail:
                log_file.write(f"\nSTDERR: {stderr_tail}")
            log_file.flush()

    print(f"[parts-embed-all] All done.")

if __name__ == "__main__":
    main()
