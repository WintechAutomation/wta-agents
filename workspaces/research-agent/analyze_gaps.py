"""
Phase 3 Step 2: 수동 vs LLM 추출 누락 패턴 분석
포장혼입검사 밝기비대칭 페이지(파일럿) 심층 분석 + 전체 31페이지 통계 분석
"""
import sys, json, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from collections import Counter, defaultdict

BASE = Path("C:/MES/wta-agents/workspaces/research-agent")
OUT_DIR = BASE / "claude-extract-results"

# ─────────────────────────────────────────
# 1. 수동 기준 전체 (Phase 1 포장혼입검사 7페이지)
# ─────────────────────────────────────────
MANUAL_ALL = {
    # Customer
    ("Customer", "Korloy"),
    # Equipment
    ("Equipment", "Korloy 포장기 #6"),
    ("Equipment", "혼입검사기"),
    # Product (6개)
    ("Product", "C형 인서트"),
    ("Product", "W형 인서트"),
    ("Product", "T형 인서트"),
    ("Product", "S형 인서트"),
    ("Product", "V형 인서트"),
    ("Product", "B형 인서트"),
    # Component (3개)
    ("Component", "acA2500-14gm"),
    ("Component", "M2514-MP2"),
    ("Component", "DOMELIGHT100"),
    # Process (7개)
    ("Process", "혼입 분류"),
    ("Process", "CB 방향 구분"),
    ("Process", "앞뒷면 구분"),
    ("Process", "CB 혼입 비교"),
    ("Process", "NoseR 측정"),
    ("Process", "레시피 에디터"),
    ("Process", "위치 검사"),
    # Issue (2개)
    ("Issue", "Korloy 포장기 #6 밝기 비대칭"),
    ("Issue", "혼입 검사 이슈"),
    # Resolution (3개)
    ("Resolution", "광축 중심과 조명 중심 상하좌우 ±1mm 이내 세팅"),
    ("Resolution", "컨베이어 벨트 기준 조명 높이 10mm 수준 세팅 권장"),
    ("Resolution", "측정 가능 제품군 제한"),
    # Person (1개)
    ("Person", "정진원"),
    # Tool (1개)
    ("Tool", "코그넥스"),
}

# 파일럿용 간소 기준 (Recall 60% 측정에 사용된 10개)
MANUAL_PILOT_10 = {
    ("Equipment", "Korloy 포장기 #6"),
    ("Equipment", "혼입검사기"),
    ("Customer", "Korloy"),
    ("Component", "acA2500-14gm"),
    ("Component", "M2514-MP2"),
    ("Component", "DOMELIGHT100"),
    ("Issue", "Korloy 포장기 #6 밝기 비대칭"),
    ("Resolution", "광축 중심과 조명 중심 상하좌우 ±1mm 이내 세팅"),
    ("Resolution", "컨베이어 벨트 기준 조명 높이 10mm 수준 세팅 권장"),
    ("Resolution", "측정 가능 제품군 제한"),
}


def name_key(name: str) -> str:
    return name.replace(" ", "").lower()


def match_entity(etype: str, ename: str, llm_entities: list) -> bool:
    ekey = name_key(ename)
    for e in llm_entities:
        if e.get("type") != etype:
            continue
        n = e.get("name", e.get("id", ""))
        nk = name_key(n)
        # props에서도 검색
        props_vals = [name_key(str(v)) for v in e.get("properties", {}).values() if v]
        if ekey in nk or nk in ekey or any(ekey in pv or pv in ekey for pv in props_vals):
            return True
    return False


# ─────────────────────────────────────────
# 2. 파일럿 페이지 심층 분석
# ─────────────────────────────────────────
pilot_result = json.loads((OUT_DIR / "pilot_result.json").read_bytes())
# claude 파일럿 결과
claude_pilot = json.loads((OUT_DIR.parent / "claude-extract-results" / "pilot_result.json").read_bytes())

