"""
CS 자동 파이프라인 — 웹챗/슬랙 CS 질문 처리 단일 진입점

2026-04-10 전환: pgvector 제거, Neo4j GraphRAG 단독 사용.

사용법:
  python cs_pipeline.py "질문 텍스트"

출력 (JSON):
  {
    "session_hit": {...} | null,     # 이전 세션 이력
    "graph_result": {...},            # Neo4j 검색 결과 (nodes/relationships)
    "rag_results": [...],             # 호환: 엔티티 flat list
    "needs_dbmanager": bool,          # db-manager 폴백 필요 여부
    "merged_context": str,            # 합산 컨텍스트 텍스트
    "best_source": {...} | null,      # 최고 순위 소스 (PDF 첨부용)
    "pdf_info": {...} | null,         # PDF 추출 결과
    "rag_source": "graph"             # 검색 백엔드 식별자 (로깅용)
  }
"""

import sys
import json
import os
import urllib.request
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))

from cs_rag_search import search_with_pipeline, is_sufficient, _extract_keywords
from cs_pdf_cache import get_or_extract_pdf_page, lookup_session_attachment

_DASHBOARD_API = os.environ.get("DASHBOARD_API", "http://localhost:5555")


def _fetch_cs_history_context(query: str) -> str:
    """
    등록된 cs_history_search API로 CS 이력 DB 검색.
    질문에서 가장 구체적인 키워드로 조회 후 컨텍스트 텍스트 반환.
    """
    keywords = _extract_keywords(query)
    if not keywords:
        return ""

    # 가장 긴(구체적인) 키워드 우선
    keyword = max(keywords, key=len)

    try:
        url = f"{_DASHBOARD_API}/api/query/cs_history_search?keyword={urllib.parse.quote(keyword)}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        if not data.get("ok"):
            return ""

        result_text = data.get("result", "")
        if not result_text or "0 rows" in result_text:
            return ""

        # result는 텍스트 테이블 형식 — 그대로 컨텍스트에 포함
        return f"=== [CS 이력 DB 검색 결과 (키워드: {keyword})] ===\n{result_text[:2000]}"
    except Exception:
        return ""


def _extract_pdf_if_available(rag_results: list[dict]) -> dict | None:
    """
    엔티티 속성에 source_file + page_number가 있으면
    해당 PDF 페이지를 추출(캐시 활용)하여 반환.
    """
    for r in rag_results:
        props = r.get("properties", {}) or {}
        source_file = r.get("source_file", "") or props.get("source_file", "") or props.get("source", "")
        page = props.get("page_number") or props.get("page") or r.get("page_number") or r.get("page")
        if not source_file or not page:
            continue

        pdf_paths = [
            f"C:/MES/wta-agents/manuals/{source_file}",
            f"C:/wMES/media/manuals/{source_file}",
            f"C:/MES/wta-agents/workspaces/cs-agent/manuals/{source_file}",
        ]
        for pdf_path in pdf_paths:
            if os.path.exists(pdf_path):
                try:
                    result = get_or_extract_pdf_page(pdf_path, int(page), context=1)
                    result["source_file"] = source_file
                    result["page"] = page
                    result["name"] = r.get("name", "")
                    return result
                except Exception:
                    continue

    return None


def run(query: str) -> dict:
    """
    5단계 CS 파이프라인 실행:
    1. cs-sessions.jsonl 이전 이력 검색
    2. GraphRAG (Neo4j 단독)
    3. 충분성 판정 → db-manager 폴백 필요 여부
    4. CS 이력 DB 검색 (장비탭 이슈사항 자동 참조)
    5. PDF 추출 가능 시 자동 처리
    """
    pipeline = search_with_pipeline(query)

    session_hit = pipeline["session_hit"]
    graph_result = pipeline["graph_result"]
    rag_results = pipeline["rag_results"]
    needs_dbmanager = pipeline["needs_dbmanager"]
    merged_context = pipeline["merged_context"]
    rag_source = pipeline.get("rag_source", "graph")

    # 4단계: CS 이력 DB 검색 (장비탭 이슈사항 자동 보강)
    cs_db_context = _fetch_cs_history_context(query)
    if cs_db_context:
        merged_context = merged_context + "\n\n" + cs_db_context

    # 최상위 소스 (엔티티 첫 번째)
    best_source = rag_results[0] if rag_results else None

    # 5단계: PDF 자동 추출 (엔티티 속성에 source_file + page가 있는 경우)
    pdf_info = _extract_pdf_if_available(rag_results)

    return {
        "session_hit": session_hit,
        "graph_result": graph_result,
        "rag_results": rag_results,
        "needs_dbmanager": needs_dbmanager,
        "merged_context": merged_context,
        "best_source": best_source,
        "pdf_info": pdf_info,
        "rag_source": rag_source,
        "cs_db_context": cs_db_context,
    }


def run_with_dbmanager_context(query: str, dbmanager_text: str) -> dict:
    """
    db-manager 폴백 결과까지 포함한 최종 파이프라인.
    db-manager 응답 수신 후 호출.
    """
    from cs_rag_search import merge_results

    pipeline = run(query)
    if dbmanager_text:
        pipeline["merged_context"] = merge_results(
            pipeline["graph_result"], dbmanager_text
        )
    pipeline["dbmanager_text"] = dbmanager_text
    return pipeline


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "query argument required"}, ensure_ascii=False))
        sys.exit(1)

    query = sys.argv[1]
    result = run(query)
    print(json.dumps(result, ensure_ascii=False, indent=2))
