"""
GraphRAG PoC Phase 3 Step 1: 오류 5페이지 청크 분할 재처리
4000자 초과 페이지를 CHUNK_SIZE 단위로 분할 → 각 청크 추출 → 엔티티/관계 병합
"""
import sys, os, json, re, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv("C:/MES/wta-agents/.env")
client = anthropic.Anthropic()

MODEL = "claude-haiku-4-5-20251001"
CHUNK_SIZE = 2000  # 청크당 최대 문자 수
MAX_TOKENS = 8192  # 출력 토큰 한도 최대

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
- OWNS: Customer → Equipment
- HAS_ISSUE: Equipment → Issue
- SIMILAR_TO: Issue → Issue (동일/유사 현상)
- RESOLVED_BY: Issue → Resolution
- INVOLVES_COMPONENT: Issue → Component
- USES_COMPONENT: Equipment → Component
- INVOLVED_IN: Product → Issue
- HAS_SUBPROCESS: Process → Process
- USES_TOOL: Process → Tool
- MAINTAINS: Person → Process

## 출력 규칙
1. 반드시 순수 JSON만 출력 (마크다운 코드블록, 설명 없음)
2. 텍스트에 명시된 정보만 추출 (추정 금지)
3. id는 영문 snake_case로 고유하게 부여
4. 관계의 from_id/to_id는 entities의 id와 일치해야 함

## JSON 스키마
{"entities":[{"type":"NodeType","id":"unique_id","name":"표시명","properties":{"key":"value"}}],"relations":[{"type":"REL_TYPE","from_id":"id","to_id":"id","properties":{}}]}"""


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """텍스트를 문단 경계 기준으로 청크 분할"""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    paragraphs = text.split('\n\n')
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = current + ("\n\n" if current else "") + para
        else:
            if current:
                chunks.append(current.strip())
            # 단일 문단이 chunk_size 초과하면 강제 분할
            if len(para) > chunk_size:
                for i in range(0, len(para), chunk_size):
                    chunks.append(para[i:i + chunk_size].strip())
                current = ""
            else:
                current = para

    if current.strip():
        chunks.append(current.strip())

    return chunks


def extract_chunk(chunk_text: str, page_title: str, chunk_idx: int, total_chunks: int) -> dict:
    """단일 청크에서 엔티티·관계 추출"""
    user_prompt = f"""다음 제조업 기술 문서(파트 {chunk_idx}/{total_chunks})에서 엔티티와 관계를 추출하세요.

문서 제목: {page_title}
---
{chunk_text}
---

순수 JSON만 출력하세요."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[
            {"role": "user", "content": SYSTEM_PROMPT + "\n\n" + user_prompt}
        ]
    )

    raw = response.content[0].text
    usage = response.usage

    json_match = re.search(r'\{[\s\S]*\}', raw)
    if not json_match:
        raise ValueError(f"JSON 미발견 (파트 {chunk_idx}). 응답 앞 200자: {raw[:200]}")

    extracted = json.loads(json_match.group())
    cost = usage.input_tokens * 0.00000025 + usage.output_tokens * 0.00000125
    return {
        "extracted": extracted,
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost_usd": round(cost, 6)
        },
        "raw_len": len(raw),
        "chunk_idx": chunk_idx
    }


def merge_chunks(chunk_results: list[dict]) -> dict:
    """여러 청크 결과 병합 (id 기준 중복 제거)"""
    seen_entity_ids = set()
    seen_relation_keys = set()
    merged_entities = []
    merged_relations = []
    total_cost = 0.0
    total_input = 0
    total_output = 0

    for chunk in chunk_results:
        extracted = chunk.get("extracted", {})
        usage = chunk.get("usage", {})
        total_cost += usage.get("cost_usd", 0)
        total_input += usage.get("input_tokens", 0)
        total_output += usage.get("output_tokens", 0)

        for entity in extracted.get("entities", []):
            eid = entity.get("id", "")
            if eid and eid not in seen_entity_ids:
                seen_entity_ids.add(eid)
                merged_entities.append(entity)

        for rel in extracted.get("relations", []):
            rel_key = f"{rel.get('type')}:{rel.get('from_id')}:{rel.get('to_id')}"
            if rel_key not in seen_relation_keys:
                seen_relation_keys.add(rel_key)
                merged_relations.append(rel)

    return {
        "extracted": {"entities": merged_entities, "relations": merged_relations},
        "usage": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cost_usd": round(total_cost, 6)
        },
        "chunks_processed": len(chunk_results)
    }


