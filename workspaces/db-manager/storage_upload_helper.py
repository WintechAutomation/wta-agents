"""
Supabase Storage 업로드 헬퍼 — manual_documents_v2 파이프라인 전용
docs-agent의 manuals_v2_parse_docling.py에서 import 해서 사용.

사용 예:
    from storage_upload_helper import upload_manual_image, build_object_path
    path = build_object_path(category="1_robot", file_id="1_robot_abc123", page=12, figure_id="fig_012_01")
    url = upload_manual_image(local_png_path, path, thumb=False)

설계 원칙:
- service key는 C:/MES/backend/.env의 SERVICE_ROLE_KEY만 참조 (평문 인자/출력 금지)
- 버킷: vector (기존 재사용, public read)
- prefix: manual_images/{category}/{file_id}/page_{N:04d}_{figure_id}.png
- 썸네일: {...}_thumb.png (256px)
"""
from __future__ import annotations
import os
import io
import json
import mimetypes
import urllib.request
import urllib.error
from typing import Optional

BACKEND_ENV_PATH = "C:/MES/backend/.env"
SUPABASE_URL = "http://localhost:8000"
BUCKET = "vector"
PREFIX = "manual_images"

_svc_key_cache: Optional[str] = None


def _load_service_key() -> str:
    """backend .env에서 SERVICE_ROLE_KEY 로드 (평문 반환 금지 목적상 모듈 내부만 사용)."""
    global _svc_key_cache
    if _svc_key_cache:
        return _svc_key_cache
    if not os.path.isfile(BACKEND_ENV_PATH):
        raise RuntimeError(f"backend .env not found: {BACKEND_ENV_PATH}")
    with open(BACKEND_ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("SERVICE_ROLE_KEY="):
                _svc_key_cache = line.split("=", 1)[1].strip()
                return _svc_key_cache
    raise RuntimeError("SERVICE_ROLE_KEY not found in backend .env")


def build_object_path(category: str, file_id: str, page: int, figure_id: str, thumb: bool = False) -> str:
    """
    Storage object path 생성.
    결과 예: manual_images/1_robot/1_robot_a3f8d21b9e04/page_0012_fig_012_01.png
    """
    suffix = "_thumb" if thumb else ""
    return f"{PREFIX}/{category}/{file_id}/page_{page:04d}_{figure_id}{suffix}.png"


def upload_manual_image(local_path: str, object_path: str, upsert: bool = True, content_type: str = "image/png") -> str:
    """
    로컬 PNG를 vector 버킷에 업로드하고 public URL 반환.

    Args:
        local_path: 업로드할 파일 경로
        object_path: Storage 내 경로 (build_object_path 결과 권장)
        upsert: 기존 파일 덮어쓰기 허용 여부
        content_type: MIME 타입 (기본 image/png)

    Returns:
        public URL 문자열
    """
    if not os.path.isfile(local_path):
        raise FileNotFoundError(local_path)

    svc_key = _load_service_key()
    with open(local_path, "rb") as f:
        data = f.read()

    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{object_path}"
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {svc_key}",
            "apikey": svc_key,
            "Content-Type": content_type,
            "x-upsert": "true" if upsert else "false",
            "Cache-Control": "3600",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            _ = resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"upload failed {e.code}: {body}") from e

    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{object_path}"


def check_bucket_public() -> bool:
    """vector 버킷이 public 상태인지 재확인."""
    svc_key = _load_service_key()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/storage/v1/bucket/{BUCKET}",
        headers={"Authorization": f"Bearer {svc_key}", "apikey": svc_key},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        meta = json.loads(r.read())
    return bool(meta.get("public"))


if __name__ == "__main__":
    # self-check
    print(f"bucket={BUCKET} public={check_bucket_public()}")
    print(f"sample path: {build_object_path('1_robot', '1_robot_a3f8d21b9e04', 12, 'fig_012_01')}")
    print(f"sample thumb: {build_object_path('1_robot', '1_robot_a3f8d21b9e04', 12, 'fig_012_01', thumb=True)}")
