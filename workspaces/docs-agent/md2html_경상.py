# -*- coding: utf-8 -*-
"""경상연구개발 v2 md → 단일 HTML (base64 이미지 임베드)"""
import sys, io, os, re, base64, mimetypes
import markdown

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = r'C:\MES\wta-agents\reports\MAX\경상연구개발\재작성-v2'
IMG_BASE = r'C:\MES\wta-agents\reports\MAX\경상연구개발\참고문서-이미지'

TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  body {{ font-family:'Malgun Gothic','Pretendard Variable',sans-serif; max-width:960px; margin:0 auto; padding:28px; line-height:1.75; color:#222; background:#fafbfc; }}
  h1 {{ color:#1a237e; border-bottom:3px solid #4472C4; padding-bottom:10px; font-size:24px; }}
  h2 {{ color:#1a237e; margin-top:32px; font-size:19px; border-left:4px solid #4472C4; padding-left:10px; }}
  h3 {{ color:#2c3e50; margin-top:24px; font-size:16px; }}
  h4 {{ color:#4472C4; font-size:14px; }}
  p, li {{ font-size:14px; }}
  table {{ border-collapse:collapse; margin:12px 0; font-size:13px; width:100%; }}
  th, td {{ border:1px solid #d0d7de; padding:8px 10px; text-align:left; }}
  th {{ background:#e8eaf6; color:#1a237e; }}
  img {{ max-width:100%; border:1px solid #e0e0e0; border-radius:6px; margin:10px 0; box-shadow:0 2px 6px rgba(0,0,0,0.05); }}
  blockquote {{ border-left:4px solid #4472C4; margin:12px 0; padding:8px 14px; background:#f0f4f8; color:#333; }}
  code {{ background:#f1f3f5; padding:2px 6px; border-radius:3px; font-size:12px; }}
  hr {{ border:none; border-top:1px dashed #bbb; margin:24px 0; }}
  .header-box {{ background:linear-gradient(135deg,#4472C4 0%,#1a237e 100%); color:#fff; padding:18px 24px; border-radius:10px; margin-bottom:20px; }}
  .header-box h1 {{ color:#fff; border:none; margin:0; }}
  .header-box .meta {{ font-size:12px; opacity:0.9; margin-top:6px; }}
  footer {{ text-align:center; color:#999; font-size:11px; margin-top:32px; padding:12px; border-top:1px solid #e0e0e0; }}
</style>
</head>
<body>
<div class="header-box">
  <h1>{title}</h1>
  <div class="meta">(주)윈텍오토메이션 생산관리팀 AI운영팀 · CONFIDENTIAL · 2026-04-11</div>
</div>
{body}
<footer>경상연구개발 재작성-v2 · Confluence 원문 기반 · docs-agent/research-agent 공동 작성</footer>
</body>
</html>
"""

def embed_images(html, task_folder):
    """<img src="../../참고문서-이미지/..." → base64 data URI"""
    def repl(m):
        src = m.group(1)
        # 상대경로 해석
        abs_path = os.path.normpath(os.path.join(BASE, task_folder, src))
        if not os.path.exists(abs_path):
            # fallback: basename 기준 IMG_BASE/task_folder/에서 검색
            fallback = os.path.join(IMG_BASE, task_folder, os.path.basename(src))
            if os.path.exists(fallback):
                abs_path = fallback
            else:
                print(f'  [missing] {abs_path}')
                return m.group(0)
        with open(abs_path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('ascii')
        mime, _ = mimetypes.guess_type(abs_path)
        mime = mime or 'image/png'
        return f'src="data:{mime};base64,{data}"'
    return re.sub(r'src="([^"]+\.(?:png|jpg|jpeg|gif))"', repl, html)

def convert(task_folder, fname, title):
    md_path = os.path.join(BASE, task_folder, fname)
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()
    html_body = markdown.markdown(md_text, extensions=['tables','fenced_code'])
    html_body = embed_images(html_body, task_folder)
    full = TEMPLATE.format(title=title, body=html_body)
    out_path = md_path.replace('.md', '.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(full)
    size_kb = os.path.getsize(out_path) / 1024
    print(f'✓ {task_folder}/{fname.replace(".md",".html")} ({size_kb:.0f} KB)')
    return out_path

tasks = [
    ('1-장비물류', '개발보고서.md', '[경상연구개발 #1] 장비물류 개발보고서'),
    ('1-장비물류', '연구일지.md', '[경상연구개발 #1] 장비물류 연구일지'),
    ('5-호닝신뢰성', '개발보고서.md', '[경상연구개발 #5] 호닝신뢰성 개발보고서'),
    ('5-호닝신뢰성', '연구일지.md', '[경상연구개발 #5] 호닝신뢰성 연구일지'),
]
outputs = []
for folder, fn, title in tasks:
    outputs.append(convert(folder, fn, title))

print()
print('outputs:')
for p in outputs:
    print(' ', p)
