"""
manuals-v2 PoC10 GraphRAG 파이프라인 (issue-manager 운영)

목적
    reports/manuals-v2/poc/{file_id}/chunks.jsonl 의 사전 청크된 텍스트를
    qwen3.5:35b-a3b 로 엔티티/관계 추출 → Neo4j(bolt://localhost:7688) 에
    :ManualV2_PoC10_ISSUE 레이블로 MERGE 적재. 기존 Phase* PoC 노드와 완전 분리.

참조 파이프라인
    workspaces/db-manager/cm-graphrag-pipeline.py  (Phase4_CM 패턴)
    workspaces/db-manager/manual-graphrag-test.py  (Phase5_Manual 패턴)

실행
    python graphrag_poc10_pipeline.py --dry 1_robot_2d70fa79608e 1_robot_54fdb56329f0
    python graphrag_poc10_pipeline.py --only 1_robot_2d70fa79608e 1_robot_54fdb56329f0
    python graphrag_poc10_pipeline.py                         # PoC10 전체, 작은 순
    python graphrag_poc10_pipeline.py --max-windows 20        # 파일당 윈도우 상한

교차검증 고정 조건 (qa-agent 와 동일)
    - 입력    : reports/manuals-v2/poc/{file_id}/chunks.jsonl (PoC10)
    - LLM     : qwen3.5:35b-a3b, temperature=0
    - 윈도우  : 2000자 (concat 후 2000자 슬라이딩, overlap 0)
    - 스키마  : 10 node type / 11 rel type (cm-graphrag-pipeline 그대로)
    - 속성    : _id, _source_id, _run_id, _corpus='manuals_v2', _lang
    - 레이블  : ManualV2_PoC10_ISSUE  (qa-agent는 ManualV2_PoC10_QA)

체크포인트
    reports/manuals-v2/work/graphrag_poc10_state.json  (file_id × window_idx)
    reports/manuals-v2/work/graphrag_poc10.log
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 경로 ────────────────────────────────────────────────────────────────
REPO = Path("C:/MES/wta-agents")
POC_DIR = REPO / "reports" / "manuals-v2" / "poc"
REPORTS = REPO / "reports" / "manuals-v2"
WORK_DIR = REPORTS / "work"
STATE_PATH = WORK_DIR / "graphrag_poc10_issue_state.json"
LOG_PATH = WORK_DIR / "graphrag_poc10_issue.log"
REPROCESS_STATE = REPORTS / "legacy" / "manuals_v2_reprocess_state.json"
NEO4J_ENV = REPO / "workspaces" / "research-agent" / "neo4j-poc.env"

WORK_DIR.mkdir(parents=True, exist_ok=True)

# ── 모델/서버 ───────────────────────────────────────────────────────────
OLLAMA_BASE = "http://182.224.6.147:11434"
EXTRACT_MODEL = "qwen3.5:35b-a3b"
WINDOW_SIZE = 2000
NEO4J_URI = "bolt://localhost:7688"
TEAM_LABEL = "ManualsV2_PoC10_ISSUE"      # MAX 지정 — qa-agent는 _QA
BASE_LABEL = "ManualsV2Entity"            # 스킬 M10 — 공용 manuals-v2 라벨
ID_PREFIX = "mv2i"
TEAM_NAME = "issue-manager"

# cm-graphrag-pipeline 기본 10/11 + 확정판 Step 5B Figure/Table/Diagram 추가
VALID_NODE_TYPES = {
    "Customer", "Equipment", "Product", "Component", "Process",
    "Issue", "Resolution", "Person", "Tool", "Manual",
    "Figure", "Table", "Diagram",
}
VALID_REL_TYPES = {
    "OWNS", "HAS_ISSUE", "SIMILAR_TO", "RESOLVED_BY",
    "INVOLVES_COMPONENT", "USES_COMPONENT", "INVOLVED_IN",
    "HAS_SUBPROCESS", "USES_TOOL", "MAINTAINS", "DOCUMENTS",
    "BELONGS_TO", "REFERENCES", "DEPICTS",
}

KST = timezone(timedelta(hours=9))

# ── 로깅 ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[graphrag-poc10] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
)
log = logging.getLogger("graphrag-poc10")


# ── 유틸 ────────────────────────────────────────────────────────────────
def now_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


def load_neo4j_password() -> str:
    for raw in NEO4J_ENV.read_text(encoding="utf-8").splitlines():
        if raw.startswith("NEO4J_AUTH=neo4j/"):
            return raw.split("/", 1)[1].strip()
    raise RuntimeError("NEO4J_AUTH missing")


def load_poc10_ids() -> list[str]:
    data = json.loads(REPROCESS_STATE.read_text(encoding="utf-8"))
    return [it["id"] for it in data.get("items", [])]


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {
        "task_id": "tq-issue-manager-d3fe53",
        "team": TEAM_NAME,
        "team_label": TEAM_LABEL,
        "base_label": BASE_LABEL,
        "model": EXTRACT_MODEL,
        "window_size": WINDOW_SIZE,
        "created_at": now_kst(),
        "items": {},
    }


def save_state(state: dict) -> None:
    state["last_update"] = now_kst()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_id(raw: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", raw)[:80]


# ── chunks.jsonl 로더 + 윈도우 생성 ───────────────────────────────────────
def read_chunks(file_id: str) -> tuple[str, list[dict]]:
    path = POC_DIR / file_id / "chunks.jsonl"
    if not path.exists():
        raise FileNotFoundError(path)
    items: list[dict] = []
    with path.open(encoding="utf-8") as fp:
        for line in fp:
            obj = json.loads(line)
            text = (obj.get("content") or obj.get("text") or "").strip()
            if not text:
                continue
            items.append({
                "chunk_id": obj.get("chunk_id", ""),
                "lang": obj.get("lang", "unknown"),
                "section_path": obj.get("section_path", ""),
                "text": text,
            })
    langs = [it["lang"] for it in items if it["lang"]]
    lang = max(set(langs), key=langs.count) if langs else "unknown"
    return lang, items


def build_windows(chunks: list[dict], size: int) -> list[dict]:
    """청크 순서대로 이어 붙여 2000자 윈도우로 분할"""
    windows: list[dict] = []
    buf: list[str] = []
    buf_ids: list[str] = []
    buf_len = 0
    for ch in chunks:
        text = ch["text"]
        if buf_len + len(text) + 2 > size and buf:
            windows.append({
                "idx": len(windows),
                "text": "\n\n".join(buf)[:size],
                "chunk_ids": buf_ids.copy(),
            })
            buf.clear()
            buf_ids.clear()
            buf_len = 0
        buf.append(text)
        buf_ids.append(ch["chunk_id"])
        buf_len += len(text) + 2
    if buf:
        windows.append({
            "idx": len(windows),
            "text": "\n\n".join(buf)[:size],
            "chunk_ids": buf_ids.copy(),
        })
    return windows


# ── LLM 엔티티 추출 ─────────────────────────────────────────────────────
EXTRACT_PROMPT = """다음 기술 문서에서 엔티티와 관계를 추출하세요.

