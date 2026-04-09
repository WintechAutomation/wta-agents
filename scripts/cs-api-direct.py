"""cs-api-direct.py -Claude API 직접 호출 CS RAG 파이프라인.

슬랙 CS 질문 → 벡터 검색(3개 테이블) → Claude API → 슬랙 응답.
Claude Code 세션 경유 없이 API 직접 호출로 응답 속도 개선.

사용법:
  # CLI 테스트 (벡터 검색만 -API 키 불필요)
  py cs-api-direct.py "모터 과열 발생 시 조치 방법" --search-only

  # 전체 파이프라인 (API 키 필요)
  py cs-api-direct.py "CSD5 서보 에러코드 E-01"

  # 슬랙 연동 모드 (slack-bot에서 호출)
  py cs-api-direct.py --slack --channel "#cs" --user "홍길동" "서보 알람 해결법"

환경변수:
  ANTHROPIC_API_KEY -Claude API 키 (필수, 하드코딩 금지)
  CS_MODEL          -Claude 모델 (기본: claude-sonnet-4-20250514)

DB: C:/MES/backend/.env에서 DB_PASSWORD 로드.
임베딩: Qwen3-Embedding-8B (182.224.6.147:11434).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import psycopg2
import requests

log = logging.getLogger("cs-api-direct")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

# Windows cp949 인코딩 문제 방지
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 설정 ──
KST = timezone(timedelta(hours=9))

# 임베딩 (OLLAMA_HOST 환경변수 override 가능, 기본 localhost)
_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
EMBED_URL = f"{_OLLAMA_HOST}/api/embed"
EMBED_MODEL = "qwen3-embedding:8b"
EMBED_DIM_2000 = 2000  # csagent.vector_embeddings, manual.documents
EMBED_DIM_4096 = 4096  # manual.wta_documents

# Claude API
CLAUDE_MODEL = os.environ.get("CS_MODEL", "claude-sonnet-4-20250514")
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"

# DB
MES_ENV_FILE = Path("C:/MES/backend/.env")
DB_BASE = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "dbname": "postgres",
}

# 세션 로그
CS_SESSIONS_FILE = Path("C:/MES/wta-agents/reports/cs-sessions.jsonl")

# CS URL
CS_WTA_URL = "https://cs-wta.com/cs"

# 시스템 프롬프트
SYSTEM_PROMPT = """당신은 (주)윈텍오토메이션의 CS 기술지원 AI 전문가입니다.

역할:
- 초경합금 인서트 자동화/검사/연삭 장비 전문 기술지원
- CS 이력, 장비 매뉴얼, WTA 기술문서를 기반으로 정확한 답변 제공
- 고객 문의에 전문적이고 겸손한 태도로 응대

답변 규칙:
1. 제공된 검색 결과를 근거로 답변하세요. 근거 없는 추측은 금지.
2. 관련 CS 이력이 있으면 이력 번호와 링크를 포함하세요.
3. 매뉴얼 참조 시 파일명과 페이지를 명시하세요.
4. 한국어로 답변하세요.
5. 칭찬/맞장구 표현 삼가. 전문적·겸손한 태도 유지.
6. 답변은 간결하되, 필요한 기술적 세부사항은 빠짐없이 포함하세요.
7. 확실하지 않은 내용은 "확인이 필요합니다"라고 명시하세요."""


# ── DB 비밀번호 로드 ──

def _load_db_password() -> str:
    """C:/MES/backend/.env에서 DB_PASSWORD 로드."""
    if not MES_ENV_FILE.is_file():
        raise RuntimeError(f".env 파일 없음: {MES_ENV_FILE}")
    with MES_ENV_FILE.open(encoding="utf-8") as f:
        for line in f:
            if line.startswith("DB_PASSWORD="):
                return line.strip().split("=", 1)[1]
    raise RuntimeError(".env에 DB_PASSWORD 항목 없음")


def _get_conn() -> psycopg2.extensions.connection:
    """PostgreSQL 연결."""
    password = _load_db_password()
    return psycopg2.connect(**DB_BASE, password=password, connect_timeout=10)


# ── 임베딩 ──

def _embed(text: str, dim: int = EMBED_DIM_2000) -> list[float]:
    """Qwen3-Embedding-8B로 텍스트 벡터화."""
    resp = requests.post(
        EMBED_URL,
        json={"model": EMBED_MODEL, "input": [text]},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "embeddings" not in data or not data["embeddings"]:
        raise RuntimeError("임베딩 응답에 embeddings 없음")
    return data["embeddings"][0][:dim]


# ── 벡터 검색 (3개 테이블) ──

def search_cs_history(conn, emb_str: str, top_k: int = 10) -> list[dict]:
    """csagent.vector_embeddings -CS 이력 검색 (2000차원)."""
    sql = """
        SELECT source_id, text, metadata,
               1 - (embedding <=> %s::vector) AS similarity
        FROM csagent.vector_embeddings
        WHERE source_type = 'cs_history'
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (emb_str, emb_str, top_k))
        rows = cur.fetchall()

    results = []
    for source_id, text, metadata_raw, similarity in rows:
        meta = metadata_raw if isinstance(metadata_raw, dict) else json.loads(metadata_raw or "{}")
        results.append({
            "source": "cs_history",
            "source_id": str(source_id),
            "similarity": round(float(similarity), 4),
            "project_name": meta.get("project_name", ""),
            "customer": meta.get("customer", ""),
            "handling_method": meta.get("handling_method", ""),
            "text": text[:500],
            "url": f"{CS_WTA_URL}/{source_id}",
        })
    return results


