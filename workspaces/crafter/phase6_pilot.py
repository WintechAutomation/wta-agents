"""
Phase6 파일럿 — pgvector chunk 50건 → Claude API → 엔티티/관계 추출

입력: C:/MES/wta-agents/workspaces/crafter/phase6_pilot_50.json
출력: C:/MES/wta-agents/workspaces/crafter/phase6_pilot_result.json

모델: claude-haiku-4-5-20251001 (research-agent v3 스크립트와 동일)
프롬프트: v3 라벨 체계 (Customer/Equipment/Product/Component/Process/Issue/Resolution/Person/Tool)

Neo4j flush 없음 — 품질 샘플링 전용.
"""
import sys
import io
import os
import re
import json
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from dotenv import load_dotenv
import anthropic

load_dotenv("C:/MES/wta-agents/.env")
client = anthropic.Anthropic()
MODEL = "claude-haiku-4-5-20251001"

# Haiku 4.5 가격 (USD per token)
PRICE_IN = 1.00 / 1_000_000    # $1.00/1M input
PRICE_OUT = 5.00 / 1_000_000   # $5.00/1M output

SYSTEM_PROMPT = """당신은 제조업 기술 문서에서 지식 그래프 엔티티와 관계를 추출하는 전문가입니다.

## 온톨로지 v1 (Phase2/3/5 통일)

### 노드 유형 (9개)
- Customer: 고객사 {name, alias, country}
- Equipment: 장비/검사기 {name, type, model, customer}
  ★ "~부", "~기", "~기계" 등 명사로 끝나는 장비 이름 모두 포함
- Product: 제품/형번 {type, material, description}
- Component: 부품/광학계/센서/모터 {model, name, type, spec}
  ★ 영문+숫자 모델번호(예: acA2500-14gm, SGM7A, FX5U-32M) 반드시 포착
- Process: 공정/기능/절차 {name, description, tool, parent}
- Issue: 이슈/알람/에러 {title, symptom, root_cause, error_code}
- Resolution: 조치방안 {description, category, effectiveness}
  ★ 각 조치를 반드시 별도 Resolution으로 분리
- Person: 담당자 {name, dept, role}
- Tool: 소프트웨어 도구 {name, type}

### 관계 유형 (10개)
OWNS(Customer→Equipment), HAS_ISSUE(Equipment→Issue),
SIMILAR_TO(Issue→Issue), RESOLVED_BY(Issue→Resolution),
INVOLVES_COMPONENT(Issue→Component), USES_COMPONENT(Equipment→Component),
INVOLVED_IN(Product→Issue), HAS_SUBPROCESS(Process→Process),
USES_TOOL(Process→Tool), MAINTAINS(Person→Process)

## 출력 규칙
1. 반드시 순수 JSON만 출력 (마크다운/설명 없음)
2. 텍스트에 명시된 정보만 추출 (추측 금지)
3. id는 영문 snake_case
4. from_id/to_id는 entities의 id와 일치
5. 매뉴얼 문서면 Equipment/Component/Process 중심, 이슈 기록이면 Issue/Resolution 중심

## JSON 스키마
{"entities":[{"type":"NodeType","id":"unique_id","name":"표시명","properties":{}}],"relations":[{"type":"REL_TYPE","from_id":"id","to_id":"id","properties":{}}]}"""


def extract_chunk(content: str, source_file: str, page: int) -> dict:
    """단일 chunk에서 엔티티/관계 추출."""
    user_prompt = (
        f"문서: {source_file} (page {page})\n"
        f"---\n{content}\n---\n"
        "순수 JSON만 출력:"
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[
            {"role": "user", "content": SYSTEM_PROMPT + "\n\n" + user_prompt}
        ],
    )
    raw = resp.content[0].text
    in_tok = resp.usage.input_tokens
    out_tok = resp.usage.output_tokens
    cost = in_tok * PRICE_IN + out_tok * PRICE_OUT

    ents, rels = [], []
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            obj = json.loads(m.group())
            ents = obj.get("entities", []) or []
            rels = obj.get("relations", []) or []
        except Exception as e:
            print(f"  [parse error] {e}", file=sys.stderr)

    return {
        "entities": ents,
        "relations": rels,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": cost,
    }


def main():
    in_path = Path("C:/MES/wta-agents/workspaces/crafter/phase6_pilot_50.json")
    out_path = Path("C:/MES/wta-agents/workspaces/crafter/phase6_pilot_result.json")

    if not in_path.exists():
        print(f"[ERROR] 입력 파일 없음: {in_path}")
        sys.exit(1)

    chunks = json.loads(in_path.read_text(encoding="utf-8"))
    print(f"[PILOT] 입력 {len(chunks)} chunks, 모델={MODEL}")
    print("=" * 70)

    results = []
    tot_in = tot_out = 0
    tot_cost = 0.0
    tot_ents = tot_rels = 0
    t0 = time.time()

    for i, c in enumerate(chunks, 1):
        content = c.get("content", "")
        src = c.get("source_file", "")
        page = c.get("page_number", 0)
        if not content:
            continue
        try:
            r = extract_chunk(content, src, page)
        except Exception as e:
            print(f"[{i}/{len(chunks)}] ERROR: {e}")
            continue

        tot_in += r["input_tokens"]
        tot_out += r["output_tokens"]
        tot_cost += r["cost_usd"]
        tot_ents += len(r["entities"])
        tot_rels += len(r["relations"])

        results.append({
            "chunk_id": c.get("id"),
            "source_file": src,
            "page": page,
            "content_len": len(content),
            "entities": r["entities"],
            "relations": r["relations"],
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
            "cost_usd": r["cost_usd"],
        })

        print(
            f"[{i:2d}/{len(chunks)}] {src[:40]:40s} p{page:3d} "
            f"→ ent={len(r['entities']):2d} rel={len(r['relations']):2d} "
            f"in={r['input_tokens']:5d} out={r['output_tokens']:4d} "
            f"${r['cost_usd']:.5f}"
        )
        time.sleep(0.15)  # rate limit 완화

    elapsed = time.time() - t0

    # 총 pgvector chunk 수 (견적용)
    TOTAL_CHUNKS = 285_248

    avg_cost = tot_cost / len(results) if results else 0
    full_cost = avg_cost * TOTAL_CHUNKS
    avg_sec = elapsed / len(results) if results else 0
    full_hours_serial = avg_sec * TOTAL_CHUNKS / 3600
    full_hours_par10 = full_hours_serial / 10

    summary = {
        "model": MODEL,
        "pilot_chunks": len(results),
        "elapsed_sec": round(elapsed, 1),
        "avg_sec_per_chunk": round(avg_sec, 2),
        "total_entities": tot_ents,
        "total_relations": tot_rels,
        "avg_entities_per_chunk": round(tot_ents / len(results), 1) if results else 0,
        "avg_relations_per_chunk": round(tot_rels / len(results), 1) if results else 0,
        "total_input_tokens": tot_in,
        "total_output_tokens": tot_out,
        "total_cost_usd": round(tot_cost, 4),
        "avg_cost_per_chunk_usd": round(avg_cost, 5),
        "projected_full_run": {
            "target_chunks": TOTAL_CHUNKS,
            "estimated_cost_usd": round(full_cost, 2),
            "estimated_hours_serial": round(full_hours_serial, 1),
            "estimated_hours_parallel10": round(full_hours_par10, 1),
        },
    }

    out_path.write_text(
        json.dumps({"summary": summary, "results": results},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("=" * 70)
    print("[요약]")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n저장: {out_path}")


if __name__ == "__main__":
    main()
