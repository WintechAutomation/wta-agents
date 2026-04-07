"""
GraphRAG PoC Phase 3 Step 2: Claude Haiku 프롬프트 v2 (개선판)
개선 사항:
  A. Resolution - 각 조치를 별도 엔티티로 분리, description에 수치/구체적 내용 포함
  B. Issue - 장비명 포함한 구체적 제목 형식 요구
  C. Component - 모델번호(영문+숫자) 우선 포착 명시
  D. few-shot 예시 1개 추가
"""
import sys, json, re, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv("C:/MES/wta-agents/.env")
client = anthropic.Anthropic()

MODEL = "claude-haiku-4-5-20251001"

# ── 기존 프롬프트 (v1) ──────────────────────────────────────────
SYSTEM_PROMPT_V1 = """당신은 제조업 기술 문서에서 지식 그래프 엔티티와 관계를 추출하는 전문가입니다.

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

# ── 개선 프롬프트 (v2) ──────────────────────────────────────────
SYSTEM_PROMPT_V2 = """당신은 제조업 기술 문서에서 지식 그래프 엔티티와 관계를 추출하는 전문가입니다.

## 온톨로지 v1.1 스키마

### 노드 유형 (9개)
- Customer: 고객사 {name, alias, country}
- Equipment: 장비 {name, type, model, customer} — 문서에 언급된 **모든** 장비 포함 (주장비·보조장비 구분 없이)
- Product: 제품 {type, material, description} — 인서트 형번(C형·W형·T형 등) 전부 추출
- Component: 부품/광학계 {model, name, type, spec} — **모델번호(영문+숫자 혼합, 예: acA2500-14gm, M2514-MP2) 우선 포착**; 없으면 일반명칭
- Process: 공정/기능 {name, description, tool, parent}
- Issue: 이슈 {title, date, status, symptom, root_cause} — title은 **"[장비명] [현상]"** 형식으로 구체적으로 (예: "Korloy 포장기 #6 밝기 비대칭")
- Resolution: 조치방안 {description, category, effectiveness}
  ★ **각 조치방안은 반드시 별도 Resolution으로 분리** (여러 조치를 하나로 합치지 말 것)
  ★ description에는 **수치·구체적 방법** 포함 (예: "조명 높이 10mm 수준", "±1mm 이내 세팅")
  ★ category: "광학계 세팅" | "조명 조정" | "제품 운영 정책" | "소프트웨어 설정" | "기구 수정" | "기타"
- Person: 담당자 {name, dept, role}
- Tool: 소프트웨어 도구 {name, type}

### 관계 유형 (10개)
- OWNS: Customer → Equipment
- HAS_ISSUE: Equipment → Issue
- SIMILAR_TO: Issue → Issue (동일/유사 현상)
- RESOLVED_BY: Issue → Resolution  ← **각 Resolution마다 별도 RESOLVED_BY 관계 생성**
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

## few-shot 예시 (아래 패턴을 참고)
입력: "Korloy 포장기 #6에서 C,W형 경면 제품 밝기 비대칭 현상 발생. 조치1: 광축 중심과 조명 중심 ±1mm 세팅. 조치2: 조명 높이 10mm 수준 권장. 조치3: 경면 제품군 검사 제한."
출력:
{"entities":[
  {"type":"Equipment","id":"korloy_packing_6","name":"Korloy 포장기 #6","properties":{"customer":"Korloy"}},
  {"type":"Issue","id":"issue_brightness_asymmetry","name":"Korloy 포장기 #6 밝기 비대칭","properties":{"symptom":"C,W형 경면 제품 밝기 비대칭"}},
  {"type":"Resolution","id":"res_axis_align","name":"광축 중심과 조명 중심 ±1mm 이내 세팅","properties":{"description":"광축 중심과 조명 중심 상하좌우 ±1mm 이내 세팅","category":"광학계 세팅"}},
  {"type":"Resolution","id":"res_light_height","name":"조명 높이 10mm 수준 세팅","properties":{"description":"컨베이어 벨트 기준 조명 높이 10mm 수준으로 세팅","category":"조명 조정"}},
  {"type":"Resolution","id":"res_product_limit","name":"경면 제품군 검사 제한","properties":{"description":"경면 및 랜드부 경사가 큰 제품 검사 제한","category":"제품 운영 정책"}}
],"relations":[
  {"type":"HAS_ISSUE","from_id":"korloy_packing_6","to_id":"issue_brightness_asymmetry","properties":{}},
  {"type":"RESOLVED_BY","from_id":"issue_brightness_asymmetry","to_id":"res_axis_align","properties":{}},
  {"type":"RESOLVED_BY","from_id":"issue_brightness_asymmetry","to_id":"res_light_height","properties":{}},
  {"type":"RESOLVED_BY","from_id":"issue_brightness_asymmetry","to_id":"res_product_limit","properties":{}}
]}

