"""cs_rag_agent.py — CS RAG 서비스 레이어 (Pydantic AI 타입/DI 시스템 기반).

cs-agent(Claude 세션)가 직접 Tool 함수를 호출하고, 결과를 분석하여 답변을 생성한다.
별도 LLM 호출 없음 — cs-agent 자신이 LLM 역할.

직접 호출 가능한 공개 함수:
  run_search()          — CS이력 + 매뉴얼 통합 벡터 검색 → CombinedSearchResult
  cs_history_detail()   — 특정 CS 이력 상세 조회 → dict
  page_image()          — 매뉴얼 페이지 이미지 URL 조회 → dict
  extract_pdf_excerpt() — 매뉴얼 PDF 관련 페이지 추출 + Storage 업로드 → str|None

사용법 (cs-agent에서):
  from cs_rag_agent import run_search, cs_history_detail, page_image, extract_pdf_excerpt
  result = asyncio.run(run_search("CSD5 배선"))
  detail = cs_history_detail("1043")
  img    = page_image("Samsung_CSD5_UserManual_KO.pdf", 31)
  excerpt_url = extract_pdf_excerpt(pdf_url, source_file, page_number)

CLI:
  py cs_rag_agent.py "모터 과열 발생 시 조치 방법"
  py cs_rag_agent.py "CSD5 서보 에러코드" --sources manual --json
  py cs_rag_agent.py "서보 과열 시 조치" --top 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import logging
import psycopg2
import psycopg2.pool
import requests
from pydantic import BaseModel

log = logging.getLogger("cs_rag")

# ── 설정 ──
EMBED_URL = "http://182.224.6.147:11434/api/embed"  # Qwen3-Embedding-8B (2000차원)
OLLAMA_EMBED_URL = EMBED_URL  # 하위호환 별칭
OLLAMA_EMBED_MODEL = "qwen3-embedding:8b"
OLLAMA_EMBED_DIM = 2000
VECTOR_TOP_K = 20
CS_WTA_URL = "https://cs-wta.com/cs"

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password",
    "dbname": "postgres",
}

# ── Supabase Storage 설정 ──
_SUPABASE_URL = "http://localhost:8000"
_SUPABASE_BUCKET = "vector"
_SERVICE_ROLE_KEY = ""
# 외부 접근 가능한 공개 URL (Cloudflare Tunnel 경유)
_SUPABASE_PUBLIC_URL = "https://mes-wta.com"

_env_path = Path(__file__).parent.parent.parent / "backend" / ".env"
if _env_path.is_file():
    with _env_path.open(encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line.startswith("SERVICE_ROLE_KEY="):
                _SERVICE_ROLE_KEY = _line.split("=", 1)[1].strip()
            elif _line.startswith("SUPABASE_PUBLIC_URL="):
                _SUPABASE_PUBLIC_URL = _line.split("=", 1)[1].strip()
_SUPABASE_PUBLIC_URL = os.environ.get("SUPABASE_PUBLIC_URL", _SUPABASE_PUBLIC_URL)


def _to_public_url(url: str) -> str:
    """localhost URL을 외부 접근 가능한 공개 URL로 치환."""
    if not url:
        return url
    return url.replace("http://localhost:8000", _SUPABASE_PUBLIC_URL)


# ── Pydantic 타입 정의 ──

class CSHistoryItem(BaseModel):
    """CS 이력 검색 결과 단건."""
    source_id: str
    similarity: float
    project_name: str = ""
    customer: str = ""
    handling_method: str = ""
    symptom_and_cause: str = ""
    action_result: str = ""
    url: str = ""  # https://cs-wta.com/cs/{source_id}


class ManualItem(BaseModel):
    """장비 매뉴얼 검색 결과 단건."""
    source_id: str
    similarity: float
    source_file: str = ""   # 원본 파일명
    category: str = ""
    page_number: int = 0
    chunk_type: str = ""
    content: str = ""
    reference: str = ""     # "파일명 p.XX" 형식 참조 텍스트
    pdf_url: str = ""       # Supabase Storage PDF URL
    page_url: str = ""      # pdf_url#page=N 형식
    image_url: str = ""     # 같은 페이지 image_caption 이미지 URL


class CombinedSearchResult(BaseModel):
    """통합 검색 결과 (CS 이력 + 매뉴얼)."""
    query: str
    cs_history_count: int
    manual_count: int
    cs_history_items: list[CSHistoryItem]
    manual_items: list[ManualItem]


# ── Dependency Injection ──

@dataclass
class CSRagDeps:
    """cs-agent가 주입하는 의존성."""
    embed_url: str = EMBED_URL
    db_config: dict = field(default_factory=lambda: DB_CONFIG.copy())
    top_k: int = VECTOR_TOP_K
    sources: str = "all"   # all | cs_history | manual


# ── DB 커넥션 풀 ──

_conn_pool: psycopg2.pool.SimpleConnectionPool | None = None


def _get_pool() -> psycopg2.pool.SimpleConnectionPool:
    """싱글턴 커넥션 풀 반환 (min=1, max=5)."""
    global _conn_pool
    if _conn_pool is None or _conn_pool.closed:
        _conn_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1, maxconn=5, **DB_CONFIG,
        )
    return _conn_pool


def _get_conn():
    """풀에서 커넥션 획득. with문으로 사용 시 자동 반환."""
    return _get_pool().getconn()


def _put_conn(conn, error: bool = False):
    """커넥션을 풀에 반환. 에러 발생 시 rollback 후 폐기."""
    try:
        if error:
            conn.rollback()
            _get_pool().putconn(conn, close=True)
        else:
            _get_pool().putconn(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


# ── 내부 구현 ──

def _embed(embed_url: str, text: str) -> list[float]:
    """Qwen3 임베딩 생성 (2000차원). 실패 시 빈 리스트."""
    try:
        resp = requests.post(
            embed_url,
            json={"model": OLLAMA_EMBED_MODEL, "input": [text]},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        emb = data["embeddings"][0]
        return emb[:OLLAMA_EMBED_DIM]
    except Exception as e:
        log.warning("Qwen3 임베딩 실패: %s", e)
        return []


def _embed_ollama(text: str) -> list[float]:
    """Ollama Qwen3 임베딩 생성 (2000차원, RAG 검색용). 실패 시 빈 리스트."""
    try:
        resp = requests.post(
            OLLAMA_EMBED_URL,
            json={"model": OLLAMA_EMBED_MODEL, "input": [text]},
            timeout=300,
        )
        resp.raise_for_status()
        data = resp.json()
        if "embeddings" not in data:
            log.warning("Ollama 임베딩 응답에 embeddings 키 없음")
            return []
        return data["embeddings"][0][:OLLAMA_EMBED_DIM]
    except Exception as e:
        log.warning("Ollama 임베딩 실패: %s", e)
        return []


def _search_cs_history(conn, emb_str: str, top_k: int) -> list[CSHistoryItem]:
    """csagent.vector_embeddings에서 CS 이력 검색."""
    sql = """
        SELECT
            source_id,
            text,
            metadata,
            1 - (embedding <=> %s::vector) AS similarity
        FROM csagent.vector_embeddings
        WHERE source_type = 'cs_history'
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (emb_str, emb_str, top_k))
        rows = cur.fetchall()

    items = []
    for source_id, text, metadata_raw, similarity in rows:
        meta = metadata_raw if isinstance(metadata_raw, dict) else json.loads(metadata_raw or "{}")
        symptom = ""
        action = ""
        for line in text.split("\n"):
            if line.startswith("증상 및 원인:"):
                symptom = line[len("증상 및 원인:"):].strip()
            elif line.startswith("조치 결과:"):
                action = line[len("조치 결과:"):].strip()
        items.append(CSHistoryItem(
            source_id=str(source_id),
            similarity=round(float(similarity), 4),
            project_name=meta.get("project_name", ""),
            customer=meta.get("customer", ""),
            handling_method=meta.get("handling_method", ""),
            symptom_and_cause=symptom,
            action_result=action,
            url=f"{CS_WTA_URL}/{source_id}",
        ))
    return items


