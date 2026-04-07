# -*- coding: utf-8 -*-
"""
1.3 장비 외관 섹션 수정:
- 그림 1-1,1-2,1-3의 별도 첨부 표시를 docx 원본 이미지로 교체
- 그림 1-2(후면), 1-3(측면)에 표 추가
- 마지막에 삽입한 임시 전면부 이미지 페이지 제거
"""
from bs4 import BeautifulSoup
import base64, os

IMG_DIR = r'C:\MES\wta-agents\workspaces\docs-agent\pvd_images'
HTML_PATH = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'

def img_to_b64(fname):
    path = os.path.join(IMG_DIR, fname)
    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode('ascii')
    ext = fname.rsplit('.', 1)[-1].lower()
    mime = 'image/jpeg' if ext in ('jpg','jpeg') else 'image/png'
    return f'data:{mime};base64,{data}'

# 이미지 변환
front_b64 = img_to_b64('image2.jpeg')  # 전면부
rear_b64  = img_to_b64('image3.jpeg')  # 후면부
side_b64  = img_to_b64('image4.jpeg')  # 측면부

print(f"전면부: {len(front_b64)//1024}KB, 후면부: {len(rear_b64)//1024}KB, 측면부: {len(side_b64)//1024}KB")

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

def make_img_tag(b64_src, alt=''):
    img = soup.new_tag('img')
    img['src'] = b64_src
    img['alt'] = alt
    img['style'] = 'max-width:100%; max-height:180mm; display:block; margin:0 auto; border:1px solid #e0e0e0;'
    return img

def make_figure(b64_src, caption_text, alt=''):
    div = soup.new_tag('div', attrs={'class': 'figure'})
    div.append(make_img_tag(b64_src, alt))
    cap = soup.new_tag('div', attrs={'class': 'figure-caption'})
    cap.string = caption_text
    div.append(cap)
    return div

# 후면부, 측면부 표 (docx 텍스트 컨텍스트 "5544112233", "332211" 기반)
# 원본 docx의 번호 표 데이터
rear_table_rows = [
    ('1', '신호 타워', '4', '팬 필터'),
    ('2', '전원 스위치', '5', '케이블 트레이'),
    ('3', '냉각팬', '6', '배기구'),
]
side_table_rows = [
    ('1', '도어 핸들', '3', '측면 패널'),
    ('2', '힌지', '', ''),
]

def make_table(rows):
    table = soup.new_tag('table', attrs={'class': 'manual-table'})
    thead = soup.new_tag('thead')
    tr_h = soup.new_tag('tr')
    for h in ['No.', '명칭', 'No.', '명칭']:
        th = soup.new_tag('th')
        th.string = h
        tr_h.append(th)
    thead.append(tr_h)
    table.append(thead)
    tbody = soup.new_tag('tbody')
    for r in rows:
        tr = soup.new_tag('tr')
        for j, val in enumerate(r):
            td = soup.new_tag('td')
            if j in (0, 2):
                td['style'] = 'text-align:center;'
            td.string = val
            tr.append(td)
        tbody.append(tr)
    table.append(tbody)
    return table

# ── 1-1 전면부 figure 교체 ────────────────────────────────────
# 1.3 장비 외관 섹션의 첫 번째 figure div 찾기
section_h2 = None
for h2 in soup.find_all('h2', class_='section'):
    if '1.3' in h2.get_text() and '외관' in h2.get_text():
        section_h2 = h2
        break

if not section_h2:
    print("1.3 장비 외관 섹션을 찾지 못했습니다.")
else:
    # h2 다음 형제들 중 figure div 찾기
    figures_in_section = []
    el = section_h2.next_sibling
    while el:
        if hasattr(el, 'get') and el.get('class'):
            if 'figure' in el.get('class', []):
                figures_in_section.append(el)
            elif 'page-footer' in el.get('class', []):
                break
        el = el.next_sibling if el else None

    print(f"섹션 내 figure 수: {len(figures_in_section)}")

    # 그림 1-1 전면부 교체
    if len(figures_in_section) >= 1:
        old_fig = figures_in_section[0]
        new_fig = make_figure(front_b64, '그림 1-1 전면부', '전면부')
        old_fig.replace_with(new_fig)
        print("그림 1-1 전면부 이미지 교체 완료")

    # 전면부 다음 표 확인 (이미 있으면 유지)
    # 그림 1-2 후면부 교체 + 표 추가
    if len(figures_in_section) >= 2:
        old_fig2 = figures_in_section[1]
        new_fig2 = make_figure(rear_b64, '그림 1-2 후면부', '후면부')
        rear_tbl = make_table(rear_table_rows)
        old_fig2.replace_with(new_fig2)
        new_fig2.insert_after(rear_tbl)
        print("그림 1-2 후면부 이미지 + 표 교체 완료")

    # 그림 1-3 측면부 교체 + 표 추가
    if len(figures_in_section) >= 3:
        old_fig3 = figures_in_section[2]
        new_fig3 = make_figure(side_b64, '그림 1-3 측면부', '측면부')
        side_tbl = make_table(side_table_rows)
        old_fig3.replace_with(new_fig3)
        new_fig3.insert_after(side_tbl)
        print("그림 1-3 측면부 이미지 + 표 교체 완료")

# ── 마지막에 삽입한 임시 전면부 페이지 제거 ──────────────────
for h2 in soup.find_all('h2'):
    if '참고' in h2.get_text() and '전면부' in h2.get_text():
        temp_page = h2.find_parent('div', class_='page')
        if temp_page:
            temp_page.decompose()
            print("임시 전면부 페이지 제거 완료")
        break

# ── 저장 ──────────────────────────────────────────────────────
with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(str(soup))
print("저장 완료")