## JSON 스키마
{"entities":[{"type":"NodeType","id":"unique_id","name":"표시명","properties":{"key":"value"}}],"relations":[{"type":"REL_TYPE","from_id":"id","to_id":"id","properties":{}}]}"""


def extract(text: str, page_title: str, system_prompt: str,
            chunk_size: int = 2000, max_tokens: int = 8192) -> dict:
    """청크 분할 추출 + 병합"""
    # 청크 분할
    chunks = []
    if len(text) <= chunk_size:
        chunks = [text]
    else:
        paragraphs = text.split('\n\n')
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 <= chunk_size:
                current = current + ("\n\n" if current else "") + para
            else:
                if current:
                    chunks.append(current.strip())
                if len(para) > chunk_size:
                    for i in range(0, len(para), chunk_size):
                        chunks.append(para[i:i + chunk_size].strip())
                    current = ""
                else:
                    current = para
        if current.strip():
            chunks.append(current.strip())

    seen_e, seen_r = set(), set()
    entities, relations = [], []
    total_cost = 0.0
    total_in, total_out = 0, 0

    for i, chunk in enumerate(chunks, 1):
        user_prompt = f"문서(파트 {i}/{len(chunks)}): {page_title}\n---\n{chunk}\n---\n순수 JSON만 출력:"
        resp = client.messages.create(
            model=MODEL, max_tokens=max_tokens,
            messages=[{"role": "user", "content": system_prompt + "\n\n" + user_prompt}]
        )
        raw = resp.content[0].text
        total_in += resp.usage.input_tokens
        total_out += resp.usage.output_tokens
        total_cost += resp.usage.input_tokens * 0.00000025 + resp.usage.output_tokens * 0.00000125

        m = re.search(r'\{[\s\S]*\}', raw)
        if not m:
            continue
        try:
            ext = json.loads(m.group())
        except Exception:
            continue

        for e in ext.get("entities", []):
            eid = e.get("id", "")
            if eid and eid not in seen_e:
                seen_e.add(eid)
                entities.append(e)
        for r in ext.get("relations", []):
            key = f"{r.get('type')}:{r.get('from_id')}:{r.get('to_id')}"
            if key not in seen_r:
                seen_r.add(key)
                relations.append(r)

        if i < len(chunks):
            time.sleep(0.2)

    return {
        "extracted": {"entities": entities, "relations": relations},
        "usage": {"input_tokens": total_in, "output_tokens": total_out,
                  "cost_usd": round(total_cost, 6)},
        "chunks": len(chunks),
    }


# 수동 기준 (10개 — 파일럿 Recall 측정용)
MANUAL_BASELINE_10 = {
    "Equipment": ["Korloy 포장기 #6", "혼입검사기"],
    "Customer": ["Korloy"],
    "Component": ["acA2500-14gm", "M2514-MP2", "DOMELIGHT100"],
    "Issue": ["Korloy 포장기 #6 밝기 비대칭"],
    "Resolution": [
        "광축 중심과 조명 중심 상하좌우 ±1mm 이내 세팅",
        "컨베이어 벨트 기준 조명 높이 10mm 수준 세팅 권장",
        "측정 가능 제품군 제한",
    ],
}


def compute_recall(entities: list, baseline: dict) -> dict:
    auto_names = set()
    for e in entities:
        n = e.get("name", e.get("id", "")).replace(" ", "").lower()
        if n:
            auto_names.add(n)

    matched, missed = [], []
    for etype, names in baseline.items():
        for name in names:
            key = name.replace(" ", "").lower()
            found = any(key in an or an in key for an in auto_names)
            if found:
                matched.append(f"{etype}:{name}")
            else:
                missed.append(f"{etype}:{name}")

    total = sum(len(v) for v in baseline.values())
    return {
        "total": total,
        "matched": matched,
        "missed": missed,
        "recall_pct": round(len(matched) / total * 100, 1) if total else 0,
    }


if __name__ == "__main__":
    TXT_ALL = Path("C:/MES/wta-agents/workspaces/research-agent/poc-texts-all")
    OUT_DIR = Path("C:/MES/wta-agents/workspaces/research-agent/claude-extract-results")

    # A/B 테스트: 밝기비대칭 파일럿 페이지
    pilot_file = TXT_ALL / "포장혼입검사" / \
        "9485484034-Korloy_포장기_#6(#25-3)_혼입_검사_특정_제품_밝기_비대칭.txt"

    text = pilot_file.read_text(encoding="utf-8")
    title_m = re.search(r'제목: (.+)', text)
    page_title = title_m.group(1).strip() if title_m else pilot_file.stem

    print("=" * 60)
    print("A/B 테스트: 프롬프트 v1 vs v2 (파일럿 페이지)")
    print("=" * 60)

    results = {}
    for version, prompt in [("v1_baseline", SYSTEM_PROMPT_V1), ("v2_improved", SYSTEM_PROMPT_V2)]:
        print(f"\n[{version}] 추출 중...")
        r = extract(text, page_title, prompt)
        ents = r["extracted"]["entities"]
        rels = r["extracted"]["relations"]
        cmp = compute_recall(ents, MANUAL_BASELINE_10)

        print(f"  엔티티: {len(ents)}개, 관계: {len(rels)}개")
        print(f"  Recall: {cmp['recall_pct']}% ({len(cmp['matched'])}/10)")
        print(f"  매칭: {cmp['matched']}")
        print(f"  누락: {cmp['missed']}")
        print(f"  비용: ${r['usage']['cost_usd']:.4f}")

        results[version] = {
            "entities": len(ents),
            "relations": len(rels),
            "recall_pct": cmp["recall_pct"],
            "matched": cmp["matched"],
            "missed": cmp["missed"],
            "cost_usd": r["usage"]["cost_usd"],
            "raw": r,
        }
        time.sleep(1)

    # 결과 저장
    out_file = OUT_DIR / "ab_test_results.json"
    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {out_file}")

    # 비교 요약
    v1 = results["v1_baseline"]
    v2 = results["v2_improved"]
    print("\n" + "=" * 60)
    print("비교 요약")
    print("=" * 60)
    print(f"  Recall: v1={v1['recall_pct']}% → v2={v2['recall_pct']}%  "
          f"({'+'  if v2['recall_pct'] >= v1['recall_pct'] else ''}{v2['recall_pct'] - v1['recall_pct']:.1f}%p)")
    print(f"  엔티티: v1={v1['entities']} → v2={v2['entities']}")
    print(f"  비용: v1=${v1['cost_usd']:.4f} → v2=${v2['cost_usd']:.4f}")
