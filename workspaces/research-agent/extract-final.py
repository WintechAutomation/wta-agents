"""
경상연구개발 최종 31건 원문 추출
구조: reports/MAX/confluence-{주제}/{pageId}-{title}/
  - index.html  (ADF→HTML)
  - images/
  - images-meta.json  { page_id, page_title, downloaded: [...] }
"""
import requests, json, time, re, sys, html as html_module
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TOKEN = open('C:/MES/wta-agents/config/atlassian-api-token.txt').read().strip()
AUTH = ('hjcho@wta.kr', TOKEN)
BASE = 'https://iwta.atlassian.net'
REPORTS_BASE = Path('C:/MES/wta-agents/reports/MAX')

LIST_FILE = Path('C:/MES/wta-agents/workspaces/research-agent/final-extract-list.json')
PROGRESS_FILE = Path('C:/MES/wta-agents/workspaces/research-agent/final-extract-progress.json')

TIMEOUT = 30
MAX_RETRIES = 3

if PROGRESS_FILE.exists():
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
    return f'{page_id}-{safe[:60]}'

def get_r(url):
    for i in range(MAX_RETRIES):
        try:
            return requests.get(url, auth=AUTH, allow_redirects=True, timeout=TIMEOUT)
        except Exception as e:
            if i < MAX_RETRIES - 1:
                time.sleep(5 * (i + 1))
            else:
                raise

def adf_to_html(node, idir='images'):
    if not isinstance(node, dict):
        return ''
    ntype = node.get('type', '')
    content = node.get('content', [])
    if ntype == 'doc':
        return '\n'.join(adf_to_html(c, idir) for c in content)
    elif ntype == 'paragraph':
        inner = ''.join(adf_to_html(c, idir) for c in content)
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
        lv = node.get('attrs', {}).get('level', 2)
        inner = ''.join(adf_to_html(c, idir) for c in content)
        return f'<h{lv}>{inner}</h{lv}>'
    elif ntype == 'bulletList':
        items = ''.join(
            f'<li>{"".join(adf_to_html(c, idir) for c in item.get("content", []))}</li>'
            for item in content if item.get('type') == 'listItem'
        )
        return f'<ul>{items}</ul>'
    elif ntype == 'orderedList':
        items = ''.join(
            f'<li>{"".join(adf_to_html(c, idir) for c in item.get("content", []))}</li>'
            for item in content if item.get('type') == 'listItem'
        )
        return f'<ol>{items}</ol>'
    elif ntype == 'listItem':
        return ''.join(adf_to_html(c, idir) for c in content)
    elif ntype in ('mediaSingle', 'mediaGroup'):
        parts = []
        for c in content:
            if c.get('type') == 'media':
                mid = c.get('attrs', {}).get('id', '')
                alt = html_module.escape(c.get('attrs', {}).get('alt', ''))
                if mid:
                    parts.append(
                        f'<figure><img src="{idir}/{mid}" alt="{alt}" '
                        f'style="max-width:100%;border:1px solid #ddd;border-radius:4px;margin:8px 0;">'
                        f'<figcaption style="font-size:12px;color:#666;">{alt}</figcaption></figure>'
                    )
        return '\n'.join(parts)
    elif ntype == 'codeBlock':
        lang = node.get('attrs', {}).get('language', '')
        code = ''.join(c.get('text', '') for c in content if c.get('type') == 'text')
        return f'<pre><code class="language-{lang}">{html_module.escape(code)}</code></pre>'
    elif ntype == 'blockquote':
        inner = '\n'.join(adf_to_html(c, idir) for c in content)
        return f'<blockquote style="border-left:4px solid #ddd;padding-left:12px;color:#555;">{inner}</blockquote>'
    elif ntype == 'table':
        rows = ''.join(adf_to_html(c, idir) for c in content)
        return f'<table style="border-collapse:collapse;width:100%;margin:12px 0;">{rows}</table>'
    elif ntype == 'tableRow':
        return f'<tr>{"".join(adf_to_html(c, idir) for c in content)}</tr>'
    elif ntype in ('tableCell', 'tableHeader'):
        tag = 'th' if ntype == 'tableHeader' else 'td'
        inner = ''.join(adf_to_html(c, idir) for c in content)
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
        pt = node.get('attrs', {}).get('panelType', 'info')
        bg = {'info': '#deebff', 'note': '#fffae6', 'warning': '#fff3cd',
              'error': '#ffebe6', 'success': '#e3fcef'}.get(pt, '#f4f5f7')
        inner = '\n'.join(adf_to_html(c, idir) for c in content)
        return f'<div style="background:{bg};border-radius:4px;padding:12px 16px;margin:12px 0;">{inner}</div>'
    elif ntype == 'expand':
        title = node.get('attrs', {}).get('title', '')
        inner = '\n'.join(adf_to_html(c, idir) for c in content)
        return f'<details><summary><strong>{html_module.escape(title)}</strong></summary>{inner}</details>'
    else:
        return '\n'.join(adf_to_html(c, idir) for c in content)


