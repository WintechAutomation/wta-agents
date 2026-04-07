"""
v3 프롬프트 5페이지 확장 테스트 (주제별 1페이지씩)
엔티티 수, 관계 수, Resolution 분리도, Component 포착률 측정
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

CHUNK_SIZE = 2000
MAX_TOKENS = 8192

# 5페이지 샘플 (주제별 1페이지)
TEST_FILES = [
    ("포장혼입검사", "8685453351-혼입_검사_이슈.txt"),
    ("장비물류", "9043474945-후지산기_핸들러_물류.txt"),
    ("분말검사", "8619938893-측면_Burr_불가_제품_분류.txt"),
    ("연삭측정제어", "9043605003-연삭_핸들러_연삭제어.txt"),
    ("호닝신뢰성", "8081960803-호닝_형상_검사기_개요.txt"),
]


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


def extract_file(txt_file, system_prompt):
    text = txt_file.read_text(encoding='utf-8')
    title_m = re.search(r'제목: (.+)', text)
    title = title_m.group(1).strip() if title_m else txt_file.stem
    chunks = split_chunks(text, CHUNK_SIZE)

    seen_e, seen_r = set(), set()
    entities, relations = [], []
    total_cost = 0.0

    for i, chunk in enumerate(chunks, 1):
        user_prompt = f"문서(파트 {i}/{len(chunks)}): {title}\n---\n{chunk}\n---\n순수 JSON만 출력:"
        resp = client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": system_prompt + "\n\n" + user_prompt}]
        )
        raw = resp.content[0].text
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

    # 타입별 카운트
    type_counts = {}
    for e in entities:
        t = e.get("type", "")
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "title": title,
        "text_len": len(text),
        "chunks": len(chunks),
        "entities": len(entities),
        "relations": len(relations),
        "type_counts": type_counts,
        "cost_usd": round(total_cost, 6),
        "resolution_count": type_counts.get("Resolution", 0),
        "component_count": type_counts.get("Component", 0),
        "issue_count": type_counts.get("Issue", 0),
    }


if __name__ == "__main__":
    TXT_ALL = Path("C:/MES/wta-agents/workspaces/research-agent/poc-texts-all")
    OUT_DIR = Path("C:/MES/wta-agents/workspaces/research-agent/claude-extract-results")

    print("=== v3 프롬프트 5페이지 확장 테스트 ===\n")
    results_v3 = []
    total_cost = 0.0
    existing_results = []  # v1과 비교할 기존 결과 (all_results.json에서)

    all_data = json.loads((OUT_DIR / "all_results.json").read_text(encoding='utf-8'))

    for topic, filename in TEST_FILES:
        txt_file = TXT_ALL / topic / filename
        if not txt_file.exists():
            # 파일 없으면 대안 찾기
            files = sorted((TXT_ALL / topic).glob("*.txt"))
            if files:
                txt_file = files[0]
                filename = txt_file.name
            else:
                print(f"  [{topic}] 파일 없음")
                continue

        print(f"[{topic}] {filename[:50]}")

        # v3 추출
        r_v3 = extract_file(txt_file, SYSTEM_PROMPT_V3)
        results_v3.append({"topic": topic, "file": filename, **r_v3})
        total_cost += r_v3["cost_usd"]

        # v1 결과 찾기 (비교용)
        v1_match = next((r for r in all_data["results"]
                        if r.get("file") == filename and "error" not in r), None)
        v1_e = len(v1_match.get("extracted", {}).get("entities", [])) if v1_match else "N/A"
        v1_r = len(v1_match.get("extracted", {}).get("relations", [])) if v1_match else "N/A"
        v1_res = sum(1 for e in v1_match.get("extracted", {}).get("entities", [])
                    if e.get("type") == "Resolution") if v1_match else "N/A"
        v1_comp = sum(1 for e in v1_match.get("extracted", {}).get("entities", [])
                     if e.get("type") == "Component") if v1_match else "N/A"

        print(f"  v1: 엔티티 {v1_e}, 관계 {v1_r}, Resolution {v1_res}, Component {v1_comp}")
        print(f"  v3: 엔티티 {r_v3['entities']}, 관계 {r_v3['relations']}, "
              f"Resolution {r_v3['resolution_count']}, Component {r_v3['component_count']}")
        print(f"  Resolution 타입별: {r_v3['type_counts']}, 비용: ${r_v3['cost_usd']:.4f}")
        time.sleep(0.5)

    print(f"\n총 비용: ${total_cost:.4f}")
    print(f"\n[v3 5페이지 요약]")
    total_e = sum(r["entities"] for r in results_v3)
    total_r = sum(r["relations"] for r in results_v3)
    total_res = sum(r["resolution_count"] for r in results_v3)
    total_comp = sum(r["component_count"] for r in results_v3)
    print(f"  엔티티: {total_e}, 관계: {total_r}, Resolution: {total_res}, Component: {total_comp}")

    out = OUT_DIR / "v3_5page_test.json"
    out.write_text(json.dumps({"results": results_v3, "total_cost": total_cost},
                              ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"결과: {out}")
