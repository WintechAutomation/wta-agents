"""
Phase6 GraphRAG 파일럿 — Claude Sonnet 세션 직접 추출
동일 조건: phase6_pilot_50.json, v1 온톨로지 프롬프트
"""
import json, time, os, re

# API 키 로드
def load_env(path):
    env = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

env = load_env("C:/MES/wta-agents/.env")
api_key = env.get("ANTHROPIC_API_KEY", "")
if not api_key:
    raise RuntimeError("ANTHROPIC_API_KEY not found")

import anthropic
client = anthropic.Anthropic(api_key=api_key)

SYSTEM_PROMPT = """당신은 제조업 기술 문서에서 지식 그래프 엔티티와 관계를 추출하는 전문가입니다.

## 온톨로지 v1
### 노드 유형 (9개)
- Customer: 고객사
- Equipment: 장비/검사기 (~부, ~기, ~기계)
- Product: 제품/형번
- Component: 부품/광학계/센서/모터 (영문+숫자 모델번호 포함)
- Process: 공정/기능/절차
- Issue: 이슈/알람/에러
- Resolution: 조치방안
- Person: 담당자
- Tool: 소프트웨어 도구

### 관계 유형 (10개)
OWNS, HAS_ISSUE, SIMILAR_TO, RESOLVED_BY, INVOLVES_COMPONENT,
USES_COMPONENT, INVOLVED_IN, HAS_SUBPROCESS, USES_TOOL, MAINTAINS

## 출력 규칙
1. 반드시 순수 JSON만 출력 (마크다운/설명 없음)
2. 텍스트에 명시된 정보만 추출
3. id는 영문 snake_case
4. from_id/to_id는 entities의 id와 일치

## 스키마
{"entities":[{"type":"NodeType","id":"uid","name":"표시명","properties":{}}],"relations":[{"type":"REL","from_id":"id","to_id":"id","properties":{}}]}"""

def extract(chunk):
    page = chunk.get("page_number") or 0
    user_msg = f"""문서: {chunk['source_file']} (page {page})
---
{chunk['content']}
---
순수 JSON만 출력:"""

    t0 = time.time()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}]
    )
    elapsed = time.time() - t0

    raw = msg.content[0].text.strip()
    # JSON 블록 추출
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        raw = m.group(0)
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = {"entities": [], "relations": [], "_parse_error": raw[:200]}

    return parsed, elapsed


def main():
    with open("C:/MES/wta-agents/workspaces/crafter/phase6_pilot_50.json", encoding="utf-8") as f:
        chunks = json.load(f)

    results = []
    total_start = time.time()

    for i, chunk in enumerate(chunks):
        print(f"[{i+1:02d}/50] {chunk['source_file'][:50]}...", flush=True)
        parsed, wall_sec = extract(chunk)
        entities = parsed.get("entities", [])
        relations = parsed.get("relations", [])
        results.append({
            "chunk_id": str(chunk["id"]),
            "source_file": chunk["source_file"],
            "page": chunk.get("page_number"),
            "content_len": len(chunk["content"]),
            "content_preview": chunk["content"][:200],
            "entities": entities,
            "relations": relations,
            "wall_sec": round(wall_sec, 3)
        })
        print(f"    → entities={len(entities)}, relations={len(relations)}, {wall_sec:.1f}s")

    total_elapsed = time.time() - total_start
    wall_secs = [r["wall_sec"] for r in results]
    total_entities = sum(len(r["entities"]) for r in results)
    total_relations = sum(len(r["relations"]) for r in results)

    summary = {
        "track": "claude_session",
        "model": "claude-sonnet-4-6",
        "pilot_chunks": len(chunks),
        "elapsed_sec": round(total_elapsed, 2),
        "avg_sec_per_chunk": round(sum(wall_secs) / len(wall_secs), 3),
        "min_sec_per_chunk": round(min(wall_secs), 3),
        "max_sec_per_chunk": round(max(wall_secs), 3),
        "avg_tok_per_s": None,
        "total_entities": total_entities,
        "total_relations": total_relations,
        "avg_entities_per_chunk": round(total_entities / len(chunks), 2),
        "avg_relations_per_chunk": round(total_relations / len(chunks), 2),
    }

    output = {"summary": summary, "results": results}

    out_path = "C:/MES/wta-agents/workspaces/db-manager/phase6_pilot_claude_direct_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n=== 완료 ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
