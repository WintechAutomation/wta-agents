"""
실패 6페이지 재처리: text[:2000]으로 입력 단축하여 JSON 초과 생성 방지
"""
import sys, json, re, time, urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

OLLAMA_BASE = "http://182.224.6.147:11434"
MODEL = "qwen3.5:35b-a3b"
BASE_DIR = Path("C:/MES/wta-agents/workspaces/research-agent")
DATA_DIR = BASE_DIR / "poc-texts-all"
OUT_DIR = BASE_DIR / "parallel-results-qwen35-35b-a3b"

FAILED_IDS = {
    "9463300099", "8316485870", "8517419053",
    "8081965089", "8138785229", "8315830532"
}

SYSTEM_PROMPT = """You are an expert at extracting knowledge graph entities and relations from Korean manufacturing technical documents.

## Ontology v1.1 Schema
Node Types (9): Customer, Equipment, Product, Component, Process, Issue, Resolution, Person, Tool
Relation Types (10): OWNS, HAS_ISSUE, SIMILAR_TO, RESOLVED_BY, INVOLVES_COMPONENT, USES_COMPONENT, INVOLVED_IN, HAS_SUBPROCESS, USES_TOOL, MAINTAINS

Rules:
1. Output ONLY pure JSON — no markdown, no explanation
2. Extract only explicitly stated content
3. from_id/to_id must match entity ids
4. Keep the list concise — extract only the most important entities (max 20)

Format: {"entities":[{"type":"NodeType","id":"id","name":"name","properties":{}}],"relations":[{"type":"REL_TYPE","from_id":"id","to_id":"id","properties":{}}]}"""


def call_ollama(text: str, page_title: str, timeout: int = 240) -> dict:
    user_prompt = f"Extract entities and relations from this manufacturing document.\n\nTitle: {page_title}\n---\n{text[:2000]}\n---\n\nOutput ONLY pure JSON (max 20 entities):"
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": SYSTEM_PROMPT + "\n\n" + user_prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 2048, "num_ctx": 6144}
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    elapsed = time.time() - t0
    raw = data["message"]["content"]
    raw_clean = re.sub(r'<think>[\s\S]*?</think>', '', raw).strip()
    raw_clean = re.sub(r'```json\s*|```\s*', '', raw_clean)
    json_match = re.search(r'\{[\s\S]*\}', raw_clean)
    if not json_match:
        raise ValueError(f"JSON not found. Raw: {raw[:200]}")
    extracted = json.loads(json_match.group())
    return {"extracted": extracted, "elapsed_sec": round(elapsed, 1)}


def process_page(args):
    page, idx, total = args
    page_id = page["page_id"]
    title = page["title"]
    topic = page["topic"]
    file_rel = page["file"]
    txt_path = DATA_DIR / file_rel
    if not txt_path.exists():
        return {"page_id": page_id, "error": "file_not_found", "idx": idx}
    text = txt_path.read_text(encoding="utf-8")
    try:
        result = call_ollama(text, title)
        e = len(result["extracted"].get("entities", []))
        r = len(result["extracted"].get("relations", []))
        print(f"  [{idx}/{total}] {title[:30]} → 엔티티 {e}, 관계 {r}, {result['elapsed_sec']}s")
        return {"page_id": page_id, "topic": topic, "title": title, "idx": idx, **result}
    except Exception as ex:
        print(f"  [{idx}/{total}] {title[:30]} → 오류: {ex}")
        return {"page_id": page_id, "title": title, "idx": idx, "error": str(ex)}


if __name__ == "__main__":
    index = json.loads((DATA_DIR / "_index.json").read_text(encoding="utf-8"))
    failed_pages = [p for p in index if p["page_id"] in FAILED_IDS]
    print(f"재처리 대상: {len(failed_pages)}페이지 (text[:2000], max 20 entities)")
    print(f"모델: {MODEL}\n")

    args_list = [(p, i+1, len(failed_pages)) for i, p in enumerate(failed_pages)]
    results, errors = [], []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(process_page, a): a for a in args_list}
        for future in as_completed(futures):
            r = future.result()
            if "error" in r:
                errors.append(r)
            else:
                results.append(r)

    results.sort(key=lambda x: x.get("idx", 0))

    retry_path = OUT_DIR / "retry_results.json"
    retry_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    if errors:
        (OUT_DIR / "retry_errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")

    total_e = sum(len(r["extracted"].get("entities", [])) for r in results)
    total_r = sum(len(r["extracted"].get("relations", [])) for r in results)
    print(f"\n완료: {len(results)}/{len(failed_pages)}성공 | 오류: {len(errors)}")
    print(f"추출: 엔티티 {total_e}, 관계 {total_r}")
    print(f"저장: {retry_path}")
