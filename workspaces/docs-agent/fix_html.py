import json

import os
base = os.path.join('C:', os.sep, 'MES', 'wta-agents', 'reports', '김근형')
with open(os.path.join(base, 'erp_data.json'), 'r', encoding='utf-8') as f:
    combined = json.load(f)

equip_plan = combined['equip_plan']
data = combined['data']

with open(os.path.join(base, 'erp_재고현황_발주내역.html'), 'r', encoding='utf-8') as f:
    html = f.read()

script_start = html.index('<script>') + len('<script>')
script_end = html.index('</script>')
script = html[script_start:script_end]
lines = script.split('\n')

new_lines = []
skip_until_closing = False

for line in lines:
    stripped = line.strip()

    # Replace the _json line with just data assignment
    if stripped.startswith('const _json = '):
        # Directly assign data array (not as JSON object)
        new_lines.append('  const data = DATA_ARRAY;')
        continue
    if stripped == 'const data = _json.data;':
        # Skip this line - already handled above
        continue

    # Replace EQUIP_PLAN_DEFAULT with value from JSON
    if stripped.startswith('const EQUIP_PLAN_DEFAULT = '):
        ep_str = json.dumps(equip_plan, ensure_ascii=False)
        new_lines.append('const EQUIP_PLAN_DEFAULT = ' + ep_str + ';')
        # Check if it's a single-line or multi-line declaration
        if not stripped.endswith(';'):
            skip_until_closing = True
        continue

    if skip_until_closing:
        if stripped == '};':
            skip_until_closing = False
        continue

    new_lines.append(line)

new_script = '\n'.join(new_lines)

# Now replace DATA_ARRAY placeholder with actual data
# Use ensure_ascii=True to avoid any unicode issues in JS
data_json = json.dumps(data, ensure_ascii=True)
new_script = new_script.replace('DATA_ARRAY;', data_json + ';')

html_new = html[:script_start] + new_script + html[script_end:]

with open(os.path.join(base, 'erp_재고현황_발주내역.html'), 'w', encoding='utf-8') as f:
    f.write(html_new)

print(f'Done. File size: {len(html_new)}')
