"""
Phase6 파일럿 Track A — Ollama qwen3.5:9b (think=false)

Ollama native API (/api/chat) 사용, think=false로 reasoning 제거.
"""
import sys
import io
import os
import re
import json
import time
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OLLAMA_URL = "http://182.224.6.147:11434/api/chat"
MODEL = "qwen3.5:9b"

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


def extract_chunk(content: str, source_file: str, page: int) -> dict:
    user_prompt = (
        f"문서: {source_file} (page {page})\n---\n{content}\n---\n순수 JSON만 출력:"
    )
    body = {
        "model": MODEL,
        "think": False,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 2048},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.loads(r.read())
    dt = time.time() - t0

    raw = resp.get("message", {}).get("content", "") or ""
    in_tok = resp.get("prompt_eval_count", 0)
    out_tok = resp.get("eval_count", 0)
    eval_dur_s = resp.get("eval_duration", 0) / 1e9
    tok_per_s = out_tok / eval_dur_s if eval_dur_s > 0 else 0

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
        "wall_sec": round(dt, 2),
        "tok_per_s": round(tok_per_s, 1),
        "raw_content": raw,
    }


def main():
    in_path = Path("C:/MES/wta-agents/workspaces/crafter/phase6_pilot_50.json")
    out_path = Path("C:/MES/wta-agents/workspaces/crafter/phase6_pilot_ollama_result.json")

    chunks = json.loads(in_path.read_text(encoding="utf-8"))
    print(f"[PILOT A] Ollama {MODEL}, 입력 {len(chunks)} chunks")
    print("=" * 80)

    results = []
    tot_in = tot_out = 0
    tot_ents = tot_rels = 0
    tot_wall = 0.0
    chunk_times = []
    t0 = time.time()

    for i, c in enumerate(chunks, 1):
        content = c.get("content", "") or ""
        src = c.get("source_file", "") or ""
        page = c.get("page_number") or 0
        if not content:
            continue
        try:
            r = extract_chunk(content, src, page)
        except Exception as e:
            print(f"[{i}/{len(chunks)}] ERROR: {e}")
            continue

        tot_in += r["input_tokens"]
        tot_out += r["output_tokens"]
        tot_ents += len(r["entities"])
        tot_rels += len(r["relations"])
        tot_wall += r["wall_sec"]
        chunk_times.append(r["wall_sec"])

        results.append({
            "chunk_id": c.get("id"),
            "source_file": src,
            "page": page,
            "content_len": len(content),
            "content_preview": content[:200],
            "entities": r["entities"],
            "relations": r["relations"],
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
            "wall_sec": r["wall_sec"],
            "tok_per_s": r["tok_per_s"],
        })

        print(
            f"[{i:2d}/{len(chunks)}] {src[:38]:38s} p{page:3d} "
            f"ent={len(r['entities']):2d} rel={len(r['relations']):2d} "
            f"out={r['output_tokens']:4d} "
            f"{r['wall_sec']:5.1f}s {r['tok_per_s']:5.1f}t/s"
        )

    elapsed = time.time() - t0
    TOTAL_CHUNKS = 285_248
    avg_sec = elapsed / len(results) if results else 0
    full_hours_serial = avg_sec * TOTAL_CHUNKS / 3600
    avg_tok_s = tot_out / tot_wall if tot_wall > 0 else 0

    summary = {
        "track": "A",
        "model": MODEL,
        "endpoint": OLLAMA_URL,
        "pilot_chunks": len(results),
        "elapsed_sec": round(elapsed, 1),
        "avg_sec_per_chunk": round(avg_sec, 2),
        "min_sec_per_chunk": round(min(chunk_times), 2) if chunk_times else 0,
        "max_sec_per_chunk": round(max(chunk_times), 2) if chunk_times else 0,
        "avg_tok_per_s": round(avg_tok_s, 1),
        "total_entities": tot_ents,
        "total_relations": tot_rels,
        "avg_entities_per_chunk": round(tot_ents / len(results), 1) if results else 0,
        "avg_relations_per_chunk": round(tot_rels / len(results), 1) if results else 0,
        "total_input_tokens": tot_in,
        "total_output_tokens": tot_out,
        "projected_full_run": {
            "target_chunks": TOTAL_CHUNKS,
            "estimated_hours_serial": round(full_hours_serial, 1),
            "estimated_hours_parallel8": round(full_hours_serial / 8, 1),
        },
    }

    out_path.write_text(
        json.dumps({"summary": summary, "results": results},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("=" * 80)
    print("[요약]")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n저장: {out_path}")


if __name__ == "__main__":
    main()
