"""
연구노트 v3 재작성 — image-meta.json 기반 (v3.1 개선)

개선 사항 (MAX 지적):
1. 캡션 = [IMG] 직후 텍스트 (prefix 누적 금지)
2. image-*.png 파일명 노이즈 제거
3. 핵심 내용 = index.html 본문 요약 + 구조 요약
4. 중복 캡션 #1/#2 suffix
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path('C:/MES/wta-agents/reports/MAX')
TOPICS = [
    ('장비물류', 1),
    ('분말검사', 2),
    ('연삭측정제어', 3),
    ('포장혼입검사', 4),
    ('호닝신뢰성', 5),
]


def strip_filename_noise(text: str) -> str:
    """image-xxxx.png / attachment ID 등 파일명 노이즈 제거."""
    text = re.sub(r'image-\d{8}-\d{6}\.(png|jpe?g|gif|bmp|svg|webp)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', '', text)
    text = re.sub(r'\.(png|jpe?g|gif|bmp|svg|webp)\b', '', text, flags=re.IGNORECASE)
    return text


def clean_text(text: str) -> str:
    """마커 + 파일명 노이즈 제거, 공백 정규화."""
    text = re.sub(r'\[SECTION\]', ' ', text)
    text = re.sub(r'\[이미지:[^\]]*\]', ' ', text)
    text = re.sub(r'\[IMG\]', ' ', text)
    text = strip_filename_noise(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_caption(img: dict, used: set) -> str:
    """[IMG] 직후 텍스트 추출 → 캡션 생성."""
    # 1. caption 우선
    caption = img.get('caption', '').strip()
    if caption:
        caption = clean_text(caption)
        if caption:
            return dedup_caption(caption[:80], used)
    # 2. [IMG] 직후 텍스트 (다음 마커까지)
    st = img.get('surrounding_text', '')
    m = re.search(r'\[IMG\](.*?)(?=\[이미지:|\[SECTION\]|\[IMG\]|$)', st, re.DOTALL)
    after = m.group(1) if m else ''
    after = clean_text(after)
    if after and len(after) >= 3:
        # 너무 길면 첫 80자
        cap = after[:80].strip()
        if cap:
            return dedup_caption(cap, used)
    # 3. [IMG] 직전 마지막 짧은 청크
    m = re.search(r'(?:\[이미지:[^\]]*\]|\[SECTION\]|^)([^\[]+)\[IMG\]', st)
    if m:
        before = clean_text(m.group(1))
        if before:
            cap = before[-80:].strip()
            if cap:
                return dedup_caption(cap, used)
    # 4. fallback: alt
    alt = clean_text(img.get('alt', ''))
    if alt:
        return dedup_caption(alt[:80], used)
    return dedup_caption(img.get('filename', '이미지'), used)


def dedup_caption(cap: str, used: set) -> str:
    """중복 캡션에 #N suffix."""
    if cap not in used:
        used.add(cap)
        return cap
    n = 2
    while f'{cap} #{n}' in used:
        n += 1
    new_cap = f'{cap} #{n}'
    used.add(new_cap)
    return new_cap


