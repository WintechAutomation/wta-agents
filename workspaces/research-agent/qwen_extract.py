"""
GraphRAG PoC Phase 2: qwen2.5-coder:32b (Ollama 로컬) 엔티티·관계 자동 추출
온톨로지 v1.1 스키마(9노드/10관계) 기반
"""
import sys, os, json, re, time, urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

OLLAMA_BASE = "http://182.224.6.147:11434"
MODEL = "qwen2.5-coder:32b"

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
1. Output ONLY pure JSON (no markdown, no explanation)
2. Extract only what is explicitly stated in the text
3. Use unique snake_case ids
4. from_id/to_id must match entities ids

## JSON Schema
{"entities":[{"type":"NodeType","id":"unique_id","name":"표시명","properties":{}}],"relations":[{"type":"REL_TYPE","from_id":"id","to_id":"id","properties":{}}]}"""


def extract_from_text(text: str, page_title: str = "") -> dict:
    user_prompt = f"""Extract entities and relations from this manufacturing document.

Title: {page_title}
---
{text[:4000]}
---

Output ONLY pure JSON:"""

    full_prompt = SYSTEM_PROMPT + "\n\n" + user_prompt

    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": full_prompt}],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 4096}
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read())
    elapsed = time.time() - t0

    raw = data["message"]["content"]

    # JSON 추출 (코드블록 제거)
    raw_clean = re.sub(r'```json\s*', '', raw)
    raw_clean = re.sub(r'```\s*', '', raw_clean)
    json_match = re.search(r'\{[\s\S]*\}', raw_clean)
    if not json_match:
        raise ValueError(f"JSON 미발견. 응답 앞 200자: {raw[:200]}")

    extracted = json.loads(json_match.group())
    return {
        "extracted": extracted,
        "elapsed_sec": round(elapsed, 1),
        "raw_len": len(raw)
    }


def run_pilot(txt_file: Path) -> dict:
    text = txt_file.read_text(encoding="utf-8")
    title_match = re.search(r'제목: (.+)', text)
    page_title = title_match.group(1).strip() if title_match else txt_file.stem

    print(f"\n  대상: {page_title} ({len(text):,}자)")
    result = extract_from_text(text, page_title)
    entities = result["extracted"].get("entities", [])
    relations = result["extracted"].get("relations", [])
    print(f"  → 엔티티 {len(entities)}개, 관계 {len(relations)}개, 시간 {result['elapsed_sec']}s")
    return result


# 수동 기준 (밝기비대칭 이슈 페이지)
MANUAL_BASELINE = {
    "Equipment": ["Korloy 포장기 #6", "혼입검사기"],
    "Customer": ["Korloy"],
    "Component": ["acA2500-14gm", "M2514-MP2", "DOMELIGHT100"],
    "Issue": ["Korloy 포장기 #6 밝기 비대칭"],
    "Resolution": ["광축 중심과 조명 중심 상하좌우 ±1mm 이내 세팅",
                   "컨베이어 벨트 기준 조명 높이 10mm 수준 세팅 권장",
                   "측정 가능 제품군 제한"],
}


def compare_with_manual(auto_entities: list, manual_entities: dict) -> dict:
    auto_names = set()
    for e in auto_entities:
        n = e.get("name", e.get("id", "")).replace(" ", "").lower()
        if n:
            auto_names.add(n)

    matched, missed = [], []
    for etype, names in manual_entities.items():
        for name in names:
            key = name.replace(" ", "").lower()
            found = any(key in an or an in key for an in auto_names)
            if found:
                matched.append(f"{etype}:{name}")
            else:
                missed.append(f"{etype}:{name}")

    total = sum(len(v) for v in manual_entities.values())
    return {
        "total_manual": total,
        "matched": matched,
        "missed": missed,
        "recall_pct": round(len(matched) / total * 100, 1) if total else 0
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["pilot", "all"], default="pilot")
    args = parser.parse_args()

    TXT_ALL = Path("C:/MES/wta-agents/workspaces/research-agent/poc-texts-all")
    OUT_DIR = Path("C:/MES/wta-agents/workspaces/research-agent/qwen-extract-results")
    OUT_DIR.mkdir(exist_ok=True)

    if args.mode == "pilot":
        pilot_file = TXT_ALL / "포장혼입검사" / "9485484034-Korloy_포장기_#6(#25-3)_혼입_검사_특정_제품_밝기_비대칭.txt"
        print(f"=== Phase 2 파일럿: {MODEL} 엔티티 추출 ===")
        result = run_pilot(pilot_file)

        entities = result["extracted"].get("entities", [])
        cmp = compare_with_manual(entities, MANUAL_BASELINE)
        print(f"\n  [정확도] 수동 기준 Recall: {cmp['recall_pct']}% ({len(cmp['matched'])}/{cmp['total_manual']})")
        print(f"  매칭됨: {cmp['matched']}")
        print(f"  누락됨: {cmp['missed']}")

        out = {"mode": "pilot", "model": MODEL, "file": pilot_file.name,
               "result": result, "comparison": cmp}
        out_file = OUT_DIR / "pilot_result.json"
        out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  결과 저장: {out_file}")

    elif args.mode == "all":
        print(f"=== Phase 2 전체: {MODEL} 31페이지 추출 ===")
        topics = ["포장혼입검사", "장비물류", "분말검사", "연삭측정제어", "호닝신뢰성"]
        all_results = []
        total_time = 0.0
        page_num = 0
        errors = 0

        for topic in topics:
            topic_dir = TXT_ALL / topic
            if not topic_dir.exists():
                continue
            txt_files = sorted(topic_dir.glob("*.txt"))
            print(f"\n[{topic}] {len(txt_files)}페이지")

            for txt_file in txt_files:
                page_num += 1
                print(f"  [{page_num}] {txt_file.name[:55]}")
                try:
                    result = run_pilot(txt_file)
                    result["topic"] = topic
                    result["file"] = txt_file.name
                    all_results.append(result)
                    total_time += result.get("elapsed_sec", 0)
                except Exception as e:
                    print(f"  → 오류: {e}")
                    all_results.append({"topic": topic, "file": txt_file.name, "error": str(e)})
                    errors += 1
                time.sleep(1)

        out_file = OUT_DIR / "all_results.json"
        out_file.write_text(json.dumps({
            "total_pages": page_num,
            "success_pages": page_num - errors,
            "error_pages": errors,
            "total_time_sec": round(total_time, 1),
            "cost_usd": 0,
            "results": all_results
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"\n=== 완료 ===")
        print(f"총 {page_num}페이지 ({errors}개 오류), 총 시간: {total_time:.0f}s")
        print(f"결과: {out_file}")
