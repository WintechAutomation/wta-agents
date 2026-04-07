"""MD → HTML (GitHub 스타일, 표·코드블록 지원) + dashboard 업로드."""
import sys
import re
import uuid
import json
import urllib.request
from pathlib import Path
from urllib.parse import quote

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SRC = Path('C:/MES/wta-agents/reports/research/graphrag-ontology-draft-v1.md')
OUT_NAME = 'graphrag-ontology-draft-v1.1.html'
OUT_PATH = Path('C:/MES/wta-agents/workspaces/docs-agent') / OUT_NAME
TITLE = 'WTA GraphRAG 온톨로지 초안 v1.1'

CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Malgun Gothic', sans-serif; max-width: 960px; margin: 0 auto; padding: 32px 40px; color: #24292f; line-height: 1.65; background: #fff; }
h1 { font-size: 2em; border-bottom: 1px solid #d0d7de; padding-bottom: 0.3em; margin-top: 24px; }
h2 { font-size: 1.5em; border-bottom: 1px solid #d0d7de; padding-bottom: 0.3em; margin-top: 24px; }
h3 { font-size: 1.25em; margin-top: 24px; }
h4 { font-size: 1em; margin-top: 24px; }
hr { border: none; border-top: 1px solid #d0d7de; margin: 24px 0; }
p { margin: 0 0 16px; }
ul, ol { padding-left: 2em; margin: 0 0 16px; }
li { margin: 0.25em 0; }
a { color: #0969da; text-decoration: none; }
a:hover { text-decoration: underline; }
code { background: rgba(175,184,193,0.2); padding: 0.2em 0.4em; border-radius: 6px; font-size: 85%; font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace; }
pre { background: #f6f8fa; padding: 16px; border-radius: 6px; overflow-x: auto; font-size: 85%; line-height: 1.45; }
pre code { background: transparent; padding: 0; border-radius: 0; font-size: 100%; }
table { border-collapse: collapse; margin: 0 0 16px; display: block; overflow-x: auto; max-width: 100%; }
table th, table td { border: 1px solid #d0d7de; padding: 6px 13px; }
table th { background: #f6f8fa; font-weight: 600; text-align: left; }
table tr:nth-child(2n) { background: #f6f8fa; }
blockquote { margin: 0 0 16px; padding: 0 1em; color: #656d76; border-left: 0.25em solid #d0d7de; }
strong { font-weight: 600; color: #1f2328; }
em { font-style: italic; }
"""


def inline(text: str) -> str:
    """인라인 마크다운 변환."""
    # escape first
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    # inline code
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # links
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', text)
    # bold
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    # italic
    text = re.sub(r'(?<![*_])\*([^*\n]+)\*(?![*_])', r'<em>\1</em>', text)
    return text


def is_table_sep(line: str) -> bool:
    s = line.strip()
    if not s.startswith('|') or not s.endswith('|'):
        return False
    cells = [c.strip() for c in s.strip('|').split('|')]
    return all(re.match(r'^:?-+:?$', c) for c in cells) and len(cells) >= 1


def parse_table_row(line: str) -> list:
    s = line.strip().strip('|')
    return [inline(c.strip()) for c in s.split('|')]


def convert(md_text: str) -> str:
    lines = md_text.splitlines()
    out = []
    i = 0
    in_code = False
    code_buf = []
    code_lang = ''
    list_stack = []  # list of ('ul'|'ol', indent)

    def close_lists(to_depth=0):
        while len(list_stack) > to_depth:
            tag, _ = list_stack.pop()
            out.append(f'</{tag}>')

    while i < len(lines):
        line = lines[i]

        # code block fence
        m = re.match(r'^```(\w*)\s*$', line)
        if m:
            if in_code:
                out.append('<pre><code>' + '\n'.join(code_buf).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;') + '</code></pre>')
                in_code = False
                code_buf = []
            else:
                close_lists(0)
                in_code = True
                code_lang = m.group(1)
            i += 1
            continue

        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # table detection
        if (line.strip().startswith('|') and i + 1 < len(lines)
                and is_table_sep(lines[i + 1])):
            close_lists(0)
            header = parse_table_row(line)
            out.append('<table>')
            out.append('<thead><tr>' + ''.join(f'<th>{h}</th>' for h in header) + '</tr></thead>')
            out.append('<tbody>')
            i += 2  # skip header + sep
            while i < len(lines) and lines[i].strip().startswith('|'):
                row = parse_table_row(lines[i])
                out.append('<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>')
                i += 1
            out.append('</tbody></table>')
            continue

        # heading
        m = re.match(r'^(#{1,6})\s+(.+)$', line)
        if m:
            close_lists(0)
            level = len(m.group(1))
            out.append(f'<h{level}>{inline(m.group(2).strip())}</h{level}>')
            i += 1
            continue

        # hr
        if re.match(r'^---+\s*$', line):
            close_lists(0)
            out.append('<hr>')
            i += 1
            continue

        # blockquote
        if line.strip().startswith('> '):
            close_lists(0)
            block = []
            while i < len(lines) and lines[i].strip().startswith('> '):
                block.append(lines[i].strip()[2:])
                i += 1
            out.append('<blockquote>' + inline(' '.join(block)) + '</blockquote>')
            continue

        # lists
        m_ul = re.match(r'^(\s*)[-*+]\s+(.+)$', line)
        m_ol = re.match(r'^(\s*)(\d+)\.\s+(.+)$', line)
        if m_ul or m_ol:
            indent = len((m_ul or m_ol).group(1))
            depth = indent // 2 + 1
            tag = 'ul' if m_ul else 'ol'
            content = (m_ul.group(2) if m_ul else m_ol.group(3))
            # adjust stack
            while len(list_stack) > depth:
                t, _ = list_stack.pop()
                out.append(f'</{t}>')
            while len(list_stack) < depth:
                out.append(f'<{tag}>')
                list_stack.append((tag, indent))
            # if same depth different tag
            if list_stack and list_stack[-1][0] != tag:
                t, _ = list_stack.pop()
                out.append(f'</{t}>')
                out.append(f'<{tag}>')
                list_stack.append((tag, indent))
            out.append(f'<li>{inline(content)}</li>')
            i += 1
            continue

        # blank line
        if line.strip() == '':
            close_lists(0)
            i += 1
            continue

        # paragraph
        close_lists(0)
        out.append(f'<p>{inline(line.strip())}</p>')
        i += 1

    close_lists(0)
    if in_code:
        out.append('<pre><code>' + '\n'.join(code_buf).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;') + '</code></pre>')

    return '\n'.join(out)


def build_html(body_html: str) -> str:
    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{TITLE}</title>
<style>{CSS}</style>
</head>
<body>
{body_html}
</body>
</html>
'''


def build_multipart(field: str, filename: str, data: bytes, content_type: str):
    boundary = '----WtaBoundary' + uuid.uuid4().hex
    fname_enc = quote(filename, safe='')
    parts = []
    parts.append(f'--{boundary}'.encode())
    parts.append(
        f'Content-Disposition: form-data; name="{field}"; filename="file.bin"; filename*=UTF-8\'\'{fname_enc}'.encode()
    )
    parts.append(f'Content-Type: {content_type}'.encode())
    parts.append(b'')
    parts.append(data)
    parts.append(f'--{boundary}--'.encode())
    parts.append(b'')
    body = b'\r\n'.join(parts)
    ct = f'multipart/form-data; boundary={boundary}'
    return body, ct


def main():
    md = SRC.read_text(encoding='utf-8')
    print(f'원본: {SRC} ({len(md):,} bytes)')
    body = convert(md)
    html = build_html(body)
    OUT_PATH.write_text(html, encoding='utf-8')
    print(f'HTML: {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes)')

    # 업로드 시도
    data = OUT_PATH.read_bytes()
    body_bytes, ct = build_multipart('file', OUT_NAME, data, 'text/html')
    req = urllib.request.Request('http://localhost:5555/api/upload', data=body_bytes, method='POST')
    req.add_header('Content-Type', ct)
    req.add_header('Content-Length', str(len(body_bytes)))
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status = resp.status
            rb = resp.read().decode('utf-8')
        print(f'\n업로드 응답 {status}:')
        print(rb)
        if status == 200:
            d = json.loads(rb)
            if d.get('ok'):
                stored = d['file']['stored_name']
                url = f'https://agent.mes-wta.com/api/files/{stored}'
                print(f'\n✓ URL: {url}')
                # 검증
                vreq = urllib.request.Request(url, method='GET')
                with urllib.request.urlopen(vreq, timeout=30) as vr:
                    print(f'검증 GET {vr.status}')
    except urllib.error.HTTPError as e:
        print(f'업로드 실패 {e.code}: {e.read().decode("utf-8", errors="replace")}')
    except Exception as e:
        print(f'오류: {e}')


if __name__ == '__main__':
    main()
