"""
GraphRAG PoC: 규칙 기반(Rule-based) 엔티티 추출 (LLM fallback)
대상: 혼입분류_정리 페이지 (9596731397)
LLM 미가용 시 패턴 매칭으로 추출 — 수동 결과와 비교
"""
import sys, re, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

TXT_FILE = Path("C:/MES/wta-agents/workspaces/research-agent/poc-texts/9596731397-혼입분류_정리.txt")
text = TXT_FILE.read_text(encoding="utf-8")

# ===== 규칙 기반 추출 패턴 =====

# 1) 광학 부품 모델 (영문+숫자 패턴)
component_patterns = [
    (r'\bacA\d{4}-\d+\w*\b', '카메라'),
    (r'\bM\d{4}-\w+\b', '렌즈'),
    (r'\bDOMELIGHT\w*\b', '조명'),
    (r'\bBasler\b', '카메라 브랜드'),
]

# 2) 코그넥스 도구 (Tool)
tool_patterns = [
    r'코그넥스',
    r'Align\s*Tool',
    r'Polygon\s*Tool',
    r'FindCircleTool',
    r'FindCornerTool',
    r'Tracker\s*Tool',
]

# 3) 공정명 키워드
process_patterns = [
    r'혼입\s*분류',
    r'CB\s*방향\s*구분',
    r'앞뒷면\s*구분',
    r'CB\s*혼입\s*비교',
    r'NoseR\s*측정',
    r'레시피\s*에디터',
    r'위치\s*검사',
]

# 4) 제품 유형 (인서트 종류)
product_patterns = [
    r'[CWTSV]형\s*인서트',
    r'B형\s*인서트',
    r'경면\s*제품',
]

# 5) 고객사
customer_patterns = [
    r'Korloy|한국야금',
]

# 6) 담당자명 (한글 2~4글자 + 팀/담당)
person_patterns = [
    r'[가-힣]{2,4}\s*(?:팀장|담당|주임|대리|과장|차장|부장)',
    r'정진원',
]

def extract_unique(patterns, text, label):
    found = []
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        for m in matches:
            m = m.strip()
            if m and m not in found:
                found.append(m)
    return [(label, m) for m in found]

results = []
results += extract_unique([p[0] for p in component_patterns], text, "Component")
results += extract_unique(tool_patterns, text, "Tool")
results += extract_unique(process_patterns, text, "Process")
results += extract_unique(product_patterns, text, "Product")
results += extract_unique(customer_patterns, text, "Customer")
results += extract_unique(person_patterns, text, "Person")

print(f"=== 규칙 기반 추출 결과 ({TXT_FILE.name}) ===")
print(f"총 {len(results)}개 엔티티 후보 발견\n")

by_type = {}
for etype, name in results:
    by_type.setdefault(etype, []).append(name)

for etype, names in sorted(by_type.items()):
    print(f"[{etype}] ({len(names)}개)")
    for n in names:
        print(f"  - {n}")

# ===== 수동 추출 기준선과 비교 =====
MANUAL_ENTITIES = {
    "Process": ["혼입 분류", "CB 방향 구분", "앞뒷면 구분", "CB 혼입 비교", "NoseR 측정", "레시피 에디터", "위치 검사"],
    "Tool": ["코그넥스"],
    "Product": ["C형 인서트", "W형 인서트", "T형 인서트", "S형 인서트", "V형 인서트", "B형 인서트"],
    "Component": ["acA2500-14gm", "M2514-MP2", "DOMELIGHT100"],
    "Person": ["정진원"],
}
MANUAL_TOTAL = sum(len(v) for v in MANUAL_ENTITIES.values())

auto_names_flat = [n.replace(" ", "") for _, n in results]

matched, missed = [], []
for etype, names in MANUAL_ENTITIES.items():
    for name in names:
        key = name.replace(" ", "")
        found = any(key in an or an in key for an in auto_names_flat)
        if found:
            matched.append(f"{etype}:{name}")
        else:
            missed.append(f"{etype}:{name}")

print(f"\n=== 수동 기준 비교 ===")
print(f"수동 기준: {MANUAL_TOTAL}개")
print(f"규칙 기반 매칭: {len(matched)}개 ({len(matched)/MANUAL_TOTAL*100:.0f}%)")
print(f"\n매칭됨: {matched}")
print(f"누락됨: {missed}")

out = {
    "source_file": TXT_FILE.name,
    "method": "rule-based",
    "rule_extracted": len(results),
    "manual_baseline": MANUAL_TOTAL,
    "matched": matched,
    "missed": missed,
    "recall_pct": round(len(matched)/MANUAL_TOTAL*100, 1),
    "by_type": {k: v for k, v in by_type.items()},
}
out_file = Path("C:/MES/wta-agents/workspaces/research-agent/poc-rule-extract-result.json")
out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n결과 저장: {out_file}")
