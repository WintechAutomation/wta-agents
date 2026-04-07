"""149개 미처리 .docx 파일 파싱 전용 (임베딩 없이).
run-wta-embed-all.py와 동일하지만 --no-embed 옵션 추가."""

import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path("C:/MES/wta-agents")
SOURCE_DIR = str(BASE_DIR / "data" / "wta-manuals-final")
SCRIPT = str(BASE_DIR / "scripts" / "batch-parse.py")

CATEGORIES = [
    "CBN", "CVD", "Double_Side_Grinder", "Fujisanki_Grinding_Handler",
    "Honing", "Honing_Inspection", "Inspection", "Labeling",
    "Laser_Marking", "Macoho", "Mask_Auto", "PVD",
    "Packaging", "Press", "Repalleting", "Single_Side_Grinder",
    "Sintering_Sorter", "WBM_WVR_Daesung_Honing",
]

total = len(CATEGORIES)
for i, cat in enumerate(CATEGORIES, 1):
    print(f"\n[{i}/{total}] {cat}", flush=True)
    start = time.time()
    result = subprocess.run(
        [sys.executable, "-u", SCRIPT,
         "--source-dir", SOURCE_DIR,
         "--category", cat,
         "--table", "wta_documents",
         "--no-embed"],
        capture_output=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(BASE_DIR),
    )
    elapsed = time.time() - start
    status = "OK" if result.returncode == 0 else f"ERROR(rc={result.returncode})"
    print(f"[{i}/{total}] {status} {cat} ({elapsed:.0f}s)", flush=True)

print("\n[DONE] All categories parsed.", flush=True)