def _fetch_page_images(conn, source_file: str, page_numbers: list[int]) -> dict[int, str]:
    """source_file + page_number 목록에 대해 image_caption image_url 일괄 조회."""
    if not page_numbers:
        return {}
    sql = """
        SELECT page_number, image_url
        FROM manual.documents
        WHERE source_file = %s
          AND chunk_type = 'image_caption'
          AND page_number = ANY(%s)
          AND image_url IS NOT NULL AND image_url != ''
        ORDER BY page_number, id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (source_file, page_numbers))
        rows = cur.fetchall()
    result: dict[int, str] = {}
    for page, img_url in rows:
        if page not in result:
            result[page] = img_url
    return result


def _search_manual(conn, emb_str: str, top_k: int) -> list[ManualItem]:
    """manual.documents에서 매뉴얼 검색 + 페이지 이미지 URL 포함."""
    sql = """
        SELECT
            id,
            source_file,
            category,
            page_number,
            chunk_type,
            content,
            COALESCE(pdf_url, '') AS pdf_url,
            1 - (embedding <=> %s::vector) AS similarity
        FROM manual.documents
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (emb_str, emb_str, top_k))
        rows = cur.fetchall()

    if not rows:
        return []

    # 페이지 이미지 일괄 조회
    file_pages: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        if row[3]:
            file_pages[row[1]].append(row[3])

    page_images: dict[str, dict[int, str]] = {}
    for sf, pages in file_pages.items():
        page_images[sf] = _fetch_page_images(conn, sf, pages)

    items = []
    for row in rows:
        fname = os.path.basename(row[1] or "")
        page = row[3] or 0
        pdf_url = _to_public_url(row[6] or "")
        display_name = fname.replace(".pdf", "").replace(" - 복사본", "").strip()
        page_url = f"{pdf_url}#page={page}" if pdf_url and page else ""
        img_url = page_images.get(row[1] or "", {}).get(page, "")
        items.append(ManualItem(
            source_id=str(row[0]),
            similarity=round(float(row[7]), 4),
            source_file=fname,
            category=row[2] or "",
            page_number=page,
            chunk_type=row[4] or "",
            content=(row[5] or "")[:500],
            reference=f"{display_name} p.{page}" if page else display_name,
            pdf_url=pdf_url,
            page_url=page_url,
            image_url=img_url,
        ))
    return items


