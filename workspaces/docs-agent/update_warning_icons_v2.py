# -*- coding: utf-8 -*-
"""
2.3 부착 경고 표시 — ISO 7010 스타일 고품질 SVG
- 그림이 삼각형 밖으로 나가지 않도록 좌표 + evenodd 마스크 이중 처리
- 사이즈 160x160 (좀 더 크게)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from bs4 import BeautifulSoup
import base64, re

HTML_PATH = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'

def b64(svg): return 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode('utf-8')).decode('ascii')

# 공통: 160x160 viewBox, 삼각형 points="80,10 154,146 6,146"
# 내부 안전 영역: x 25~135, y 50~136 (삼각형 내접원 ~r42, 중심 80,100 근처)
# 삼각형 외부 흰색 마스크(evenodd)로 덮기

TRI = "80,10 154,146 6,146"

def wrap_svg(inner, extra_defs=""):
    """삼각형 + 내용 + 외부 마스크"""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160">
  <defs>
    <clipPath id="c">
      <polygon points="{TRI}"/>
    </clipPath>
    {extra_defs}
  </defs>
  <!-- 삼각형 배경 -->
  <polygon points="{TRI}" fill="#FFC107" stroke="#CC8800" stroke-width="4" stroke-linejoin="round"/>
  <!-- 안쪽 흰 테두리 -->
  <polygon points="{TRI}" fill="none" stroke="white" stroke-width="2" opacity="0.4" stroke-linejoin="round"/>
  <!-- 내용 (clipPath로 잘림 보장) -->
  <g clip-path="url(#c)">
    {inner}
  </g>
  <!-- evenodd 마스크: 삼각형 외부를 페이지 배경색(흰)으로 덮음 -->
  <path fill-rule="evenodd" fill="white"
        d="M0,0 H160 V160 H0 Z M{TRI.replace(' ','  ')} Z" opacity="1"/>
  <!-- 삼각형 테두리 재그리기 (마스크에 가려지지 않게) -->
  <polygon points="{TRI}" fill="none" stroke="#CC8800" stroke-width="4" stroke-linejoin="round"/>
  <polygon points="{TRI}" fill="none" stroke="white" stroke-width="2" opacity="0.35" stroke-linejoin="round"/>
</svg>'''

# ────────────────────────────────────────────────────────
# 1. 전기 위험 — 빨간 삼각형 + 번개 볼트 (유지, 색만 빨강으로)
svg_electric = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160">
  <polygon points="80,10 154,146 6,146" fill="#DC3545" stroke="#8B0000" stroke-width="4" stroke-linejoin="round"/>
  <polygon points="80,10 154,146 6,146" fill="none" stroke="white" stroke-width="2" opacity="0.3" stroke-linejoin="round"/>
  <!-- 번개 볼트 (삼각형 내부에 딱 맞게) -->
  <polygon points="84,32 60,88 78,88 72,126 102,70 84,70 90,32"
           fill="white" stroke="white" stroke-width="1" stroke-linejoin="round"/>
</svg>'''

# ────────────────────────────────────────────────────────
# 2. 끼임/말림 위험 — 두 맞물림 기어 + 손가락 끼임
_gear_inner = '''
  <!-- 큰 기어 (왼쪽, 중심 68,95) -->
  <g transform="translate(68,96)">
    <circle r="24" fill="white" stroke="#111" stroke-width="3"/>
    <circle r="10" fill="#111"/>
    <!-- 톱니 8개 -->
    <rect x="-5.5" y="-33" width="11" height="12" rx="2.5" fill="#111"/>
    <rect x="-5.5" y="21"  width="11" height="12" rx="2.5" fill="#111"/>
    <rect x="21"  y="-5.5" width="12" height="11" rx="2.5" fill="#111"/>
    <rect x="-33" y="-5.5" width="12" height="11" rx="2.5" fill="#111"/>
    <g transform="rotate(45)">
      <rect x="-5.5" y="-33" width="11" height="12" rx="2.5" fill="#111"/>
      <rect x="-5.5" y="21"  width="11" height="12" rx="2.5" fill="#111"/>
      <rect x="21"  y="-5.5" width="12" height="11" rx="2.5" fill="#111"/>
      <rect x="-33" y="-5.5" width="12" height="11" rx="2.5" fill="#111"/>
    </g>
  </g>

  <!-- 작은 기어 (오른쪽, 중심 102,72) -->
  <g transform="translate(103,72)">
    <circle r="16" fill="white" stroke="#111" stroke-width="2.5"/>
    <circle r="6.5" fill="#111"/>
    <rect x="-4" y="-23" width="8" height="9" rx="2" fill="#111"/>
    <rect x="-4" y="14"  width="8" height="9" rx="2" fill="#111"/>
    <rect x="14" y="-4"  width="9" height="8" rx="2" fill="#111"/>
    <rect x="-23" y="-4" width="9" height="8" rx="2" fill="#111"/>
    <g transform="rotate(45)">
      <rect x="-4" y="-23" width="8" height="9" rx="2" fill="#111"/>
      <rect x="-4" y="14"  width="8" height="9" rx="2" fill="#111"/>
      <rect x="14" y="-4"  width="9" height="8" rx="2" fill="#111"/>
      <rect x="-23" y="-4" width="9" height="8" rx="2" fill="#111"/>
    </g>
  </g>

  <!-- 손가락 (기어 사이로 끼이는) -->
  <!-- 검지 -->
  <path d="M48,70 C46,64 50,58 56,59 L62,80 C60,83 54,83 51,80 Z"
        fill="white" stroke="#111" stroke-width="2.5" stroke-linejoin="round"/>
  <!-- 중지 -->
  <path d="M56,72 C55,66 59,61 64,62 L68,80 C67,83 61,83 59,80 Z"
        fill="white" stroke="#111" stroke-width="2.5" stroke-linejoin="round"/>
  <!-- 손바닥 -->
  <path d="M46,78 C44,74 47,70 50,71 L52,82 L66,82 L68,78 C70,74 73,76 72,80 L70,88 L44,88 Z"
        fill="white" stroke="#111" stroke-width="2" stroke-linejoin="round"/>
  <!-- 빨간 화살표 -->
  <line x1="50" y1="65" x2="64" y2="72" stroke="#DC3545" stroke-width="3" stroke-linecap="round"/>
  <polygon points="64,68 70,72 63,76" fill="#DC3545"/>
'''
svg_entangle = wrap_svg(_gear_inner)

# ────────────────────────────────────────────────────────
# 3. 충돌 위험 — 사람 + 기계 돌출부 충돌
_collision_inner = '''
  <!-- 기계 블록 (오른쪽) -->
  <rect x="100" y="60" width="28" height="56" rx="4" fill="#333" stroke="#111" stroke-width="1.5"/>
  <!-- 돌출부 -->
  <rect x="88"  y="72" width="14" height="16" rx="3" fill="#333" stroke="#111" stroke-width="1.5"/>
  <!-- 나사 -->
  <circle cx="114" cy="70" r="4" fill="#555"/>
  <line x1="111" y1="70" x2="117" y2="70" stroke="#888" stroke-width="1.5"/>
  <line x1="114" y1="67" x2="114" y2="73" stroke="#888" stroke-width="1.5"/>
  <circle cx="114" cy="100" r="4" fill="#555"/>
  <line x1="111" y1="100" x2="117" y2="100" stroke="#888" stroke-width="1.5"/>
  <line x1="114" y1="97"  x2="114" y2="103" stroke="#888" stroke-width="1.5"/>

  <!-- 사람 (왼쪽, 이동 중) -->
  <!-- 머리 -->
  <circle cx="40" cy="64" r="10" fill="white" stroke="#111" stroke-width="2.5"/>
  <!-- 몸통 -->
  <line x1="40" y1="74" x2="40" y2="98" stroke="#111" stroke-width="4.5" stroke-linecap="round"/>
  <!-- 왼팔 (뒤로) -->
  <path d="M40,82 Q28,78 22,68" stroke="#111" stroke-width="3.5" stroke-linecap="round" fill="none"/>
  <!-- 오른팔 (앞으로) -->
  <path d="M40,82 Q54,78 62,72" stroke="#111" stroke-width="3.5" stroke-linecap="round" fill="none"/>
  <!-- 왼다리 -->
  <path d="M40,98 Q33,110 28,122" stroke="#111" stroke-width="3.5" stroke-linecap="round" fill="none"/>
  <!-- 오른다리 (앞으로 내딛음) -->
  <path d="M40,98 Q48,110 54,122" stroke="#111" stroke-width="3.5" stroke-linecap="round" fill="none"/>

  <!-- 이동 화살표 -->
  <line x1="66" y1="80" x2="84" y2="80" stroke="#E63946" stroke-width="3.5" stroke-linecap="round"/>
  <polygon points="84,74 96,80 84,86" fill="#E63946"/>

  <!-- 충돌 임팩트 별 -->
  <g transform="translate(88,80)">
    <line x1="-10" y1="0"   x2="10" y2="0"  stroke="#E63946" stroke-width="3" stroke-linecap="round"/>
    <line x1="0"  y1="-10"  x2="0"  y2="10" stroke="#E63946" stroke-width="3" stroke-linecap="round"/>
    <line x1="-7" y1="-7"   x2="7"  y2="7"  stroke="#E63946" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="7"  y1="-7"   x2="-7" y2="7"  stroke="#E63946" stroke-width="2.5" stroke-linecap="round"/>
  </g>
'''
svg_collision = wrap_svg(_collision_inner)

# ────────────────────────────────────────────────────────
# 4. 도어 인터록 — 운전 중 도어 열기 금지
_door_inner = '''
  <!-- 도어 프레임 -->
  <rect x="46" y="52" width="36" height="76" rx="4"
        fill="white" stroke="#111" stroke-width="3"/>
  <!-- 도어 패널 (열린 상태, 피벗 왼쪽) -->
  <path d="M46,52 L30,60 L30,128 L46,128 Z"
        fill="#ddd" stroke="#111" stroke-width="2.5"/>
  <!-- 도어 힌지 -->
  <ellipse cx="46" cy="64"  rx="4" ry="5" fill="#999" stroke="#666" stroke-width="1"/>
  <ellipse cx="46" cy="116" rx="4" ry="5" fill="#999" stroke="#666" stroke-width="1"/>
  <!-- 도어 손잡이 -->
  <rect x="77" y="84" width="9" height="6" rx="3" fill="#999" stroke="#666" stroke-width="1.5"/>
  <circle cx="81" cy="91" r="4.5" fill="#999" stroke="#666" stroke-width="1.5"/>
  <!-- 바닥선 -->
  <line x1="24" y1="129" x2="100" y2="129" stroke="#111" stroke-width="3" stroke-linecap="round"/>

  <!-- 사람 (오른쪽, 도어 여는 자세) -->
  <circle cx="112" cy="68" r="9" fill="white" stroke="#111" stroke-width="2.5"/>
  <line x1="112" y1="77" x2="112" y2="98" stroke="#111" stroke-width="4" stroke-linecap="round"/>
  <path d="M112,86 Q100,82 94,86" stroke="#111" stroke-width="3.5" stroke-linecap="round" fill="none"/>
  <path d="M112,86 Q120,83 124,78" stroke="#111" stroke-width="3.5" stroke-linecap="round" fill="none"/>
  <path d="M112,98 Q107,111 104,122" stroke="#111" stroke-width="3.5" stroke-linecap="round" fill="none"/>
  <path d="M112,98 Q117,111 120,122" stroke="#111" stroke-width="3.5" stroke-linecap="round" fill="none"/>

  <!-- 금지 X (굵고 선명하게) -->
  <line x1="36" y1="56" x2="126" y2="126" stroke="#DC3545" stroke-width="8" stroke-linecap="round" opacity="0.92"/>
  <line x1="126" y1="56" x2="36" y2="126" stroke="#DC3545" stroke-width="8" stroke-linecap="round" opacity="0.92"/>
'''
svg_door = wrap_svg(_door_inner)

# ────────────────────────────────────────────────────────
icon_map = {
    '전기 위험':           b64(svg_electric),
    '끼임/말림 위험':      b64(svg_entangle),
    '충돌 위험':           b64(svg_collision),
    '도어 인터록 운전 중': b64(svg_door),
}

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

section_start = next((h for h in soup.find_all(['h2','h3']) if '2.3' in h.get_text()), None)
if not section_start:
    print("2.3 섹션 없음"); sys.exit(1)

replaced = 0
sib = section_start.find_next_sibling()
while sib:
    if sib.name in ['h2','h3'] and re.search(r'2\.[4-9]|3\.', sib.get_text()):
        break
    if sib.name == 'div' and 'notice' in sib.get('class', []):
        title_el = sib.find(class_='notice-title')
        if title_el:
            title = title_el.get_text(strip=True)
            new_src = icon_map.get(title)
            if new_src:
                img = sib.find('img', class_='notice-icon')
                if img:
                    img['src'] = new_src
                    img['alt'] = title
                    replaced += 1
                    print(f"  [{replaced}] {title}")
    sib = sib.find_next_sibling()

print(f"\n총 {replaced}개 교체")
with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(str(soup))

import os
print(f"저장 완료 ({round(os.path.getsize(HTML_PATH)/1024/1024,1)}MB)")
