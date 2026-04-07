"""
UserManual 스페이스 후반부 추출 (db-manager 담당: 575~1148번, 574개 페이지)
CM 추출 스크립트(cm-extract-embed.py)와 동일 구조

실행:
  python um-extract.py
"""
import requests, os, json, time, re, sys, html as html_module, logging
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TOKEN = open('C:/MES/wta-agents/config/atlassian-api-token.txt').read().strip()
AUTH = ('hjcho@wta.kr', TOKEN)
BASE = 'https://iwta.atlassian.net'
BASE_DIR = Path('C:/MES/wta-agents/reports/MAX/confluence-UserManual')
BASE_DIR.mkdir(parents=True, exist_ok=True)

PAGES_FILE = 'C:/MES/wta-agents/workspaces/research-agent/um-pages-part2.json'
PROGRESS_FILE = 'C:/MES/wta-agents/workspaces/db-manager/um-extract-part2-progress.json'

TIMEOUT = 30
MAX_RETRIES = 3

logging.basicConfig(
    level=logging.INFO,
    format='[um-extract] %(asctime)s %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('um-extract')

if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, encoding='utf-8') as f:
        progress = json.load(f)
else:
    progress = {'done': [], 'failed': []}

done_set = set(progress['done'])


def save_progress():
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def safe_dirname(page_id, title):
    safe = re.sub(r'[<>:"/\\|?*]', '_', title)
    return f'{page_id}-{safe.strip()[:60]}'


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