def search_parts_manual(conn, emb_str: str, top_k: int = 10) -> list[dict]:
    """manual.documents -부품 매뉴얼 검색 (2000차원)."""
    sql = """
        SELECT id, source_file, category, page_number, chunk_type, content,
               COALESCE(pdf_url, '') AS pdf_url,
               1 - (embedding <=> %s::vector) AS similarity
        FROM manual.documents
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (emb_str, emb_str, top_k))
        rows = cur.fetchall()

    results = []
    for row in rows:
        fname = os.path.basename(row[1] or "")
        page = row[3] or 0
        results.append({
            "source": "parts_manual",
            "source_id": str(row[0]),
            "similarity": round(float(row[7]), 4),
            "source_file": fname,
            "category": row[2] or "",
            "page_number": page,
            "chunk_type": row[4] or "",
            "content": (row[5] or "")[:500],
            "reference": f"{fname} p.{page}" if page else fname,
        })
    return results


def search_wta_manual(conn, emb_str_4096: str, top_k: int = 10) -> list[dict]:
    """manual.wta_documents -WTA 매뉴얼 검색 (4096차원)."""
    sql = """
        SELECT id, source_file, category, chunk_index, chunk_type,
               page_number, content,
               1 - (embedding <=> %s::vector) AS similarity
        FROM manual.wta_documents
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (emb_str_4096, emb_str_4096, top_k))
        rows = cur.fetchall()

    results = []
    for row in rows:
        fname = os.path.basename(row[1] or "")
        page = row[5] or 0
        results.append({
            "source": "wta_manual",
            "source_id": str(row[0]),
            "similarity": round(float(row[7]), 4),
            "source_file": fname,
            "category": row[2] or "",
            "page_number": page,
            "chunk_type": row[4] or "",
            "content": (row[6] or "")[:500],
            "reference": f"{fname} p.{page}" if page else fname,
        })
    return results


def combined_search(query: str, top_k: int = 10) -> dict:
    """3개 테이블 통합 벡터 검색.

    Returns:
        {query, embedding_time, search_time,
         cs_history: [...], parts_manual: [...], wta_manual: [...]}
    """
    # 임베딩 생성 (2000차원 -전 테이블 공통)
    t0 = time.time()
    emb_2000 = _embed(query, EMBED_DIM_2000)
    embed_time = round(time.time() - t0, 2)

    emb_str_2000 = str(emb_2000)

    # DB 검색
    t1 = time.time()
    conn = _get_conn()
    try:
        cs_items = search_cs_history(conn, emb_str_2000, top_k)
        parts_items = search_parts_manual(conn, emb_str_2000, top_k)
        wta_items = search_wta_manual(conn, emb_str_2000, top_k)
    finally:
        conn.close()
    search_time = round(time.time() - t1, 2)

    return {
        "query": query,
        "embedding_time_sec": embed_time,
        "search_time_sec": search_time,
        "cs_history": cs_items,
        "parts_manual": parts_items,
        "wta_manual": wta_items,
    }


# ── 컨텍스트 조립 ──

