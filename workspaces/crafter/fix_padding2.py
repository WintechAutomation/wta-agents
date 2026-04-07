html_path = r'C:\MES\wta-agents\reports\MAX\slide-cs-chatbot.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()
html = html.replace('padding:32px 40px 16px 40px', 'padding:48px 40px 16px 40px')
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print("s-body padding-top: 32px -> 48px")