def adf_to_html(node, images_dir_name='images'):
    if not isinstance(node, dict):
        return ''
    ntype = node.get('type', '')
    content = node.get('content', [])

    if ntype == 'doc':
        return '\n'.join(adf_to_html(c, images_dir_name) for c in content)
    elif ntype == 'paragraph':
        inner = ''.join(adf_to_html(c, images_dir_name) for c in content)
        return f'<p>{inner}</p>' if inner.strip() else '<br>'
    elif ntype == 'text':
        text = html_module.escape(node.get('text', ''))
        for mark in node.get('marks', []):
            mt = mark.get('type', '')
            if mt == 'strong': text = f'<strong>{text}</strong>'
            elif mt == 'em': text = f'<em>{text}</em>'
            elif mt == 'code': text = f'<code>{text}</code>'
            elif mt == 'link':
                href = mark.get('attrs', {}).get('href', '#')
                text = f'<a href="{html_module.escape(href)}" target="_blank">{text}</a>'
            elif mt == 'underline': text = f'<u>{text}</u>'
            elif mt == 'strike': text = f'<s>{text}</s>'
        return text
    elif ntype == 'heading':
        level = node.get('attrs', {}).get('level', 2)
        inner = ''.join(adf_to_html(c, images_dir_name) for c in content)
        return f'<h{level}>{inner}</h{level}>'
    elif ntype == 'bulletList':
        items = ''.join(
            f'<li>{"".join(adf_to_html(c, images_dir_name) for c in item.get("content", []))}</li>'
            for item in content if item.get('type') == 'listItem'
        )
        return f'<ul>{items}</ul>'
    elif ntype == 'orderedList':
        items = ''.join(
            f'<li>{"".join(adf_to_html(c, images_dir_name) for c in item.get("content", []))}</li>'
            for item in content if item.get('type') == 'listItem'
        )
        return f'<ol>{items}</ol>'
    elif ntype == 'listItem':
        return ''.join(adf_to_html(c, images_dir_name) for c in content)
    elif ntype in ('mediaSingle', 'mediaGroup'):
        parts = []
        for c in content:
            if c.get('type') == 'media':
                attrs = c.get('attrs', {})
                media_id = attrs.get('id', '')
                alt = html_module.escape(attrs.get('alt', ''))
                if media_id:
                    parts.append(
                        f'<figure><img src="{images_dir_name}/{media_id}" alt="{alt}" '
                        f'style="max-width:100%;border:1px solid #ddd;border-radius:4px;margin:8px 0;">'
                        f'<figcaption style="font-size:12px;color:#666;">{alt}</figcaption></figure>'
                    )
        return '\n'.join(parts)
    elif ntype == 'codeBlock':
        lang = node.get('attrs', {}).get('language', '')
        code = ''.join(c.get('text', '') for c in content if c.get('type') == 'text')
        return f'<pre><code class="language-{lang}">{html_module.escape(code)}</code></pre>'
    elif ntype == 'blockquote':
        inner = '\n'.join(adf_to_html(c, images_dir_name) for c in content)
        return f'<blockquote style="border-left:4px solid #ddd;padding-left:12px;color:#555;">{inner}</blockquote>'
    elif ntype == 'table':
        rows = ''.join(adf_to_html(c, images_dir_name) for c in content)
        return f'<table style="border-collapse:collapse;width:100%;margin:12px 0;">{rows}</table>'
    elif ntype == 'tableRow':
        cells = ''.join(adf_to_html(c, images_dir_name) for c in content)
        return f'<tr>{cells}</tr>'
    elif ntype in ('tableCell', 'tableHeader'):
        tag = 'th' if ntype == 'tableHeader' else 'td'
        inner = ''.join(adf_to_html(c, images_dir_name) for c in content)
        style = 'border:1px solid #ddd;padding:6px 10px;'
        if ntype == 'tableHeader':
            style += 'background:#f4f5f7;font-weight:bold;'
        return f'<{tag} style="{style}">{inner}</{tag}>'
    elif ntype == 'rule':
        return '<hr>'
    elif ntype == 'hardBreak':
        return '<br>'
    elif ntype == 'inlineCard':
        url = node.get('attrs', {}).get('url', '')
        return f'<a href="{html_module.escape(url)}" target="_blank">{html_module.escape(url)}</a>'
    elif ntype == 'panel':
        panel_type = node.get('attrs', {}).get('panelType', 'info')
        colors = {'info': '#deebff', 'note': '#fffae6', 'warning': '#fff3cd', 'error': '#ffebe6', 'success': '#e3fcef'}
        bg = colors.get(panel_type, '#f4f5f7')
        inner = '\n'.join(adf_to_html(c, images_dir_name) for c in content)
        return f'<div style="background:{bg};border-radius:4px;padding:12px 16px;margin:12px 0;">{inner}</div>'
    elif ntype == 'expand':
        title = node.get('attrs', {}).get('title', '')
        inner = '\n'.join(adf_to_html(c, images_dir_name) for c in content)
        return f'<details><summary><strong>{html_module.escape(title)}</strong></summary>{inner}</details>'
    else:
        return '\n'.join(adf_to_html(c, images_dir_name) for c in content)


def process_page(page_id, page_title):
    dir_name = safe_dirname(page_id, page_title)
    page_dir = BASE_DIR / dir_name
    images_dir = page_dir / 'images'
    page_dir.mkdir(exist_ok=True)
    images_dir.mkdir(exist_ok=True)

    url = f'{BASE}/wiki/rest/api/content/{page_id}?expand=body.atlas_doc_format,version,ancestors'
    try:
        r = get_with_retry(url)
    except Exception as e:
        print(f'  ERR [{page_id}] {page_title}: {e}')
        return False

    if r.status_code != 200:
        print(f'  ERR [{page_id}] HTTP {r.status_code}')
        return False

    page_data = r.json()
    adf_value = page_data.get('body', {}).get('atlas_doc_format', {}).get('value', '{}')
    try:
        adf = json.loads(adf_value)
    except Exception:
        adf = {}

    att_url = f'{BASE}/wiki/rest/api/content/{page_id}/child/attachment?limit=100'
    try:
        att_r = get_with_retry(att_url)
        attachments = att_r.json().get('results', []) if att_r.status_code == 200 else []
    except Exception:
        attachments = []

    media_id_map = {}
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

    body_html = adf_to_html(adf, 'images')
    for media_id, fname in media_id_map.items():
        body_html = body_html.replace(f'images/{media_id}"', f'images/{fname}"')
    body_html = re.sub(r'images/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"', 'images/not-found"', body_html)
    body_html = re.sub(r'images/att\d+"', 'images/not-found"', body_html)

    ancestors = page_data.get('ancestors', [])
    breadcrumb = ' > '.join(a['title'] for a in ancestors) + (' > ' if ancestors else '') + page_title
    version = page_data.get('version', {}).get('number', '')
    confluence_url = f'https://iwta.atlassian.net/wiki/spaces/UserManual/pages/{page_id}'

    html_content = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_module.escape(page_title)}</title>
