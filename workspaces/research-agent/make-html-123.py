import os, glob, re

def make_html(subject_name, subject_title, md_folder, img_folder, output_path, img_rel_path):
    # 1. MD 파일들 읽기 (page ID 순서로 정렬)
    md_files = sorted(glob.glob(os.path.join(md_folder, 'page-*-content.md')))

    # 2. pages.json에서 페이지 제목 매핑
    import json
    pages_meta = {}
    pages_json = os.path.join(md_folder, 'pages.json')
    if os.path.exists(pages_json):
        raw = json.load(open(pages_json, encoding='utf-8'))
        # pages.json 형식이 배열인 경우와 {pages: [...]} 객체인 경우 모두 처리
        pages_data = raw if isinstance(raw, list) else raw.get('pages', [])
        for p in pages_data:
            pages_meta[str(p.get('pageId', p.get('id', '')))] = p

    # 3. 이미지 파일 목록
    img_files = sorted(glob.glob(os.path.join(img_folder, 'p*-img*.png')) +
                       glob.glob(os.path.join(img_folder, 'p*-img*.jpg')))

    # 4. 이미지를 페이지ID별로 그룹핑
    img_by_page = {}
    for img in img_files:
        fname = os.path.basename(img)
        # 파일명 형식: p{pageId}-img{NNN}-{original}.png
        m = re.match(r'p(\d+)-img(\d+)', fname)
        if m:
            pid = m.group(1)
            if pid not in img_by_page:
                img_by_page[pid] = []
            img_by_page[pid].append(fname)

    # 5. HTML 생성
    sections = []
    for md_file in md_files:
        # 페이지 ID 추출
        pid = re.search(r'page-(\d+)-content', os.path.basename(md_file))
        pid = pid.group(1) if pid else 'unknown'

        # MD 내용 읽기
        content = open(md_file, encoding='utf-8').read()

        # blob: URL 이미지 참조 제거 (실제 이미지는 아래 갤러리로 표시)
        content = re.sub(r'!\[.*?\]\(blob:.*?\)', '[이미지]', content)

        # 페이지 메타
        meta = pages_meta.get(pid, {})
        page_title = meta.get('title', f'페이지 {pid}')
        page_url = meta.get('url', f'https://iwta.atlassian.net/wiki/spaces/...pages/{pid}')

        # 이미지 갤러리
        gallery = ''
        if pid in img_by_page:
            gallery = '<div class="img-gallery">'
            for img_fname in img_by_page[pid]:
                gallery += f'<figure><img src="{img_rel_path}/{img_fname}" loading="lazy" alt="{img_fname}"><figcaption>{img_fname}</figcaption></figure>'
            gallery += '</div>'

        # Markdown을 간단한 HTML로 변환 (기본 변환)
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
  <div class="page-meta">
    <a href="{page_url}" target="_blank">🔗 원본 보기</a>
    &nbsp;|&nbsp; 페이지 ID: {pid}
  </div>
  <div class="page-body">{html_content}</div>
  {gallery}
</div>'''
        sections.append(section)

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{subject_title} — 참고문서</title>
<style>
  body {{ font-family: 'Malgun Gothic', sans-serif; max-width: 1200px; margin: 0 auto; padding: 24px; color: #172B4D; }}
  h1 {{ font-size: 22px; color: #0052CC; border-bottom: 3px solid #0052CC; padding-bottom: 10px; }}
  .page-section {{ border: 1px solid #DFE1E6; border-radius: 6px; margin: 28px 0; padding: 24px; }}
  .page-title {{ font-size: 18px; color: #0052CC; margin-top: 0; border-left: 4px solid #0065FF; padding-left: 10px; }}
  .page-h1 {{ font-size: 18px; color: #253858; }}
  .page-meta {{ font-size: 12px; color: #6B778C; margin-bottom: 16px; }}
  .page-meta a {{ color: #0065FF; text-decoration: none; }}
  .page-body {{ font-size: 14px; line-height: 1.7; }}
  .page-body code {{ background: #F4F5F7; padding: 2px 6px; border-radius: 3px; font-size: 12px; }}
  .img-gallery {{ margin-top: 20px; border-top: 1px solid #DFE1E6; padding-top: 16px; }}
  .img-gallery h3 {{ font-size: 14px; color: #6B778C; margin-bottom: 12px; }}
  figure {{ display: inline-block; margin: 8px; vertical-align: top; max-width: 350px; }}
  figure img {{ max-width: 100%; border: 1px solid #DFE1E6; border-radius: 4px; cursor: zoom-in; }}
  figure figcaption {{ font-size: 11px; color: #6B778C; text-align: center; margin-top: 4px; }}
  strong {{ color: #172B4D; }}
</style>
</head>
<body>
<h1>과제 {subject_name} 참고문서</h1>
<p style="color:#6B778C;font-size:14px;">생성일: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')} | 수집 페이지: {len(md_files)}개</p>
{''.join(sections)}
</body>
</html>'''

    open(output_path, 'w', encoding='utf-8').write(html)
    print(f'생성 완료: {output_path}')

# 실행
base = 'C:/MES/wta-agents/reports/MAX/경상연구개발'

make_html('① 장비물류', '① 장비 무인화운영을 위한 장비 물류 개발',
    f'{base}/참고문서-원본/1-장비물류',
    f'{base}/참고문서-이미지/1-장비물류',
    f'{base}/참고문서-원본/1-장비물류/index.html',
    '../../../참고문서-이미지/1-장비물류')

make_html('② 분말검사', '② 프레스성형 품질향상을 위한 분말성형체 검사기술 개발',
    f'{base}/참고문서-원본/2-분말검사',
    f'{base}/참고문서-이미지/2-분말검사',
    f'{base}/참고문서-원본/2-분말검사/index.html',
    '../../../참고문서-이미지/2-분말검사')

make_html('③ 연삭측정제어', '③ 정밀 연삭 가공을 위한 측정 제어장치 및 그 제어방법',
    f'{base}/참고문서-원본/3-연삭측정제어',
    f'{base}/참고문서-이미지/3-연삭측정제어',
    f'{base}/참고문서-원본/3-연삭측정제어/index.html',
    '../../../참고문서-이미지/3-연삭측정제어')

print('과제①②③ HTML 생성 완료')
