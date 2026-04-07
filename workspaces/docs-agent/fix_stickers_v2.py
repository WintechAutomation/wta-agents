import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

fpath = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'
with open(fpath, 'r', encoding='utf-8') as f:
    html = f.read()

# Fix 1: 충돌 위험 — SLA-029(도어 이미지) → SLA-004(일반 주의 삼각형, 충돌에 적합)
old_collision = 'src="https://kslabel.co.kr/data/item/1532677890/thumb-SLA029_280x280.jpg" style="width:150px; height:150px;'
new_collision = 'src="https://kslabel.co.kr/data/item/1532673352/thumb-SLA004_311x156.jpg" style="width:140px; height:140px;'
html = html.replace(old_collision, new_collision)
# Update alt text
html = html.replace('alt="충돌 위험 (SLA-029)"', 'alt="충돌 위험 (SLA-004)"')
print('  교체: 충돌 위험 SLA-029 → SLA-004')

# Fix 2: 도어 인터록 — JSL-081(중국어) → SLA-029(도어 이미지, 한국어)
old_door = 'src="https://kslabel.co.kr/data/item/1577665238/thumb-JSL081_280x280.jpg" style="width:150px; height:150px;'
new_door = 'src="https://kslabel.co.kr/data/item/1532677890/thumb-SLA029_280x280.jpg" style="width:140px; height:140px;'
html = html.replace(old_door, new_door)
html = html.replace('alt="도어 인터록 운전 중 (JSL-081)"', 'alt="도어 인터록 운전 중 (SLA-029)"')
print('  교체: 도어 인터록 JSL-081 → SLA-029')

# Fix 3: 전기 위험 — 사이즈만 150→140
html = html.replace(
    'alt="전기 위험 (SLE-199)" class="notice-icon" src="https://kslabel.co.kr/data/item/1532662271/thumb-SLE199_280x280.jpg" style="width:150px; height:150px;',
    'alt="전기 위험 (SLE-199)" class="notice-icon" src="https://kslabel.co.kr/data/item/1532662271/thumb-SLE199_280x280.jpg" style="width:140px; height:140px;'
)
print('  축소: 전기 위험 150→140px')

# Fix 4: 끼임/말림 — 사이즈만 150→140
html = html.replace(
    'alt="끼임/말림 위험 (SLC-135)" class="notice-icon" src="https://kslabel.co.kr/data/item/1533020828/thumb-SLC135_280x280.jpg" style="width:150px; height:150px;',
    'alt="끼임/말림 위험 (SLC-135)" class="notice-icon" src="https://kslabel.co.kr/data/item/1533020828/thumb-SLC135_280x280.jpg" style="width:140px; height:140px;'
)
print('  축소: 끼임/말림 위험 150→140px')

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(html)

print('\n수정 완료: 2개 이미지 교체 + 4개 사이즈 140px 통일')
