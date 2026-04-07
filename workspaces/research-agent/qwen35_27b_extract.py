"""
GraphRAG Phase 2 재시도: qwen3.5:27b (Ollama) 엔티티·관계 자동 추출
온톨로지 v1.1 스키마(9노드/10관계) 기반
31페이지 전체 처리 → 수동 결과(71노드/58관계)와 비교
"""
import sys, os, json, re, time, urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

OLLAMA_BASE = "http://182.224.6.147:11434"
MODEL = "qwen3.5:27b"
BASE_DIR = Path("C:/MES/wta-agents/workspaces/research-agent")
DATA_DIR = BASE_DIR / "poc-texts-all"
OUT_DIR = BASE_DIR / "qwen35-27b-results"
OUT_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT = """You are an expert at extracting knowledge graph entities and relations from Korean manufacturing technical documents.

## Ontology v1.1 Schema

### Node Types (9)
- Customer: 고객사 {name, alias, country}
- Equipment: 장비 {name, type, model, customer}
- Product: 제품 {type, material, description}
- Component: 부품/광학계 {model, name, type, spec}
- Process: 공정/기능 {name, description, tool, parent}
- Issue: 이슈 {title, date, status, symptom, root_cause}
- Resolution: 조치방안 {description, category, effectiveness}
- Person: 담당자 {name, dept, role}
- Tool: 소프트웨어 도구 {name, type}

### Relation Types (10)
OWNS, HAS_ISSUE, SIMILAR_TO, RESOLVED_BY, INVOLVES_COMPONENT, USES_COMPONENT, INVOLVED_IN, HAS_SUBPROCESS, USES_TOOL, MAINTAINS

## Rules
1. Output ONLY pure JSON — no markdown, no explanation, no <think> tags
2. Extract only what is explicitly stated in the text
3. Use unique snake_case ids
4. from_id/to_id must match entity ids exactly

## Output Format
{"entities":[{"type":"NodeType","id":"unique_id","name":"표시명","properties":{}}],"relations":[{"type":"REL_TYPE","from_id":"id","to_id":"id","properties":{}}]}"""


def call_ollama(text: str, page_title: str) -> dict:
    user_prompt = f"""Extract entities and relations from this manufacturing document.

Title: {page_title}
---
{text[:5000]}
---

Output ONLY pure JSON:"""

    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": SYSTEM_PROMPT + "\n\n" + user_prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 4096}
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())
    elapsed = time.time() - t0

    raw = data["message"]["content"]

    # <think>...</think> 태그 제거 (qwen3.5 thinking mode)
    raw_clean = re.sub(r'<think>[\s\S]*?</think>', '', raw).strip()
    raw_clean = re.sub(r'```json\s*', '', raw_clean)
    raw_clean = re.sub(r'```\s*', '', raw_clean)

    json_match = re.search(r'\{[\s\S]*\}', raw_clean)
    if not json_match:
        raise ValueError(f"JSON 미발견. 응답 앞 300자: {raw[:300]}")

    extracted = json.loads(json_match.group())
    return {
        "extracted": extracted,
        "elapsed_sec": round(elapsed, 1),
        "model": MODEL
    }


def load_index() -> list:
    idx_path = DATA_DIR / "_index.json"
    return json.loads(idx_path.read_text(encoding="utf-8"))


