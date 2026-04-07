"""
GraphRAG PoC Phase 3 Step 2: 프롬프트 v3
v2 대비 추가 개선:
  E. few-shot에 "부품: 모델번호" 패턴 명시
  F. 보조 장비(검사부/모듈) 명칭 추출 가이드
  G. Product 형번 목록 추출 가이드
"""
import sys, json, re, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv("C:/MES/wta-agents/.env")
client = anthropic.Anthropic()
MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT_V3 = """당신은 제조업 기술 문서에서 지식 그래프 엔티티와 관계를 추출하는 전문가입니다.

## 온톨로지 v1.1 스키마

### 노드 유형 (9개)
- Customer: 고객사 {name, alias, country}
- Equipment: 장비 {name, type, model, customer}
  ★ 문서에 등장하는 **모든** 장비/검사기/검사부 추출 (예: "혼입검사기", "포장기", "핸들러")
  ★ "~부", "~기", "~기계" 등 명사로 끝나는 장비 이름 모두 포함
- Product: 제품 {type, material, description}
  ★ 인서트 형번 전부 추출 (C형, W형, T형, S형, V형, B형 등 문서에 나온 모든 형번)
- Component: 부품/광학계 {model, name, type, spec}
  ★ **"카메라 : acA2500-14gm" 형식 → id에 모델번호, name에 종류(카메라/렌즈/조명)**
  ★ 영문+숫자 혼합 모델번호 (예: acA2500-14gm, M2514-MP2, DOMELIGHT100) 반드시 포착
  ★ 모델번호 없으면 일반 부품명 사용
- Process: 공정/기능 {name, description, tool, parent}
- Issue: 이슈 {title, date, status, symptom, root_cause}
  ★ title 형식: "[장비명] [현상]" (예: "Korloy 포장기 #6 밝기 비대칭")
- Resolution: 조치방안 {description, category, effectiveness}
  ★ **각 조치를 반드시 별도 Resolution으로 분리** (통합 금지)
  ★ description에 수치·구체적 방법 포함 (예: "±1mm 이내", "높이 10mm 수준")
  ★ category: 광학계 세팅 | 조명 조정 | 제품 운영 정책 | 소프트웨어 설정 | 기구 수정 | 기타
- Person: 담당자 {name, dept, role}
- Tool: 소프트웨어 도구 {name, type}

### 관계 유형 (10개)
OWNS(Customer→Equipment), HAS_ISSUE(Equipment→Issue), SIMILAR_TO(Issue→Issue),
RESOLVED_BY(Issue→Resolution) ★각 Resolution마다 별도 관계,
INVOLVES_COMPONENT(Issue→Component), USES_COMPONENT(Equipment→Component),
INVOLVED_IN(Product→Issue), HAS_SUBPROCESS(Process→Process),
USES_TOOL(Process→Tool), MAINTAINS(Person→Process)

## 출력 규칙
1. 반드시 순수 JSON만 출력 (마크다운, 설명 없음)
2. 텍스트에 명시된 정보만 추출
3. id는 영문 snake_case
4. from_id/to_id는 entities id와 일치

## few-shot 예시
입력:
"한국 야금 포장기 혼입검사부에서 C, W형 경면 제품 밝기 비대칭 현상 확인.
광학계 구성 카메라: acA2500-14gm, 렌즈: M2514-MP2, 조명: DOMELIGHT100
조치1: 광축 중심과 조명 중심 ±1mm 이내 세팅.
조치2: 조명 높이 10mm 수준 권장.
조치3: 경면 제품군 측정 제한."

출력:
{"entities":[
  {"type":"Customer","id":"korloy","name":"한국 야금","properties":{}},
  {"type":"Equipment","id":"packing_machine_6","name":"Korloy 포장기 #6","properties":{"customer":"한국 야금"}},
  {"type":"Equipment","id":"contamination_inspector","name":"혼입검사기","properties":{"type":"검사기"}},
  {"type":"Product","id":"prod_c_type","name":"C형 경면 제품","properties":{"material":"경면"}},
  {"type":"Product","id":"prod_w_type","name":"W형 경면 제품","properties":{"material":"경면"}},
  {"type":"Component","id":"aca2500_14gm","name":"카메라","properties":{"model":"acA2500-14gm","type":"카메라"}},
  {"type":"Component","id":"m2514_mp2","name":"렌즈","properties":{"model":"M2514-MP2","type":"렌즈"}},
  {"type":"Component","id":"domelight100","name":"조명","properties":{"model":"DOMELIGHT100","type":"조명"}},
  {"type":"Issue","id":"issue_brightness","name":"Korloy 포장기 #6 밝기 비대칭","properties":{"symptom":"C,W형 경면 제품 밝기 비대칭"}},
  {"type":"Resolution","id":"res_axis","name":"광축 중심 ±1mm 이내 세팅","properties":{"description":"광축 중심과 조명 중심 상하좌우 ±1mm 이내 세팅","category":"광학계 세팅"}},
  {"type":"Resolution","id":"res_height","name":"조명 높이 10mm 수준 권장","properties":{"description":"컨베이어 벨트 기준 조명 높이 10mm 수준으로 세팅","category":"조명 조정"}},
  {"type":"Resolution","id":"res_limit","name":"경면 제품군 측정 제한","properties":{"description":"경면 및 랜드부 경사가 큰 제품 측정 제한","category":"제품 운영 정책"}}
],"relations":[
  {"type":"OWNS","from_id":"korloy","to_id":"packing_machine_6","properties":{}},
  {"type":"HAS_ISSUE","from_id":"packing_machine_6","to_id":"issue_brightness","properties":{}},
  {"type":"USES_COMPONENT","from_id":"contamination_inspector","to_id":"aca2500_14gm","properties":{}},
  {"type":"USES_COMPONENT","from_id":"contamination_inspector","to_id":"m2514_mp2","properties":{}},
  {"type":"USES_COMPONENT","from_id":"contamination_inspector","to_id":"domelight100","properties":{}},
  {"type":"INVOLVES_COMPONENT","from_id":"issue_brightness","to_id":"aca2500_14gm","properties":{}},
  {"type":"RESOLVED_BY","from_id":"issue_brightness","to_id":"res_axis","properties":{}},
  {"type":"RESOLVED_BY","from_id":"issue_brightness","to_id":"res_height","properties":{}},
  {"type":"RESOLVED_BY","from_id":"issue_brightness","to_id":"res_limit","properties":{}}
]}

## JSON 스키마
{"entities":[{"type":"NodeType","id":"unique_id","name":"표시명","properties":{}}],"relations":[{"type":"REL_TYPE","from_id":"id","to_id":"id","properties":{}}]}"""


