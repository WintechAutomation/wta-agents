"""erp_data.json의 최신 데이터를 두 HTML 파일에 재적용"""
import json, os

base = os.path.join('C:', os.sep, 'MES', 'wta-agents', 'reports', '김근형')

with open(os.path.join(base, 'erp_data.json'), 'r', encoding='utf-8') as f:
    combined = json.load(f)

data = combined['data']
data_json = json.dumps(data, ensure_ascii=True)

def replace_data_array(html):
    """const data = [...]; 부분을 새 데이터로 교체"""
    marker = 'const data = ['
    start = html.index(marker)
    # Start scanning from the opening [
    bracket_start = start + len('const data = ')
    depth = 0
    end = None
    for i in range(bracket_start, len(html)):
        if html[i] == '[':
            depth += 1
        elif html[i] == ']':
            depth -= 1
            if depth == 0:
                end = i + 1
                # Skip trailing semicolon
                if end < len(html) and html[end] == ';':
                    end += 1
                break
    if end is None:
        raise ValueError('Could not find end of data array')
    return html[:start] + 'const data = ' + data_json + ';' + html[end:]

# 1. 전체목록 HTML
fpath1 = os.path.join(base, 'erp_재고현황_발주내역.html')
with open(fpath1, 'r', encoding='utf-8') as f:
    html1 = f.read()
html1 = replace_data_array(html1)
with open(fpath1, 'w', encoding='utf-8') as f:
    f.write(html1)
print(f'erp_재고현황_발주내역.html: {len(html1)} bytes')

# 2. TOP20 HTML
fpath2 = os.path.join(base, 'erp_현재고_TOP20.html')
with open(fpath2, 'r', encoding='utf-8') as f:
    html2 = f.read()
html2 = replace_data_array(html2)
with open(fpath2, 'w', encoding='utf-8') as f:
    f.write(html2)
print(f'erp_현재고_TOP20.html: {len(html2)} bytes')
