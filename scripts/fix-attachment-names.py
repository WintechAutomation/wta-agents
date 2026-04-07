"""fix-attachment-names.py — 이중 인코딩된 한글 파일명 복구.

UTF-8 바이트가 Latin-1로 잘못 해석되어 다시 UTF-8로 저장된 파일명을 복구.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ATTACHMENTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "cs_attachments",
)

fixed = 0
skipped = 0
errors = 0

for folder in sorted(os.listdir(ATTACHMENTS_DIR)):
    folder_path = os.path.join(ATTACHMENTS_DIR, folder)
    if not os.path.isdir(folder_path):
        continue

    for filename in os.listdir(folder_path):
        try:
            # Latin-1 encode -> UTF-8 decode (double encoding fix)
            corrected = filename.encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            # Already correct or different encoding
            skipped += 1
            continue

        if corrected == filename:
            skipped += 1
            continue

        old_path = os.path.join(folder_path, filename)
        new_path = os.path.join(folder_path, corrected)

        if os.path.exists(new_path):
            print(f"  [skip] already exists: {folder}/{corrected}")
            skipped += 1
            continue

        try:
            os.rename(old_path, new_path)
            print(f"  [fix] {folder}/{filename} -> {corrected}")
            fixed += 1
        except OSError as e:
            print(f"  [err] {folder}/{filename}: {e}")
            errors += 1

print(f"\nDone. fixed={fixed}, skipped={skipped}, errors={errors}")
