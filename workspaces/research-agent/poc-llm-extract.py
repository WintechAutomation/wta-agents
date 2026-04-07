"""
GraphRAG PoC: Ollama qwen3.5:35b-a3b로 엔티티·관계 자동 추출 파일럿
대상: 혼입분류_정리 페이지 (9596731397)
수동 추출 결과와 비교하여 정확도 측정
"""
import sys, os, json, re, urllib.request, urllib.error
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

OLLAMA_BASE = "http://182.224.6.147:11434"
LLM_MODEL = "gemma4:e2b"

# 대상 파일
TXT_FILE = Path("C:/MES/wta-agents/workspaces/research-agent/poc-texts/9596731397-혼입분류_정리.txt")
text = TXT_FILE.read_text(encoding="utf-8")

PROMPT = f"""당신은 제조업 기술 문서에서 지식 그래프용 엔티티와 관계를 추출하는 전문가입니다.

**추출할 엔티티 유형:**
- Customer: 고객사명
- Equipment: 장비명
- Product: 제품유형
- Component: 부품/광학계 모델명
- Process: 공정/기능명
- Issue: 이슈명/증상
- Resolution: 조치방안
- Person: 담당자명
- Tool: 소프트웨어 도구명

**추출할 관계 유형:**
OWNS, HAS_ISSUE, RESOLVED_BY, INVOLVES_COMPONENT, USES_COMPONENT, INVOLVED_IN, HAS_SUBPROCESS, USES_TOOL, MAINTAINS, SIMILAR_TO

**반드시 아래 JSON 형식만 출력하세요 (설명, 마크다운 코드블록 없이):**
{{"entities":[{{"type":"EntityType","id":"unique_id","name":"표시명","properties":{{}}}}],"relations":[{{"type":"REL_TYPE","from_id":"id","to_id":"id"}}]}}

**분석할 문서:**
{text[:3000]}"""

print("=== Ollama 엔티티·관계 자동 추출 파일럿 ===")
print(f"모델: {LLM_MODEL}")
print(f"대상: {TXT_FILE.name} ({len(text):,}자, 앞 3000자)\n")

payload = json.dumps({
    "model": LLM_MODEL,
    "messages": [{"role": "user", "content": PROMPT}],
    "stream": False,
    "options": {"temperature": 0.0, "num_predict": 4096}
}).encode("utf-8")

req = urllib.request.Request(
    f"{OLLAMA_BASE}/api/chat",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)

print("LLM 호출 중... (최대 5분)")
try:
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read())
        raw = data["message"]["content"]
except Exception as e:
    print(f"API 호출 실패: {e}")
    sys.exit(1)

print(f"응답 수신: {len(raw)}자")

# JSON 추출
json_match = re.search(r'\{[\s\S]*\}', raw)
if not json_match:
    print("JSON 형식 미발견. 원시 응답:")
    print(raw[:1000])
    sys.exit(1)

try:
    extracted = json.loads(json_match.group())
except json.JSONDecodeError as e:
    print(f"JSON 파싱 오류: {e}")
    print(raw[:500])
    sys.exit(1)

entities = extracted.get("entities", [])
relations = extracted.get("relations", [])

print(f"\n자동 추출: 엔티티 {len(entities)}개, 관계 {len(relations)}개")

# ===== 수동 추출 기준선 (poc-load-graph.py에서 9596731397 페이지 관련) =====
MANUAL_ENTITIES = {
    "Process": ["혼입 분류", "CB 방향 구분", "앞뒷면 구분", "CB 혼입 비교", "NoseR 측정", "레시피 에디터", "위치 검사"],
    "Tool": ["코그넥스"],
    "Product": ["C형 인서트", "W형 인서트", "T형 인서트", "S형 인서트", "V형 인서트", "B형 인서트"],
    "Component": ["acA2500-14gm", "M2514-MP2", "DOMELIGHT100"],
    "Person": ["정진원"],
}
MANUAL_TOTAL = sum(len(v) for v in MANUAL_ENTITIES.values())

print(f"\n=== 정확도 비교 ===")
print(f"수동 추출 기준: {MANUAL_TOTAL}개 엔티티")

# 자동 추출된 엔티티 이름 집합
auto_names = set()
for e in entities:
    name = e.get("name", e.get("id", "")).strip()
    auto_names.add(name)

# 수동 항목 매칭 확인 (부분 일치 포함)
matched = []
missed = []
for etype, names in MANUAL_ENTITIES.items():
    for name in names:
        # 자동 추출 결과에서 유사 매칭
        found = any(
            name in auto_n or auto_n in name or
            name.replace(" ", "") in auto_n.replace(" ", "")
            for auto_n in auto_names
        )
        if found:
            matched.append(f"{etype}:{name}")
        else:
            missed.append(f"{etype}:{name}")

precision_base = len(matched)
recall_pct = precision_base / MANUAL_TOTAL * 100

print(f"\n[매칭됨 ({len(matched)}개)]")
for m in matched:
    print(f"  ✓ {m}")

print(f"\n[누락됨 ({len(missed)}개)]")
for m in missed:
    print(f"  ✗ {m}")

# 오추출 확인 (자동 추출 중 수동 기준에 없는 항목)
known_names = set()
for names in MANUAL_ENTITIES.values():
    for n in names:
        known_names.add(n)

extra = []
for e in entities:
    name = e.get("name", e.get("id", "")).strip()
    if name and not any(k in name or name in k for k in known_names):
        extra.append(f"{e.get('type','?')}:{name}")

print(f"\n[추가 발견 ({len(extra)}개 — 수동 기준 외 항목)]")
for ex in extra[:10]:
    print(f"  + {ex}")

print(f"\n=== 자동 추출 정확도 요약 ===")
print(f"  수동 기준 Recall: {recall_pct:.0f}% ({len(matched)}/{MANUAL_TOTAL})")
print(f"  추가 발견 엔티티: {len(extra)}개")
print(f"  자동 추출 관계: {len(relations)}개")

# 결과 저장
out = {
    "source_file": TXT_FILE.name,
    "model": LLM_MODEL,
    "text_chars_used": min(len(text), 3000),
    "auto_entities_count": len(entities),
    "auto_relations_count": len(relations),
    "manual_baseline_count": MANUAL_TOTAL,
    "matched_count": len(matched),
    "missed_count": len(missed),
    "extra_count": len(extra),
    "recall_pct": round(recall_pct, 1),
    "matched": matched,
    "missed": missed,
    "extra": extra,
    "entities": entities,
    "relations": relations,
}
out_file = Path("C:/MES/wta-agents/workspaces/research-agent/poc-llm-extract-result.json")
out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n결과 저장: {out_file}")
