"""
Confluence/Jira RAG 파이프라인 2단계 파생 데이터 생성

입력 (1단계 산출물):
  reports/MAX/confluence-{주제}/{pageId}-{title}/
    - index.html
    - images/
    - images-meta.json (page_id/title/space/breadcrumb/version/confluence_url/downloaded[])

출력 (동일 폴더, 원본 보존):
  - content.md            : 본문 MD (이미지 로컬 상대경로 ![alt](images/..))
  - meta.json             : page_id/title/space/breadcrumb/version/url/topic/word_count/image_count/tags
  - image-meta.json       : 이미지별 filename/att_id/file_id/alt/caption/parent_section/surrounding_text/order

원칙: 원본 덮어쓰기 금지. 한국어 원문 유지.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path('C:/MES/wta-agents/reports/MAX')
TOPICS = ['장비물류', '분말검사', '연삭측정제어', '포장혼입검사', '호닝신뢰성']

# 불용어 (tag 추출용)
STOPWORDS = {
    '있음', '없음', '위치', '경우', '이후', '이전', '동일', '적용', '진행', '확인',
    '대해', '대한', '관련', '필요', '사용', '처리', '작업', '내용', '정리', '참고',
    '있다', '없다', '된다', '이다', '하다', '되다', '합니다', '있습니다', '합니다.',
    '가능', '불가능', '존재', '기준', '방법', '방식', '상태', '시점', '부분', '전체',
    '그리고', '또는', '하지만', '때문', '통해', '위해', '따라', '통한', '이러한',
    '이때', '해당', '각각', '모두', '전부', '일부', '아래', '위의', '다음', '그림',
    '와이티에이', 'wta', 'WTA', 'the', 'for', 'and', 'with', 'from', 'that',
}


def strip_tags(s: str) -> str:
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'&nbsp;', ' ', s)
    s = re.sub(r'&lt;', '<', s)
    s = re.sub(r'&gt;', '>', s)
    s = re.sub(r'&amp;', '&', s)
    s = re.sub(r'&quot;', '"', s)
    s = re.sub(r'&#39;', "'", s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def extract_body(html: str) -> str:
    """<body>...</body> 내부만 추출, head/style/script/source-link 제거."""
    html = re.sub(r'<head[^>]*>.*?</head>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # source-link, breadcrumb, meta div 제거
    html = re.sub(r'<p\s+class="source-link"[^>]*>.*?</p>', '', html, flags=re.DOTALL)
    html = re.sub(r'<div\s+class="breadcrumb"[^>]*>.*?</div>', '', html, flags=re.DOTALL)
    html = re.sub(r'<div\s+class="meta"[^>]*>.*?</div>', '', html, flags=re.DOTALL)
    m = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)
    return html


def html_to_md(html: str) -> str:
    """HTML body → Markdown (간이 변환)."""
    s = html

    # figure/figcaption: 이미지+캡션 병합
    def _figure(m):
        block = m.group(1)
        img = re.search(r'<img\s+([^>]*?)/?>', block, re.IGNORECASE)
        if not img:
            return ''
        attrs = img.group(1)
        src_m = re.search(r'src\s*=\s*"([^"]+)"', attrs)
        alt_m = re.search(r'alt\s*=\s*"([^"]*)"', attrs)
        src = src_m.group(1) if src_m else ''
        alt = alt_m.group(1) if alt_m else ''
        cap_m = re.search(r'<figcaption[^>]*>(.*?)</figcaption>', block, re.DOTALL)
        cap = strip_tags(cap_m.group(1)) if cap_m else ''
        label = alt or cap or Path(src).name
        out = f'\n\n![{label}]({src})\n'
        if cap and cap != alt:
            out += f'*{cap}*\n'
        return out
    s = re.sub(r'<figure[^>]*>(.*?)</figure>', _figure, s, flags=re.DOTALL)

    # 단독 img
    def _img(m):
        attrs = m.group(1)
        src_m = re.search(r'src\s*=\s*"([^"]+)"', attrs)
        alt_m = re.search(r'alt\s*=\s*"([^"]*)"', attrs)
        src = src_m.group(1) if src_m else ''
        alt = alt_m.group(1) if alt_m else Path(src).name
        return f'\n\n![{alt}]({src})\n'
    s = re.sub(r'<img\s+([^>]*?)/?>', _img, s, flags=re.IGNORECASE)

    # 표 변환
    def _table(m):
        tbl = m.group(1)
        rows_html = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, re.DOTALL)
        rows = []
        for rh in rows_html:
            cells = re.findall(r'<(?:td|th)[^>]*>(.*?)</(?:td|th)>', rh, re.DOTALL)
            cleaned = [strip_tags(c).replace('|', '\\|') for c in cells]
            if cleaned:
                rows.append(cleaned)
        if not rows:
            return ''
        cols = max(len(r) for r in rows)
        out = ['']
        header = rows[0] + [''] * (cols - len(rows[0]))
        out.append('| ' + ' | '.join(header) + ' |')
        out.append('| ' + ' | '.join(['---'] * cols) + ' |')
        for row in rows[1:]:
            padded = row + [''] * (cols - len(row))
            out.append('| ' + ' | '.join(padded) + ' |')
        out.append('')
        return '\n'.join(out)
    s = re.sub(r'<table[^>]*>(.*?)</table>', _table, s, flags=re.DOTALL)

    # 헤딩
    s = re.sub(r'<h1[^>]*>(.*?)</h1>', lambda m: '\n# ' + strip_tags(m.group(1)) + '\n', s, flags=re.DOTALL)
    s = re.sub(r'<h2[^>]*>(.*?)</h2>', lambda m: '\n## ' + strip_tags(m.group(1)) + '\n', s, flags=re.DOTALL)
    s = re.sub(r'<h3[^>]*>(.*?)</h3>', lambda m: '\n### ' + strip_tags(m.group(1)) + '\n', s, flags=re.DOTALL)
    s = re.sub(r'<h4[^>]*>(.*?)</h4>', lambda m: '\n#### ' + strip_tags(m.group(1)) + '\n', s, flags=re.DOTALL)
    s = re.sub(r'<h5[^>]*>(.*?)</h5>', lambda m: '\n##### ' + strip_tags(m.group(1)) + '\n', s, flags=re.DOTALL)

    # 리스트
    s = re.sub(r'<li[^>]*>(.*?)</li>', lambda m: '\n- ' + strip_tags(m.group(1)), s, flags=re.DOTALL)
    s = re.sub(r'</?(ul|ol)[^>]*>', '\n', s, flags=re.IGNORECASE)

    # 문단/BR
    s = re.sub(r'<p[^>]*>(.*?)</p>', lambda m: '\n' + strip_tags(m.group(1)) + '\n', s, flags=re.DOTALL)
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.IGNORECASE)

    # 나머지 인라인 태그 제거 (strong/em/code 등) 후 엔티티 변환
    s = strip_tags(s)

    # Strip_tags collapses newlines — 다시 markdown 구조를 살려야 하는데 이미 손상.
    # → 태그 제거 전에 줄바꿈을 치환해두지 않았으므로, MD 특수문자만 보존하기 위해
    #   다시 접근: 위 처리들이 모두 개행을 포함한 결과를 생성했으므로,
    #   마지막 strip_tags가 모두 한 줄로 만드는 것이 문제. strip_tags를 우회 수정 필요.
    return s


def html_to_md_v2(html: str) -> str:
    """HTML body → Markdown. 줄바꿈 보존형."""
    s = html

    # 블록 경계에 marker 삽입
    block_tags = ['figure', 'table', 'h1', 'h2', 'h3', 'h4', 'h5', 'p', 'br', 'li',
                  'ul', 'ol', 'tr', 'div', 'hr']
    # figure 변환 (이미지+캡션)
    def _figure(m):
        block = m.group(1)
        img = re.search(r'<img\s+([^>]*?)/?>', block, re.IGNORECASE)
        if not img:
            return '\n\n'
        attrs = img.group(1)
        src_m = re.search(r'src\s*=\s*"([^"]+)"', attrs)
        alt_m = re.search(r'alt\s*=\s*"([^"]*)"', attrs)
        src = src_m.group(1) if src_m else ''
        alt = alt_m.group(1) if alt_m else ''
        cap_m = re.search(r'<figcaption[^>]*>(.*?)</figcaption>', block, re.DOTALL)
        cap = strip_tags(cap_m.group(1)) if cap_m else ''
        label = alt or cap or Path(src).name
        out = f'\n\n![{label}]({src})\n'
        if cap and cap != alt and cap:
            out += f'*{cap}*\n'
        return out
    s = re.sub(r'<figure[^>]*>(.*?)</figure>', _figure, s, flags=re.DOTALL)

    def _img(m):
        attrs = m.group(1)
        src_m = re.search(r'src\s*=\s*"([^"]+)"', attrs)
        alt_m = re.search(r'alt\s*=\s*"([^"]*)"', attrs)
        src = src_m.group(1) if src_m else ''
        alt = alt_m.group(1) if alt_m else Path(src).name
        return f'\n\n![{alt}]({src})\n'
    s = re.sub(r'<img\s+([^>]*?)/?>', _img, s, flags=re.IGNORECASE)

    # 표 변환
    def _table(m):
        tbl = m.group(1)
        rows_html = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, re.DOTALL)
        rows = []
        for rh in rows_html:
            cells = re.findall(r'<(?:td|th)[^>]*>(.*?)</(?:td|th)>', rh, re.DOTALL)
            cleaned = []
            for c in cells:
                # 셀 내부 <br> → 공백
                c2 = re.sub(r'<br\s*/?>', ' ', c, flags=re.IGNORECASE)
                cleaned.append(strip_tags(c2).replace('|', '\\|'))
            if cleaned:
                rows.append(cleaned)
        if not rows:
            return '\n\n'
        cols = max(len(r) for r in rows)
        lines = ['', '']
        header = rows[0] + [''] * (cols - len(rows[0]))
        lines.append('| ' + ' | '.join(header) + ' |')
        lines.append('| ' + ' | '.join(['---'] * cols) + ' |')
        for row in rows[1:]:
            padded = row + [''] * (cols - len(row))
            lines.append('| ' + ' | '.join(padded) + ' |')
        lines.append('')
        return '\n'.join(lines)
    s = re.sub(r'<table[^>]*>(.*?)</table>', _table, s, flags=re.DOTALL)

    # 헤딩
    s = re.sub(r'<h1[^>]*>(.*?)</h1>', lambda m: '\n\n# ' + strip_tags(m.group(1)) + '\n', s, flags=re.DOTALL)
    s = re.sub(r'<h2[^>]*>(.*?)</h2>', lambda m: '\n\n## ' + strip_tags(m.group(1)) + '\n', s, flags=re.DOTALL)
    s = re.sub(r'<h3[^>]*>(.*?)</h3>', lambda m: '\n\n### ' + strip_tags(m.group(1)) + '\n', s, flags=re.DOTALL)
    s = re.sub(r'<h4[^>]*>(.*?)</h4>', lambda m: '\n\n#### ' + strip_tags(m.group(1)) + '\n', s, flags=re.DOTALL)
    s = re.sub(r'<h5[^>]*>(.*?)</h5>', lambda m: '\n\n##### ' + strip_tags(m.group(1)) + '\n', s, flags=re.DOTALL)

    # 리스트 아이템
    def _li(m):
        inner = m.group(1)
        inner = re.sub(r'<p[^>]*>(.*?)</p>', lambda m2: strip_tags(m2.group(1)) + ' ', inner, flags=re.DOTALL)
        inner = re.sub(r'<br\s*/?>', ' ', inner, flags=re.IGNORECASE)
        return '\n- ' + strip_tags(inner)
    s = re.sub(r'<li[^>]*>(.*?)</li>', _li, s, flags=re.DOTALL)
    s = re.sub(r'</?(ul|ol)[^>]*>', '\n', s, flags=re.IGNORECASE)

    # 문단
    s = re.sub(r'<p[^>]*>(.*?)</p>', lambda m: '\n\n' + strip_tags(m.group(1)) + '\n', s, flags=re.DOTALL)
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.IGNORECASE)

    # 남은 태그 제거 (strong/em/code/div/span 등) — 줄바꿈은 남김
    s = re.sub(r'<[^>]+>', '', s)

    # HTML 엔티티
    s = s.replace('&nbsp;', ' ')
    s = s.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    s = s.replace('&quot;', '"').replace('&#39;', "'")

    # 빈 bullet 제거, 과다 개행 정리
    s = re.sub(r'^\s*-\s*$', '', s, flags=re.MULTILINE)
    s = re.sub(r'[ \t]+\n', '\n', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip() + '\n'


def extract_image_contexts(html_body: str, page_title: str):
    """HTML body에서 이미지 태그 탐색 + 앞뒤 200자 문맥 + parent_section.

    전략: 이미지를 플레이스홀더 토큰으로 치환 → 전체 HTML 태그 제거 →
    토큰 위치에서 앞뒤 문자열 슬라이싱. 이렇게 하면 윈도우 경계 부분 태그 노이즈 없음.
    """
    # 헤딩을 특수 마커로 치환 (parent_section 추적용)
    heading_marker = '§§§H{lv}§§§{text}§§§/H§§§'

    def replace_heading(m):
        lv = m.group(1)
        text = strip_tags(m.group(2))
        return ' ' + heading_marker.format(lv=lv, text=text) + ' '

    s = re.sub(r'<h([1-5])[^>]*>(.*?)</h\1>', replace_heading, html_body, flags=re.DOTALL)

    # 이미지 및 figure 블록을 토큰으로 치환
    tokens = []  # {'filename','src','alt','caption'}

    def replace_figure(m):
        fblock = m.group(1)
        img_m = re.search(r'<img\s+([^>]*?)/?>', fblock, re.IGNORECASE)
        if not img_m:
            return ' '
        attrs = img_m.group(1)
        src_m = re.search(r'src\s*=\s*"([^"]+)"', attrs)
        alt_m = re.search(r'alt\s*=\s*"([^"]*)"', attrs)
        src = src_m.group(1) if src_m else ''
        alt = alt_m.group(1) if alt_m else ''
        filename = Path(src).name if src else ''
        cap_m = re.search(r'<figcaption[^>]*>(.*?)</figcaption>', fblock, re.DOTALL)
        caption = strip_tags(cap_m.group(1)) if cap_m else ''
        idx = len(tokens)
        tokens.append({'filename': filename, 'src': src, 'alt': alt, 'caption': caption})
        return f' §§§IMG_{idx}§§§ '

    s = re.sub(r'<figure[^>]*>(.*?)</figure>', replace_figure, s, flags=re.DOTALL)

    def replace_img(m):
        attrs = m.group(1)
        src_m = re.search(r'src\s*=\s*"([^"]+)"', attrs)
        alt_m = re.search(r'alt\s*=\s*"([^"]*)"', attrs)
        src = src_m.group(1) if src_m else ''
        alt = alt_m.group(1) if alt_m else ''
        filename = Path(src).name if src else ''
        idx = len(tokens)
        tokens.append({'filename': filename, 'src': src, 'alt': alt, 'caption': ''})
        return f' §§§IMG_{idx}§§§ '

    s = re.sub(r'<img\s+([^>]*?)/?>', replace_img, s, flags=re.IGNORECASE)

    # 남은 HTML 태그 제거 및 엔티티 변환
    s = re.sub(r'<[^>]+>', ' ', s)
    s = s.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>')
    s = s.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', "'")
    s = re.sub(r'\s+', ' ', s)

    # 결과 구성
    results = []
    # 헤딩 마커 추적 (parent_section)
    def parent_section_at(pos: int, text: str) -> str:
        # pos 앞쪽에서 마지막 §§§H..§§§ 찾기
        prefix = text[:pos]
        matches = list(re.finditer(r'§§§H\d§§§(.*?)§§§/H§§§', prefix))
        if matches:
            return matches[-1].group(1).strip()
        return page_title

    token_re = re.compile(r'§§§IMG_(\d+)§§§')
    for tm in token_re.finditer(s):
        idx = int(tm.group(1))
        tok = tokens[idx]
        pos = tm.start()
        end = tm.end()
        # parent section
        parent = parent_section_at(pos, s)
        # 앞뒤 200자, 단 다른 IMG 토큰/H 마커는 placeholder로 치환
        before = s[max(0, pos - 300):pos]
        after = s[end:end + 300]
        # 마커 치환
        before = re.sub(r'§§§H\d§§§', ' [SECTION] ', before)
        before = before.replace('§§§/H§§§', '')
        before = re.sub(r'§§§IMG_(\d+)§§§',
                         lambda m: f' [이미지:{tokens[int(m.group(1))].get("filename","")}] ', before)
        after = re.sub(r'§§§H\d§§§', ' [SECTION] ', after)
        after = after.replace('§§§/H§§§', '')
        after = re.sub(r'§§§IMG_(\d+)§§§',
                        lambda m: f' [이미지:{tokens[int(m.group(1))].get("filename","")}] ', after)
        before = re.sub(r'\s+', ' ', before).strip()[-200:]
        after = re.sub(r'\s+', ' ', after).strip()[:200]

        results.append({
            'filename': tok['filename'],
            'src': tok['src'],
            'alt': tok['alt'],
            'caption': tok['caption'] if tok['caption'] != tok['filename'] else '',
            'parent_section': parent,
            'surrounding_text': (before + ' [IMG] ' + after).strip(),
            '_pos': pos,
        })

    # 페이지 내 등장 순서
    for i, r in enumerate(results, 1):
        r['order'] = i
        del r['_pos']
    return results


def extract_tags(text: str, title: str, n: int = 10):
    """본문에서 한국어 명사성 키워드 추출 (간이)."""
    # 한글 2자 이상 연속 + 영숫자 키워드
    words = re.findall(r'[가-힣]{2,}|[A-Za-z][A-Za-z0-9]{2,}', text)
    words = [w for w in words if w.lower() not in STOPWORDS and len(w) >= 2]
    # 제목의 주요 단어는 가중치
    title_words = set(re.findall(r'[가-힣]{2,}|[A-Za-z][A-Za-z0-9]{2,}', title))
    cnt = Counter(words)
    for w in title_words:
        if w in cnt:
            cnt[w] += 3
    # 빈도순
    return [w for w, _ in cnt.most_common(n)]


def derive_page(page_dir: Path, topic: str) -> dict:
    html_path = page_dir / 'index.html'
    images_meta_path = page_dir / 'images-meta.json'
    if not html_path.exists():
        return {'error': 'index.html missing'}

    html = html_path.read_text(encoding='utf-8', errors='replace')
    body = extract_body(html)

    # MD 변환
    md = html_to_md_v2(body)

    # 1단계 images-meta.json 로드
    stage1_meta = {}
    stage1_downloaded = []
    if images_meta_path.exists():
        stage1_meta = json.loads(images_meta_path.read_text(encoding='utf-8'))
        stage1_downloaded = stage1_meta.get('downloaded', [])
    downloaded_by_filename = {d.get('filename'): d for d in stage1_downloaded}

    # 이미지 문맥 추출
    page_title = stage1_meta.get('page_title', '') or page_dir.name.split('-', 1)[-1]
    image_contexts = extract_image_contexts(body, page_title)

    # 이미지 meta 병합
    image_metas = []
    seen_filenames = set()
    for ctx in image_contexts:
        fn = ctx['filename']
        dl = downloaded_by_filename.get(fn, {})
        image_metas.append({
            'filename': fn,
            'att_id': dl.get('att_id', ''),
            'file_id': dl.get('file_id', ''),
            'alt': ctx['alt'],
            'caption': ctx['caption'],
            'parent_section': ctx['parent_section'],
            'surrounding_text': ctx['surrounding_text'],
            'order': ctx['order'],
        })
        seen_filenames.add(fn)

    # HTML 본문에 없고 downloaded에만 있는 이미지는 첨부 전용으로 기록
    order_next = len(image_metas) + 1
    for d in stage1_downloaded:
        fn = d.get('filename', '')
        if fn and fn not in seen_filenames:
            image_metas.append({
                'filename': fn,
                'att_id': d.get('att_id', ''),
                'file_id': d.get('file_id', ''),
                'alt': '',
                'caption': '',
                'parent_section': page_title,
                'surrounding_text': '',
                'order': order_next,
                'attached_only': True,
            })
            order_next += 1

    # word_count (공백 기준)
    text_only = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', md)
    text_only = re.sub(r'[|\-#*`]', ' ', text_only)
    word_count = len(re.findall(r'\S+', text_only))

    # tags
    tags = extract_tags(text_only, page_title, n=8)

    # meta.json
    meta = {
        'page_id': stage1_meta.get('page_id', ''),
        'title': page_title,
        'space': stage1_meta.get('space', ''),
        'breadcrumb': stage1_meta.get('breadcrumb', ''),
        'version': stage1_meta.get('version', ''),
        'confluence_url': stage1_meta.get('confluence_url', ''),
        'topic': topic,
        'word_count': word_count,
        'image_count': len(image_metas),
        'tags': tags,
    }

    # 저장 (content.md는 부서장 지시로 생성 제외)
    (page_dir / 'meta.json').write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    (page_dir / 'image-meta.json').write_text(
        json.dumps(image_metas, ensure_ascii=False, indent=2), encoding='utf-8')

    return {
        'page_id': meta['page_id'],
        'title': page_title,
        'md_chars': len(md),
        'word_count': word_count,
        'image_count': len(image_metas),
        'image_in_body': sum(1 for m in image_metas if not m.get('attached_only')),
        'image_attached_only': sum(1 for m in image_metas if m.get('attached_only')),
    }


def main():
    summary = {}
    total = 0
    failures = []

    for topic in TOPICS:
        topic_dir = BASE / f'confluence-{topic}'
        if not topic_dir.exists():
            print(f'⚠️ {topic_dir} 없음 — 스킵')
            continue
        page_dirs = sorted([p for p in topic_dir.iterdir() if p.is_dir()])
        print(f'\n=== [{topic}] {len(page_dirs)}건 ===')
        results = []
        for pd in page_dirs:
            try:
                r = derive_page(pd, topic)
                if 'error' in r:
                    failures.append((str(pd), r['error']))
                    print(f'  ❌ {pd.name}: {r["error"]}')
                    continue
                results.append(r)
                print(f'  ✓ {pd.name[:60]:60s} | md={r["md_chars"]:>6}자 | img={r["image_count"]:>3} (본문 {r["image_in_body"]} / 첨부 {r["image_attached_only"]})')
            except Exception as e:
                failures.append((str(pd), str(e)))
                print(f'  ❌ {pd.name}: {e}')
        summary[topic] = {'total': len(page_dirs), 'success': len(results)}
        total += len(page_dirs)

    print('\n=== 요약 ===')
    for t, s in summary.items():
        print(f'  {t}: {s["success"]}/{s["total"]}')
    print(f'  전체: {sum(s["success"] for s in summary.values())}/{total}')
    if failures:
        print(f'\n실패 {len(failures)}건:')
        for p, e in failures:
            print(f'  - {p}: {e}')


if __name__ == '__main__':
    main()
