"""
CS 자동 파이프라인 — 웹챗/슬랙 CS 질문 처리 단일 진입점

사용법:
  python cs_pipeline.py "질문 텍스트"

출력 (JSON):
  {
    "session_hit": {...} | null,     # 이전 세션 이력
    "rag_results": [...],            # RAG 검색 결과
    "needs_dbmanager": bool,         # db-manager 폴백 필요 여부
    "merged_context": str,           # 합산 컨텍스트 텍스트
    "best_source": {...} | null,     # 최고 점수 소스 (PDF 첨부용)
    "pdf_info": {...} | null         # PDF 추출 결과 (source_file + page 있을 때)
  }
"""

import sys
import json
import os

sys.path.insert(0, os.path.dirname(__file__))

from cs_rag_search import search_with_pipeline, is_sufficient
from cs_pdf_cache import get_or_extract_pdf_page, lookup_session_attachment


def _extract_pdf_if_available(rag_results: list[dict]) -> dict | None:
    """
    RAG 결과에서 source_file + page_number가 있는 최고 점수 결과의
    PDF를 추출(또는 캐시에서 로드)하여 반환.
    """
    for r in rag_results:
        source_file = r.get("source_file", "")
        page = r.get("page_number") or r.get("page")
        if not source_file or not page:
            continue

        # PDF 파일 경로 찾기 (db-manager 매뉴얼 저장 경로)
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
                    result["score"] = r.get("score", 0)
                    return result
                except Exception:
                    continue

    return None


def run(query: str) -> dict:
    """
    4단계 CS 파이프라인 실행:
    1. cs-sessions.jsonl 이전 이력 검색
    2. self RAG (pgvector 직접)
    3. db-manager 폴백 필요 여부 판단
    4. PDF 추출 가능 시 자동 처리
    """
    # 1단계 + 2단계: search_with_pipeline이 이전 세션 + RAG 통합 처리
    pipeline = search_with_pipeline(query)

    session_hit = pipeline["session_hit"]
    rag_results = pipeline["rag_results"]
    needs_dbmanager = pipeline["needs_dbmanager"]
    merged_context = pipeline["merged_context"]

    # 최고 점수 소스
    best_source = rag_results[0] if rag_results else None

    # 4단계: PDF 자동 추출 (source_file + page 있는 경우)
    pdf_info = _extract_pdf_if_available(rag_results)

    return {
        "session_hit": session_hit,
        "rag_results": rag_results,
        "needs_dbmanager": needs_dbmanager,
        "merged_context": merged_context,
        "best_source": best_source,
        "pdf_info": pdf_info,
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
            pipeline["rag_results"], dbmanager_text
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