엔티티 타입: Equipment(장비), Component(부품), Process(공정/작업), Issue(문제/이슈), Person(담당자), Customer(고객사), Manual(매뉴얼), Product(제품), Resolution(조치), Tool(공구), Figure(그림), Table(표), Diagram(도식)
관계 타입: OWNS, HAS_ISSUE, SIMILAR_TO, RESOLVED_BY, INVOLVES_COMPONENT, USES_COMPONENT, INVOLVED_IN, HAS_SUBPROCESS, USES_TOOL, MAINTAINS, DOCUMENTS, BELONGS_TO, REFERENCES, DEPICTS

JSON 형식으로만 응답하세요:
{
  "entities": [{"id":"eng_id","name":"한국어명","type":"Equipment","properties":{}}],
  "relations": [{"source":"id1","target":"id2","type":"USES_COMPONENT"}]
}

문서:
"""


def extract_entities(text: str, title: str) -> dict:
    if len(text) < 50:
        return {"entities": [], "relations": []}
    prompt = EXTRACT_PROMPT + f"제목: {title}\n\n{text[:WINDOW_SIZE]}"
    try:
        r = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={
                "model": EXTRACT_MODEL,
                "prompt": prompt,
                "stream": False,
                "think": False,   # qwen3.5:35b-a3b 사고모드 비활성화 (num_predict 절약, 재현성↑)
                "options": {"num_predict": 2048, "temperature": 0.0},
            },
            timeout=300,
        )
        if r.status_code != 200:
            log.warning(f"LLM HTTP {r.status_code}")
            return {"entities": [], "relations": []}
        raw = r.json().get("response", "").strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {"entities": [], "relations": []}
        return json.loads(match.group())
    except Exception as exc:
        log.warning(f"extract error [{title[:30]}]: {exc}")
        return {"entities": [], "relations": []}


# ── Neo4j 적재 ──────────────────────────────────────────────────────────
def load_to_neo4j(driver, file_id: str, window_idx: int, lang: str,
                  run_id: str, extracted: dict) -> tuple[int, int]:
    entities = extracted.get("entities") or []
    relations = extracted.get("relations") or []
    if not entities:
        return 0, 0

    id_map: dict[str, str] = {}
    node_count = 0
    rel_count = 0
    fid_key = safe_id(file_id)

    with driver.session() as s:
        for ent in entities:
            etype = (ent.get("type") or "").strip()
            if etype not in VALID_NODE_TYPES:
                continue
            orig_id = (ent.get("id") or "").strip()
            if not orig_id:
                continue
            sid = f"{ID_PREFIX}_{fid_key}_{safe_id(orig_id)}"
            id_map[orig_id] = sid
            props = {
                k: v for k, v in (ent.get("properties") or {}).items()
                if v not in (None, "")
            }
            props.update({
                "_id": sid,
                "_source_id": file_id,
                "_run_id": run_id,
                "_corpus": "manuals_v2",
                "source": "manuals_v2",          # 스킬 M10 alias
                "_team": TEAM_NAME,
                "_lang": lang,
                "_window_idx": window_idx,
            })
            try:
                s.run(
                    f"MERGE (n:{BASE_LABEL}:{TEAM_LABEL}:{etype} {{_id: $_id}}) "
                    f"SET n += $props, n.name = $name",
                    _id=sid, props=props, name=ent.get("name") or orig_id,
                )
                node_count += 1
            except Exception as exc:
                log.debug(f"node merge fail: {exc}")

        for rel in relations:
            src = id_map.get((rel.get("source") or "").strip())
            tgt = id_map.get((rel.get("target") or "").strip())
            rtype = (rel.get("type") or "").strip()
            if not src or not tgt or rtype not in VALID_REL_TYPES:
                continue
            try:
                s.run(
                    f"MATCH (a:{TEAM_LABEL} {{_id: $src}}), "
                    f"(b:{TEAM_LABEL} {{_id: $tgt}}) "
                    f"MERGE (a)-[r:{rtype}]->(b) "
                    f"SET r._run_id=$rid, r._team=$team, r._source_id=$fid",
                    src=src, tgt=tgt, rid=run_id, team=TEAM_NAME, fid=file_id,
                )
                rel_count += 1
            except Exception as exc:
                log.debug(f"rel merge fail: {exc}")

    return node_count, rel_count


def count_label(driver, file_id: str | None = None) -> dict:
    q_nodes = f"MATCH (n:{TEAM_LABEL}) RETURN count(n) AS c"
    q_rels = (f"MATCH (a:{TEAM_LABEL})-[r]->(b:{TEAM_LABEL}) "
              f"RETURN count(r) AS c")
    out: dict = {}
    with driver.session() as s:
        out["total_nodes"] = s.run(q_nodes).single()["c"]
        out["total_rels"] = s.run(q_rels).single()["c"]
        if file_id:
            out["file_nodes"] = s.run(
                f"MATCH (n:{TEAM_LABEL}) WHERE n._source_id=$fid RETURN count(n) AS c",
                fid=file_id,
            ).single()["c"]
    return out


# ── 메인 ────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="특정 file_id만")
    parser.add_argument("--dry", nargs="*", help="인덱싱 없이 윈도우 생성만")
    parser.add_argument("--max-windows", type=int, default=None)
    parser.add_argument("--skip-huge", action="store_true",
                        help="1000청크 초과 파일 제외")
    args = parser.parse_args()

    log.info(
        f"=== graphrag_poc10_pipeline start model={EXTRACT_MODEL} "
        f"base={BASE_LABEL} team={TEAM_LABEL} ==="
    )
    dry_targets = args.dry
    targets = args.only or dry_targets or load_poc10_ids()

    inventory: list[tuple[str, int, int, str]] = []
    for fid in targets:
        try:
            lang, chunks = read_chunks(fid)
        except FileNotFoundError:
            log.warning(f"SKIP {fid}: chunks.jsonl missing")
            continue
        wins = build_windows(chunks, WINDOW_SIZE)
        if args.skip_huge and len(chunks) > 1000:
            log.info(f"SKIP {fid}: {len(chunks)} chunks (>1000)")
            continue
        if args.max_windows:
            wins = wins[: args.max_windows]
        inventory.append((fid, len(chunks), len(wins), lang))
    inventory.sort(key=lambda x: x[1])

    log.info(f"queue: {len(inventory)} file_ids")
    for fid, nc, nw, lang in inventory:
        log.info(f"  {fid}  chunks={nc}  windows={nw}  lang={lang}")

    if dry_targets is not None:
        log.info("dry run, no LLM/Neo4j")
        return

    # 연결
    from neo4j import GraphDatabase
    pw = load_neo4j_password()
    driver = GraphDatabase.driver(NEO4J_URI, auth=("neo4j", pw))
    driver.verify_connectivity()
    log.info(f"neo4j pre-state: {count_label(driver)}")

    run_id = f"run-{datetime.now(KST).strftime('%Y%m%d-%H%M%S')}"
    state = load_state()
    state["run_id"] = run_id
    save_state(state)

    for fid, n_chunks, n_windows, lang in inventory:
        item = state["items"].setdefault(fid, {
            "status": "pending", "done_windows": [], "nodes": 0, "rels": 0,
        })
        if item["status"] == "done":
            log.info(f"SKIP {fid}: already done")
            continue
        item["status"] = "running"
        item["n_chunks"] = n_chunks
        item["n_windows"] = n_windows
        item["lang"] = lang
        item.setdefault("started_at", now_kst())
        save_state(state)

        lang2, chunks = read_chunks(fid)
        windows = build_windows(chunks, WINDOW_SIZE)
        if args.max_windows:
            windows = windows[: args.max_windows]

        t0 = time.time()
        done_set = set(item.get("done_windows", []))
        nodes_sum = item.get("nodes", 0)
        rels_sum = item.get("rels", 0)
        title = f"{fid} ({lang})"
        for win in windows:
            if win["idx"] in done_set:
                continue
            extracted = extract_entities(win["text"], title)
            n, r = load_to_neo4j(driver, fid, win["idx"], lang, run_id, extracted)
            nodes_sum += n
            rels_sum += r
            done_set.add(win["idx"])
            item["done_windows"] = sorted(done_set)
            item["nodes"] = nodes_sum
            item["rels"] = rels_sum
            save_state(state)
            if win["idx"] % 5 == 0 or win["idx"] == len(windows) - 1:
                log.info(
                    f"  {fid} win {win['idx']+1}/{len(windows)} "
                    f"nodes+={n} rels+={r} total={nodes_sum}/{rels_sum}"
                )

        item.update(
            status="done",
            elapsed_sec=round(time.time() - t0, 1),
            ended_at=now_kst(),
        )
        save_state(state)
        log.info(
            f"DONE {fid} elapsed={item['elapsed_sec']}s "
            f"nodes={nodes_sum} rels={rels_sum}"
        )

    state["status"] = "done" if all(
        v["status"] == "done" for v in state["items"].values()
    ) else "partial"
    save_state(state)
    log.info(f"neo4j post-state: {count_label(driver)}")
    log.info(f"=== graphrag_poc10_pipeline end status={state['status']} ===")
    driver.close()


if __name__ == "__main__":
    main()
