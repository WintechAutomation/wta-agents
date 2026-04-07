# -*- coding: utf-8 -*-
"""
docx에서 문단 순서대로 이미지 등장 위치와 바로 앞 텍스트(캡션/제목)를 출력
pvd_images_named/ 파일명과 실제 순서 비교
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from docx import Document
import os, re

DOCX_PATH = r'C:\MES\wta-agents\data\wta-manuals-final\PVD\PVD_Unloading_Manual_Revised_20220328.docx'
IMG_DIR   = r'C:\MES\wta-agents\workspaces\docs-agent\pvd_images_named'

doc = Document(DOCX_PATH)
body = doc.element.body
NS_W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
NS_A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
NS_R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

# 현재 named 파일 목록
named_files = {}
for fname in sorted(os.listdir(IMG_DIR)):
    m = re.match(r'^(\d{3})_(.+)\.(jpeg|jpg|png)$', fname, re.I)
    if m:
        named_files[int(m.group(1))] = (fname, m.group(2).replace('_', ' '))

# 문단 순서대로 이미지 탐색
paras = list(body.iter(f'{NS_W}p'))
seq = 0
text_buf = []

print(f"{'순번':>4} | {'docx 내 텍스트 컨텍스트':<45} | {'named 파일'}")
print("-" * 110)

for p in paras:
    t = ''.join(x.text or '' for x in p.iter(f'{NS_W}t')).strip()
    if t:
        text_buf = (text_buf + [t])[-3:]

    blips = p.findall(f'.//{NS_A}blip')
    for blip in blips:
        rId = blip.get(f'{NS_R}embed')
        if not rId:
            continue
        rel = doc.part.rels.get(rId)
        orig_fname = os.path.basename(rel.target_ref) if rel else '?'
        seq += 1
        ctx = ' / '.join(text_buf) if text_buf else ''
        named = named_files.get(seq)
        named_str = named[0] if named else '*** 없음 ***'
        named_cap = named[1] if named else ''
        match_mark = '' if (named and named_cap in ctx) else ' ← 불일치?'
        print(f"{seq:>4} | {ctx[:45]:<45} | {named_str}{match_mark}")

print()
print(f"docx 총 이미지: {seq}개 | named 파일: {len(named_files)}개")
