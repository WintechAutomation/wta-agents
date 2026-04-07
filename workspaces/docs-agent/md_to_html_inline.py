"""
연구노트 MD → 단일파일 HTML (이미지 base64 인라인)
"""
import base64
import io
import re
import sys
from pathlib import Path
from urllib.parse import unquote

from PIL import Image

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path('C:/MES/wta-agents/reports/MAX')
OUT = Path('C:/MES/wta-agents/workspaces/docs-agent')
TOPICS = [
    ('장비물류', 1),
    ('분말검사', 2),
    ('연삭측정제어', 3),
    ('포장혼입검사', 4),
    ('호닝신뢰성', 5),
]

MAX_DIM = 1200
JPEG_QUALITY = 80

CSS = """
* { box-sizing: border-box; }
body { font-family: 'Malgun Gothic','맑은 고딕',sans-serif; max-width: 980px; margin: 0 auto; padding: 32px 24px; color: #222; line-height: 1.7; background: #fafafa; }
h1 { font-size: 28px; border-bottom: 3px solid #CC0000; padding-bottom: 10px; margin-top: 0; }
h2 { font-size: 22px; color: #003366; border-left: 5px solid #4472C4; padding-left: 12px; margin-top: 36px; }
h3 { font-size: 17px; color: #444; margin-top: 20px; }
hr { border: none; border-top: 1px dashed #ccc; margin: 24px 0; }
p { margin: 10px 0; }
ul, ol { padding-left: 28px; }
li { margin: 4px 0; }
code { background: #f0f0f0; padding: 1px 6px; border-radius: 3px; font-size: 0.92em; }
a { color: #1565C0; text-decoration: none; }
a:hover { text-decoration: underline; }
img { max-width: 100%; height: auto; display: block; margin: 12px auto; border: 1px solid #e0e0e0; border-radius: 4px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
.caption { text-align: center; font-style: italic; color: #666; font-size: 13px; margin: 4px 0 20px; }
.section-label { display: inline-block; background: #4472C4; color: #fff; padding: 4px 12px; border-radius: 4px; font-weight: 700; font-size: 14px; margin: 16px 0 8px; }
.meta-line { color: #555; font-size: 14px; }
strong { color: #CC0000; }
"""


def img_to_data_uri(img_path: Path) -> str:
    """이미지 파일 → base64 data URI. 리사이즈 + JPEG 변환."""
    try:
        with Image.open(img_path) as im:
            im = im.convert('RGB') if im.mode in ('RGBA', 'P', 'LA') else im
            if im.mode != 'RGB':
                im = im.convert('RGB')
            w, h = im.size
            if max(w, h) > MAX_DIM:
                scale = MAX_DIM / max(w, h)
                im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format='JPEG', quality=JPEG_QUALITY, optimize=True)
            data = buf.getvalue()
        b64 = base64.b64encode(data).decode('ascii')
        return f'data:image/jpeg;base64,{b64}'
    except Exception as e:
        print(f'  ⚠️ 이미지 오류 {img_path.name}: {e}')
        return ''


def render_inline(text: str) -> str:
    """인라인 마크다운 (bold, code, link)."""
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', text)
    return text


def convert_md_to_html(md_path: Path, topic: str) -> str:
    lines = md_path.read_text(encoding='utf-8').splitlines()
    html_parts = []
    in_list = False

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # 이미지: ![caption](path)
        m = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line)
        if m:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            alt = m.group(1)
            src = unquote(m.group(2))
            img_full = BASE / src
            data_uri = img_to_data_uri(img_full)
            if data_uri:
                html_parts.append(f'<img src="{data_uri}" alt="{render_inline(alt)}">')
            else:
                html_parts.append(f'<p class="caption">[이미지 로드 실패: {img_full.name}]</p>')
            i += 1
            continue

        # 제목
        if line.startswith('### '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<h3>{render_inline(line[4:])}</h3>')
        elif line.startswith('## '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<h2>{render_inline(line[3:])}</h2>')
        elif line.startswith('# '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<h1>{render_inline(line[2:])}</h1>')
        elif line == '---':
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append('<hr>')
        elif re.match(r'^(- |\d+\. )', line):
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            content = re.sub(r'^(- |\d+\. )', '', line)
            html_parts.append(f'<li>{render_inline(content)}</li>')
        elif line.startswith('*') and line.endswith('*') and len(line) > 2 and not line.startswith('**'):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            cap = line[1:-1]
            html_parts.append(f'<p class="caption">{render_inline(cap)}</p>')
        elif line.strip() == '':
            if in_list:
                html_parts.append('</ul>')
                in_list = False
        else:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<p>{render_inline(line)}</p>')
        i += 1

    if in_list:
        html_parts.append('</ul>')

    body = '\n'.join(html_parts)
    title = md_path.stem
    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>{CSS}</style>
</head>
<body>
{body}
</body>
</html>
'''


def main():
    print('=== MD → HTML (base64 인라인) ===\n')
    for topic, idx in TOPICS:
        md_path = BASE / f'연구개발-{idx}-{topic}.md'
        if not md_path.exists():
            print(f'  ⚠️ 없음: {md_path.name}')
            continue
        print(f'[{idx}] {topic} 변환 중...')
        html = convert_md_to_html(md_path, topic)
        out_path = OUT / f'연구개발-{idx}-{topic}.html'
        out_path.write_text(html, encoding='utf-8')
        size_mb = out_path.stat().st_size / 1024 / 1024
        print(f'  ✓ {out_path.name} ({size_mb:.2f} MB)\n')


if __name__ == '__main__':
    main()
