from playwright.sync_api import sync_playwright
import os

html_path = r'C:\MES\wta-agents\reports\MAX\slide-cs-chatbot.html'
pdf_path = r'C:\MES\wta-agents\reports\MAX\slide-cs-chatbot.pdf'
file_url = 'file:///' + html_path.replace(os.sep, '/')

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(file_url, wait_until='networkidle')
    page.pdf(
        path=pdf_path,
        format='A4',
        landscape=True,
        print_background=True,
        margin={'top': '0mm', 'right': '0mm', 'bottom': '0mm', 'left': '0mm'}
    )
    browser.close()

size_kb = os.path.getsize(pdf_path) / 1024
print(f'PDF saved: {pdf_path} ({size_kb:.0f}KB)')