def run_extraction():
    pages = load_index()
    print(f"대상 페이지: {len(pages)}개")
    print(f"모델: {MODEL}")
    print(f"서버: {OLLAMA_BASE}\n")

    results = []
    errors = []
    total_entities = 0
    total_relations = 0

    for i, page in enumerate(pages):
        topic = page["topic"]
        page_id = page["page_id"]
        title = page["title"]
        file_rel = page["file"]

        txt_path = DATA_DIR / file_rel
        if not txt_path.exists():
            print(f"  [{i+1}/{len(pages)}] 파일 없음: {file_rel}")
            errors.append({"page_id": page_id, "error": "file_not_found"})
            continue

        text = txt_path.read_text(encoding="utf-8")
        print(f"[{i+1}/{len(pages)}] {topic}/{title[:30]} ({len(text):,}자)", end=" ... ", flush=True)

        try:
            result = call_ollama(text, title)
            entities = result["extracted"].get("entities", [])
            relations = result["extracted"].get("relations", [])
            total_entities += len(entities)
            total_relations += len(relations)
            print(f"엔티티 {len(entities)}개, 관계 {len(relations)}개, {result['elapsed_sec']}s")

            results.append({
                "page_id": page_id,
                "topic": topic,
                "title": title,
                **result
            })

        except Exception as e:
            print(f"오류: {e}")
            errors.append({"page_id": page_id, "title": title, "error": str(e)})

    # 결과 저장
    out_path = OUT_DIR / "all_results.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    if errors:
        err_path = OUT_DIR / "errors.json"
        err_path.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"완료: {len(results)}/{len(pages)} 페이지 성공")
    print(f"총 추출: 엔티티 {total_entities}개, 관계 {total_relations}개")
    print(f"오류: {len(errors)}개")
    if errors:
        print("오류 페이지:", [e['page_id'] for e in errors])
    print(f"결과 저장: {out_path}")

    return results, errors


# 수동 기준 (Phase 1 전체 집계 - 71노드/58관계)
MANUAL_BASELINE = {
    "nodes_total": 71,
    "relations_total": 58,
    "key_entities": [
        # 포장혼입검사
        "Korloy 포장기 #6", "혼입검사기", "acA2500-14gm", "M2514-MP2",
        "DOMELIGHT100", "Korloy", "밝기 비대칭 이슈",
        # 호닝신뢰성
        "호닝 형상 검사기", "크래비스 모듈", "간저우 하이썽",
        # 연삭측정제어
        "WTA 양면 연삭 핸들러", "연삭 핸들러",
        # 장비물류
        "헤드 ATC", "AGV 물류",
        # 분말검사
        "측면 광학계",
    ]
}


def compare_with_manual(results: list) -> dict:
    all_entities = []
    all_relations = []
    for r in results:
        all_entities.extend(r["extracted"].get("entities", []))
        all_relations.extend(r["extracted"].get("relations", []))

    auto_names = set()
    for e in all_entities:
        n = e.get("name", e.get("id", "")).replace(" ", "").lower()
        if n:
            auto_names.add(n)

    matched, missed = [], []
    for name in MANUAL_BASELINE["key_entities"]:
        key = name.replace(" ", "").lower()
        found = any(key in an or an in key for an in auto_names)
        if found:
            matched.append(name)
        else:
            missed.append(name)

    return {
        "auto_entities": len(all_entities),
        "auto_relations": len(all_relations),
        "manual_nodes": MANUAL_BASELINE["nodes_total"],
        "manual_relations": MANUAL_BASELINE["relations_total"],
        "key_entity_recall": f"{len(matched)}/{len(MANUAL_BASELINE['key_entities'])} ({round(len(matched)/len(MANUAL_BASELINE['key_entities'])*100,1)}%)",
        "matched_entities": matched,
        "missed_entities": missed,
        "entity_coverage_ratio": round(len(all_entities) / MANUAL_BASELINE["nodes_total"], 2),
        "relation_coverage_ratio": round(len(all_relations) / MANUAL_BASELINE["relations_total"], 2),
    }


if __name__ == "__main__":
    results, errors = run_extraction()

    if results:
        print("\n[수동 결과 비교]")
        cmp = compare_with_manual(results)
        print(f"  자동 추출: 엔티티 {cmp['auto_entities']}개 / 관계 {cmp['auto_relations']}개")
        print(f"  수동 기준: 노드 {cmp['manual_nodes']}개 / 관계 {cmp['manual_relations']}개")
        print(f"  핵심 엔티티 재현율: {cmp['key_entity_recall']}")
        print(f"  매칭: {cmp['matched_entities']}")
        print(f"  누락: {cmp['missed_entities']}")

        cmp_path = OUT_DIR / "comparison.json"
        cmp_path.write_text(json.dumps(cmp, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n비교 결과 저장: {cmp_path}")