# ── 공개 Tool 함수 (cs-agent에서 직접 import/호출) ──

async def run_search(
    question: str,
    top_k: int = VECTOR_TOP_K,
    sources: str = "all",
    deps: CSRagDeps | None = None,
) -> CombinedSearchResult:
    """CS이력 + 매뉴얼 통합 벡터 검색.

    Args:
        question: 검색 질문 텍스트
        top_k: 각 소스별 최대 결과 수
        sources: "all" | "cs_history" | "manual"
        deps: 의존성 주입 (기본값 사용 시 None)
    """
    if deps is None:
        deps = CSRagDeps(top_k=top_k, sources=sources)

    embedding = _embed_ollama(question)  # RAG 검색은 Ollama 2000차원 사용
    if not embedding:
        return CombinedSearchResult(
            query=question, cs_history_count=0, manual_count=0,
            cs_history_items=[], manual_items=[],
        )
    emb_str = str(embedding)

    conn = _get_conn()
    _err = False
    try:
        cs_items = _search_cs_history(conn, emb_str, deps.top_k) if deps.sources in ("all", "cs_history") else []
        manual_items = _search_manual(conn, emb_str, deps.top_k) if deps.sources in ("all", "manual") else []
    except Exception:
        _err = True
        raise
    finally:
        _put_conn(conn, error=_err)

    return CombinedSearchResult(
        query=question,
        cs_history_count=len(cs_items),
        manual_count=len(manual_items),
        cs_history_items=cs_items,
        manual_items=manual_items,
    )


def cs_history_detail(cs_id: str, deps: CSRagDeps | None = None) -> dict:
    """특정 CS 이력 상세 조회 (제목, 담당자, 증상/조치 전문 등).

    Args:
        cs_id: CS 이력 ID
        deps: 의존성 주입 (기본값 사용 시 None)
    """
    if deps is None:
        deps = CSRagDeps()

    sql = """
        SELECT
            h.id, h.title, h.status, h.cs_handler,
            h.cs_received_at::text, h.cs_completed_at::text,
            h.handling_method, h.free_paid_type,
            h.symptom_and_cause, h.action_result,
            s.project_name, s.customer, s.serial_no, s.domestic_overseas
        FROM csagent.cs_history h
        LEFT JOIN shipment_table s ON s.id = h.shipment_id
        WHERE h.id = %s
    """
    conn = psycopg2.connect(**deps.db_config)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (cs_id,))
            row = cur.fetchone()
            if not row:
                return {"error": f"CS 이력 {cs_id} 없음"}
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, [str(v) if v is not None else "" for v in row]))
    finally:
        conn.close()


