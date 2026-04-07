# -*- coding: utf-8 -*-
"""
1. .figure div 내 이미지를 '별도 첨부' 표시로 교체 (헤더/로고 유지)
2. '그림 1-1 전면부' 이미지를 추출해서 마지막 페이지에 원본 이미지로 삽입
"""
from bs4 import BeautifulSoup
import re, base64

src = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'

with open(src, 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

# ── 1. 그림 1-1 전면부 이미지 추출 ─────────────────────────────
front_img_src = None
for caption in soup.find_all('div', class_='figure-caption'):
    if '1-1' in caption.get_text() and '전면부' in caption.get_text():
        # 캡션 앞 형제 또는 부모 figure div 내 img 탐색
        figure_div = caption.find_parent('div', class_='figure') or caption.parent
        img = figure_div.find('img') if figure_div else None
        if img and img.get('src','').startswith('data:image'):
            front_img_src = img.get('src')
            print("그림 1-1 전면부 이미지 발견. 크기:", round(len(front_img_src)*0.75/1024), "KB")
            break

if not front_img_src:
    print("경고: 그림 1-1 전면부 이미지를 찾지 못했습니다.")

# ── 2. .figure 내 이미지 → 별도 첨부 표시로 교체 ──────────────
# 보호 대상: page-header, cover-logo, back-cover, toc
protected = set()
for sel in ['page-header', 'cover-logo', 'back-cover', 'toc-list']:
    for div in soup.find_all(class_=sel):
        for img in div.find_all('img'):
            protected.add(id(img))

# .figure div 안의 이미지만 교체
count = 0
for fig_div in soup.find_all('div', class_='figure'):
    for img in fig_div.find_all('img'):
        if id(img) in protected:
            continue
        src_val = img.get('src', '')
        if not src_val.startswith('data:image'):
            continue
        count += 1
        size_kb = round(len(src_val)*0.75/1024)

        # 캡션 텍스트 찾기
        caption_el = fig_div.find('div', class_='figure-caption')
        caption_text = caption_el.get_text(strip=True) if caption_el else f'그림 {count}'

        placeholder = soup.new_tag('div')
        placeholder['style'] = (
            'border:2px dashed #bbb; border-radius:6px; padding:16px; '
            'text-align:center; color:#888; background:#f9f9f9; '
            'margin:8px 0; font-size:9pt;'
        )
        placeholder.string = f'📎 {caption_text} — 원본 파일 별도 첨부 (약 {size_kb}KB)'
        img.replace_with(placeholder)

print(f'.figure 이미지 {count}개 → 첨부 표시로 교체 완료')

# ── 3. 마지막 페이지에 전면부 이미지 삽입 ──────────────────────
if front_img_src:
    # back-cover가 있는 페이지를 찾아 그 바로 앞에 새 페이지 삽입
    back_cover = soup.find('div', class_='back-cover')
    if back_cover:
        back_page = back_cover.find_parent('div', class_='page') or back_cover.parent

        new_page = soup.new_tag('div', attrs={'class': 'page'})

        # 헤더 복사 (기존 마지막 일반 페이지에서)
        all_pages = soup.find_all('div', class_='page')
        last_regular = None
        for p in reversed(all_pages):
            if not p.find('div', class_='back-cover') and p.find('div', class_='page-header'):
                last_regular = p
                break
        if last_regular:
            hdr = last_regular.find('div', class_='page-header')
            if hdr:
                new_page.append(hdr.__copy__() if hasattr(hdr,'__copy__') else BeautifulSoup(str(hdr), 'html.parser').find())

        # 본문
        body_div = soup.new_tag('div', attrs={'class': 'page-body'})

        title = soup.new_tag('h2', attrs={'class': 'section'})
        title.string = '참고: 장비 외관 전면부'
        body_div.append(title)

        fig = soup.new_tag('div', attrs={'class': 'figure'})
        real_img = soup.new_tag('img')
        real_img['src'] = front_img_src
        real_img['style'] = 'max-width:100%; max-height:200mm; display:block; margin:0 auto; border:1px solid #ddd;'
        real_img['alt'] = '장비 외관 전면부'
        fig.append(real_img)

        cap = soup.new_tag('div', attrs={'class': 'figure-caption'})
        cap.string = '그림 참고-1 장비 외관 전면부 (원본 이미지)'
        fig.append(cap)
        body_div.append(fig)

        new_page.append(body_div)

        back_page.insert_before(new_page)
        print("마지막 페이지에 전면부 원본 이미지 삽입 완료")

# ── 4. 저장 ────────────────────────────────────────────────────
with open(src, 'w', encoding='utf-8') as f:
    f.write(str(soup))
print("저장 완료")
