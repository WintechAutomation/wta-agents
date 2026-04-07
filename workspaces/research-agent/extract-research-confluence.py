"""
경상연구개발 5개 주제 Confluence 추출 스크립트
- ADF -> Markdown 변환 (이미지 인라인 참조 포함)
- 이미지 메타 JSON (alt, caption, parent_section, context)
- 저장: reports/MAX/confluence-경상연구개발/{주제명}/
"""
import requests, os, json, time, re, sys, html as html_module
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TOKEN = open('C:/MES/wta-agents/config/atlassian-api-token.txt').read().strip()
AUTH = ('hjcho@wta.kr', TOKEN)
BASE = 'https://iwta.atlassian.net'
OUTPUT_BASE = Path('C:/MES/wta-agents/reports/MAX/confluence-경상연구개발')
OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

PAGES_FILE = Path('C:/MES/wta-agents/workspaces/research-agent/cql-research-pages.json')
PROGRESS_FILE = Path('C:/MES/wta-agents/workspaces/research-agent/research-extract-progress.json')

TIMEOUT = 30
MAX_RETRIES = 3

# 진행 상황 로드
if PROGRESS_FILE.exists():
    with open(PROGRESS_FILE, encoding='utf-8') as f:
        progress = json.load(f)
else:
    progress = {'done': [], 'failed': []}

done_set = set(progress['done'])

def save_progress():
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

def get_with_retry(url, stream=False):
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, auth=AUTH, allow_redirects=True, timeout=TIMEOUT, stream=stream)
            return r
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise

def safe_dirname(page_id, title):
    safe = re.sub(r'[<>:"/\\|?*]', '_', title)
    safe = safe.strip()[:60]
    return f'{page_id}-{safe}'


# =====================
# ADF -> Markdown 변환
# 이미지 메타 수집을 위해 context 추적
# =====================

