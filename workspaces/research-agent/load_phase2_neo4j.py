"""
Phase 3: Phase 2 추출 결과 전체 Neo4j 적재
- claude-extract-results/all_results.json (26페이지 성공분)
- claude-extract-results/chunk_retry_results.json (오류 4페이지 재처리)
- claude-extract-results/chunk_retry_honing_issue.json (호닝 제작 이슈)
총 31페이지 624 엔티티 / 533 관계
"""
import sys, json, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7688"
NEO4J_USER = "neo4j"
_env_file = Path("C:/MES/wta-agents/workspaces/research-agent/neo4j-poc.env")
NEO4J_PASS = ""
for _line in _env_file.read_text().splitlines():
    if _line.startswith("NEO4J_AUTH=neo4j/"):
        NEO4J_PASS = _line.split("/", 1)[1].strip()
        break

# 온톨로지 v1.1 허용 노드 유형
VALID_NODE_TYPES = {
    "Customer", "Equipment", "Product", "Component",
    "Process", "Issue", "Resolution", "Person", "Tool"
}

# 허용 관계 유형
VALID_REL_TYPES = {
    "OWNS", "HAS_ISSUE", "SIMILAR_TO", "RESOLVED_BY",
    "INVOLVES_COMPONENT", "USES_COMPONENT", "INVOLVED_IN",
    "HAS_SUBPROCESS", "USES_TOOL", "MAINTAINS"
}


def sanitize_id(raw_id: str, topic: str, page_idx: int) -> str:
    """중복 방지를 위해 topic + page_idx prefix 추가"""
    prefix = re.sub(r'[^a-z0-9]', '_', topic.lower())[:8]
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', raw_id)
    return f"{prefix}_{page_idx}_{safe}"


def load_results() -> list[dict]:
    """3개 결과 파일 통합 로드"""
    base = Path("C:/MES/wta-agents/workspaces/research-agent/claude-extract-results")
    all_data = json.loads((base / "all_results.json").read_text(encoding="utf-8"))
    retry_data = json.loads((base / "chunk_retry_results.json").read_text(encoding="utf-8"))
    honing_data = json.loads((base / "chunk_retry_honing_issue.json").read_text(encoding="utf-8"))

    pages = []

    # all_results: 성공분만
    for r in all_data["results"]:
        if "error" not in r:
            pages.append(r)

    # chunk_retry: 4개 성공분
    for r in retry_data["results"]:
        if "error" not in r and "extracted" in r:
            pages.append(r)

    # 호닝 제작 이슈 단일 파일
    if "error" not in honing_data and "extracted" in honing_data:
        pages.append(honing_data)

    print(f"로드된 페이지: {len(pages)}개")
    return pages


def load_to_neo4j(pages: list[dict]):
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    total_nodes = 0
    total_rels = 0
    errors = 0

    with driver.session() as session:
        # Phase2 라벨 노드 기존 데이터 정리 (재실행 시 중복 방지)
        session.run("MATCH (n:Phase2) DETACH DELETE n")
        print("기존 Phase2 노드 정리 완료")

        for page_idx, page in enumerate(pages):
            topic = page.get("topic", "unknown")
            filename = page.get("file", "")
            extracted = page.get("extracted", {})
            entities = extracted.get("entities", [])
            relations = extracted.get("relations", [])

            # 엔티티 → Neo4j 노드 생성
            id_map = {}  # original_id → neo4j_id
            for ent in entities:
                ent_type = ent.get("type", "")
                if ent_type not in VALID_NODE_TYPES:
                    continue
                orig_id = ent.get("id", "")
                if not orig_id:
                    continue
                neo4j_id = sanitize_id(orig_id, topic, page_idx)
                id_map[orig_id] = neo4j_id

                props = ent.get("properties", {}) or {}
                props = {k: v for k, v in props.items() if v is not None and v != ""}
                props["_id"] = neo4j_id
                props["_topic"] = topic
                props["_file"] = filename
                name = ent.get("name", orig_id)

                try:
                    session.run(
                        f"MERGE (n:Phase2:{ent_type} {{_id: $_id}}) "
                        f"SET n += $props, n.name = $name",
                        _id=neo4j_id, props=props, name=name
                    )
                    total_nodes += 1
                except Exception as e:
                    errors += 1
                    print(f"  노드 오류 [{ent_type}/{orig_id}]: {e}")

            # 관계 생성
            for rel in relations:
                rel_type = rel.get("type", "")
                if rel_type not in VALID_REL_TYPES:
                    continue
                from_orig = rel.get("from_id", "")
                to_orig = rel.get("to_id", "")
                from_id = id_map.get(from_orig)
                to_id = id_map.get(to_orig)
                if not from_id or not to_id:
                    continue
                try:
                    session.run(
                        f"MATCH (a:Phase2 {{_id: $from_id}}) "
                        f"MATCH (b:Phase2 {{_id: $to_id}}) "
                        f"MERGE (a)-[r:{rel_type}]->(b)",
                        from_id=from_id, to_id=to_id
                    )
                    total_rels += 1
                except Exception as e:
                    errors += 1
                    print(f"  관계 오류 [{rel_type}]: {e}")

    driver.close()
    return total_nodes, total_rels, errors


def verify_neo4j():
    """적재 결과 검증"""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    with driver.session() as session:
        node_count = session.run("MATCH (n:Phase2) RETURN count(n) AS c").single()["c"]
        rel_count = session.run("MATCH (:Phase2)-[r]->(:Phase2) RETURN count(r) AS c").single()["c"]
        labels = session.run(
            "MATCH (n:Phase2) RETURN DISTINCT labels(n) AS l"
        ).data()
        label_list = []
        for row in labels:
            for lbl in row["l"]:
                if lbl != "Phase2":
                    label_list.append(lbl)

        # 라벨별 노드 수
        label_counts = {}
        for lbl in set(label_list):
            cnt = session.run(f"MATCH (n:Phase2:{lbl}) RETURN count(n) AS c").single()["c"]
            label_counts[lbl] = cnt

    driver.close()
    return node_count, rel_count, label_counts


if __name__ == "__main__":
    print("=== Phase 3: Phase 2 결과 Neo4j 적재 ===\n")

    pages = load_results()
    total_entities = sum(len(p.get("extracted", {}).get("entities", [])) for p in pages)
    total_relations = sum(len(p.get("extracted", {}).get("relations", [])) for p in pages)
    print(f"입력 총계: 엔티티 {total_entities}개, 관계 {total_relations}개\n")

    print("Neo4j 적재 중...")
    nodes, rels, errs = load_to_neo4j(pages)
    print(f"\n적재 완료: 노드 {nodes}개, 관계 {rels}개, 오류 {errs}개")

    print("\n검증 중...")
    n_count, r_count, label_counts = verify_neo4j()
    print(f"Neo4j 확인: Phase2 노드 {n_count}개, 관계 {r_count}개")
    print(f"라벨별: {label_counts}")
