"""
Ollama Phase 2 추출 결과 → Neo4j 적재
- parallel-results-qwen35-35b-a3b/all_results.json (25페이지 성공)
- parallel-results-qwen35-35b-a3b/retry_results.json (6페이지 재처리)
- 라벨: PhaseOllama
"""
import sys, json, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from neo4j import GraphDatabase
from collections import Counter

BASE_DIR = Path("C:/MES/wta-agents/workspaces/research-agent")
OUT_DIR = BASE_DIR / "parallel-results-qwen35-35b-a3b"

_env = BASE_DIR / "neo4j-poc.env"
NEO4J_PASS = ""
for line in _env.read_text().splitlines():
    if line.startswith("NEO4J_AUTH=neo4j/"):
        NEO4J_PASS = line.split("/", 1)[1].strip(); break

NEO4J_URI = "bolt://localhost:7688"
NEO4J_USER = "neo4j"

VALID_NODE_TYPES = {"Customer","Equipment","Product","Component","Process","Issue","Resolution","Person","Tool"}
VALID_REL_TYPES = {"OWNS","HAS_ISSUE","SIMILAR_TO","RESOLVED_BY","INVOLVES_COMPONENT","USES_COMPONENT","INVOLVED_IN","HAS_SUBPROCESS","USES_TOOL","MAINTAINS"}


def sanitize_id(raw_id: str, topic: str, idx: int) -> str:
    prefix = re.sub(r'[^a-z0-9]', '_', topic.lower())[:8]
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', raw_id)
    return f"ollama_{prefix}_{idx}_{safe}"


def load_pages() -> list:
    pages = json.loads((OUT_DIR / "all_results.json").read_text("utf-8"))
    retry_path = OUT_DIR / "retry_results.json"
    if retry_path.exists():
        retry = json.loads(retry_path.read_text("utf-8"))
        pages.extend(retry)
        print(f"기본 {len(pages)-len(retry)}페이지 + 재처리 {len(retry)}페이지 = 총 {len(pages)}페이지")
    else:
        print(f"기본 {len(pages)}페이지 (retry 없음)")
    return pages


def load_to_neo4j(pages: list):
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    total_nodes, total_rels, errors = 0, 0, 0
    type_counts = Counter()

    with driver.session() as s:
        s.run("MATCH (n:PhaseOllama) DETACH DELETE n")
        print("기존 PhaseOllama 노드 정리 완료")

        for page_idx, page in enumerate(pages):
            topic = page.get("topic", "unknown")
            title = page.get("title", "")
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
                props["_title"] = title
                props["_source"] = "ollama_qwen35_35b_a3b"
                name = ent.get("name", orig_id)
                try:
                    s.run(
                        f"MERGE (n:PhaseOllama:{ent_type} {{_id: $_id}}) SET n += $props, n.name = $name",
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
                        f"MATCH (a:PhaseOllama {{_id: $fid}}) MATCH (b:PhaseOllama {{_id: $tid}}) MERGE (a)-[r:{rel_type}]->(b)",
                        fid=from_id, tid=to_id
                    )
                    total_rels += 1
                except Exception:
                    errors += 1

    driver.close()
    return total_nodes, total_rels, errors, dict(type_counts)


def print_summary():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    with driver.session() as s:
        labels = ["Phase2", "Phase3", "PhaseOllama"]
        print("\n=== Neo4j 전체 현황 ===")
        for lbl in labels:
            try:
                n = s.run(f"MATCH (n:{lbl}) RETURN count(n) AS c").single()["c"]
                r = s.run(f"MATCH (:{lbl})-[rel]->(:{lbl}) RETURN count(rel) AS c").single()["c"]
                print(f"  {lbl:15s}: 노드 {n:4d} / 관계 {r:4d}")
            except Exception:
                pass
        total = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        print(f"  {'전체':15s}: 노드 {total:4d}")
    driver.close()


if __name__ == "__main__":
    print("=== Ollama Phase 2 결과 Neo4j 적재 ===\n")
    pages = load_pages()
    nodes, rels, errs, type_dist = load_to_neo4j(pages)
    print(f"\n적재 완료: 노드 {nodes}개, 관계 {rels}개, 오류 {errs}개")
    print(f"타입별: {dict(sorted(type_dist.items(), key=lambda x: -x[1]))}")
    print_summary()