# claude_extract pilot
claude_pilot_path = OUT_DIR / "pilot_result.json"
# 실제로 claude_extract_results/pilot_result.json이 claude 파일럿
# qwen-extract-results/pilot_result.json이 qwen 파일럿

claude_pilot_ents = claude_pilot.get("result", {}).get("extracted", {}).get("entities", []) or \
                    claude_pilot.get("extracted", {}).get("entities", [])

print("=" * 60)
print("1. 파일럿 페이지 (밝기비대칭) 심층 분석")
print("=" * 60)

print(f"\n[수동 기준 10개 vs Claude Haiku]\n")
matched_10, missed_10 = [], []
for etype, ename in MANUAL_PILOT_10:
    if match_entity(etype, ename, claude_pilot_ents):
        matched_10.append((etype, ename))
    else:
        missed_10.append((etype, ename))

print(f"  매칭: {len(matched_10)}/10 = {len(matched_10)*10}%")
for t, n in matched_10:
    print(f"    ✅ {t}: {n}")
print(f"  누락: {len(missed_10)}/10")
for t, n in missed_10:
    print(f"    ❌ {t}: {n}")

# 수동 27개 전체 기준
print(f"\n[수동 전체 27개 vs Claude Haiku]\n")
matched_all, missed_all = [], []
for etype, ename in MANUAL_ALL:
    if match_entity(etype, ename, claude_pilot_ents):
        matched_all.append((etype, ename))
    else:
        missed_all.append((etype, ename))
print(f"  Recall: {len(matched_all)}/{len(MANUAL_ALL)} = {round(len(matched_all)/len(MANUAL_ALL)*100)}%")
print(f"  누락 ({len(missed_all)}개):")
by_type = defaultdict(list)
for t, n in missed_all:
    by_type[t].append(n)
for t in sorted(by_type):
    print(f"    {t}: {', '.join(by_type[t])}")


# ─────────────────────────────────────────
# 3. 전체 31페이지 통계 분석
# ─────────────────────────────────────────
print("\n" + "=" * 60)
print("2. 전체 31페이지 엔티티 분포 분석")
print("=" * 60)

all_data = json.loads((OUT_DIR / "all_results.json").read_text(encoding='utf-8'))
retry_data = json.loads((OUT_DIR / "chunk_retry_results.json").read_text(encoding='utf-8'))
honing_data = json.loads((OUT_DIR / "chunk_retry_honing_issue.json").read_text(encoding='utf-8'))

all_pages = []
for r in all_data["results"]:
    if "error" not in r:
        all_pages.append(r)
for r in retry_data["results"]:
    if "error" not in r and "extracted" in r:
        all_pages.append(r)
if "error" not in honing_data and "extracted" in honing_data:
    all_pages.append(honing_data)

# 타입별 카운트
type_counts = Counter()
name_lengths = defaultdict(list)
entities_per_page = []
relations_per_page = []
resolution_lengths = []

for page in all_pages:
    ext = page.get("extracted", {})
    ents = ext.get("entities", [])
    rels = ext.get("relations", [])
    entities_per_page.append(len(ents))
    relations_per_page.append(len(rels))
    for e in ents:
        t = e.get("type", "Unknown")
        type_counts[t] += 1
        n = e.get("name", "")
        name_lengths[t].append(len(n))
        if t == "Resolution":
            resolution_lengths.append(len(n))

print(f"\n총 페이지: {len(all_pages)}")
print(f"평균 엔티티/페이지: {sum(entities_per_page)/len(entities_per_page):.1f}")
print(f"평균 관계/페이지: {sum(relations_per_page)/len(relations_per_page):.1f}")
print(f"\n타입별 총 엔티티:")
for t, cnt in type_counts.most_common():
    avg_name_len = sum(name_lengths[t]) / len(name_lengths[t]) if name_lengths[t] else 0
    print(f"  {t:12s}: {cnt:4d}개  (평균 이름 길이: {avg_name_len:.1f}자)")