def page_image(source_file: str, page_number: int, deps: CSRagDeps | None = None) -> dict:
    """매뉴얼 특정 페이지 이미지 URL 조회.

    Args:
        source_file: DB source_file 값 (예: Samsung_CSD5_UserManual_KO.pdf)
        page_number: 페이지 번호 (1-indexed)
        deps: 의존성 주입 (기본값 사용 시 None)

    Returns:
        {"image_url": "...", "found": True/False}
    """
    if deps is None:
        deps = CSRagDeps()

    conn = psycopg2.connect(**deps.db_config)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT image_url FROM manual.documents
                WHERE source_file = %s
                  AND chunk_type = 'image_caption'
                  AND page_number = %s
                  AND image_url IS NOT NULL AND image_url != ''
                ORDER BY id LIMIT 1
                """,
                (source_file, page_number),
            )
            row = cur.fetchone()
            if row:
                return {"image_url": row[0], "found": True}
            return {"image_url": "", "found": False}
    finally:
        conn.close()


def extract_pdf_excerpt(
    pdf_url: str,
    source_file: str,
    page_number: int,
    context_pages: int = 1,
) -> str | None:
    """매뉴얼 PDF에서 특정 페이지 앞뒤 포함 추출 후 Supabase Storage 업로드.

    Args:
        pdf_url: 원본 PDF 공개 URL (Supabase Storage)
        source_file: DB source_file 값 (파일명)
        page_number: 중심 페이지 번호 (1-indexed)
        context_pages: 앞뒤로 포함할 페이지 수 (기본 1 → 앞뒤 1페이지씩)

    Returns:
        업로드된 발췌 PDF URL (vector/excerpts/), 실패 시 None
    """
    if not pdf_url or not page_number or not _SERVICE_ROLE_KEY:
        return None

    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None

    # 1. 원본 PDF 다운로드 (내부 localhost URL 사용)
    download_url = pdf_url.replace(_SUPABASE_PUBLIC_URL, _SUPABASE_URL)
    try:
        resp = requests.get(download_url, timeout=60)
        resp.raise_for_status()
    except Exception:
        return None

    # 2. 페이지 추출 (PyMuPDF 0-indexed)
    try:
        src_doc = fitz.open(stream=resp.content, filetype="pdf")
        total_pages = src_doc.page_count
        center = page_number - 1
        start = max(0, center - context_pages)
        end = min(total_pages - 1, center + context_pages)

        excerpt_doc = fitz.open()
        excerpt_doc.insert_pdf(src_doc, from_page=start, to_page=end)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        excerpt_doc.save(tmp_path)
        excerpt_doc.close()
        src_doc.close()
    except Exception:
        return None

    # 3. Supabase Storage 업로드 (vector/excerpts/)
    stem = re.sub(r'[^a-zA-Z0-9._-]', '_', Path(source_file).stem)
    storage_path = f"excerpts/{stem}_p{start + 1}-{end + 1}.pdf"

    headers = {
        "Authorization": f"Bearer {_SERVICE_ROLE_KEY}",
        "apikey": _SERVICE_ROLE_KEY,
        "Content-Type": "application/pdf",
        "x-upsert": "true",
    }
    try:
        with open(tmp_path, "rb") as f:
            up_resp = requests.post(
                f"{_SUPABASE_URL}/storage/v1/object/{_SUPABASE_BUCKET}/{storage_path}",
                headers=headers,
                data=f,
                timeout=60,
            )
        if up_resp.status_code in (200, 201):
            return f"{_SUPABASE_PUBLIC_URL}/storage/v1/object/public/{_SUPABASE_BUCKET}/{storage_path}"
        return None
    except Exception:
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ── Q&A 캐시 시스템 (답변 품질 자동 개선) ──

# 주제 카테고리 정의
QA_CATEGORIES = {
    "encoder": ["엔코더", "encoder", "리셋", "reset", "절대치", "abs", "다회전"],
    "alarm": ["알람", "alarm", "에러", "error", "E.", "경고", "fault"],
    "parameter": ["파라메터", "파라미터", "parameter", "정수", "설정값", "ft-", "Ft-"],
    "wiring": ["배선", "wiring", "결선", "커넥터", "connector", "케이블"],
    "motor": ["모터", "motor", "과열", "진동", "소음", "토크"],
    "communication": ["통신", "serial", "RS232", "RS485", "ethernet", "프로토콜", "baud"],
    "maintenance": ["보수", "점검", "교체", "수리", "maintenance", "유지보수"],
    "operation": ["조작", "운전", "시운전", "원점", "JOG", "homing", "작동"],
    "plc": ["PLC", "래더", "IO", "입출력", "시퀀스"],
    "pneumatic": ["공압", "실린더", "밸브", "진공", "vacuum"],
    "vision": ["비전", "카메라", "검사", "inspection", "vision"],
    "printer": ["프린터", "라벨", "마킹", "printer", "label", "zebra"],
}

# 캐시 유사도 임계값
QA_CACHE_THRESHOLD = 0.92


def classify_question(question: str) -> list[str]:
    """질문을 주제 카테고리로 분류. 매칭 키워드 수 기반 우��순위, 최대 3개."""
    q_lower = question.lower()
    scored = []
    for category, keywords in QA_CATEGORIES.items():
        hit_count = sum(1 for kw in keywords if kw.lower() in q_lower)
        if hit_count > 0:
            scored.append((category, hit_count))
    # 매칭 키워드 수 많은 순 정렬 → 상위 3개
    scored.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in scored[:3]] or ["general"]


def search_qa_cache(
    question: str,
    threshold: float = QA_CACHE_THRESHOLD,
    deps: CSRagDeps | None = None,
    count_hit: bool = True,
) -> dict | None:
    """Q&A 캐시에서 유사 질문 검색. 임계값 이상이면 캐시 히트.

    Returns:
        {"id": int, "question": str, "answer": str, "tags": list,
         "confidence": float, "similarity": float} 또는 None
    """
    if deps is None:
        deps = CSRagDeps()

    embedding = _embed(deps.embed_url, question)
    if not embedding:
        return None
    emb_str = str(embedding)

    conn = _get_conn()
    _err = False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, question, answer, tags, score, topic, source_ids,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM csagent.qa_cache
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT 1
            """, (emb_str, emb_str))
            row = cur.fetchone()
            if row and row[7] >= threshold:
                # 실제 답변 사용 시에만 카운트 증가
                if count_hit:
                    cur.execute("UPDATE csagent.qa_cache SET use_count = use_count + 1, updated_at = now() WHERE id = %s", (row[0],))
                conn.commit()
                return {
                    "id": row[0],
                    "question": row[1],
                    "answer": row[2],
                    "tags": row[3] or [],
                    "score": row[4],
                    "topic": row[5],
                    "source_ids": row[6] or [],
                    "similarity": round(float(row[7]), 4),
                }
    except Exception:
        _err = True
        raise
    finally:
        _put_conn(conn, error=_err)
    return None