class AdfConverter:
    def __init__(self, images_dir_name='images'):
        self.images_dir = images_dir_name
        self.image_metas = []  # 이미지 메타 데이터 수집
        self._current_section = ''
        self._context_buffer = []

    def convert(self, node):
        return self._node_to_md(node, depth=0)

    def _node_to_md(self, node, depth=0):
        if not isinstance(node, dict):
            return ''
        ntype = node.get('type', '')
        content = node.get('content', [])

        if ntype == 'doc':
            parts = [self._node_to_md(c, depth) for c in content]
            return '\n\n'.join(p for p in parts if p.strip())

        elif ntype == 'heading':
            level = node.get('attrs', {}).get('level', 2)
            inner = ''.join(self._node_to_md(c, depth) for c in content)
            self._current_section = inner
            return f'{"#" * level} {inner}'

        elif ntype == 'paragraph':
            inner = ''.join(self._node_to_md(c, depth) for c in content)
            return inner if inner.strip() else ''

        elif ntype == 'text':
            text = node.get('text', '')
            for mark in node.get('marks', []):
                mt = mark.get('type', '')
                if mt == 'strong': text = f'**{text}**'
                elif mt == 'em': text = f'*{text}*'
                elif mt == 'code': text = f'`{text}`'
                elif mt == 'link':
                    href = mark.get('attrs', {}).get('href', '#')
                    text = f'[{text}]({href})'
                elif mt == 'underline': text = f'<u>{text}</u>'
                elif mt == 'strike': text = f'~~{text}~~'
            return text

        elif ntype == 'bulletList':
            items = []
            for item in content:
                if item.get('type') == 'listItem':
                    item_text = ''.join(self._node_to_md(c, depth) for c in item.get('content', []))
                    items.append(f'- {item_text.strip()}')
            return '\n'.join(items)

        elif ntype == 'orderedList':
            items = []
            for i, item in enumerate(content, 1):
                if item.get('type') == 'listItem':
                    item_text = ''.join(self._node_to_md(c, depth) for c in item.get('content', []))
                    items.append(f'{i}. {item_text.strip()}')
            return '\n'.join(items)

        elif ntype == 'listItem':
            return ''.join(self._node_to_md(c, depth) for c in content)

        elif ntype in ('mediaSingle', 'mediaGroup'):
            parts = []
            for c in content:
                if c.get('type') == 'media':
                    attrs = c.get('attrs', {})
                    media_id = attrs.get('id', '')
                    alt = attrs.get('alt', '')
                    if media_id:
                        filename_placeholder = f'img_{media_id}'
                        parts.append(f'![{alt}]({self.images_dir}/{filename_placeholder})')
                        # 이미지 메타 등록 (나중에 실제 파일명으로 교체됨)
                        self.image_metas.append({
                            'media_id': media_id,
                            'filename': filename_placeholder,
                            'alt': alt,
                            'caption': '',
                            'parent_section': self._current_section,
                        })
            return '\n'.join(parts)

        elif ntype == 'caption':
            inner = ''.join(self._node_to_md(c, depth) for c in content)
            # 마지막 이미지 메타에 caption 추가
            if self.image_metas and inner.strip():
                self.image_metas[-1]['caption'] = inner.strip()
            return f'*{inner}*' if inner.strip() else ''

        elif ntype == 'codeBlock':
            lang = node.get('attrs', {}).get('language', '')
            code = ''.join(c.get('text', '') for c in content if c.get('type') == 'text')
            return f'```{lang}\n{code}\n```'

        elif ntype == 'blockquote':
            inner = '\n'.join(self._node_to_md(c, depth) for c in content)
            return '\n'.join(f'> {line}' for line in inner.split('\n'))

        elif ntype == 'table':
            return self._table_to_md(node)

        elif ntype == 'rule':
            return '---'

        elif ntype == 'hardBreak':
            return '\n'

        elif ntype == 'inlineCard':
            url = node.get('attrs', {}).get('url', '')
            return f'[{url}]({url})'

        elif ntype == 'panel':
            panel_type = node.get('attrs', {}).get('panelType', 'info')
            inner = '\n'.join(self._node_to_md(c, depth) for c in content)
            return f'> **[{panel_type.upper()}]** {inner}'

        elif ntype == 'expand':
            title = node.get('attrs', {}).get('title', '')
            inner = '\n'.join(self._node_to_md(c, depth) for c in content)
            return f'**{title}**\n{inner}'

        else:
            return '\n'.join(self._node_to_md(c, depth) for c in content)

    def _table_to_md(self, node):
        rows = node.get('content', [])
        md_rows = []
        for row in rows:
            cells = []
            for cell in row.get('content', []):
                cell_text = ''.join(self._node_to_md(c) for c in cell.get('content', []))
                cells.append(cell_text.strip().replace('\n', ' '))
            md_rows.append('| ' + ' | '.join(cells) + ' |')
        if len(md_rows) >= 1:
            # 헤더 구분선 추가
            first_row = rows[0] if rows else None
            if first_row:
                col_count = len(first_row.get('content', []))
                sep = '| ' + ' | '.join(['---'] * col_count) + ' |'
                md_rows.insert(1, sep)
        return '\n'.join(md_rows)