def extract(text: str, page_title: str, system_prompt: str,
            chunk_size: int = 2000, max_tokens: int = 8192) -> dict:
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
                seen_e.add(eid); entities.append(e)
        for r in ext.get("relations", []):
            key = f"{r.get('type')}:{r.get('from_id')}:{r.get('to_id')}"
            if key not in seen_r:
                seen_r.add(key); relations.append(r)
        if i < len(chunks):
            time.sleep(0.2)

    return {"extracted": {"entities": entities, "relations": relations},
            "usage": {"input_tokens": total_in, "output_tokens": total_out,
                      "cost_usd": round(total_cost, 6)}, "chunks": len(chunks)}


MANUAL_BASELINE_10 = {
    "Equipment": ["Korloy 포장기 #6", "혼입검사기"],
    "Customer": ["Korloy"],
    "Component": ["acA2500-14gm", "M2514-MP2", "DOMELIGHT100"],
    "Issue": ["Korloy 포장기 #6 밝기 비대칭"],
    "Resolution": ["광축 중심과 조명 중심 상하좌우 ±1mm 이내 세팅",
                   "컨베이어 벨트 기준 조명 높이 10mm 수준 세팅 권장",
                   "측정 가능 제품군 제한"],
}


def compute_recall(entities, baseline):
    auto = set()
    for e in entities:
        n = e.get("name", e.get("id", "")).replace(" ", "").lower()
        # properties에서도 모델번호 탐색
        for v in e.get("properties", {}).values():
            if isinstance(v, str):
                auto.add(v.replace(" ", "").lower())
        if n:
            auto.add(n)

    matched, missed = [], []
    for etype, names in baseline.items():
        for name in names:
            key = name.replace(" ", "").lower()
            found = any(key in a or a in key for a in auto)
            if found:
                matched.append(f"{etype}:{name}")
            else:
                missed.append(f"{etype}:{name}")
    total = sum(len(v) for v in baseline.values())
    return {"total": total, "matched": matched, "missed": missed,
            "recall_pct": round(len(matched) / total * 100, 1) if total else 0}


if __name__ == "__main__":
    TXT_ALL = Path("C:/MES/wta-agents/workspaces/research-agent/poc-texts-all")
    OUT_DIR = Path("C:/MES/wta-agents/workspaces/research-agent/claude-extract-results")

    pilot_file = TXT_ALL / "포장혼입검사" / \
        "9485484034-Korloy_포장기_#6(#25-3)_혼입_검사_특정_제품_밝기_비대칭.txt"
    text = pilot_file.read_text(encoding="utf-8")
    title_m = re.search(r'제목: (.+)', text)
    page_title = title_m.group(1).strip() if title_m else pilot_file.stem

    print("=== v3 프롬프트 테스트 ===\n")

    # v3 3회 반복 (안정성 확인)
    recalls = []
    for run in range(3):
        r = extract(text, page_title, SYSTEM_PROMPT_V3)
        ents = r["extracted"]["entities"]
        cmp = compute_recall(ents, MANUAL_BASELINE_10)
        recalls.append(cmp["recall_pct"])
        print(f"[Run {run+1}] Recall: {cmp['recall_pct']}% | 엔티티: {len(ents)} | 비용: ${r['usage']['cost_usd']:.4f}")
        print(f"  매칭: {cmp['matched']}")
        print(f"  누락: {cmp['missed']}")
        if run < 2:
            time.sleep(1)

    avg_recall = sum(recalls) / len(recalls)
    print(f"\n평균 Recall (3회): {avg_recall:.1f}%")

    # 결과 저장
    final_r = extract(text, page_title, SYSTEM_PROMPT_V3)
    results = {
        "v3_improved": {
            "prompt_version": "v3",
            "runs_recall": recalls,
            "avg_recall": avg_recall,
            "entities": len(final_r["extracted"]["entities"]),
            "relations": len(final_r["extracted"]["relations"]),
            "cost_usd": final_r["usage"]["cost_usd"],
        }
    }
    # 기존 ab_test_results.json에 추가
    ab_path = OUT_DIR / "ab_test_results.json"
    existing = json.loads(ab_path.read_text(encoding='utf-8'))
    existing.update(results)
    ab_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n결과 저장: {ab_path}")
