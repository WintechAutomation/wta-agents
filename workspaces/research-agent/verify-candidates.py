"""
후보 페이지 연관성 검증 스크립트
- Confluence API로 각 페이지 첫 문단 + 이미지 캡션 조회
- 주제 키워드 기반 판정 (직접/간접/무관)
"""
import requests, json, re, sys, time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TOKEN = open('C:/MES/wta-agents/config/atlassian-api-token.txt').read().strip()
AUTH = ('hjcho@wta.kr', TOKEN)
BASE = 'https://iwta.atlassian.net'

CANDIDATES_FILE = Path('C:/MES/wta-agents/workspaces/research-agent/research-candidate-pages.json')
OUTPUT_FILE = Path('C:/MES/wta-agents/workspaces/research-agent/candidate-verification.json')

# 주제별 핵심 키워드 (직접/간접 판정용)
TOPIC_KEYWORDS = {
    '장비물류': {
        'direct': ['ATC', 'AMR', '물류', 'AGV', 'Side ATC', '툴교환', '자동 툴', '오토 툴', '트랜스퍼', '팔레트', '물류 이동'],
        'indirect': ['핸들러', '자동화', '이송', '그리퍼'],
    },
    '분말검사': {
        'direct': ['성형체', '소성체', '분말', 'burr', 'CELL LINE', 'Press-IM', '버 검사', '버검사'],
        'indirect': ['광학계', '조명', '시인성', '검사'],
    },
    '연삭측정제어': {
        'direct': ['연삭 핸들러', '높이 측정', '비전 측정', '연삭기 핸들러', '핸들러 측정'],
        'indirect': ['연삭', '핸들러', '측정'],
    },
    '포장혼입검사': {
        'direct': ['혼입 검사', '포장기', '혼입검사', '포장 혼입', 'IM 포장', '혼입 분류', '혼입검출'],
        'indirect': ['혼입', '포장', '검출', '티칭'],
    },
    '호닝신뢰성': {
        'direct': ['호닝 형상 검사기', '호닝형상검사기', '호닝 강성', '강성 개선', '재현성', '신뢰성'],
        'indirect': ['호닝', '형상 검사', '검사기'],
    },
}


def get_with_retry(url, max_retries=2):
    for i in range(max_retries):
        try:
            r = requests.get(url, auth=AUTH, timeout=15)
            return r
        except Exception as e:
            if i < max_retries - 1:
                time.sleep(3)
            else:
                raise


def adf_extract_text(node, max_chars=400):
    """ADF에서 텍스트만 추출 (재귀)"""
    if not isinstance(node, dict):
        return ''
    ntype = node.get('type', '')
    content = node.get('content', [])

    if ntype == 'text':
        return node.get('text', '')
    elif ntype in ('doc', 'paragraph', 'heading', 'bulletList', 'orderedList',
                   'listItem', 'blockquote', 'panel', 'expand', 'tableCell', 'tableHeader'):
        return ' '.join(adf_extract_text(c) for c in content)
    else:
        return ' '.join(adf_extract_text(c) for c in content)


def adf_extract_image_captions(node):
    """ADF에서 이미지 alt/caption 텍스트 추출"""
    captions = []
    if not isinstance(node, dict):
        return captions
    ntype = node.get('type', '')
    content = node.get('content', [])

    if ntype == 'media':
        alt = node.get('attrs', {}).get('alt', '')
        if alt:
            captions.append(alt)
    elif ntype == 'caption':
        text = adf_extract_text(node)
        if text.strip():
            captions.append(text.strip())

    for c in content:
        captions.extend(adf_extract_image_captions(c))
    return captions


def judge_relevance(topic, title, text, captions):
    """키워드 기반 연관성 판정"""
    combined = (title + ' ' + text + ' ' + ' '.join(captions)).lower()
    kw = TOPIC_KEYWORDS.get(topic, {})

    direct_hits = [k for k in kw.get('direct', []) if k.lower() in combined]
    indirect_hits = [k for k in kw.get('indirect', []) if k.lower() in combined]

    if len(direct_hits) >= 2:
        label = '✅'
        reason = f'직접 키워드 {len(direct_hits)}개 매칭: {", ".join(direct_hits[:3])}'
    elif len(direct_hits) == 1:
        label = '✅' if len(indirect_hits) >= 1 else '⚠️'
        reason = f'직접 키워드: {direct_hits[0]}' + (f', 간접: {indirect_hits[0]}' if indirect_hits else '')
    elif len(indirect_hits) >= 2:
        label = '⚠️'
        reason = f'간접 키워드 {len(indirect_hits)}개: {", ".join(indirect_hits[:3])}'
    else:
        label = '❌'
        reason = '주제 관련 키워드 미발견'

    return label, reason