def _build_context(search_result: dict) -> str:
    """검색 결과를 Claude에 전달할 컨텍스트 문자열로 조립."""
    parts = []

    # CS 이력
    cs_items = [r for r in search_result["cs_history"] if r["similarity"] >= 0.3]
    if cs_items:
        parts.append("## CS 이력 검색 결과")
        for i, item in enumerate(cs_items[:5], 1):
            parts.append(
                f"{i}. [{item['project_name']}] {item['customer']} "
                f"(유사도 {item['similarity']:.1%})\n"
                f"   처리방법: {item['handling_method']}\n"
                f"   내용: {item['text'][:300]}\n"
                f"   링크: {item['url']}"
            )

    # 부품 매뉴얼
    parts_items = [r for r in search_result["parts_manual"] if r["similarity"] >= 0.3]
    if parts_items:
        parts.append("\n## 부품 매뉴얼 검색 결과")
        for i, item in enumerate(parts_items[:5], 1):
            parts.append(
                f"{i}. [{item['category']}] {item['reference']} "
                f"(유사도 {item['similarity']:.1%})\n"
                f"   {item['content'][:300]}"
            )

    # WTA 매뉴얼
    wta_items = [r for r in search_result["wta_manual"] if r["similarity"] >= 0.3]
    if wta_items:
        parts.append("\n## WTA 매뉴얼 검색 결과")
        for i, item in enumerate(wta_items[:5], 1):
            parts.append(
                f"{i}. [{item['category']}] {item['reference']} "
                f"(유사도 {item['similarity']:.1%})\n"
                f"   {item['content'][:300]}"
            )

    if not parts:
        return "검색 결과가 없습니다. 일반 지식으로 답변해주세요."

    return "\n".join(parts)


# ── Claude API 호출 ──

def _get_api_key() -> str:
    """ANTHROPIC_API_KEY를 환경변수 또는 wta-agents/.env에서 로드."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    # wta-agents/.env 폴백
    wta_env = Path("C:/MES/wta-agents/.env")
    if wta_env.is_file():
        with wta_env.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(
        "ANTHROPIC_API_KEY 미설정 — 환경변수 또는 C:/MES/wta-agents/.env 에 설정 필요"
    )


def call_claude(question: str, context: str) -> dict:
    """Claude API 직접 호출.

    Returns:
        {"answer": str, "model": str, "input_tokens": int, "output_tokens": int, "time_sec": float}
    """
    api_key = _get_api_key()

    user_message = f"""다음은 고객/직원의 CS 질문입니다:

질문: {question}

아래는 벡터 검색으로 찾은 관련 자료입니다:

{context}

