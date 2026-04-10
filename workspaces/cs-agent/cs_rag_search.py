"""
CS RAG 검색 유틸리티 — Neo4j GraphRAG 단독 검색

2026-04-10 전환: pgvector 제거, Neo4j(bolt://localhost:7688) 단독 사용.
운영 후 품질 이슈 발생 시에만 pgvector와 하이브리드화 재검토.

사용법:
  from cs_rag_search import search_with_pipeline

  result = search_with_pipeline("파나소닉 A6B Pr4.39 브레이크 해제 속도")
  # result["rag_results"] → Neo4j 엔티티/관계 기반 결과
"""

import os
import re

# ── Neo4j 연결 설정 (dashboard와 동일) ──
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7688")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASS", "WtaPoc2026!Graph")

# ── GraphRAG 충분성 판정 기준 ──
GRAPH_MIN_NODES = 1       # 최소 엔티티 수
GRAPH_MIN_RELS = 0        # 최소 관계 수 (엔티티만 있어도 OK)


def _neo4j_query(cypher: str, params: dict | None = None) -> tuple[list[dict] | None, str | None]:
    """Neo4j Bolt로 Cypher 실행. (records, error) 반환."""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        return None, "neo4j 드라이버 미설치 (pip install neo4j)"
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
        with driver.session() as session:
            result = session.run(cypher, params or {})
            records = [dict(r) for r in result]
        driver.close()
        return records, None
    except Exception as e:
        return None, str(e)


def _extract_keywords(query: str) -> list[str]:
    """질문에서 검색 키워드 추출 (2글자 이상 단어).
    한글/영문/숫자 토큰 분리. 불용어 간단 제거."""
    stopwords = {"어떻게", "무엇", "뭐야", "뭔가요", "알려", "알려줘",
                 "방법", "어떤", "해줘", "해주세요", "입니다", "인가요",
                 "있나요", "있어", "나요", "해야", "하나요"}
    tokens = re.findall(r"[A-Za-z0-9가-힣]+", query)
    kws = [t for t in tokens if len(t) >= 2 and t not in stopwords]
    # 중복 제거 (순서 유지)
    seen = set()
    uniq = []
    for k in kws:
        if k not in seen:
            seen.add(k)
            uniq.append(k)
    return uniq


def search_graph(query: str, top_k: int = 10) -> dict:
    """
    Neo4j GraphRAG 키워드 검색.

    반환:
    {
        "nodes": [{"id","labels","name","properties"}...],
        "relationships": [{"id","type","start","end"}...],
        "node_count": int,
        "rel_count": int,
        "keywords": [...],
    }
    """
    keywords = _extract_keywords(query)
    if not keywords:
        return {"nodes": [], "relationships": [], "node_count": 0,
                "rel_count": 0, "keywords": []}

    # toLower CONTAINS OR 조건 (대시보드 /api/search/hybrid와 동일 방식)
    where_clauses = " OR ".join(
        [f"toLower(n.name) CONTAINS toLower($kw{i})" for i in range(len(keywords))]
    )
    params: dict = {f"kw{i}": kw for i, kw in enumerate(keywords)}
    params["lim"] = top_k

    cypher = f"""
        MATCH (n)
        WHERE {where_clauses}
        WITH n LIMIT $lim
        OPTIONAL MATCH (n)-[r]-(m)
        RETURN n, r, m
        LIMIT 200
    """
    records, err = _neo4j_query(cypher, params)
    if err or not records:
        return {"nodes": [], "relationships": [], "node_count": 0,
                "rel_count": 0, "keywords": keywords, "error": err}

    seen_nodes: dict[str, dict] = {}
    seen_rels: dict[str, dict] = {}

    for rec in records:
        # 원본 매칭 노드 n은 항상 포함
        for key in ["n", "m"]:
            node = rec.get(key)
            if node is None or not hasattr(node, "element_id"):
                continue
            nid = str(node.element_id)
            if nid not in seen_nodes:
                props = dict(node)
                labels = list(node.labels) if hasattr(node, "labels") else []
                seen_nodes[nid] = {
                    "id": nid,
                    "labels": labels,
                    "name": props.get("name", ""),
                    "properties": {k: str(v)[:300] for k, v in props.items()},
                }

        rel = rec.get("r")
        if rel is not None and hasattr(rel, "element_id"):
            rid = str(rel.element_id)
            if rid not in seen_rels:
                try:
                    seen_rels[rid] = {
                        "id": rid,
                        "type": rel.type,
                        "start": str(rel.start_node.element_id),
                        "end": str(rel.end_node.element_id),
                    }
                except Exception:
                    pass

    return {
        "nodes": list(seen_nodes.values()),
        "relationships": list(seen_rels.values()),
        "node_count": len(seen_nodes),
        "rel_count": len(seen_rels),
        "keywords": keywords,
    }


