"""
CS PDF 캐시 + 세션 참조 유틸리티

사용법:
  from cs_pdf_cache import get_or_extract_pdf_page, lookup_session_attachment

  url = get_or_extract_pdf_page(pdf_path, page_num)  # 캐시 or 새 추출 후 업로드
  prev = lookup_session_attachment(keyword)           # 이전 세션에서 관련 링크 검색
"""

import hashlib
import json
import os
import requests
import fitz  # PyMuPDF

CACHE_DIR = os.path.join(os.path.dirname(__file__), "reports", "cs-cache")
SESSIONS_PATH = os.path.join(os.path.dirname(__file__), "reports", "cs-sessions.jsonl")
DASHBOARD_UPLOAD_URL = "http://localhost:5555/api/upload"
CLOUDFLARE_BASE = "https://agent.mes-wta.com"

os.makedirs(CACHE_DIR, exist_ok=True)


def _file_hash(pdf_path: str) -> str:
    """PDF 파일 경로에서 짧은 해시 생성 (8자)"""
    return hashlib.md5(pdf_path.encode()).hexdigest()[:8]


def _cache_path(pdf_path: str, start: int, end: int) -> str:
    """캐시 파일 경로: cs-cache/{파일명}_{hash}_p{start}-{end}.pdf"""
    h = _file_hash(pdf_path)
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    return os.path.join(CACHE_DIR, f"{base}_{h}_p{start}-{end}.pdf")


def _cache_meta_path(pdf_path: str, start: int, end: int) -> str:
    """캐시 메타 파일 경로 (업로드 URL 저장): .json"""
    return _cache_path(pdf_path, start, end).replace(".pdf", ".json")


def _load_cache_meta(pdf_path: str, start: int, end: int) -> dict | None:
    meta_path = _cache_meta_path(pdf_path, start, end)
    if os.path.exists(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _save_cache_meta(pdf_path: str, start: int, end: int, meta: dict) -> None:
    meta_path = _cache_meta_path(pdf_path, start, end)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)


def _extract_pages(pdf_path: str, start: int, end: int) -> str:
    """PDF에서 start~end 페이지(1-indexed) 추출 → 캐시 파일 저장 후 경로 반환"""
    out_path = _cache_path(pdf_path, start, end)
    doc = fitz.open(pdf_path)
    total = doc.page_count
    from_page = max(0, start - 1)
    to_page = min(total - 1, end - 1)
    new_doc = fitz.open()
    new_doc.insert_pdf(doc, from_page=from_page, to_page=to_page)
    new_doc.save(out_path)
    new_doc.close()
    doc.close()
    return out_path


def _upload_file(file_path: str) -> str:
    """대시보드 /api/upload에 파일 업로드 → Cloudflare URL 반환"""
    with open(file_path, "rb") as f:
        resp = requests.post(
            DASHBOARD_UPLOAD_URL,
            files={"file": (os.path.basename(file_path), f, "application/pdf")},
            timeout=30,
        )
    resp.raise_for_status()
    data = resp.json()
    stored_name = data["file"]["stored_name"]
    return f"{CLOUDFLARE_BASE}/api/files/{stored_name}"


def get_or_extract_pdf_page(pdf_path: str, page: int, context: int = 1) -> dict:
    """
    page 기준 앞뒤 context 페이지 포함하여 추출 (기본: 앞뒤 1페이지).
    캐시에 있으면 기존 URL 반환, 없으면 추출 + 업로드 후 캐시 저장.

    반환: {"url": str, "cached": bool, "local_path": str, "pages": str}
    예: page=264, context=1 → 263~265페이지 추출
    """
    start = max(1, page - context)
    end = page + context  # _extract_pages에서 총 페이지 초과 처리

    meta = _load_cache_meta(pdf_path, start, end)
    if meta and meta.get("url"):
        return {
            "url": meta["url"],
            "cached": True,
            "local_path": meta.get("local_path", ""),
            "pages": f"{start}-{end}",
        }

    # 새 추출
    local_path = _extract_pages(pdf_path, start, end)
    url = _upload_file(local_path)

    meta = {"url": url, "local_path": local_path, "pdf_path": pdf_path, "start": start, "end": end}
    _save_cache_meta(pdf_path, start, end, meta)

    return {"url": url, "cached": False, "local_path": local_path, "pages": f"{start}-{end}"}


def lookup_session_attachment(keyword: str) -> dict | None:
    """
    cs-sessions.jsonl에서 keyword가 포함된 최근 세션 중
    attachments가 있는 항목 반환.

    반환: {"url": str, "description": str, "request_id": str} or None
    """
    if not os.path.exists(SESSIONS_PATH):
        return None

    keyword_lower = keyword.lower()
    matches = []

    with open(SESSIONS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                session = json.loads(line)
            except json.JSONDecodeError:
                continue

            query = session.get("query", "").lower()
            attachments = session.get("attachments")
            if keyword_lower in query and attachments:
                matches.append(session)

    if not matches:
        return None

    # 가장 최근 항목
    latest = matches[-1]
    att = latest["attachments"][0]
    return {
        "url": att.get("download_url", ""),
        "description": att.get("description", ""),
        "request_id": latest.get("request_id", ""),
    }
