# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

html_path = r'C:\MES\wta-agents\reports\MAX\slide-cs-chatbot.html'

with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# CSS: change global s-body padding to 16px (smaller base)
# Then add per-slide overrides for slides 3+ via inline style
# Approach: change s-body padding in CSS to 16px,
# and for slides 1-2 (system overview) keep as is,
# for slides 3+ add inline padding-top:36px

# Actually simpler: just increase global s-body padding-top from 24px to 36px
# Slides 1 (cover) and 8 (ending) don't use s-body at all
# Slide 2 (system overview) - might get affected but it has more content
# Let's set it to 32px as a middle ground
html = html.replace(
    'padding:24px 40px 16px 40px',
    'padding:32px 40px 16px 40px'
)

print("s-body padding-top updated: 24px -> 32px")

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

print("Done")
