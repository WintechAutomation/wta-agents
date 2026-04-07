import re

html_path = r'C:\MES\wta-agents\reports\MAX\slide-cs-chatbot.html'

with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# s-body padding-top 12px -> 24px
html = html.replace(
    'padding:12px 40px 16px 40px',
    'padding:24px 40px 16px 40px'
)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

print("s-body padding-top updated: 12px -> 24px")