def save_qa_cache(
    question: str,
    answer: str,
    tags: list[str] | None = None,
    sources: list[dict] | None = None,
    confidence: float = 0.7,
    deps: CSRagDeps | None = None,
) -> int | None:
    """Q&A 캐시에 새 항목 저장. 중복 시 업데이트.

    Returns:
        저장된 레코드 ID 또는 None
    """
    if deps is None:
        deps = CSRagDeps()

    if tags is None:
        tags = classify_question(question)
    if sources is None:
        sources = []

    embedding = _embed(deps.embed_url, question)
    if not embedding:
        return None
    emb_str = str(embedding)

    # sources에서 source_ids 추출
    source_ids = [s.get("id", s.get("source_id", "")) for s in sources if isinstance(s, dict)]
    topic = tags[0] if tags else "general"

    conn = _get_conn()
    _err = False
    try:
        with conn.cursor() as cur:
            # 기존 동일 질문 검색 (벡터 유사도 0.98 이상이면 동일 질문으로 판단)
            cur.execute("""
                SELECT id, 1 - (embedding <=> %s::vector) AS sim
                FROM csagent.qa_cache WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector LIMIT 1
            """, (emb_str, emb_str))
            existing = cur.fetchone()

            if existing and existing[1] >= 0.98:
                # 기존 항목 업데��트 (카운트 리셋 — 새 답변이므로 피드백 초기화)
                cur.execute("""
                    UPDATE csagent.qa_cache
                    SET answer = %s, embedding = %s::vector, tags = %s, topic = %s,
                        score = %s, source_ids = %s,
                        good_count = 0, bad_count = 0, use_count = 0,
                        updated_at = now()
                    WHERE id = %s RETURNING id
                """, (answer, emb_str, tags, topic, confidence, source_ids, existing[0]))
            else:
                # 새 항목 삽입
                cur.execute("""
                    INSERT INTO csagent.qa_cache (question, embedding, answer, tags, topic, channel, agent, score, source_ids)
                    VALUES (%s, %s::vector, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (question, emb_str, answer, tags, topic, "slack", "cs-agent", confidence, source_ids))
            row = cur.fetchone()
            conn.commit()
            return row[0] if row else None
    except Exception:
        _err = True
        raise
    finally:
        _put_conn(conn, error=_err)


def update_qa_feedback(
    qa_id: int,
    rating: str,
    deps: CSRagDeps | None = None,
) -> bool:
    """Q&A 캐시 항목에 피드백 반영 (good/bad).

    score 자동 조정: good → +0.05, bad → -0.15
    Returns: True if updated, False if qa_id not found.
    """
    if deps is None:
        deps = CSRagDeps()

    conn = _get_conn()
    _err = False
    try:
        with conn.cursor() as cur:
            if rating == "good":
                cur.execute("""
                    UPDATE csagent.qa_cache
                    SET good_count = good_count + 1,
                        score = LEAST(1.0, score + 0.05),
                        updated_at = now()
                    WHERE id = %s
                """, (qa_id,))
            elif rating == "bad":
                cur.execute("""
                    UPDATE csagent.qa_cache
                    SET bad_count = bad_count + 1,
                        score = GREATEST(0.0, score - 0.15),
                        updated_at = now()
                    WHERE id = %s
                """, (qa_id,))
            else:
                return False
            updated = cur.rowcount > 0
        conn.commit()
        return updated
    except Exception:
        _err = True
        raise
    finally:
        _put_conn(conn, error=_err)


def evaluate_answer_quality(question: str, answer: str) -> dict:
    """답변 품질 자체 평가. 규칙 기반 휴리스틱.

    Returns:
        {"score": 0.0~1.0, "reasons": [...], "needs_improvement": bool}
    """
    score = 0.5
    reasons = []

    # 길이 기반
    ans_len = len(answer)
    if ans_len < 50:
        score -= 0.2
        reasons.append("답변이 너무 짧음")
    elif 200 <= ans_len <= 1500:
        score += 0.1
        reasons.append("충분한 길이")
    elif ans_len > 1500:
        score -= 0.05
        reasons.append("답변이 과도하게 길음")

    # 구체성: 파라메터 번호, 페이지 참조, 단계 번호 포함 여부
    if re.search(r'(run-\d+|ft-[\d.]+|Ft-[\d.]+|p\.\d+|페이지)', answer, re.IGNORECASE):
        score += 0.15
        reasons.append("구체적 파라메터/페이지 참조 포함")

    if re.search(r'[①②③④⑤⑥⑦⑧⑨⑩]|(\d+\.\s)|(\d+\))', answer):
        score += 0.1
        reasons.append("단계별 절차 포함")

    # CS 이력 참조
    if re.search(r'CS-\d+', answer):
        score += 0.1
        reasons.append("CS 이력 참조 포함")

    # 매뉴얼 참조
    if "매뉴얼" in answer or "페이지" in answer or "참조:" in answer:
        score += 0.1
        reasons.append("매뉴얼 참조 포함")

    # 부정적 답변 (문장 끝 패턴만 감점 — "이전엔 없습니다만..." 같은 문맥은 제외)
    neg_endings = re.findall(r'(없습니다\s*[.。]|찾을 수 없|등록되어 있지 않|모르겠습니다)', answer)
    if neg_endings:
        score -= 0.1
        reasons.append(f"정보 부족 표현 {len(neg_endings)}건")

    score = max(0.0, min(1.0, score))
    return {
        "score": round(score, 2),
        "reasons": reasons,
        "needs_improvement": score < 0.5,
    }


def cleanup_qa_cache(
    min_score: float = 0.2,
    min_bad_count: int = 3,
    stale_days: int = 90,
    dry_run: bool = True,
) -> dict:
    """저품질/미사용 캐시 항목 정리.

    삭제 기준:
    - score < min_score AND bad_count >= min_bad_count (저품질)
    - stale_days일 이상 use_count=0 (미사용)

    Returns: {"low_quality": int, "stale": int, "total_deleted": int}
    """
    conn = _get_conn()
    _err = False
    try:
        with conn.cursor() as cur:
            # 저품질 항목
            cur.execute("""
                SELECT count(*) FROM csagent.qa_cache
                WHERE score < %s AND bad_count >= %s
            """, (min_score, min_bad_count))
            low_q = cur.fetchone()[0]

            # 미사용 항목
            cur.execute("""
                SELECT count(*) FROM csagent.qa_cache
                WHERE use_count = 0 AND created_at < now() - make_interval(days => %s)
            """, (stale_days,))
            stale = cur.fetchone()[0]

            if not dry_run:
                cur.execute("""
                    DELETE FROM csagent.qa_cache
                    WHERE (score < %s AND bad_count >= %s)
                       OR (use_count = 0 AND created_at < now() - make_interval(days => %s))
                """, (min_score, min_bad_count, stale_days))
                actual_deleted = cur.rowcount
                conn.commit()
                log.info("캐시 정리 실행: %d건 삭제", actual_deleted)
            else:
                actual_deleted = 0

        return {"low_quality": low_q, "stale": stale, "total_deleted": actual_deleted, "dry_run": dry_run}
    except Exception:
        _err = True
        raise
    finally:
        _put_conn(conn, error=_err)


async def answer_with_cache(
    question: str,
    deps: CSRagDeps | None = None,
) -> dict:
    """캐시 우선 답변 워크플로우.

    1. 캐시 검색 → 히트 시 즉시 반환
    2. 미스 시 RAG 검색 → 답변 품질 평가 → 캐시 저장
    Returns: {"answer": str, "source": "cache"|"rag", "qa_id": int|None, "quality": dict, "rag_result": SearchResult|None}
    """
    if deps is None:
        deps = CSRagDeps()

    # 1. 캐시 검색
    cached = search_qa_cache(question, deps=deps)
    if cached and cached.get("score", 0) >= 0.5:
        log.info("캐시 히트: id=%s, similarity=%s, score=%s", cached["id"], cached.get("similarity"), cached.get("score"))
        # 캐시 히트 시에도 답변 품질 재평가 (원본 quality 보존)
        quality = evaluate_answer_quality(question, cached["answer"])
        quality["reasons"].insert(0, "캐시 히트")
        return {
            "answer": cached["answer"],
            "source": "cache",
            "qa_id": cached["id"],
            "quality": quality,
            "rag_result": None,
        }

    log.info("캐시 미스 → RAG 검색: %s", question[:50])
    # 2. RAG 검색
    rag_result = await run_search(question, deps=deps)

    # 3. 답변 조합 (RAG 결과 텍스트화)
    parts = []
    for item in (rag_result.cs_history_items or [])[:3]:
        if item.action_result:
            parts.append(f"[CS이력] {item.action_result[:200]}")
    for item in (rag_result.manual_items or [])[:3]:
        if item.content:
            parts.append(f"[매뉴얼] {item.content[:200]}")
    answer_text = "\n".join(parts) if parts else "관련 정보를 찾지 못했습니다."

    # 4. 품질 평가
    quality = evaluate_answer_quality(question, answer_text)

    # 5. 캐시 저장 (품질 점수 0.4 이상 + RAG 결과가 있는 경우만)
    qa_id = None
    if quality["score"] >= 0.4 and parts:
        source_refs = []
        for item in (rag_result.cs_history_items or [])[:3]:
            source_refs.append({"id": str(item.source_id), "type": "cs_history"})
        for item in (rag_result.manual_items or [])[:3]:
            source_refs.append({"id": str(item.source_id), "type": "manual"})
        qa_id = save_qa_cache(
            question=question,
            answer=answer_text,
            tags=classify_question(question),
            sources=source_refs,
            confidence=quality["score"],
            deps=deps,
        )

    return {
        "answer": answer_text,
        "source": "rag",
        "qa_id": qa_id,
        "quality": quality,
        "rag_result": rag_result,
    }


# ── CLI 진입점 ──

def _cli_search(args):
    """RAG 검색 (기존 기능)."""
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    result = asyncio.run(run_search(args.question, top_k=args.top, sources=args.sources))

    if args.json:
        print(result.model_dump_json(indent=2, ensure_ascii=False))
        return

    print(f"\n[검색 결과: CS이력 {result.cs_history_count}건 | 매뉴얼 {result.manual_count}건]\n")

    if result.cs_history_items:
        print("=== CS 이력 ===")
        for i, item in enumerate(result.cs_history_items, 1):
            header = f"{item.project_name} | {item.customer}" if item.project_name or item.customer else f"CS #{item.source_id}"
            print(f"── [{i}] 유사도: {item.similarity} | {header} ──")
            if item.symptom_and_cause:
                print(f"  증상: {item.symptom_and_cause[:80]}")
            if item.action_result:
                print(f"  조치: {item.action_result[:80]}")
            print(f"  링크: {item.url}")
            print()

    if result.manual_items:
        print("=== 매뉴얼 ===")
        for i, item in enumerate(result.manual_items, 1):
            print(f"── [{i}] 유사도: {item.similarity} | {item.reference} ──")
            print(f"  {item.content[:120].replace(chr(10), ' ')}")
            if item.page_url:
                print(f"  PDF: {item.page_url}")
            if item.image_url:
                print(f"  이미지: {item.image_url}")
            print()


def _cli_cache_check(args):
    """캐시 검색 — 유사 질문이 캐시에 있는지 확인."""
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    cached = search_qa_cache(args.question, threshold=args.threshold, count_hit=False)
    if cached:
        out = {
            "hit": True,
            "id": cached["id"],
            "similarity": cached["similarity"],
            "score": cached.get("score", 0),
            "topic": cached.get("topic", ""),
            "tags": cached.get("tags", []),
            "question": cached["question"],
            "answer": cached["answer"],
        }
    else:
        out = {"hit": False, "tags": classify_question(args.question)}

    print(json.dumps(out, ensure_ascii=False, indent=2))


def _cli_cache_save(args):
    """답변을 캐시에 저장."""
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    tags = args.tags.split(",") if args.tags else classify_question(args.question)
    sources = []
    if args.source_ids:
        for sid in args.source_ids.split(","):
            sid = sid.strip()
            stype = "cs_history" if sid.startswith("CS-") or sid.isdigit() else "manual"
            sources.append({"id": sid, "type": stype})

    qa_id = save_qa_cache(
        question=args.question,
        answer=args.answer,
        tags=tags,
        sources=sources,
        confidence=args.score,
    )

    quality = evaluate_answer_quality(args.question, args.answer)
    out = {"qa_id": qa_id, "tags": tags, "quality": quality}
    print(json.dumps(out, ensure_ascii=False, indent=2))


def _cli_feedback(args):
    """캐시 항목에 피드백 반영."""
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    updated = update_qa_feedback(args.qa_id, args.rating)
    print(json.dumps({"ok": updated, "qa_id": args.qa_id, "rating": args.rating}))


def _cli_cache_cleanup(args):
    """저품질/미사용 캐시 정리."""
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    result = cleanup_qa_cache(
        min_score=args.min_score,
        min_bad_count=args.min_bad,
        stale_days=args.stale_days,
        dry_run=not args.execute,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="CS RAG 통합 검색 + Q&A 캐시")
    sub = parser.add_subparsers(dest="command")

    # search (기본 — 하위호환)
    p_search = sub.add_parser("search", help="RAG 벡터 검색")
    p_search.add_argument("question", help="기술문의 질문")
    p_search.add_argument("--top", type=int, default=VECTOR_TOP_K)
    p_search.add_argument("--sources", default="all", choices=["all", "cs_history", "manual"])
    p_search.add_argument("--json", action="store_true")

    # cache-check
    p_cc = sub.add_parser("cache-check", help="캐시 검색")
    p_cc.add_argument("question", help="질문")
    p_cc.add_argument("--threshold", type=float, default=QA_CACHE_THRESHOLD)

    # cache-save
    p_cs = sub.add_parser("cache-save", help="답변 캐시 저장")
    p_cs.add_argument("question", help="질문")
    p_cs.add_argument("answer", help="답변")
    p_cs.add_argument("--tags", default="", help="태그 (콤마 구분)")
    p_cs.add_argument("--source-ids", default="", help="출처 ID (콤마 구분)")
    p_cs.add_argument("--score", type=float, default=0.7, help="초기 품질 점수")

    # feedback
    p_fb = sub.add_parser("feedback", help="피드백 반영")
    p_fb.add_argument("qa_id", type=int, help="Q&A 캐시 ID")
    p_fb.add_argument("rating", choices=["good", "bad"], help="평가")

    # cache-cleanup
    p_cl = sub.add_parser("cache-cleanup", help="저품질/미사용 캐시 정리")
    p_cl.add_argument("--min-score", type=float, default=0.2, help="삭제 기준 최소 score (기본 0.2)")
    p_cl.add_argument("--min-bad", type=int, default=3, help="삭제 기준 최소 bad_count (기본 3)")
    p_cl.add_argument("--stale-days", type=int, default=90, help="미사용 판단 기준 일수 (기본 90)")
    p_cl.add_argument("--execute", action="store_true", help="실제 삭제 실행 (기본 dry-run)")

    # 하위호환: 첫 인자가 서브커맨드가 아니면 기존 search로 동작
    known_commands = {"search", "cache-check", "cache-save", "feedback", "cache-cleanup"}
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] not in known_commands and not _sys.argv[1].startswith("-"):
        parser2 = argparse.ArgumentParser()
        parser2.add_argument("question")
        parser2.add_argument("--top", type=int, default=VECTOR_TOP_K)
        parser2.add_argument("--sources", default="all", choices=["all", "cs_history", "manual"])
        parser2.add_argument("--json", action="store_true")
        args = parser2.parse_args()
        _cli_search(args)
        return

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
    elif args.command == "search":
        _cli_search(args)
    elif args.command == "cache-check":
        _cli_cache_check(args)
    elif args.command == "cache-save":
        _cli_cache_save(args)
    elif args.command == "feedback":
        _cli_feedback(args)
    elif args.command == "cache-cleanup":
        _cli_cache_cleanup(args)


if __name__ == "__main__":
    main()