위 자료를 근거로 질문에 답변해주세요."""

    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 2048,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_message}],
    }

    t0 = time.time()
    resp = requests.post(
        CLAUDE_API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    elapsed = round(time.time() - t0, 2)

    if resp.status_code != 200:
        err = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        raise RuntimeError(f"Claude API 오류 ({resp.status_code}): {err}")

    data = resp.json()
    answer = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            answer += block["text"]

    usage = data.get("usage", {})
    return {
        "answer": answer,
        "model": data.get("model", CLAUDE_MODEL),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "time_sec": elapsed,
    }


# ── 세션 로깅 ──

def _log_session(question: str, search_result: dict, claude_result: dict | None,
                 channel: str = "", user: str = ""):
    """CS 세션을 JSONL에 기록."""
    now = datetime.now(KST)
    entry = {
        "timestamp": now.isoformat(),
        "channel": channel,
        "user": user,
        "question": question,
        "search_counts": {
            "cs_history": len(search_result.get("cs_history", [])),
            "parts_manual": len(search_result.get("parts_manual", [])),
            "wta_manual": len(search_result.get("wta_manual", [])),
        },
        "embedding_time": search_result.get("embedding_time_sec", 0),
        "search_time": search_result.get("search_time_sec", 0),
    }
    if claude_result:
        entry["answer_preview"] = claude_result["answer"]
        entry["full_response"] = claude_result["answer"]
        entry["model"] = claude_result["model"]
        entry["input_tokens"] = claude_result["input_tokens"]
        entry["output_tokens"] = claude_result["output_tokens"]
        entry["claude_time"] = claude_result["time_sec"]
    else:
        entry["answer_preview"] = "(search-only)"

    try:
        CS_SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CS_SESSIONS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("세션 로깅 실패: %s", e)


# ── 전체 파이프라인 ──

def run_pipeline(question: str, top_k: int = 10,
                 search_only: bool = False,
                 channel: str = "", user: str = "") -> dict:
    """CS RAG 전체 파이프라인 실행.

    Args:
        question: CS 질문
        top_k: 각 테이블 검색 건수
        search_only: True이면 벡터 검색만 (API 키 불필요)
        channel: 슬랙 채널 (로깅용)
        user: 질문자 (로깅용)

    Returns:
        {"question", "search_result", "context", "answer", "claude_result", "total_time"}
    """
    total_start = time.time()

    # 1. 벡터 검색
    log.info("벡터 검색 시작: %s", question[:50])
    search_result = combined_search(question, top_k)
    log.info(
        "검색 완료 -CS이력: %d건, 부품매뉴얼: %d건, WTA매뉴얼: %d건 (임베딩 %.1fs, 검색 %.1fs)",
        len(search_result["cs_history"]),
        len(search_result["parts_manual"]),
        len(search_result["wta_manual"]),
        search_result["embedding_time_sec"],
        search_result["search_time_sec"],
    )

    # 2. 컨텍스트 조립
    context = _build_context(search_result)

    if search_only:
        _log_session(question, search_result, None, channel, user)
        return {
            "question": question,
            "search_result": search_result,
            "context": context,
            "answer": None,
            "claude_result": None,
            "total_time_sec": round(time.time() - total_start, 2),
        }

    # 3. Claude API 호출
    log.info("Claude API 호출 시작 (모델: %s)", CLAUDE_MODEL)
    claude_result = call_claude(question, context)
    log.info(
        "Claude 응답 완료 -%d tokens in, %d tokens out (%.1fs)",
        claude_result["input_tokens"],
        claude_result["output_tokens"],
        claude_result["time_sec"],
    )

    # 4. 세션 로깅
    _log_session(question, search_result, claude_result, channel, user)

    total_time = round(time.time() - total_start, 2)
    log.info("전체 파이프라인 완료: %.1fs", total_time)

    return {
        "question": question,
        "search_result": search_result,
        "context": context,
        "answer": claude_result["answer"],
        "claude_result": claude_result,
        "total_time_sec": total_time,
    }


# ── CLI ──

def main():
    parser = argparse.ArgumentParser(description="CS RAG -Claude API 직접 호출 파이프라인")
    parser.add_argument("question", help="CS 질문")
    parser.add_argument("--top", type=int, default=10, help="각 테이블 검색 건수 (기본 10)")
    parser.add_argument("--search-only", action="store_true", help="벡터 검색만 (API 키 불필요)")
    parser.add_argument("--slack", action="store_true", help="슬랙 연동 모드")
    parser.add_argument("--channel", default="", help="슬랙 채널")
    parser.add_argument("--user", default="", help="질문자")
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    args = parser.parse_args()

    result = run_pipeline(
        args.question,
        top_k=args.top,
        search_only=args.search_only,
        channel=args.channel,
        user=args.user,
    )

    if args.json:
        # JSON 출력 (search_result 내 긴 content 제거)
        output = {
            "question": result["question"],
            "total_time_sec": result["total_time_sec"],
            "search_counts": {
                "cs_history": len(result["search_result"]["cs_history"]),
                "parts_manual": len(result["search_result"]["parts_manual"]),
                "wta_manual": len(result["search_result"]["wta_manual"]),
            },
        }
        if result["answer"]:
            output["answer"] = result["answer"]
        if result["claude_result"]:
            output["model"] = result["claude_result"]["model"]
            output["tokens"] = {
                "input": result["claude_result"]["input_tokens"],
                "output": result["claude_result"]["output_tokens"],
            }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    # 사람이 읽기 좋은 출력
    sr = result["search_result"]
    print(f"\n{'='*60}")
    print(f"질문: {result['question']}")
    print(f"{'='*60}")
    print(f"임베딩: {sr['embedding_time_sec']}s | 검색: {sr['search_time_sec']}s | 총: {result['total_time_sec']}s")
    print(f"CS이력: {len(sr['cs_history'])}건 | 부품매뉴얼: {len(sr['parts_manual'])}건 | WTA매뉴얼: {len(sr['wta_manual'])}건")

    if args.search_only:
        print(f"\n{'─'*60}")
        print("[벡터 검색 결과 -유사도 상위 항목]")
        for source_name, items in [("CS이력", sr["cs_history"]), ("부품매뉴얼", sr["parts_manual"]), ("WTA매뉴얼", sr["wta_manual"])]:
            top_items = [r for r in items if r["similarity"] >= 0.3][:3]
            if top_items:
                print(f"\n  [{source_name}]")
                for r in top_items:
                    label = r.get("reference") or r.get("project_name") or r["source_id"]
                    print(f"    {r['similarity']:.1%} -{label}")
                    text = r.get("content") or r.get("text", "")
                    if text:
                        print(f"         {text[:120]}...")
        return

    if result["answer"]:
        cr = result["claude_result"]
        print(f"\n{'─'*60}")
        print(f"[Claude 답변] ({cr['model']}, {cr['input_tokens']}+{cr['output_tokens']} tokens, {cr['time_sec']}s)")
        print(f"{'─'*60}")
        print(result["answer"])
    print()


if __name__ == "__main__":
    main()
