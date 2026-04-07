import json, sys, re
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')

with open('C:/MES/wta-agents/workspaces/cs-agent/pvd_cs_full.json', encoding='utf-8') as f:
    data = json.load(f)

CATEGORIES = [
    ("에러/알람",    r"에러|알람|오류|alarm|error|fault|경보"),
    ("스페이서",     r"스페이서|spacer"),
    ("진공/진공도",  r"진공|vacuum|펌프|pump|리크|leak"),
    ("로딩/언로딩",  r"로딩|언로딩|loading|unloading|인덱스|index"),
    ("파워/전원",    r"파워|전원|power|voltage|전압|UPS|퓨즈|fuse|전기"),
    ("코팅 품질",    r"코팅|coating|박리|색상|두께|density|품질"),
    ("센서/감지",    r"센서|sensor|감지|detect|광센서|proximity"),
    ("타겟/소모품",  r"타겟|target|cathode|캐소드|소모"),
    ("냉각/수냉",    r"냉각|수냉|cooling|water|온도|temperature|열"),
    ("기계/실린더",  r"실린더|cylinder|모터|motor|서보|servo|액추에이터|구동|불량"),
]

def classify(title, symptom=""):
    text = f"{title} {symptom or ''}"
    for name, pat in CATEGORIES:
        if re.search(pat, text, re.IGNORECASE):
            return name
    return "기타"

for r in data:
    r['category'] = classify(r.get('title',''), r.get('symptom_and_cause','') or '')

# Group by category
from collections import defaultdict
cat_map = defaultdict(list)
for r in data:
    cat_map[r['category']].append(r)

# Sort by count
cat_order = sorted(cat_map.keys(), key=lambda c: -len(cat_map[c]))[:10]

# Extract action keywords from action_result
ACTION_KW = {
    '교체': r'교체|replace|대체|신품',
    '조정/정렬': r'조정|정렬|align|adjust|세팅|setting|위치',
    '청소/세척': r'청소|세척|clean|이물질|먼지|제거',
    '재설치/재조립': r'재설치|재조립|재결합|재체결|재연결',
    '파라미터 수정': r'파라미터|parameter|설정값|값.*변경|수정.*설정',
    '재시동/초기화': r'재시동|재부팅|초기화|reset|restart|재가동',
    'A/S 요청': r'A/S|방문|출장|제조사|업체',
    '점검/확인': r'점검|확인|체크|check|검사',
}

CAUSE_KW = {
    '마모/소모': r'마모|소모|worn|마찰|손상|닳',
    '이물질': r'이물질|먼지|debris|오염|contamination',
    '조립 불량': r'조립|체결|틀어짐|이탈|빠짐',
    '설정 오류': r'설정.*오류|파라미터.*오류|셋팅.*불량|잘못된.*설정',
    '노후화': r'노후|열화|오래|수명|age',
    '외부 충격': r'충격|impact|파손|깨짐|변형',
    '전기적 결함': r'전기|ショート|단선|절연|voltage|과전류|과열',
}

results = []
for cat in cat_order:
    records = cat_map[cat]
    n = len(records)

    # Collect texts
    symptoms = [r.get('symptom_and_cause','') or '' for r in records]
    actions = [r.get('action_result','') or '' for r in records]
    titles = [r.get('title','') or '' for r in records]

    sym_text = ' '.join(symptoms)
    act_text = ' '.join(actions)

    # Count action keywords
    act_hits = {}
    for kw, pat in ACTION_KW.items():
        cnt = len(re.findall(pat, act_text, re.IGNORECASE))
        if cnt > 0:
            act_hits[kw] = cnt
    top_actions = sorted(act_hits.items(), key=lambda x: -x[1])[:4]

    # Count cause keywords
    cause_hits = {}
    for kw, pat in CAUSE_KW.items():
        cnt = len(re.findall(pat, sym_text, re.IGNORECASE))
        if cnt > 0:
            cause_hits[kw] = cnt
    top_causes = sorted(cause_hits.items(), key=lambda x: -x[1])[:3]

    # Common title words
    title_words = []
    for t in titles:
        words = re.findall(r'[가-힣]{2,}', t)
        title_words.extend(words)
    common_words = [w for w, c in Counter(title_words).most_common(6)
                    if w not in ('발생','확인','불량','현상','증상','장비','문제')]

    results.append({
        'category': cat,
        'count': n,
        'top_actions': top_actions,
        'top_causes': top_causes,
        'common_words': common_words[:4],
        'sample_titles': [r.get('title','') for r in records[:5]],
    })

    print(f"\n[{cat}] {n}건")
    print(f"  주요원인: {top_causes}")
    print(f"  조치유형: {top_actions}")
    print(f"  빈출단어: {common_words}")

out = 'C:/MES/wta-agents/workspaces/cs-agent/pvd_analysis_result.json'
with open(out, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nSaved: {out}")