def is_sufficient(graph_result: dict) -> bool:
    """GraphRAG 결과가 충분한지 판단.

    기준: 매칭된 노드 수 >= GRAPH_MIN_NODES
    """
    return graph_result.get("node_count", 0) >= GRAPH_MIN_NODES


def format_graph_context(graph_result: dict) -> str:
    """
    Neo4j 검색 결과를 LLM 프롬프트용 컨텍스트 텍스트로 포맷팅.
    """
    nodes = graph_result.get("nodes", [])
    rels = graph_result.get("relationships", [])

    if not nodes:
        return "=== [GraphRAG: 관련 엔티티 없음] ==="

    lines = ["=== [GraphRAG 검색 결과] ==="]
    lines.append(f"키워드: {', '.join(graph_result.get('keywords', []))}")
    lines.append(f"엔티티 {len(nodes)}개, 관계 {len(rels)}개\n")

    # 노드 상세 (최대 20개)
    lines.append("## 관련 엔티티")
    for i, n in enumerate(nodes[:20], 1):
        labels = ",".join(n.get("labels", []))
        name = n.get("name", "")
        props = n.get("properties", {})
        desc = props.get("description", "") or props.get("content", "") or ""
        line = f"{i}. [{labels}] {name}"
        if desc:
            line += f"\n   {desc[:200]}"
        lines.append(line)

    # 관계 요약 (최대 20개)
    if rels:
        lines.append("\n## 관계")
        node_map = {n["id"]: n.get("name", n["id"][:8]) for n in nodes}
        for i, r in enumerate(rels[:20], 1):
            s_name = node_map.get(r.get("start", ""), "?")
            e_name = node_map.get(r.get("end", ""), "?")
            lines.append(f"{i}. {s_name} --[{r.get('type','')}]--> {e_name}")

    return "\n".join(lines)


def merge_results(graph_result: dict, db_manager_text: str) -> str:
    """GraphRAG + db-manager 폴백 텍스트를 합산 컨텍스트로 포맷팅."""
    parts = [format_graph_context(graph_result)]
    if db_manager_text:
        parts.append("\n\n=== [db-manager 보조 결과] ===")
        parts.append(db_manager_text)
    return "\n".join(parts)


def search_with_pipeline(query: str, top_k: int = 10) -> dict:
    """
    CS 검색 파이프라인 (GraphRAG 단독):
    1. 이전 세션 텍스트 매칭 (cs-sessions.jsonl)
    2. Neo4j GraphRAG 검색
    3. 결과 부족 시 db-manager 폴백 필요 여부 반환

    반환:
    {
        "session_hit": dict | None,
        "graph_result": dict,         # Neo4j 검색 결과 (nodes/rels)
        "rag_results": list[dict],    # 기존 호환: graph 엔티티를 flat list로 노출
        "needs_dbmanager": bool,
        "merged_context": str,
        "rag_source": "graph",        # 로깅용
    }
    """
    from cs_pdf_cache import lookup_session

    # 1단계: 이전 세션 매칭
    session_hit = lookup_session(query)

    # 2단계: GraphRAG
    graph_result = search_graph(query, top_k=top_k)

    # 3단계: 충분성 판정 → db-manager 폴백
    needs_dbmanager = not is_sufficient(graph_result)

    # 컨텍스트 포맷팅
    merged = format_graph_context(graph_result)

    # 기존 호환 rag_results: 노드를 flat list로 변환
    rag_results = []
    for n in graph_result.get("nodes", [])[:top_k]:
        props = n.get("properties", {})
        rag_results.append({
            "content": props.get("description", "") or props.get("content", "") or n.get("name", ""),
            "source_file": props.get("source_file", "") or props.get("source", ""),
            "score": 1.0,  # GraphRAG는 유사도 점수 없음 (매칭 여부만)
            "labels": n.get("labels", []),
            "name": n.get("name", ""),
            "properties": props,
        })

    return {
        "session_hit": session_hit,
        "graph_result": graph_result,
        "rag_results": rag_results,
        "needs_dbmanager": needs_dbmanager,
        "merged_context": merged,
        "rag_source": "graph",
    }


# ── 레거시 호환: 기존 search_rag 호출부가 있을 수 있음 ──
def search_rag(query: str, top_k: int = 5) -> list[dict]:
    """레거시 호환. GraphRAG 결과의 flat list 반환."""
    result = search_with_pipeline(query, top_k=top_k)
    return result["rag_results"]


if __name__ == "__main__":
    import sys
    import json as _json

    q = sys.argv[1] if len(sys.argv) > 1 else "디버링 설정 변경 방법"
    print(f"[TEST] query: {q}")
    result = search_with_pipeline(q)
    print(_json.dumps({
        "node_count": result["graph_result"]["node_count"],
        "rel_count": result["graph_result"]["rel_count"],
        "keywords": result["graph_result"].get("keywords", []),
        "needs_dbmanager": result["needs_dbmanager"],
        "rag_source": result["rag_source"],
    }, ensure_ascii=False, indent=2))
    print("\n--- merged_context ---")
    print(result["merged_context"][:1500])