def verify_page(pid, ptitle, topic, breadcrumb=''):
    """단일 페이지 검증"""
    url = f'{BASE}/wiki/rest/api/content/{pid}?expand=body.atlas_doc_format'
    try:
        r = get_with_retry(url)
    except Exception as e:
        return {
            'id': pid, 'title': ptitle, 'topic': topic,
            'breadcrumb': breadcrumb,
            'summary': f'API 오류: {e}',
            'label': '❌', 'reason': 'API 접근 실패'
        }

    if r.status_code != 200:
        return {
            'id': pid, 'title': ptitle, 'topic': topic,
            'breadcrumb': breadcrumb,
            'summary': f'HTTP {r.status_code}',
            'label': '❌', 'reason': f'HTTP {r.status_code}'
        }

    data = r.json()
    adf_val = data.get('body', {}).get('atlas_doc_format', {}).get('value', '{}')
    try:
        adf = json.loads(adf_val)
    except Exception:
        adf = {}

    full_text = adf_extract_text(adf)
    captions = adf_extract_image_captions(adf)
    summary = re.sub(r'\s+', ' ', full_text).strip()[:300]

    label, reason = judge_relevance(topic, ptitle, full_text, captions)

    return {
        'id': pid,
        'title': ptitle,
        'topic': topic,
        'breadcrumb': breadcrumb,
        'summary': summary,
        'image_captions': captions[:5],
        'label': label,
        'reason': reason,
    }


# 1. 후보 페이지 목록 로드
with open(CANDIDATES_FILE, encoding='utf-8') as f:
    candidates = json.load(f)

# 2. 혼입 분류 자식 페이지 목록 조회 (8725987333)
print('[혼입 분류 자식 페이지 조회]')
children_r = get_with_retry(f'{BASE}/wiki/rest/api/content/8725987333/child/page?limit=50&expand=ancestors')
child_pages = []
if children_r.status_code == 200:
    for c in children_r.json().get('results', []):
        ancs = c.get('ancestors', [])
        bc = ' > '.join(a['title'] for a in ancs[-2:]) if ancs else ''
        child_pages.append({'id': c['id'], 'title': c['title'], 'breadcrumb': bc})
    print(f'  자식 {len(child_pages)}개')
    for cp in child_pages:
        print(f'  {cp["id"]} | {cp["title"]}')

# 3. 전체 검증 대상 구성
# 우선순위: 호닝(10) → 포장혼입검사(3+12=15) → 장비물류(14) → 분말(2) → 연삭(4)
order = ['호닝신뢰성', '포장혼입검사', '장비물류', '분말검사', '연삭측정제어']
all_tasks = []

for topic in order:
    pages = candidates.get(topic, [])
    for p in pages:
        all_tasks.append((p['id'], p['title'], topic, p.get('breadcrumb', '')))
    # 포장혼입검사에 자식 페이지 추가
    if topic == '포장혼입검사':
        for cp in child_pages:
            all_tasks.append((cp['id'], cp['title'], '포장혼입검사', cp.get('breadcrumb', '혼입 분류 자식')))

print(f'\n총 {len(all_tasks)}개 페이지 검증 시작')

# 4. 검증 실행
results = []
for i, (pid, ptitle, topic, bc) in enumerate(all_tasks):
    print(f'[{i+1}/{len(all_tasks)}] [{topic}] {pid} | {ptitle[:45]}')
    result = verify_page(pid, ptitle, topic, bc)
    results.append(result)
    print(f'  {result["label"]} {result["reason"]}')
    time.sleep(0.2)

# 5. 저장
OUTPUT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'\n저장: {OUTPUT_FILE}')

# 6. 요약
from collections import Counter
by_topic = {}
for r in results:
    t = r['topic']
    if t not in by_topic:
        by_topic[t] = {'✅': [], '⚠️': [], '❌': []}
    by_topic[t][r['label']].append(r['title'])

print('\n=== 판정 요약 ===')
for topic in order:
    d = by_topic.get(topic, {})
    total = sum(len(v) for v in d.values())
    print(f'\n[{topic}] 총 {total}건')
    for label in ['✅', '⚠️', '❌']:
        items = d.get(label, [])
        if items:
            print(f'  {label} {len(items)}건')
            for t in items:
                print(f'    - {t[:55]}')