# ─────────────────────────────────────────
# 4. Resolution 누락 원인 심층 분석
# ─────────────────────────────────────────
print("\n" + "=" * 60)
print("3. Resolution(조치방안) 추출 패턴 분석")
print("=" * 60)

resolutions_all = []
for page in all_pages:
    ext = page.get("extracted", {})
    topic = page.get("topic", "")
    for e in ext.get("entities", []):
        if e.get("type") == "Resolution":
            resolutions_all.append({
                "topic": topic,
                "name": e.get("name", ""),
                "desc": e.get("properties", {}).get("description", ""),
            })

# 짧은 이름 Resolution (10자 미만 = 추상적/통합 표현)
short_res = [r for r in resolutions_all if len(r["name"]) < 15]
specific_res = [r for r in resolutions_all if len(r["name"]) >= 15]
print(f"\n조치방안 총 {len(resolutions_all)}개")
print(f"  짧은 이름(<15자): {len(short_res)}개 — 추상적/통합 표현")
print(f"  구체적(>=15자): {len(specific_res)}개 — 수동 기준 유사")
print(f"\n  짧은 Resolution 샘플:")
for r in short_res[:10]:
    print(f"    [{r['topic']}] '{r['name']}'")


# ─────────────────────────────────────────
# 5. 누락 패턴 요약
# ─────────────────────────────────────────
print("\n" + "=" * 60)
print("4. 누락 패턴 요약 및 프롬프트 개선 방향")
print("=" * 60)

gaps = {
    "Resolution 통합/요약": {
        "설명": "복수 조치방안을 하나의 Resolution으로 합쳐서 출력. 수동은 세분화.",
        "예시": "R001+R002 → '세팅 권장' 단일 Resolution",
        "빈도": "높음",
        "개선안": "프롬프트에 '각 조치방안은 별도 Resolution으로 분리' 명시",
    },
    "보조 장비 누락": {
        "설명": "주 이슈 장비가 아닌 관련 장비(혼입검사기 등) 누락",
        "예시": "Equipment:혼입검사기",
        "빈도": "중간",
        "개선안": "Equipment 정의에 '문서에서 언급된 모든 장비 유형 포함' 명시",
    },
    "운영 정책 조치 누락": {
        "설명": "세팅 조치보다 '제품군 제한' 같은 운영 정책성 조치방안 누락",
        "예시": "Resolution:측정 가능 제품군 제한",
        "빈도": "중간",
        "개선안": "Resolution category 예시에 '운영 정책' 추가",
    },
    "Component 모델번호 누락": {
        "설명": "acA2500-14gm 같은 정확한 모델번호보다 일반명칭으로 추출",
        "빈도": "낮음 (파일럿에서는 포착, 일부 페이지 누락)",
        "개선안": "Component 정의에 '모델번호 패턴(영문+숫자 혼합) 우선 포착' 명시",
    },
}

for gap_name, gap_info in gaps.items():
    print(f"\n■ {gap_name} ({gap_info.get('빈도', '')})")
    print(f"  원인: {gap_info['설명']}")
    if '예시' in gap_info:
        print(f"  예시: {gap_info['예시']}")
    print(f"  개선안: {gap_info['개선안']}")

# 결과 저장
analysis = {
    "pilot_recall_10": round(len(matched_10) / 10 * 100, 1),
    "pilot_recall_27": round(len(matched_all) / len(MANUAL_ALL) * 100, 1),
    "missed_10": [f"{t}:{n}" for t, n in missed_10],
    "missed_27": [f"{t}:{n}" for t, n in missed_all],
    "type_distribution": dict(type_counts),
    "resolution_total": len(resolutions_all),
    "resolution_short": len(short_res),
    "resolution_specific": len(specific_res),
    "gap_patterns": list(gaps.keys()),
}
(OUT_DIR / "gap_analysis.json").write_text(
    json.dumps(analysis, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"\n분석 결과 저장: {OUT_DIR / 'gap_analysis.json'}")
