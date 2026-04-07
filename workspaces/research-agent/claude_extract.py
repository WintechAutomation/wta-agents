"""
GraphRAG PoC Phase 2: Claude Haiku API 엔티티·관계 자동 추출
온톨로지 v1.1 스키마(9노드/10관계) 기반 JSON 구조화 출력
"""
import sys, os, json, re, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv("C:/MES/wta-agents/.env")
client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 자동 로드

MODEL = "claude-haiku-4-5-20251001"

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


def extract_from_text(text: str, page_title: str = "") -> dict:
    """단일 텍스트에서 엔티티·관계 추출"""
    user_prompt = f"""다음 제조업 기술 문서에서 엔티티와 관계를 추출하세요.

문서 제목: {page_title}
---
{text[:4000]}
---

순수 JSON만 출력하세요."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[
            {"role": "user", "content": SYSTEM_PROMPT + "\n\n" + user_prompt}
        ]
    )

    raw = response.content[0].text
    usage = response.usage

    # JSON 추출
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if not json_match:
        raise ValueError(f"JSON 미발견. 원시 응답 앞 200자: {raw[:200]}")

    extracted = json.loads(json_match.group())
    return {
        "extracted": extracted,
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost_usd": round(usage.input_tokens * 0.00000025 + usage.output_tokens * 0.00000125, 6)
        },
        "raw_len": len(raw)
    }


def run_pilot(txt_file: Path) -> dict:
    """단일 파일 파일럿 실행"""
    text = txt_file.read_text(encoding="utf-8")
    # 헤더에서 제목 추출
    title_match = re.search(r'제목: (.+)', text)
    page_title = title_match.group(1).strip() if title_match else txt_file.stem

    print(f"\n  대상: {page_title} ({len(text):,}자)")
    result = extract_from_text(text, page_title)
    entities = result["extracted"].get("entities", [])
    relations = result["extracted"].get("relations", [])
    print(f"  → 엔티티 {len(entities)}개, 관계 {len(relations)}개")
    print(f"  → 토큰: in={result['usage']['input_tokens']}, out={result['usage']['output_tokens']}, 비용=${result['usage']['cost_usd']:.4f}")
    return result


def compare_with_manual(auto_entities: list, manual_entities: dict) -> dict:
    """자동 추출 vs 수동 기준 비교"""
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
    parser.add_argument("--topic", default="포장혼입검사")
    args = parser.parse_args()

    TXT_ALL = Path("C:/MES/wta-agents/workspaces/research-agent/poc-texts-all")
    OUT_DIR = Path("C:/MES/wta-agents/workspaces/research-agent/claude-extract-results")
    OUT_DIR.mkdir(exist_ok=True)

    # 수동 기준 (포장혼입검사, 밝기비대칭 이슈 페이지)
    MANUAL_BASELINE = {
        "Equipment": ["Korloy 포장기 #6", "혼입검사기"],
        "Customer": ["Korloy"],
        "Component": ["acA2500-14gm", "M2514-MP2", "DOMELIGHT100"],
        "Issue": ["Korloy 포장기 #6 밝기 비대칭"],
        "Resolution": ["광축 중심과 조명 중심 상하좌우 ±1mm 이내 세팅",
                       "컨베이어 벨트 기준 조명 높이 10mm 수준 세팅 권장",
                       "측정 가능 제품군 제한"],
    }

    all_results = []
    total_cost = 0.0

    if args.mode == "pilot":
        # 파일럿: 포장혼입검사 중 가장 내용 풍부한 밝기비대칭 이슈 페이지
        pilot_file = TXT_ALL / "포장혼입검사" / "9485484034-Korloy_포장기_#6(#25-3)_혼입_검사_특정_제품_밝기_비대칭.txt"
        print("=== Phase 2 파일럿: Claude Haiku 엔티티 추출 ===")
        result = run_pilot(pilot_file)
        total_cost += result["usage"]["cost_usd"]

        # 비교
        entities = result["extracted"].get("entities", [])
        cmp = compare_with_manual(entities, MANUAL_BASELINE)
        print(f"\n  [정확도] 수동 기준 Recall: {cmp['recall_pct']}% ({len(cmp['matched'])}/{cmp['total_manual']})")
        print(f"  매칭됨: {cmp['matched']}")
        print(f"  누락됨: {cmp['missed']}")

        out = {
            "mode": "pilot",
            "file": pilot_file.name,
            "result": result,
            "comparison": cmp,
        }
        out_file = OUT_DIR / "pilot_result.json"
        out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  결과 저장: {out_file}")
        print(f"  총 비용: ${total_cost:.4f}")

    elif args.mode == "all":
        # 전체 31페이지
        print("=== Phase 2 전체: 31페이지 Claude Haiku 추출 ===")
        topics = ["포장혼입검사", "장비물류", "분말검사", "연삭측정제어", "호닝신뢰성"]
        page_num = 0

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
                    total_cost += result["usage"]["cost_usd"]
                    time.sleep(0.3)  # API rate limit 배려
                except Exception as e:
                    print(f"  → 오류: {e}")
                    all_results.append({"topic": topic, "file": txt_file.name, "error": str(e)})

        # 전체 결과 저장
        out_file = OUT_DIR / "all_results.json"
        out_file.write_text(json.dumps({
            "total_pages": page_num,
            "total_cost_usd": round(total_cost, 4),
            "results": all_results
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"\n=== 완료 ===")
        print(f"총 {page_num}페이지, 총 비용: ${total_cost:.4f}")
        print(f"결과: {out_file}")
