import os

base = os.path.join('C:', os.sep, 'MES', 'wta-agents', 'reports', '김근형')
fpath = os.path.join(base, 'erp_재고현황_발주내역.html')

with open(fpath, 'r', encoding='utf-8') as f:
    html = f.read()

# Update ALIASES to include broader press-related keywords
old = "'프레스':['프레스','Press','press']"
new = "'프레스':['프레스','Press','press','프레스핸들러']"

html = html.replace(old, new)

# Also need to handle project names that contain these equipment keywords
# but the current issue is that "Press Tool", "Press 상부" should map to 프레스
# Since we already have 'Press' in the aliases, these should already match.
# But let me verify the actual project names in the data have "프레스" or "Press"

# Check: "Press Tool (24-1)" contains "Press" → already matched
# Check: "Press 상부 (24-1)" contains "Press" → already matched
# The issue might be that these are in r[8] but recalcAll was previously not checking r[8]

# Verify the parseEquipTypes function is checking r[8]
if 'parseEquipTypes(r[9], r[8])' in html:
    print('parseEquipTypes already checks r[8] - OK')
else:
    print('WARNING: parseEquipTypes not checking r[8]')

# Now also update the data itself - items with "Press Tool" or "Press 상부" in project
# should have their project updated to the actual customer project
# This is a data issue - need db-manager

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(html)

print('Aliases updated')
