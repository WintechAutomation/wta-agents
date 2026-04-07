# -*- coding: utf-8 -*-
"""
2.3 부착 경고 표시 섹션의 notice-icon을 위험 유형별 SVG로 교체
다른 섹션의 이미지는 일절 건드리지 않음
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from bs4 import BeautifulSoup
import base64, re

HTML_PATH = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'

# ── 위험 유형별 SVG 정의 ──────────────────────────────────────────
def make_b64_svg(svg_content):
    encoded = base64.b64encode(svg_content.encode('utf-8')).decode('ascii')
    return f'data:image/svg+xml;base64,{encoded}'

# 1. 전기 위험 — 빨간 삼각형 + 번개 볼트
svg_electric = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <polygon points="50,6 96,90 4,90" fill="#DC3545" stroke="#A71D2A" stroke-width="3" stroke-linejoin="round"/>
  <polygon points="50,6 96,90 4,90" fill="none" stroke="white" stroke-width="1.5" stroke-linejoin="round" opacity="0.3"/>
  <!-- 번개 볼트 -->
  <polygon points="54,22 40,55 52,55 46,80 62,47 50,47 58,22" fill="white"/>
</svg>'''

# 2. 끼임/말림 위험 — 노란 삼각형 + 기어에 손 끼임 기호
svg_entangle = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <polygon points="50,6 96,90 4,90" fill="#FFC107" stroke="#D4A017" stroke-width="3" stroke-linejoin="round"/>
  <polygon points="50,6 96,90 4,90" fill="none" stroke="white" stroke-width="1.5" stroke-linejoin="round" opacity="0.3"/>
  <!-- 기어 (끼임 심볼) -->
  <g transform="translate(50,62) scale(0.55)">
    <!-- 기어 바깥 톱니 -->
    <circle cx="0" cy="0" r="18" fill="none" stroke="black" stroke-width="4"/>
    <circle cx="0" cy="0" r="8" fill="black"/>
    <!-- 기어 톱니 8개 -->
    <rect x="-4" y="-26" width="8" height="10" fill="black" rx="1"/>
    <rect x="-4" y="16" width="8" height="10" fill="black" rx="1"/>
    <rect x="16" y="-4" width="10" height="8" fill="black" rx="1"/>
    <rect x="-26" y="-4" width="10" height="8" fill="black" rx="1"/>
    <rect x="9" y="-24" width="8" height="10" fill="black" rx="1" transform="rotate(45,13,-19)"/>
    <rect x="-17" y="-24" width="8" height="10" fill="black" rx="1" transform="rotate(-45,-13,-19)"/>
    <rect x="9" y="14" width="8" height="10" fill="black" rx="1" transform="rotate(-45,13,19)"/>
    <rect x="-17" y="14" width="8" height="10" fill="black" rx="1" transform="rotate(45,-13,19)"/>
  </g>
  <!-- 손 (기어 방향으로 향하는) -->
  <path d="M30,48 Q28,42 32,38 L40,35 Q44,34 44,38 L44,55" fill="none" stroke="black" stroke-width="3" stroke-linecap="round"/>
  <!-- 화살표 (끼임 방향) -->
  <line x1="42" y1="50" x2="50" y2="56" stroke="black" stroke-width="2.5" stroke-linecap="round"/>
</svg>'''

# 3. 충돌 위험 — 노란 삼각형 + 충돌 화살표 (사람 + 장애물 충돌)
svg_collision = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <polygon points="50,6 96,90 4,90" fill="#FFC107" stroke="#D4A017" stroke-width="3" stroke-linejoin="round"/>
  <polygon points="50,6 96,90 4,90" fill="none" stroke="white" stroke-width="1.5" stroke-linejoin="round" opacity="0.3"/>
  <!-- 사람 -->
  <circle cx="34" cy="42" r="6" fill="black"/>
  <line x1="34" y1="48" x2="34" y2="66" stroke="black" stroke-width="3.5" stroke-linecap="round"/>
  <line x1="34" y1="54" x2="26" y2="62" stroke="black" stroke-width="3" stroke-linecap="round"/>
  <line x1="34" y1="54" x2="42" y2="62" stroke="black" stroke-width="3" stroke-linecap="round"/>
  <line x1="34" y1="66" x2="28" y2="76" stroke="black" stroke-width="3" stroke-linecap="round"/>
  <line x1="34" y1="66" x2="40" y2="76" stroke="black" stroke-width="3" stroke-linecap="round"/>
  <!-- 충돌 화살표 -->
  <line x1="44" y1="54" x2="56" y2="54" stroke="black" stroke-width="3" stroke-linecap="round"/>
  <polygon points="56,49 66,54 56,59" fill="black"/>
  <!-- 장애물 (기계 블록) -->
  <rect x="66" y="44" width="18" height="22" rx="2" fill="black"/>
  <!-- 충돌 별표 -->
  <text x="58" y="45" font-size="14" fill="black" font-weight="bold">✦</text>
</svg>'''

# 4. 도어 인터록 — 노란 삼각형 + 도어 열림 금지
svg_door = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <polygon points="50,6 96,90 4,90" fill="#FFC107" stroke="#D4A017" stroke-width="3" stroke-linejoin="round"/>
  <polygon points="50,6 96,90 4,90" fill="none" stroke="white" stroke-width="1.5" stroke-linejoin="round" opacity="0.3"/>
  <!-- 도어 프레임 -->
  <rect x="33" y="38" width="22" height="36" rx="2" fill="none" stroke="black" stroke-width="3"/>
  <!-- 도어 패널 (열린 상태) -->
  <path d="M33,38 L24,42 L24,78 L33,74 Z" fill="#555" stroke="black" stroke-width="2"/>
  <!-- 경첩 -->
  <circle cx="33" cy="44" r="2" fill="white"/>
  <circle cx="33" cy="72" r="2" fill="white"/>
  <!-- 도어 손잡이 -->
  <circle cx="52" cy="58" r="3" fill="black"/>
  <!-- 금지 X 표시 -->
  <line x1="30" y1="44" x2="60" y2="74" stroke="#DC3545" stroke-width="5" stroke-linecap="round"/>
  <line x1="60" y1="44" x2="30" y2="74" stroke="#DC3545" stroke-width="5" stroke-linecap="round"/>
</svg>'''

icon_map = {
    '전기 위험': make_b64_svg(svg_electric),
    '끼임/말림 위험': make_b64_svg(svg_entangle),
    '충돌 위험': make_b64_svg(svg_collision),
    '도어 인터록 운전 중': make_b64_svg(svg_door),
}

# ── HTML 파싱 ──────────────────────────────────────────────────────
with open(HTML_PATH, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

# 2.3 섹션 범위 찾기
section_start = None
for h in soup.find_all(['h2', 'h3']):
    if '2.3' in h.get_text():
        section_start = h
        break

if not section_start:
    print("2.3 섹션을 찾을 수 없습니다.")
    sys.exit(1)

# 2.3 섹션 내의 notice div들만 수집 (2.4 이전까지)
target_notices = []
sib = section_start.find_next_sibling()
while sib:
    text = sib.get_text(strip=True)
    if sib.name in ['h2', 'h3'] and re.search(r'2\.[4-9]|3\.', sib.get_text()):
        break
    if sib.name == 'div' and 'notice' in sib.get('class', []):
        title_el = sib.find(class_='notice-title')
        if title_el:
            title = title_el.get_text(strip=True)
            target_notices.append((sib, title))
    sib = sib.find_next_sibling()

print(f"2.3 섹션 notice 박스: {len(target_notices)}개")

replaced = 0
for div, title in target_notices:
    new_src = icon_map.get(title)
    if not new_src:
        print(f"  [스킵] '{title}' — 매핑 없음")
        continue

    icon_img = div.find('img', class_='notice-icon')
    if icon_img:
        icon_img['src'] = new_src
        icon_img['alt'] = title
        replaced += 1
        print(f"  [{replaced}] '{title}' 아이콘 교체 완료")
    else:
        print(f"  [없음] '{title}' — notice-icon img 태그 없음")

print(f"\n총 {replaced}개 아이콘 교체 완료")

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(str(soup))

import os
size_mb = round(os.path.getsize(HTML_PATH) / 1024 / 1024, 1)
print(f"저장 완료 ({size_mb}MB)")
