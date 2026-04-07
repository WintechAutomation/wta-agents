"""tech-reupload.py — 복호화된 기술문서를 Supabase Storage 원래 위치에 덮어쓰기 업로드.

data/tech/{project_id}/{category}/{filename} → Supabase Storage technical/{file_path}

실행:
  python tech-reupload.py            # 전체 업로드
  python tech-reupload.py --dry-run  # 경로 매핑만 확인 (업로드 X)
"""

import argparse
import json
import logging
import mimetypes
import os
import sys

import psycopg2
import requests

# ── 설정 ──
BASE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
MANIFEST_FILE = os.path.join(BASE_DIR, "data", "tech", "file-manifest.json")
BUCKET = "technical"

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password",
    "dbname": "postgres",
}

# .env 파싱 (SUPABASE_URL, SERVICE_ROLE_KEY)
_env_path = os.path.normpath(os.path.join(BASE_DIR, "..", "backend", ".env"))
SUPABASE_URL = ""
SERVICE_ROLE_KEY = ""
if os.path.isfile(_env_path):
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line.startswith("#") or "=" not in _line:
                continue
            key, _, val = _line.partition("=")
            key, val = key.strip(), val.strip()
            if key == "SUPABASE_URL":
                SUPABASE_URL = val
            elif key == "SUPABASE_PUBLIC_URL":
                if not SUPABASE_URL:
                    SUPABASE_URL = val
            elif key == "SERVICE_ROLE_KEY":
                SERVICE_ROLE_KEY = val

# MIME 타입 확장
MIME_OVERRIDES = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xls": "application/vnd.ms-excel",
    ".doc": "application/msword",
    ".ppt": "application/vnd.ms-powerpoint",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".zip": "application/zip",
    ".dwg": "application/acad",
    ".csv": "text/csv",
    ".txt": "text/plain",
}

logging.basicConfig(
    level=logging.INFO,
    format="[tech-reupload] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("tech-reupload")


def get_content_type(filename: str) -> str:
    """파일 확장자에서 Content-Type 결정."""
    ext = os.path.splitext(filename)[1].lower()
    if ext in MIME_OVERRIDES:
        return MIME_OVERRIDES[ext]
    ct, _ = mimetypes.guess_type(filename)
    return ct or "application/octet-stream"


def load_manifest() -> list[dict]:
    """manifest에서 성공 파일(error 없는 것) 목록 로드."""
    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    files = []
    for entry in data.get("files", []):
        if "error" in entry:
            continue
        if not entry.get("saved_path"):
            continue
        files.append(entry)
    return files


def fetch_storage_paths(conn, file_ids: list[str]) -> dict[str, str]:
    """DB에서 file UUID → file_path(Storage 경로) 매핑 조회."""
    if not file_ids:
        return {}

    with conn.cursor() as cur:
        # IN절로 일괄 조회
        placeholders = ",".join(["%s"] * len(file_ids))
        cur.execute(
            f"SELECT id::text, file_path FROM project_technical_files WHERE id::text IN ({placeholders})",
            file_ids,
        )
        return {row[0]: row[1] for row in cur.fetchall()}


def upload_to_storage(local_path: str, storage_path: str) -> bool:
    """Supabase Storage에 파일 업로드 (upsert)."""
    content_type = get_content_type(os.path.basename(local_path))
    headers = {
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "apikey": SERVICE_ROLE_KEY,
        "Content-Type": content_type,
        "x-upsert": "true",
    }

    with open(local_path, "rb") as f:
        resp = requests.post(
            f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}",
            headers=headers,
            data=f,
            timeout=120,
        )

    if resp.status_code in (200, 201):
        return True
    else:
        log.error(f"  업로드 실패 ({resp.status_code}): {resp.text[:200]}")
        return False


def main():
    parser = argparse.ArgumentParser(description="기술문서 Supabase Storage 덮어쓰기 업로드")
    parser.add_argument("--dry-run", action="store_true", help="경로 매핑만 확인 (업로드 X)")
    args = parser.parse_args()

    # 사전 검증
    if not SUPABASE_URL:
        log.error("SUPABASE_URL을 .env에서 읽을 수 없음")
        sys.exit(1)
    if not SERVICE_ROLE_KEY:
        log.error("SERVICE_ROLE_KEY를 .env에서 읽을 수 없음")
        sys.exit(1)

    log.info(f"모드: {'dry-run' if args.dry_run else '업로드'}")
    log.info(f"Supabase URL: {SUPABASE_URL}")

    # manifest 로드
    files = load_manifest()
    log.info(f"대상 파일: {len(files)}개")

    if not files:
        log.info("업로드할 파일 없음 — 종료")
        return

    # DB에서 Storage 경로 조회
    file_ids = [f["id"] for f in files]
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        storage_paths = fetch_storage_paths(conn, file_ids)
    finally:
        conn.close()

    log.info(f"DB 경로 조회: {len(storage_paths)}개 매칭")

    # 업로드
    success, fail, skip = 0, 0, 0

    for idx, entry in enumerate(files, 1):
        file_id = entry["id"]
        local_path = entry["saved_path"]
        filename = entry.get("original_filename", os.path.basename(local_path))

        # Storage 경로 확인
        storage_path = storage_paths.get(file_id)
        if not storage_path:
            log.warning(f"[{idx}/{len(files)}] {filename} — DB에 file_path 없음 (id={file_id})")
            skip += 1
            continue

        # 로컬 파일 존재 확인
        if not os.path.isfile(local_path):
            log.warning(f"[{idx}/{len(files)}] {filename} — 로컬 파일 없음: {local_path}")
            skip += 1
            continue

        file_size = os.path.getsize(local_path)
        log.info(f"[{idx}/{len(files)}] {filename} ({file_size:,}B) → {storage_path}")

        if args.dry_run:
            success += 1
            continue

        if upload_to_storage(local_path, storage_path):
            success += 1
        else:
            fail += 1

    log.info("=" * 50)
    log.info(f"완료: 성공 {success}, 실패 {fail}, 스킵 {skip}")


if __name__ == "__main__":
    main()
