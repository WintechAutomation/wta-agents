"""
CS RAG 직접 검색 유틸리티 — pgvector 직접 쿼리

사용법:
  from cs_rag_search import search_rag, search_parallel

  results = search_rag("파나소닉 A6B Pr4.39 브레이크 해제 속도")
  # 반환: [{"content": str, "source_file": str, "score": float, ...}, ...]
"""

import os
import json
import requests

EMBED_DIM = 2000
OLLAMA_HOST = "http://182.224.6.147:11434"
EMBED_MODEL = "qwen3-embedding:8b"


def _load_db_password() -> str:
    env_path = "C:/MES/backend/.env"
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("DB_PASSWORD="):
                    return line.strip().split("=", 1)[1]
    return ""


def _get_embedding(text: str) -> list[float]:
    """Ollama qwen3-embedding:8b로 텍스트 임베딩 생성 → 2000차원으로 슬라이싱"""
    resp = requests.post(
        f"{OLLAMA_HOST}/api/embed",
        json={"model": EMBED_MODEL, "input": text},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    embedding = data.get("embeddings", [data.get("embedding", [])])[0]
    return embedding[:EMBED_DIM]


def search_rag(query: str, top_k: int = 5) -> list[dict]:
    """
    pgvector를 직접 쿼리하여 관련 매뉴얼/CS이력 검색.

    반환: [{"content": str, "source_file": str, "score": float, "table": str}, ...]
    """
    try:
        import psycopg2
    except ImportError:
        return []

    embedding = _get_embedding(query)
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
    password = _load_db_password()

    try:
        conn = psycopg2.connect(
            host="localhost",
            port=55432,
            user="postgres",
            password=password,
            dbname="postgres",
        )
    except Exception:
        return []

    results = []
    tables = [
        ("manual.documents", "content", "source_file"),
        ("manual.wta_documents", "content", "source_file"),
        ("csagent.vector_embeddings", "content", "source_file"),
    ]

    with conn:
        with conn.cursor() as cur:
            for table, content_col, file_col in tables:
                try:
                    cur.execute(
                        f"""
                        SELECT {content_col}, {file_col},
                               1 - (embedding <=> %s::vector) AS score
                        FROM {table}
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (vec_str, vec_str, top_k),
                    )
                    for row in cur.fetchall():
                        results.append({
                            "content": row[0],
                            "source_file": row[1] or "",
                            "score": float(row[2]),
                            "table": table,
                        })
                except Exception:
                    continue

    conn.close()

    # 점수 내림차순 정렬 후 top_k
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def merge_results(rag_results: list[dict], db_manager_text: str) -> str:
    """
    자체 RAG 결과 + db-manager 텍스트 결과를 합쳐서
    cs-agent가 판단할 수 있도록 포맷팅.
    """
    lines = []

    if rag_results:
        lines.append("=== [자체 RAG 검색 결과] ===")
        for i, r in enumerate(rag_results, 1):
            lines.append(f"\n[{i}] 출처: {r['source_file']} | 유사도: {r['score']:.3f}")
            lines.append(r["content"][:500])
    else:
        lines.append("=== [자체 RAG: 결과 없음 또는 연결 실패] ===")

    if db_manager_text:
        lines.append("\n\n=== [db-manager 검색 결과] ===")
        lines.append(db_manager_text)

    return "\n".join(lines)


RAG_SCORE_THRESHOLD = 0.60  # 이 점수 이상이어야 충분한 결과로 판단


def is_sufficient(rag_results: list[dict]) -> bool:
    """RAG 결과가 충분한지 판단 (상위 결과 점수 기준)"""
    if not rag_results:
        return False
    return rag_results[0]["score"] >= RAG_SCORE_THRESHOLD


def search_with_pipeline(query: str, top_k: int = 5) -> dict:
    """
    최종 CS 검색 파이프라인:
    1. cs-sessions.jsonl 이전 세션 검색 (최우선)
    2. 자체 RAG(pgvector) 검색
    3. 결과 부족 시 db-manager 폴백 필요 여부 반환

    반환:
    {
        "session_hit": dict | None,   # 이전 세션 히트
        "rag_results": list[dict],    # RAG 결과
        "needs_dbmanager": bool,      # db-manager 추가 검색 필요 여부
        "merged_context": str,        # 합산 컨텍스트
    }
    """
    from cs_pdf_cache import lookup_session_attachment

    # 1단계: 이전 세션 검색
    session_hit = lookup_session_attachment(query)

    # 2단계: 자체 RAG
    rag_results = search_rag(query, top_k=top_k)

    # 3단계: 폴백 필요 여부 판단
    needs_dbmanager = not is_sufficient(rag_results)

    merged = merge_results(rag_results, "")

    return {
        "session_hit": session_hit,
        "rag_results": rag_results,
        "needs_dbmanager": needs_dbmanager,
        "merged_context": merged,
    }
