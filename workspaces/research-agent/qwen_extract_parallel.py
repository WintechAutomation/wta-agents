"""
GraphRAG Phase 2: 병렬 처리 추출 스크립트
- asyncio + ThreadPoolExecutor로 N개 동시 처리
- think:false로 reasoning 비활성화
- 모델명/병렬수 CLI 인자로 변경 가능
"""
import sys, os, json, re, time, urllib.request, argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OLLAMA_BASE = "http://182.224.6.147:11434"
BASE_DIR = Path("C:/MES/wta-agents/workspaces/research-agent")
DATA_DIR = BASE_DIR / "poc-texts-all"

SYSTEM_PROMPT = """You are an expert at extracting knowledge graph entities and relations from Korean manufacturing technical documents.

## Ontology v1.1 Schema
Node Types (9): Customer, Equipment, Product, Component, Process, Issue, Resolution, Person, Tool
Relation Types (10): OWNS, HAS_ISSUE, SIMILAR_TO, RESOLVED_BY, INVOLVES_COMPONENT, USES_COMPONENT, INVOLVED_IN, HAS_SUBPROCESS, USES_TOOL, MAINTAINS

Rules:
1. Output ONLY pure JSON — no markdown, no explanation
2. Extract only explicitly stated content
3. from_id/to_id must match entity ids

Format: {"entities":[{"type":"NodeType","id":"id","name":"name","properties":{}}],"relations":[{"type":"REL_TYPE","from_id":"id","to_id":"id","properties":{}}]}"""


def call_ollama(model: str, text: str, page_title: str, timeout: int = 300) -> dict:
    user_prompt = f"Extract entities and relations from this manufacturing document.\n\nTitle: {page_title}\n---\n{text[:4000]}\n---\n\nOutput ONLY pure JSON:"

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": SYSTEM_PROMPT + "\n\n" + user_prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 4096, "num_ctx": 8192}
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
    model, page, idx, total = args
    topic = page["topic"]
    page_id = page["page_id"]
    title = page["title"]
    file_rel = page["file"]

    txt_path = DATA_DIR / file_rel
    if not txt_path.exists():
        return {"page_id": page_id, "error": "file_not_found", "idx": idx}

    text = txt_path.read_text(encoding="utf-8")
    try:
        result = call_ollama(model, text, title)
        entities = result["extracted"].get("entities", [])
        relations = result["extracted"].get("relations", [])
        print(f"  [{idx}/{total}] {topic}/{title[:25]} → 엔티티 {len(entities)}, 관계 {len(relations)}, {result['elapsed_sec']}s")
        return {
            "page_id": page_id, "topic": topic, "title": title,
            "idx": idx, **result
        }
    except Exception as e:
        print(f"  [{idx}/{total}] {title[:25]} → 오류: {e}")
        return {"page_id": page_id, "title": title, "idx": idx, "error": str(e)}


def run_parallel(model: str, workers: int = 3):
    pages = json.loads((DATA_DIR / "_index.json").read_text(encoding="utf-8"))
    total = len(pages)
    out_dir = BASE_DIR / f"parallel-results-{model.replace(':', '-').replace('.', '')}"
    out_dir.mkdir(exist_ok=True)

    print(f"모델: {model} | 병렬: {workers}개 | 페이지: {total}개")
    print(f"출력: {out_dir}\n")

    t_start = time.time()
    args_list = [(model, page, i+1, total) for i, page in enumerate(pages)]

    results = []
    errors = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_page, args): args for args in args_list}
        for future in as_completed(futures):
            result = future.result()
            if "error" in result:
                errors.append(result)
            else:
                results.append(result)

    # idx 순서로 정렬
    results.sort(key=lambda x: x.get("idx", 0))
    total_elapsed = time.time() - t_start

    # 저장
    (out_dir / "all_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if errors:
        (out_dir / "errors.json").write_text(
            json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    total_entities = sum(len(r["extracted"].get("entities", [])) for r in results)
    total_relations = sum(len(r["extracted"].get("relations", [])) for r in results)

    print(f"\n{'='*60}")
    print(f"완료: {len(results)}/{total}페이지 성공 | 오류: {len(errors)}개")
    print(f"총 추출: 엔티티 {total_entities}개, 관계 {total_relations}개")
    print(f"총 소요시간: {total_elapsed:.0f}초 ({total_elapsed/60:.1f}분)")
    print(f"페이지당 평균: {total_elapsed/max(len(results),1):.1f}초")

    # 수동 결과(71노드/58관계) 비교
    print(f"\n[수동 결과 비교]")
    print(f"  자동: 엔티티 {total_entities} / 관계 {total_relations}")
    print(f"  수동: 노드 71 / 관계 58")
    print(f"  엔티티 비율: {total_entities/71:.2f}x | 관계 비율: {total_relations/58:.2f}x")

    return results, errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3.5:35b-a3b", help="Ollama 모델명")
    parser.add_argument("--workers", type=int, default=3, help="병렬 처리 수")
    args = parser.parse_args()
    run_parallel(args.model, args.workers)