def extract_page_body(page_dir: Path, max_len: int = 320) -> str:
    """index.html에서 본문 텍스트 발췌."""
    idx = page_dir / 'index.html'
    if not idx.exists():
        return ''
    html = idx.read_text(encoding='utf-8', errors='replace')
    html = re.sub(r'<head.*?</head>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<(div|p|span)[^>]*class="breadcrumb"[^>]*>.*?</\1>', '', html, flags=re.DOTALL)
    html = re.sub(r'<(div|p|span)[^>]*class="meta"[^>]*>.*?</\1>', '', html, flags=re.DOTALL)
    html = re.sub(r'<(div|p|span)[^>]*class="source-link"[^>]*>.*?</\1>', '', html, flags=re.DOTALL)
    html = re.sub(r'<h1[^>]*>.*?</h1>', '', html, flags=re.DOTALL)
    # figure/img 제거 (캡션만 남기지 말고 통째로)
    html = re.sub(r'<figure.*?</figure>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<img[^>]*>', '', html, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', html)
    text = strip_filename_noise(text)
    text = re.sub(r'\s+', ' ', text).strip()
    # title 중복 제거
    if len(text) > max_len:
        text = text[:max_len - 1] + '…'
    return text


def summarize_page(page_dir: Path) -> dict:
    meta_path = page_dir / 'meta.json'
    img_meta_path = page_dir / 'image-meta.json'
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    images = json.loads(img_meta_path.read_text(encoding='utf-8')) if img_meta_path.exists() else []
    return {'meta': meta, 'images': images, 'page_dir': page_dir}


def build_core_summary(meta: dict, page_dir: Path) -> str:
    """핵심 내용 섹션: 구조 요약 + 본문 발췌."""
    breadcrumb = meta.get('breadcrumb', '')
    version = meta.get('version', '?')
    wc = meta.get('word_count', 0)
    ic = meta.get('image_count', 0)
    tags = meta.get('tags', [])

    parts = []
    parts.append(f'- **구조**: `{breadcrumb}` · v{version} · 본문 {wc}자 · 이미지 {ic}장')
    if tags:
        parts.append(f'- **키워드**: {", ".join(tags)}')

    body = extract_page_body(page_dir)
    if body:
        # title 중복 제거
        title = meta.get('title', '')
        if title and body.startswith(title):
            body = body[len(title):].lstrip(' -·:')
        parts.append(f'\n{body}')
    return '\n'.join(parts)


def build_topic_note(topic: str, index: int) -> Path:
    topic_dir = BASE / f'confluence-{topic}'
    if not topic_dir.exists():
        print(f'⚠️ {topic_dir} 없음')
        return None

    page_dirs = sorted([p for p in topic_dir.iterdir() if p.is_dir()])
    pages = [summarize_page(pd) for pd in page_dirs]
    pages = [p for p in pages if p]

    out_path = BASE / f'연구개발-{index}-{topic}.md'

    lines = []
    lines.append(f'# 경상연구개발 과제 #{index} — {topic}\n')
    lines.append(f'작성일: 2026-04-05 | 부서: 생산관리팀(AI운영팀) | 참조 페이지: {len(pages)}건\n')
    lines.append('---\n')

    # 개요
    lines.append('## 개요\n')
    lines.append(f'본 연구노트는 Confluence 내 **{topic}** 관련 {len(pages)}개 과제 페이지를 정리한 자료다.\n')
    lines.append('**참조 페이지 목록**:\n')
    for i, p in enumerate(pages, 1):
        m = p['meta']
        lines.append(f'{i}. `{m.get("page_id", "")}` {m.get("title", "")}')
    lines.append('')

    # 페이지별 본문
    for i, p in enumerate(pages, 1):
        m = p['meta']
        images = p['images']
        page_dir = p['page_dir']

        lines.append('---\n')
        lines.append(f'## {i}. {m.get("title", "")}\n')
        lines.append(f'- **페이지 ID**: {m.get("page_id", "")}')
        lines.append(f'- **원본 링크**: [{m.get("confluence_url", "")}]({m.get("confluence_url", "")})')
        lines.append('')

        # 핵심 내용 (구조 요약 + 본문 발췌)
        lines.append('### 핵심 내용\n')
        summary = build_core_summary(m, page_dir)
        lines.append(summary)
        lines.append('')

        # 본문 이미지 (order 순, parent_section 그룹)
        in_body_images = [img for img in images if not img.get('attached_only')]
        if in_body_images:
            lines.append('### 주요 이미지\n')
            used_captions = set()
            current_section = None
            sorted_imgs = sorted(in_body_images, key=lambda x: x.get('order', 0))
            for img in sorted_imgs:
                section = (img.get('parent_section') or '').strip()
                section = clean_text(section)
                if section and section != current_section and section != m.get('title', ''):
                    lines.append(f'**▸ {section}**\n')
                    current_section = section
                img_path = f'confluence-{topic}/{page_dir.name}/images/{img["filename"]}'
                caption = extract_caption(img, used_captions)
                img_path_enc = quote(img_path, safe='/')
                lines.append(f'![{caption}]({img_path_enc})')
                lines.append(f'*{caption}*\n')

        # 첨부 전용 이미지
        attached = [img for img in images if img.get('attached_only')]
        if attached:
            lines.append('### 관련 첨부자료\n')
            lines.append(f'본문 외 첨부된 이미지 {len(attached)}장 (참고 자료):\n')
            for img in attached[:30]:
                lines.append(f'- `{img["filename"]}`')
            if len(attached) > 30:
                lines.append(f'- ... 외 {len(attached) - 30}장')
            lines.append('')

    lines.append('---\n')
    lines.append(f'*본 연구노트는 Confluence 원문 {len(pages)}개 페이지 및 이미지 메타데이터(image-meta.json)를 기반으로 자동 생성됨.*')

    out_path.write_text('\n'.join(lines), encoding='utf-8')
    return out_path


def main():
    print('=== 연구노트 v3.1 재작성 ===\n')
    results = []
    for topic, idx in TOPICS:
        out = build_topic_note(topic, idx)
        if out:
            size = out.stat().st_size
            print(f'  ✓ 연구개발-{idx}-{topic}.md ({size:,} bytes)')
            results.append(out)
    print(f'\n완료: {len(results)}개')


if __name__ == '__main__':
    main()