def process_page(pid, ptitle, out_dir):
    """페이지 추출: index.html + images/ + images-meta.json"""
    dname = safe_dirname(pid, ptitle)
    pdir = out_dir / dname
    idir = pdir / 'images'

    # 이미 완료된 경우 스킵
    if (pdir / 'index.html').exists() and (pdir / 'images-meta.json').exists():
        print(f'  SKIP (기존): {dname}')
        return True

    pdir.mkdir(parents=True, exist_ok=True)
    idir.mkdir(exist_ok=True)

    r = get_r(f'{BASE}/wiki/rest/api/content/{pid}?expand=body.atlas_doc_format,version,ancestors,space')
    if r.status_code != 200:
        print(f'  ERR [{pid}] HTTP {r.status_code}')
        return False

    data = r.json()
    adf_val = data.get('body', {}).get('atlas_doc_format', {}).get('value', '{}')
    try:
        adf = json.loads(adf_val)
    except Exception:
        adf = {}

    space_obj = data.get('space', {})
    space_key = space_obj.get('key', '') if isinstance(space_obj, dict) else ''
    ancestors = data.get('ancestors', [])
    breadcrumb = ' > '.join(a['title'] for a in ancestors)
    if breadcrumb:
        breadcrumb += ' > '
    breadcrumb += ptitle
    version = data.get('version', {}).get('number', '')
    cf_url = f'https://iwta.atlassian.net/wiki/spaces/{space_key}/pages/{pid}'

    # 첨부 이미지 다운로드
    att_r = get_r(f'{BASE}/wiki/rest/api/content/{pid}/child/attachment?limit=100')
    attachments = att_r.json().get('results', []) if att_r.status_code == 200 else []

    media_map = {}  # media_id/att_id -> filename
    downloaded_list = []

    for att in attachments:
        if not att.get('metadata', {}).get('mediaType', '').startswith('image/'):
            continue
        att_id = att['id']
        fname = att['title']
        fid = att.get('extensions', {}).get('fileId', att_id)

        sp = idir / fname
        if sp.exists():
            media_map[fid] = fname
            media_map[att_id] = fname
            downloaded_list.append({'filename': fname, 'att_id': att_id, 'file_id': fid})
            continue

        try:
            ir = get_r(f'{BASE}/wiki/rest/api/content/{pid}/child/attachment/{att_id}/download')
            if ir.status_code == 200 and ir.content:
                sp.write_bytes(ir.content)
                media_map[fid] = fname
                media_map[att_id] = fname
                downloaded_list.append({'filename': fname, 'att_id': att_id, 'file_id': fid})
        except Exception as e:
            print(f'    WARN img [{att_id}]: {e}')
        time.sleep(0.1)

    # ADF → HTML
    body_html = adf_to_html(adf)
    for mid, fn in media_map.items():
        body_html = body_html.replace(f'images/{mid}"', f'images/{fn}"')
    body_html = re.sub(
        r'images/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"',
        'images/not-found"', body_html
    )
    body_html = re.sub(r'images/att\d+"', 'images/not-found"', body_html)

    # index.html 저장
    html_content = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_module.escape(ptitle)}</title>
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
<h1>{html_module.escape(ptitle)}</h1>
<div class="meta">
  <span>📄 페이지 ID: {pid}</span> &nbsp;
  <span>🔖 버전: {version}</span> &nbsp;
  <span>🖼️ 이미지: {len(downloaded_list)}개</span>
</div>
{body_html}
<p class="source-link">🔗 원본: <a href="{cf_url}" target="_blank">{cf_url}</a></p>
</body>
</html>'''
    (pdir / 'index.html').write_text(html_content, encoding='utf-8')

    # images-meta.json 저장
    meta = {
        'page_id': pid,
        'page_title': ptitle,
        'space': space_key,
        'breadcrumb': breadcrumb,
        'version': str(version),
        'confluence_url': cf_url,
        'downloaded': downloaded_list,
    }
    (pdir / 'images-meta.json').write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    print(f'  완료: {dname} (이미지 {len(downloaded_list)}개)')
    return True


# 메인 실행
import sys

# 인수로 주제 지정 가능 (없으면 전체)
target_topic = sys.argv[1] if len(sys.argv) > 1 else None

with open(LIST_FILE, encoding='utf-8') as f:
    all_pages = json.load(f)

# 주제별 그룹화
from collections import defaultdict
by_topic = defaultdict(list)
for p in all_pages:
    by_topic[p['topic']].append(p)

topic_order = ['장비물류', '분말검사', '연삭측정제어', '포장혼입검사', '호닝신뢰성']

total_success = 0
total_failed = 0

for topic in topic_order:
    if target_topic and topic != target_topic:
        continue

    pages = by_topic[topic]
    dir_name = f'confluence-{topic}'
    out_dir = REPORTS_BASE / dir_name
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f'\n=== [{topic}] {len(pages)}개 ===')

    t_ok = 0
    t_fail = 0
    for p in pages:
        pid, ptitle = p['id'], p['title']
        if pid in done_set:
            print(f'  SKIP: {ptitle[:45]}')
            t_ok += 1
            continue

        print(f'  처리: {pid} | {ptitle[:45]}')
        ok = process_page(pid, ptitle, out_dir)

        if ok:
            progress['done'].append(pid)
            done_set.add(pid)
            t_ok += 1
        else:
            progress['failed'].append({'id': pid, 'title': ptitle, 'topic': topic})
            t_fail += 1

        save_progress()
        time.sleep(0.3)

    print(f'[{topic}] 완료: {t_ok}성공 {t_fail}실패')
    total_success += t_ok
    total_failed += t_fail

print(f'\n=== 전체 완료: {total_success}성공 {total_failed}실패 ===')
