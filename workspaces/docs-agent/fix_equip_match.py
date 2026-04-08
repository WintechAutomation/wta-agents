import os

base = os.path.join('C:', os.sep, 'MES', 'wta-agents', 'reports', '김근형')
fpath = os.path.join(base, 'erp_재고현황_발주내역.html')

with open(fpath, 'r', encoding='utf-8') as f:
    html = f.read()

# Replace parseEquipTypes to check both r[9] (existing label) and r[8] (project name)
# Also add broader keyword matching (Press → 프레스, etc.)
old = """function parseEquipTypes(label) {
  if (!label) return [];
  const types = [];
  for (const key of Object.keys(EQUIP_PLAN)) {
    if (label.includes(key)) types.push(key);
  }
  return types;
}"""

new = """function parseEquipTypes(label, project) {
  const text = (label || '') + ' ' + (project || '');
  if (!text.trim()) return [];
  const ALIASES = {'프레스':['프레스','Press','press'],'검사기':['검사기','검사'],'PVD':['PVD'],'CVD':['CVD'],'포장기':['포장기','포장'],'소결':['소결'],'호닝형상':['호닝','호닝형상'],'CBN':['CBN'],'연삭핸들러':['연삭핸들러','연삭'],'마스크자동기':['마스크자동기','마스크']};
  const types = [];
  for (const key of Object.keys(EQUIP_PLAN)) {
    const aliases = ALIASES[key] || [key];
    if (aliases.some(a => text.includes(a))) types.push(key);
  }
  return types;
}"""

if old in html:
    html = html.replace(old, new)
    print('parseEquipTypes updated')
else:
    print('ERROR: parseEquipTypes not found')

# Update all calls to parseEquipTypes to pass r[8] as second arg
# recalcAll: parseEquipTypes(r[9]) → parseEquipTypes(r[9], r[8])
html = html.replace('parseEquipTypes(r[9])', 'parseEquipTypes(r[9], r[8])')

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(html)

print('All parseEquipTypes calls updated')
