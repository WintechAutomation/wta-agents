import sys, io, re, os, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

files = glob.glob('C:/MES/wta-agents/reports/MAX/*.html')
modified = []

for fpath in files:
    with open(fpath, 'r', encoding='utf-8') as f:
        html = f.read()

    if 'ppt-btn' not in html:
        continue

    fname = os.path.basename(fpath).replace('.html', '')
    abs_path = fpath.replace('/', '\\\\')

    # Build the new button+script block
    new_bar = f'''<div class="ppt-bar">
  <button class="ppt-btn" onclick="downloadPptx()">PPT 다운로드</button>
</div>
<script>
function downloadPptx(){{
  const btn=document.querySelector('.ppt-btn');
  btn.textContent='변환 중...';btn.disabled=true;
  fetch('/api/convert/html-to-pptx',{{
    method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{html_path:'{abs_path}'}})
  }})
  .then(r=>{{if(!r.ok)throw new Error(r.statusText);return r.blob()}})
  .then(blob=>{{
    const a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download='{fname}.pptx';
    a.click();URL.revokeObjectURL(a.href);
    btn.textContent='PPT 다운로드';btn.disabled=false;
  }})
  .catch(e=>{{
    alert('PPTX 변환 실패: '+e.message);
    btn.textContent='PPT 다운로드';btn.disabled=false;
  }});
}}
</script>'''

    # Replace patterns: <div class="ppt-bar">...<a ...>...</a>\n</div>
    # Also handle <button> variant
    pattern = r'<div class="ppt-bar">\s*<(?:a|button)[^>]*class="ppt-btn"[^>]*>.*?</(?:a|button)>\s*</div>'
    new_html, count = re.subn(pattern, lambda m: new_bar, html, flags=re.DOTALL)

    if count > 0:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(new_html)
        modified.append(fname)
        print(f'  수정: {fname}.html')
    else:
        print(f'  패턴 미매칭: {fname}.html')

print(f'\n총 {len(modified)}개 파일 수정 완료')
