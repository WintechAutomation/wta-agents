"""
호닝_형상_검사기_제작_이슈 단일 파일 재처리 — 청크 크기 1500자
"""
import sys, json, re, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv("C:/MES/wta-agents/.env")
client = anthropic.Anthropic()

MODEL = "claude-haiku-4-5-20251001"
CHUNK_SIZE = 1500
MAX_TOKENS = 8192

SYSTEM_PROMPT = """당신은 제조업 기술 문서에서 지식 그래프 엔티티와 관계를 추출하는 전문가입니다.

## 온톨로지 v1.1 스키마

### 노드 유형 (9개)
- Customer: 고객사 {name, alias, country}
- Equipment: 장비 {name, type, model, customer}
- Product: 제품 {type, material, description}
- Component: 부품/광학계 {model, name, type, spec}
- Process: 공정/기능 {name, description, tool, parent}
- Issue: 이슈 {title, date, status, symptom, root_cause}
- Resolution: 조치방안 {description, category, effectiveness}
- Person: 담당자 {name, dept, role}
- Tool: 소프트웨어 도구 {name, type}

### 관계 유형 (10개)
OWNS, HAS_ISSUE, SIMILAR_TO, RESOLVED_BY, INVOLVES_COMPONENT, USES_COMPONENT, INVOLVED_IN, HAS_SUBPROCESS, USES_TOOL, MAINTAINS

## 출력 규칙
1. 반드시 순수 JSON만 출력 (마크다운 코드블록, 설명 없음)
2. 텍스트에 명시된 정보만 추출 (추정 금지)
3. id는 영문 snake_case로 고유하게 부여
4. 관계의 from_id/to_id는 entities의 id와 일치해야 함

## JSON 스키마
{"entities":[{"type":"NodeType","id":"unique_id","name":"표시명","properties":{}}],"relations":[{"type":"REL_TYPE","from_id":"id","to_id":"id","properties":{}}]}"""


def split_chunks(text, size):
    if len(text) <= size:
        return [text]
    chunks, paragraphs, current = [], text.split('\n\n'), ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= size:
            current = current + ("\n\n" if current else "") + para
        else:
            if current:
                chunks.append(current.strip())
            if len(para) > size:
                for i in range(0, len(para), size):
                    chunks.append(para[i:i+size].strip())
                current = ""
            else:
                current = para
    if current.strip():
        chunks.append(current.strip())
    return chunks


def extract_chunk(chunk_text, page_title, idx, total):
    user_prompt = f"""다음 제조업 기술 문서(파트 {idx}/{total})에서 엔티티와 관계를 추출하세요.

문서 제목: {page_title}
---
{chunk_text}
---

순수 JSON만 출력하세요."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": SYSTEM_PROMPT + "\n\n" + user_prompt}]
    )
    raw = response.content[0].text
    usage = response.usage
    m = re.search(r'\{[\s\S]*\}', raw)
    if not m:
        raise ValueError(f"JSON 미발견 (파트 {idx}). 앞 200자: {raw[:200]}")
    extracted = json.loads(m.group())
    cost = usage.input_tokens * 0.00000025 + usage.output_tokens * 0.00000125
    return {"extracted": extracted, "usage": {"input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens, "cost_usd": round(cost, 6)}, "raw_len": len(raw)}


def merge(chunk_results):
    seen_e, seen_r = set(), set()
    entities, relations = [], []
    cost, inp, out = 0.0, 0, 0
    for c in chunk_results:
        e = c.get("extracted", {})
        u = c.get("usage", {})
        cost += u.get("cost_usd", 0); inp += u.get("input_tokens", 0); out += u.get("output_tokens", 0)
        for ent in e.get("entities", []):
            eid = ent.get("id", "")
            if eid and eid not in seen_e:
                seen_e.add(eid); entities.append(ent)
        for rel in e.get("relations", []):
            key = f"{rel.get('type')}:{rel.get('from_id')}:{rel.get('to_id')}"
            if key not in seen_r:
                seen_r.add(key); relations.append(rel)
    return {"extracted": {"entities": entities, "relations": relations},
            "usage": {"input_tokens": inp, "output_tokens": out, "cost_usd": round(cost, 6)},
            "chunks_processed": len(chunk_results)}


if __name__ == "__main__":
    TXT_ALL = Path("C:/MES/wta-agents/workspaces/research-agent/poc-texts-all")
    OUT_DIR = Path("C:/MES/wta-agents/workspaces/research-agent/claude-extract-results")

    txt_file = TXT_ALL / "호닝신뢰성" / "8138785229-호닝_형상_검사기_제작_이슈_및_조치_내용.txt"
    text = txt_file.read_text(encoding="utf-8")
    title_m = re.search(r'제목: (.+)', text)
    title = title_m.group(1).strip() if title_m else txt_file.stem

    chunks = split_chunks(text, CHUNK_SIZE)
    print(f"=== 호닝 형상 검사기 제작 이슈 재처리 (청크 {CHUNK_SIZE}자) ===")
    print(f"파일 크기: {len(text):,}자 → {len(chunks)}개 청크\n")

    results = []
    for i, chunk in enumerate(chunks, 1):
        print(f"청크 [{i}/{len(chunks)}] ({len(chunk)}자)...")
        r = extract_chunk(chunk, title, i, len(chunks))
        ents = r["extracted"].get("entities", [])
        rels = r["extracted"].get("relations", [])
        print(f"  → 엔티티 {len(ents)}개, 관계 {len(rels)}개, 비용 ${r['usage']['cost_usd']:.4f}")
        results.append(r)
        if i < len(chunks):
            time.sleep(0.3)

    merged = merge(results)
    merged["topic"] = "호닝신뢰성"
    merged["file"] = txt_file.name
    merged["page_title"] = title

    total_e = len(merged["extracted"]["entities"])
    total_r = len(merged["extracted"]["relations"])
    print(f"\n병합 결과: 엔티티 {total_e}개, 관계 {total_r}개, 총 비용 ${merged['usage']['cost_usd']:.4f}")

    out_file = OUT_DIR / "chunk_retry_honing_issue.json"
    out_file.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"결과: {out_file}")