def process_file_chunked(txt_file: Path) -> dict:
    """파일을 청크 분할하여 처리"""
    text = txt_file.read_text(encoding="utf-8")
    title_match = re.search(r'제목: (.+)', text)
    page_title = title_match.group(1).strip() if title_match else txt_file.stem

    chunks = split_into_chunks(text, CHUNK_SIZE)
    print(f"\n  대상: {page_title}")
    print(f"  파일 크기: {len(text):,}자 → {len(chunks)}개 청크")

    chunk_results = []
    for i, chunk in enumerate(chunks, 1):
        print(f"  청크 [{i}/{len(chunks)}] ({len(chunk)}자) 처리 중...")
        result = extract_chunk(chunk, page_title, i, len(chunks))
        entities = result["extracted"].get("entities", [])
        relations = result["extracted"].get("relations", [])
        print(f"    → 엔티티 {len(entities)}개, 관계 {len(relations)}개, "
              f"비용 ${result['usage']['cost_usd']:.4f}")
        chunk_results.append(result)
        if i < len(chunks):
            time.sleep(0.3)

    merged = merge_chunks(chunk_results)
    total_entities = len(merged["extracted"]["entities"])
    total_relations = len(merged["extracted"]["relations"])
    print(f"  병합 결과: 엔티티 {total_entities}개, 관계 {total_relations}개, "
          f"총 비용 ${merged['usage']['cost_usd']:.4f}")

    merged["topic"] = txt_file.parent.name
    merged["file"] = txt_file.name
    merged["page_title"] = page_title
    return merged


# 오류 5페이지 목록
ERROR_FILES = [
    ("장비물류", "8517419053-신규_물류_개발건_이슈.txt"),
    ("장비물류", "8989966340-2025-09-01_교세라_양면연삭핸들러_물류_컨셉.txt"),
    ("연삭측정제어", "9463300099-2026-01-14_연삭_핸들러_비전_측정기.txt"),
    ("호닝신뢰성", "8081965089-호닝_형상_검사기_개선_검토.txt"),
    ("호닝신뢰성", "8138785229-호닝_형상_검사기_제작_이슈_및_조치_내용.txt"),
]


if __name__ == "__main__":
    TXT_ALL = Path("C:/MES/wta-agents/workspaces/research-agent/poc-texts-all")
    OUT_DIR = Path("C:/MES/wta-agents/workspaces/research-agent/claude-extract-results")
    OUT_DIR.mkdir(exist_ok=True)

    print("=== Phase 3 Step 1: 오류 5페이지 청크 분할 재처리 ===")
    print(f"청크 크기: {CHUNK_SIZE}자, max_tokens: {MAX_TOKENS}\n")

    results = []
    total_cost = 0.0
    success = 0
    errors = 0

    for topic, filename in ERROR_FILES:
        txt_file = TXT_ALL / topic / filename
        if not txt_file.exists():
            print(f"\n  [오류] 파일 없음: {txt_file}")
            errors += 1
            continue
        try:
            result = process_file_chunked(txt_file)
            results.append(result)
            total_cost += result["usage"]["cost_usd"]
            success += 1
        except Exception as e:
            print(f"\n  [오류] {filename}: {e}")
            results.append({"topic": topic, "file": filename, "error": str(e)})
            errors += 1
        time.sleep(0.5)

    out_file = OUT_DIR / "chunk_retry_results.json"
    out_file.write_text(
        json.dumps({
            "total_files": len(ERROR_FILES),
            "success": success,
            "errors": errors,
            "total_cost_usd": round(total_cost, 4),
            "chunk_size": CHUNK_SIZE,
            "max_tokens": MAX_TOKENS,
            "results": results
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"\n=== 완료 ===")
    print(f"성공: {success}/5, 오류: {errors}/5")
    print(f"총 비용: ${total_cost:.4f}")
    print(f"결과: {out_file}")