def process_page(page_id, page_title, topic_dir):
    """페이지 ADF 추출 → MD + 이미지 메타 JSON"""
    dir_name = safe_dirname(page_id, page_title)
    page_dir = topic_dir / dir_name
    images_dir = page_dir / 'images'
    page_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(exist_ok=True)

    url = f'{BASE}/wiki/rest/api/content/{page_id}?expand=body.atlas_doc_format,version,ancestors,space'
    try:
        r = get_with_retry(url)
    except Exception as e:
        print(f'  ERR [{page_id}]: {e}')
        return False

    if r.status_code != 200:
        print(f'  ERR [{page_id}] HTTP {r.status_code}')
        return False

    page_data = r.json()
    adf_value = page_data.get('body', {}).get('atlas_doc_format', {}).get('value', '{}')
    try:
        adf = json.loads(adf_value)
    except:
        adf = {}

    space_key = page_data.get('space', {}).get('key', '')
    ancestors = page_data.get('ancestors', [])
    breadcrumb = ' > '.join(a['title'] for a in ancestors) + (' > ' if ancestors else '') + page_title
    version = page_data.get('version', {}).get('number', '')
    confluence_url = f'https://iwta.atlassian.net/wiki/spaces/{space_key}/pages/{page_id}'

    # 첨부 이미지 다운로드
    att_url = f'{BASE}/wiki/rest/api/content/{page_id}/child/attachment?limit=100'
    try:
        att_r = get_with_retry(att_url)
        attachments = att_r.json().get('results', []) if att_r.status_code == 200 else []
    except:
        attachments = []

    media_id_map = {}  # file_id -> filename
    downloaded = 0

    for att in attachments:
        if not att.get('metadata', {}).get('mediaType', '').startswith('image/'):
            continue
        att_id = att['id']
        filename = att['title']
        file_id = att.get('extensions', {}).get('fileId', att_id)

        save_path = images_dir / filename
        if save_path.exists():
            media_id_map[file_id] = filename
            media_id_map[att_id] = filename
            downloaded += 1
            continue

        dl_url = f'{BASE}/wiki/rest/api/content/{page_id}/child/attachment/{att_id}/download'
        try:
            img_r = get_with_retry(dl_url)
            if img_r.status_code == 200 and len(img_r.content) > 0:
                save_path.write_bytes(img_r.content)
                media_id_map[file_id] = filename
                media_id_map[att_id] = filename
                downloaded += 1
        except Exception as e:
            print(f'    WARN 이미지 [{att_id}]: {e}')
        time.sleep(0.1)

    # ADF → Markdown
    converter = AdfConverter(images_dir_name='images')
    md_body = converter.convert(adf)

    # 이미지 메타: media_id -> 실제 파일명으로 교체
    for meta in converter.image_metas:
        mid = meta['media_id']
        real_fname = media_id_map.get(mid, '')
        if real_fname:
            meta['filename'] = real_fname
            old_ref = f'images/img_{mid}'
            new_ref = f'images/{real_fname}'
            md_body = md_body.replace(old_ref, new_ref)
        else:
            meta['filename'] = 'not-found'
            md_body = md_body.replace(f'images/img_{mid}', 'images/not-found')

    # surrounding context 추가 (앞뒤 200자)
    for meta in converter.image_metas:
        fname = meta['filename']
        ref = f'images/{fname}'
        idx = md_body.find(ref)
        if idx >= 0:
            ctx_start = max(0, idx - 200)
            ctx_end = min(len(md_body), idx + len(ref) + 200)
            meta['surrounding_context'] = md_body[ctx_start:ctx_end]
        else:
            meta['surrounding_context'] = ''

    # MD 파일 저장
    header = f'---\nsource_page_id: {page_id}\ntitle: {page_title}\nbreadcrumb: {breadcrumb}\nspace: {space_key}\nversion: {version}\nconfluence_url: {confluence_url}\nimages: {downloaded}\n---\n\n'
    md_path = page_dir / 'content.md'
    md_path.write_text(header + md_body, encoding='utf-8')

    # 이미지 메타 JSON 저장
    meta_path = page_dir / 'images-meta.json'
    meta_path.write_text(json.dumps({
        'page_id': page_id,
        'title': page_title,
        'images': converter.image_metas
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    return True


# 메인 실행
with open(PAGES_FILE, encoding='utf-8') as f:
    all_pages = json.load(f)

total_success = 0
total_failed = 0

for topic, pages in all_pages.items():
    topic_dir = OUTPUT_BASE / topic
    topic_dir.mkdir(exist_ok=True)

    total = len(pages)
    t_success = 0
    t_failed = 0

    already_done = sum(1 for p in pages if p['id'] in done_set)
    print(f'\n[{topic}] {total}개 (이미 완료: {already_done}개)')

    for i, page in enumerate(pages):
        pid = page['id']
        ptitle = page['title']

        if pid in done_set:
            t_success += 1
            continue

        print(f'  [{i+1}/{total}] {pid} — {ptitle[:50]}')
        ok = process_page(pid, ptitle, topic_dir)

        if ok:
            progress['done'].append(pid)
            done_set.add(pid)
            t_success += 1
        else:
            progress['failed'].append({'id': pid, 'title': ptitle, 'topic': topic})
            t_failed += 1

        if (i + 1) % 10 == 0:
            save_progress()
            print(f'  → 진행: {t_success}완료/{t_failed}실패/{total}전체')

        time.sleep(0.3)

    save_progress()
    print(f'[{topic}] 완료: {t_success}성공 {t_failed}실패')
    total_success += t_success
    total_failed += t_failed

save_progress()
print(f'\n=== 전체 완료 ===')
print(f'성공: {total_success}개, 실패: {total_failed}개')
print(f'저장: {OUTPUT_BASE}')
