"""
Phase 3 Step 2: v3 프롬프트로 전체 31페이지 재추출
"""
import sys, json, re, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv("C:/MES/wta-agents/.env")
client = anthropic.Anthropic()
MODEL = "claude-haiku-4-5-20251001"
CHUNK_SIZE = 2000
MAX_TOKENS = 8192

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


def extract_file(txt_file: Path, topic: str, page_num: int) -> dict:
    text = txt_file.read_text(encoding='utf-8')
    title_m = re.search(r'제목: (.+)', text)
    title = title_m.group(1).strip() if title_m else txt_file.stem
    chunks = split_chunks(text, CHUNK_SIZE)

    seen_e, seen_r = set(), set()
    entities, relations = [], []
    total_cost = 0.0
    total_in, total_out = 0, 0

    for i, chunk in enumerate(chunks, 1):
        user_prompt = f"문서(파트 {i}/{len(chunks)}): {title}\n---\n{chunk}\n---\n순수 JSON만 출력:"
        resp = client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": SYSTEM_PROMPT_V3 + "\n\n" + user_prompt}]
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

    return {
        "topic": topic,
        "file": txt_file.name,
        "page_title": title,
        "extracted": {"entities": entities, "relations": relations},
        "usage": {"input_tokens": total_in, "output_tokens": total_out,
                  "cost_usd": round(total_cost, 6)},
        "chunks_processed": len(chunks),
    }


if __name__ == "__main__":
    TXT_ALL = Path("C:/MES/wta-agents/workspaces/research-agent/poc-texts-all")
    OUT_DIR = Path("C:/MES/wta-agents/workspaces/research-agent/claude-extract-results")
    topics = ["포장혼입검사", "장비물류", "분말검사", "연삭측정제어", "호닝신뢰성"]

    print("=== Phase 3 Step 2: v3 프롬프트 전체 31페이지 추출 ===\n")
    all_results = []
    total_cost = 0.0
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
            print(f"  [{page_num}] {txt_file.name[:55]}", end=" ", flush=True)
            try:
                r = extract_file(txt_file, topic, page_num)
                ents = len(r["extracted"]["entities"])
                rels = len(r["extracted"]["relations"])
                cost = r["usage"]["cost_usd"]
                total_cost += cost
                print(f"→ {ents}E/{rels}R ${cost:.4f}")
                all_results.append(r)
            except Exception as e:
                print(f"→ 오류: {e}")
                all_results.append({"topic": topic, "file": txt_file.name, "error": str(e)})
                errors += 1
            time.sleep(0.3)

    # 통계
    success = [r for r in all_results if "error" not in r]
    total_e = sum(len(r["extracted"]["entities"]) for r in success)
    total_r = sum(len(r["extracted"]["relations"]) for r in success)

    out_file = OUT_DIR / "v3_all_results.json"
    out_file.write_text(json.dumps({
        "prompt_version": "v3",
        "total_pages": page_num,
        "success_pages": len(success),
        "error_pages": errors,
        "total_entities": total_e,
        "total_relations": total_r,
        "total_cost_usd": round(total_cost, 4),
        "results": all_results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== 완료 ===")
    print(f"성공: {len(success)}/{page_num}, 오류: {errors}")
    print(f"총 엔티티: {total_e}, 관계: {total_r}")
    print(f"총 비용: ${total_cost:.4f}")
    print(f"결과: {out_file}")
