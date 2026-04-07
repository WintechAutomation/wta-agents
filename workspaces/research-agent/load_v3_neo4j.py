"""
Phase 3 Step 2: v3 추출 결과 Neo4j 적재 (Phase3 라벨)
기존 Phase2 유지, Phase3 라벨로 별도 추가
"""
import sys, json, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from neo4j import GraphDatabase
from collections import Counter

_env = Path("C:/MES/wta-agents/workspaces/research-agent/neo4j-poc.env")
NEO4J_PASS = ""
for line in _env.read_text().splitlines():
    if line.startswith("NEO4J_AUTH=neo4j/"):
        NEO4J_PASS = line.split("/", 1)[1].strip(); break

VALID_NODE_TYPES = {"Customer","Equipment","Product","Component","Process","Issue","Resolution","Person","Tool"}
VALID_REL_TYPES = {"OWNS","HAS_ISSUE","SIMILAR_TO","RESOLVED_BY","INVOLVES_COMPONENT","USES_COMPONENT","INVOLVED_IN","HAS_SUBPROCESS","USES_TOOL","MAINTAINS"}


def sanitize_id(raw_id: str, topic: str, idx: int) -> str:
    prefix = re.sub(r'[^a-z0-9]', '_', topic.lower())[:8]
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', raw_id)
    return f"v3_{prefix}_{idx}_{safe}"


def load_v3_to_neo4j(pages: list):
    driver = GraphDatabase.driver("bolt://localhost:7688", auth=("neo4j", NEO4J_PASS))
    total_nodes, total_rels, errors = 0, 0, 0
    type_counts = Counter()

    with driver.session() as s:
        s.run("MATCH (n:Phase3) DETACH DELETE n")
        print("기존 Phase3 노드 정리 완료")

        for page_idx, page in enumerate(pages):
            topic = page.get("topic", "unknown")
            filename = page.get("file", "")
            entities = page.get("extracted", {}).get("entities", [])
            relations = page.get("extracted", {}).get("relations", [])

            id_map = {}
            for ent in entities:
                ent_type = ent.get("type", "")
                if ent_type not in VALID_NODE_TYPES:
                    continue
                orig_id = ent.get("id", "")
                if not orig_id:
                    continue
                neo4j_id = sanitize_id(orig_id, topic, page_idx)
                id_map[orig_id] = neo4j_id
                props = {k: v for k, v in (ent.get("properties", {}) or {}).items() if v is not None and v != ""}
                props["_id"] = neo4j_id
                props["_topic"] = topic
                props["_file"] = filename
                name = ent.get("name", orig_id)
                try:
                    s.run(
                        f"MERGE (n:Phase3:{ent_type} {{_id: $_id}}) SET n += $props, n.name = $name",
                        _id=neo4j_id, props=props, name=name
                    )
                    total_nodes += 1
                    type_counts[ent_type] += 1
                except Exception as e:
                    errors += 1

            for rel in relations:
                rel_type = rel.get("type", "")
                if rel_type not in VALID_REL_TYPES:
                    continue
                from_id = id_map.get(rel.get("from_id", ""))
                to_id = id_map.get(rel.get("to_id", ""))
                if not from_id or not to_id:
                    continue
                try:
                    s.run(
                        f"MATCH (a:Phase3 {{_id: $from_id}}) MATCH (b:Phase3 {{_id: $to_id}}) MERGE (a)-[r:{rel_type}]->(b)",
                        from_id=from_id, to_id=to_id
                    )
                    total_rels += 1
                except Exception:
                    errors += 1

    driver.close()
    return total_nodes, total_rels, errors, dict(type_counts)


def compare_v2_v3():
    """Phase2 vs Phase3 통계 비교"""
    driver = GraphDatabase.driver("bolt://localhost:7688", auth=("neo4j", NEO4J_PASS))
    with driver.session() as s:
        p2_n = s.run("MATCH (n:Phase2) RETURN count(n) AS c").single()["c"]
        p2_r = s.run("MATCH (:Phase2)-[r]->(:Phase2) RETURN count(r) AS c").single()["c"]
        p3_n = s.run("MATCH (n:Phase3) RETURN count(n) AS c").single()["c"]
        p3_r = s.run("MATCH (:Phase3)-[r]->(:Phase3) RETURN count(r) AS c").single()["c"]

        # Phase3 Resolution 수
        p3_res = s.run("MATCH (n:Phase3:Resolution) RETURN count(n) AS c").single()["c"]
        p2_res = s.run("MATCH (n:Phase2:Resolution) RETURN count(n) AS c").single()["c"]
        # Phase3 Component 수
        p3_comp = s.run("MATCH (n:Phase3:Component) RETURN count(n) AS c").single()["c"]
        p2_comp = s.run("MATCH (n:Phase2:Component) RETURN count(n) AS c").single()["c"]
    driver.close()
    return {
        "phase2": {"nodes": p2_n, "rels": p2_r, "resolution": p2_res, "component": p2_comp},
        "phase3": {"nodes": p3_n, "rels": p3_r, "resolution": p3_res, "component": p3_comp},
    }


if __name__ == "__main__":
    OUT_DIR = Path("C:/MES/wta-agents/workspaces/research-agent/claude-extract-results")
    v3_data = json.loads((OUT_DIR / "v3_all_results.json").read_text(encoding='utf-8'))
    pages = [r for r in v3_data["results"] if "error" not in r]
    print(f"=== Phase3 Neo4j 적재 ({len(pages)}페이지) ===\n")

    nodes, rels, errs, type_counts = load_v3_to_neo4j(pages)
    print(f"적재: 노드 {nodes}개, 관계 {rels}개, 오류 {errs}개")
    print(f"타입별: {type_counts}")

    print("\n=== Phase2 vs Phase3 비교 ===")
    cmp = compare_v2_v3()
    p2, p3 = cmp["phase2"], cmp["phase3"]
    print(f"{'항목':12s} {'Phase2(v1)':>12} {'Phase3(v3)':>12} {'증감':>8}")
    print("-" * 48)
    for key, label in [("nodes","노드"), ("rels","관계"), ("resolution","Resolution"), ("component","Component")]:
        diff = p3[key] - p2[key]
        sign = "+" if diff >= 0 else ""
        print(f"{label:12s} {p2[key]:>12} {p3[key]:>12} {sign+str(diff):>8}")
