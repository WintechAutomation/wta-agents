import re

html_path = r'C:\MES\wta-agents\reports\MAX\slide-cs-chatbot.html'

with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

style_match = re.search(r'<style>(.*?)</style>', html, re.DOTALL)
old_style = style_match.group(1)

# Extract background-image data URIs
cover_bg_m = re.search(r"\.cover\{background:url\('(data:image/jpeg;base64,[^']+)'\)", old_style)
content_bg_m = re.search(r"\.content-slide\{background:url\('(data:image/jpeg;base64,[^']+)'\)", old_style)
ending_bg_m = re.search(r"\.ending\{background:url\('(data:image/jpeg;base64,[^']+)'\)", old_style)

cover_bg = cover_bg_m.group(1) if cover_bg_m else ''
content_bg = content_bg_m.group(1) if content_bg_m else ''
ending_bg = ending_bg_m.group(1) if ending_bg_m else ''

print(f"Cover bg: {len(cover_bg)} chars")
print(f"Content bg: {len(content_bg)} chars")
print(f"Ending bg: {len(ending_bg)} chars")

new_style = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'맑은 고딕','Malgun Gothic',-apple-system,sans-serif;background:#e8e8e8;color:#333}}
.slide-wrap{{max-width:1100px;margin:0 auto;padding:12px}}
.slide{{background:#fff;border-radius:4px;padding:0;margin-bottom:16px;position:relative;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.15);display:flex;flex-direction:column;aspect-ratio:16/9;max-height:618px}}
.slide-num{{position:absolute;bottom:10px;right:20px;font-size:11px;color:#999;font-weight:600}}
.cover{{background:url('{cover_bg}') center/cover no-repeat;justify-content:center;align-items:flex-start;padding:50px 60px;overflow:hidden}}
.cover h1{{font-size:34px;font-weight:700;color:#333;line-height:1.3;margin-bottom:10px}}
.cover .sub{{font-size:18px;color:#666;margin-bottom:28px;line-height:1.5}}
.cover .meta{{font-size:14px;color:#888;line-height:1.8}}
.content-slide{{background:url('{content_bg}') center/cover no-repeat;padding:0;overflow:hidden}}
.content-slide .s-header{{height:64px;display:flex;align-items:center;padding-left:40px;flex-shrink:0}}
.content-slide .s-title{{font-size:25px;font-weight:700;color:#CC0000;margin:0;padding-left:2em}}
.content-slide .s-body{{padding:12px 40px 16px 40px;flex:1;overflow:hidden}}
.content-slide .s-body>*{{margin-bottom:8px}}
.content-slide .s-body>*:last-child{{margin-bottom:0}}
.g2>.box,.g3>.box,.g4>.box{{min-height:auto}}
.ending{{background:url('{ending_bg}') center/cover no-repeat;justify-content:center;align-items:center;text-align:center;padding:50px;overflow:hidden}}
.slide p{{font-size:15px;line-height:1.7;color:#444;margin-bottom:6px}}
.slide li{{font-size:14px;line-height:1.7;color:#444;margin-bottom:2px}}
.slide ul{{padding-left:20px}}
.slide strong{{color:#222;font-weight:700}}
.hl{{color:#CC0000;font-weight:700}}
.safe{{color:#2E7D32}}
.accent{{color:#CC0000}}
.box{{background:#f8f8f8;border:1px solid #e0e0e0;border-radius:6px;padding:10px 14px;margin:6px 0}}
.box.red{{border-left:4px solid #CC0000}}
.box.green{{border-left:4px solid #2E7D32}}
.box.blue{{border-left:4px solid #1565C0}}
.box.orange{{border-left:4px solid #E65100}}
.box h4{{font-size:14px;font-weight:700;margin-bottom:4px;color:#222}}
.box p{{font-size:13px;margin-bottom:2px;color:#333;line-height:1.6}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:6px 0}}
.g3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:6px 0}}
.big{{text-align:center;padding:10px}}
.big .num{{font-size:38px;font-weight:900;line-height:1}}
.big .num.red{{color:#CC0000}}
.big .num.green{{color:#2E7D32}}
.big .num.blue{{color:#1565C0}}
.big .label{{font-size:12px;color:#777;margin-top:4px}}
.tag{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700}}
.tag.green{{background:#E8F5E9;color:#2E7D32}}
.tag.yellow{{background:#FFF8E1;color:#E65100}}
.tag.red{{background:#FFEBEE;color:#C62828}}
table{{width:100%;border-collapse:collapse;margin:6px 0}}
th{{text-align:left;padding:7px 10px;background:#f0f0f0;color:#555;font-size:12px;font-weight:600;border-bottom:2px solid #CC0000}}
td{{padding:7px 10px;border-bottom:1px solid #eee;font-size:13px;color:#333}}
tr:hover td{{background:#fafafa}}
.vs{{display:grid;grid-template-columns:1fr 1fr;gap:0;border:1px solid #e0e0e0;border-radius:6px;overflow:hidden;margin:8px 0}}
.vs-col{{padding:12px}}
.vs-col.bad{{background:#FFF5F5;border-right:1px solid #e0e0e0}}
.vs-col.good{{background:#F0FFF0}}
.ppt-bar{{max-width:1100px;margin:0 auto;padding:8px 20px 0;display:flex;justify-content:flex-end}}
.ppt-btn{{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;background:#CC0000;color:#fff;border:none;border-radius:6px;font-size:13px;font-weight:600;cursor:pointer;text-decoration:none;font-family:inherit}}
.ppt-btn:hover{{background:#a00}}
.footer{{text-align:center;padding:16px;color:#999;font-size:10px}}
.flow{{display:flex;align-items:center;justify-content:center;gap:6px;margin:8px 0;flex-wrap:wrap}}
.flow-box{{background:#f8f8f8;border:2px solid #e0e0e0;border-radius:6px;padding:8px 14px;text-align:center;min-width:110px;word-break:keep-all}}
.flow-box span{{font-size:11px !important}}
.flow-arrow{{font-size:22px;color:#CC0000;font-weight:700}}
.diagram{{background:#f8f8f8;border:1px solid #e0e0e0;border-radius:6px;padding:14px;margin:6px 0}}
.d-section{{margin:6px 0;padding:10px;border:1px dashed #ccc;border-radius:6px}}
.d-section-title{{font-size:11px;color:#888;font-weight:700;margin-bottom:6px;text-transform:uppercase;letter-spacing:1px}}
.d-node{{display:inline-flex;align-items:center;gap:4px;padding:7px 14px;border-radius:6px;font-size:12px;font-weight:600;margin:3px;word-break:keep-all}}
.d-node.internal{{background:#E3F2FD;border:1px solid #90CAF9;color:#1565C0}}
.d-node.db{{background:#E8F5E9;border:1px solid #A5D6A7;color:#2E7D32}}
.d-node.external{{background:#FFF3E0;border:1px solid #FFCC80;color:#E65100}}
.d-node.ai{{background:#FFEBEE;border:1px solid #EF9A9A;color:#C62828}}
.vs-col h4{{font-size:14px;font-weight:700;margin-bottom:6px}}
.vs-col.bad h4{{color:#C62828}}
.vs-col.good h4{{color:#2E7D32}}
.vs-col li{{font-size:13px;line-height:1.7;list-style:none;padding-left:16px;position:relative}}
.vs-col li::before{{position:absolute;left:0;font-size:12px}}
.vs-col.bad li::before{{content:'\\2717';color:#C62828}}
.vs-col.good li::before{{content:'\\2713';color:#2E7D32}}
.metric-strip{{display:flex;gap:0;border:1px solid #e0e0e0;border-radius:6px;overflow:hidden;margin:8px 0}}
.metric-strip .m-item{{flex:1;padding:10px 8px;text-align:center;border-right:1px solid #e0e0e0}}
.metric-strip .m-item:last-child{{border-right:none}}
.metric-strip .m-val{{font-size:26px;font-weight:900;line-height:1}}
.metric-strip .m-lbl{{font-size:11px;color:#777;margin-top:4px}}
@media(max-width:800px){{.g2,.g3,.g4{{grid-template-columns:1fr}}}}
@media print{{.slide{{break-inside:avoid;page-break-inside:avoid;box-shadow:none}}.ppt-bar{{display:none}}}}
"""

html = html.replace(old_style, new_style)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

print("CSS v2 updated successfully")
