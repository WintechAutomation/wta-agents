# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

from docx import Document

doc = Document(r'C:\MES\wta-agents\data\wta-manuals-final\PVD\PVD_Unloading_Manual_Revised_20220328.docx')
body = doc.element.body
paras = list(body.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'))

seq = 0
window = []
for p in paras:
    t = ''.join(x.text or '' for x in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')).strip()
    if t:
        window = (window + [t])[-3:]
    blips = p.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
    for blip in blips:
        rId = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
        rel = doc.part.rels.get(rId)
        fname = rel.target_ref.split('/')[-1] if rel else '?'
        seq += 1
        ctx = ' / '.join(window[-2:]) if window else ''
        print(f'img#{seq:03d} {fname:20s}  ctx: {ctx[:80]}')
    if seq >= 30:
        break
