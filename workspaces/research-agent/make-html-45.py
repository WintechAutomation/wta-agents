import os, glob, re, json
from datetime import datetime

def make_html(subject_name, subject_title, md_folder, img_folder, output_path, img_rel_path):
    md_files = sorted(glob.glob(os.path.join(md_folder, 'page-*-content.md')))

    pages_meta = {}
    pages_json = os.path.join(md_folder, 'pages.json')
    if os.path.exists(pages_json):
        raw = json.load(open(pages_json, encoding='utf-8'))
        # pages.json이 dict 래퍼인 경우와 list인 경우 모두 처리
        if isinstance(raw, dict):
            pages_data = raw.get('pages', [])
        else:
            pages_data = raw
        for p in pages_data:
            if not isinstance(p, dict):
                continue
            pid = str(p.get('pageId', p.get('id', '')))
            pages_meta[pid] = p

    img_files = sorted(glob.glob(os.path.join(img_folder, 'p*-img*.png')) +
                       glob.glob(os.path.join(img_folder, 'p*-img*.jpg')))

    img_by_page = {}
    for img in img_files:
        fname = os.path.basename(img)
        m = re.match(r'p(\d+)-img(\d+)', fname)
        if m:
            pid = m.group(1)
            if pid not in img_by_page:
                img_by_page[pid] = []
            img_by_page[pid].append(fname)

    sections = []
    for md_file in md_files:
        pid = re.search(r'page-(\d+)-content', os.path.basename(md_file))
        pid = pid.group(1) if pid else 'unknown'

        content = open(md_file, encoding='utf-8').read()
        content = re.sub(r'!\[.*?\]\(blob:.*?\)', '[이미지]', content)

        meta = pages_meta.get(pid, {})
        page_title = meta.get('title', f'페이지 {pid}')
        page_url = meta.get('url', f'https://iwta.atlassian.net/wiki/spaces/...pages/{pid}')

        # 이미지 갤러리 (이미지 많으면 그리드로)
        gallery = ''
        if pid in img_by_page:
            imgs = img_by_page[pid]
            gallery = f'<div class="img-gallery"><p class="gallery-header">📷 첨부 이미지 {len(imgs)}개</p>'
            for img_fname in imgs:
                gallery += f'<figure><img src="{img_rel_path}/{img_fname}" loading="lazy" alt="{img_fname}"><figcaption>{img_fname}</figcaption></figure>'
            gallery += '</div>'

        html_content = content
        html_content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'^# (.+)$', r'<h2 class="page-h1">\1</h2>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)
        html_content = re.sub(r'`(.+?)`', r'<code>\1</code>', html_content)
        html_content = '<p>' + re.sub(r'\n\n+', '</p><p>', html_content.strip()) + '</p>'
        html_content = re.sub(r'\n', '<br>', html_content)

        section = f'''
<div class="page-section">
  <h2 class="page-title">{page_title}</h2>
  <div class="page-meta"><a href="{page_url}" target="_blank">🔗 원본 보기</a> &nbsp;|&nbsp; 페이지 ID: {pid}</div>
  <div class="page-body">{html_content}</div>
  {gallery}
</div>'''
        sections.append(section)

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>{subject_title} — 참고문서</title>
<style>
  body {{ font-family: "Malgun Gothic", sans-serif; max-width: 1200px; margin: 0 auto; padding: 24px; color: #172B4D; }}
  h1 {{ font-size: 22px; color: #0052CC; border-bottom: 3px solid #0052CC; padding-bottom: 10px; }}
  .page-section {{ border: 1px solid #DFE1E6; border-radius: 6px; margin: 28px 0; padding: 24px; }}
  .page-title {{ font-size: 18px; color: #0052CC; margin-top: 0; border-left: 4px solid #0065FF; padding-left: 10px; }}
  .page-meta {{ font-size: 12px; color: #6B778C; margin-bottom: 16px; }}
  .page-meta a {{ color: #0065FF; text-decoration: none; }}
  .page-body {{ font-size: 14px; line-height: 1.7; }}
  .page-body code {{ background: #F4F5F7; padding: 2px 6px; border-radius: 3px; font-size: 12px; }}
  .img-gallery {{ margin-top: 20px; border-top: 1px solid #DFE1E6; padding-top: 16px; }}
  .gallery-header {{ font-size: 13px; color: #6B778C; margin-bottom: 12px; }}
  figure {{ display: inline-block; margin: 8px; vertical-align: top; max-width: 320px; }}
  figure img {{ max-width: 100%; border: 1px solid #DFE1E6; border-radius: 4px; }}
  figure figcaption {{ font-size: 11px; color: #6B778C; text-align: center; margin-top: 4px; }}
</style>
</head>
<body>
<h1>과제 {subject_name} 참고문서</h1>
<p style="color:#6B778C;font-size:14px;">생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 수집 페이지: {len(md_files)}개</p>
{"".join(sections)}
</body>
</html>'''

    open(output_path, 'w', encoding='utf-8').write(html)
    sz = os.path.getsize(output_path) // 1024
    print(f'생성 완료: {output_path} ({sz}KB)')

base = 'C:/MES/wta-agents/reports/MAX/경상연구개발'

make_html('④ 포장혼입검사', '④ 인서트 포장기 혼입검사기술 개발',
    f'{base}/참고문서-원본/4-포장혼입검사',
    f'{base}/참고문서-이미지/4-포장혼입검사',
    f'{base}/참고문서-원본/4-포장혼입검사/index.html',
    '../../../참고문서-이미지/4-포장혼입검사')

make_html('⑤ 호닝신뢰성', '⑤ 정밀 광학계 기반 호닝형상검사기의 신뢰성 확보 기술 연구',
    f'{base}/참고문서-원본/5-호닝신뢰성',
    f'{base}/참고문서-이미지/5-호닝신뢰성',
    f'{base}/참고문서-원본/5-호닝신뢰성/index.html',
    '../../../참고문서-이미지/5-호닝신뢰성')

print('과제④⑤ HTML 생성 완료')