<style>
  body {{ font-family: 'Malgun Gothic', sans-serif; max-width: 1100px; margin: 0 auto; padding: 24px; color: #172B4D; line-height: 1.7; }}
  h1 {{ font-size: 22px; color: #0052CC; border-bottom: 3px solid #0052CC; padding-bottom: 10px; margin-bottom: 20px; }}
  h2 {{ font-size: 17px; color: #253858; border-left: 4px solid #0065FF; padding-left: 10px; margin-top: 28px; }}
  h3 {{ font-size: 15px; color: #253858; margin-top: 20px; }}
  .meta {{ background: #F4F5F7; padding: 10px 14px; border-radius: 4px; font-size: 12px; color: #6B778C; margin-bottom: 20px; }}
  .breadcrumb {{ font-size: 12px; color: #6B778C; margin-bottom: 16px; }}
  img {{ max-width: 100%; height: auto; border: 1px solid #DFE1E6; border-radius: 4px; display: block; margin: 12px 0; }}
  figure {{ margin: 16px 0; }}
  figcaption {{ font-size: 11px; color: #6B778C; margin-top: -8px; }}
  pre {{ background: #F4F5F7; padding: 12px; border-radius: 4px; overflow-x: auto; font-size: 13px; }}
  code {{ background: #F4F5F7; padding: 1px 4px; border-radius: 2px; font-size: 13px; }}
  pre code {{ background: none; padding: 0; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  td, th {{ border: 1px solid #DFE1E6; padding: 6px 10px; }}
  th {{ background: #F4F5F7; }}
  ul, ol {{ padding-left: 20px; }}
  li {{ margin-bottom: 4px; }}
  a {{ color: #0065FF; }}
  .source-link {{ font-size: 12px; color: #0065FF; margin-top: 24px; border-top: 1px solid #DFE1E6; padding-top: 12px; }}
</style>
</head>
<body>
<div class="breadcrumb">{html_module.escape(breadcrumb)}</div>
<h1>{html_module.escape(page_title)}</h1>
<div class="meta">
  <span>📄 페이지 ID: {page_id}</span> &nbsp;
  <span>🔖 버전: {version}</span> &nbsp;
  <span>🖼️ 이미지: {downloaded}개</span>
</div>
{body_html}
<p class="source-link">🔗 원본: <a href="{confluence_url}" target="_blank">{confluence_url}</a></p>
</body>
</html>'''

    (page_dir / 'index.html').write_text(html_content, encoding='utf-8')
    return True


with open(PAGES_FILE, encoding='utf-8') as f:
    pages = json.load(f)

total = len(pages)
success = 0
failed = 0

log.info(f'[UM-PART2] {total}개 페이지 추출 시작 (이미 완료: {len(done_set)}개)')

for i, page in enumerate(pages):
    page_id = str(page['id'])
    page_title = page.get('title', f'page-{page_id}')

    if page_id in done_set:
        success += 1
        continue

    print(f'[{i+1}/{total}] {page_id} — {page_title[:50]}')
    ok = process_page(page_id, page_title)

    if ok:
        progress['done'].append(page_id)
        done_set.add(page_id)
        success += 1
    else:
        progress['failed'].append({'id': page_id, 'title': page_title})
        failed += 1

    if (i + 1) % 20 == 0:
        save_progress()
        log.info(f'진행: {success}완료/{failed}실패/{total}전체')

    time.sleep(0.3)

save_progress()
print(f'\n=== UM PART2 완료 ===')
print(f'성공: {success}건, 실패: {failed}건')
