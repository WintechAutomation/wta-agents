import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

fpath = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'
with open(fpath, 'r', encoding='utf-8') as f:
    html = f.read()

# Mapping: alt text -> (sticker URL, sticker code)
sticker_map = {
    '전기 위험': ('https://kslabel.co.kr/data/item/1532662271/thumb-SLE199_280x280.jpg', 'SLE-199'),
    '끼임/말림 위험': ('https://kslabel.co.kr/data/item/1533020828/thumb-SLC135_280x280.jpg', 'SLC-135'),
    '충돌 위험': ('https://kslabel.co.kr/data/item/1532677890/thumb-SLA029_280x280.jpg', 'SLA-029'),
    '도어 인터록 운전 중': ('https://kslabel.co.kr/data/item/1577665238/thumb-JSL081_280x280.jpg', 'JSL-081'),
}

count = 0
for alt_text, (url, code) in sticker_map.items():
    # Match: <img alt="ALT_TEXT" class="notice-icon" src="data:image/svg+xml;base64,..." style="..."/>
    pattern = (
        r'<img\s+alt="' + re.escape(alt_text) + r'"\s+class="notice-icon"\s+'
        r'src="data:image/svg\+xml;base64,[^"]+"\s*'
        r'style="[^"]*"\s*/>'
    )
    replacement = (
        f'<img alt="{alt_text} ({code})" class="notice-icon" '
        f'src="{url}" '
        f'style="width:150px; height:150px; flex-shrink:0; object-fit:contain; border-radius:8px;"/>'
    )
    html, n = re.subn(pattern, replacement, html, count=1)
    if n > 0:
        count += 1
        print(f'  교체: {alt_text} → {code} ({url})')
    else:
        print(f'  미매칭: {alt_text}')

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'\n총 {count}개 스티커 아이콘 교체 완료')
