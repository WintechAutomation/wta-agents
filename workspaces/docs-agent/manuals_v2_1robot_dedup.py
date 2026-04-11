# -*- coding: utf-8 -*-
"""1_robot dedup plan: md5 그룹에서 대표 파일 1개 선택"""
import json, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from collections import defaultdict

IN = r'C:\MES\wta-agents\workspaces\docs-agent\manuals_v2_1robot_extract.jsonl'
OUT_UNIQUE = r'C:\MES\wta-agents\workspaces\docs-agent\manuals_v2_1robot_unique.jsonl'
OUT_DUP = r'C:\MES\wta-agents\workspaces\docs-agent\manuals_v2_1robot_duplicates.jsonl'

rows = []
with open(IN,'r',encoding='utf-8') as f:
    for line in f:
        rows.append(json.loads(line))

# 표준명 패턴 판정
STD_RE = re.compile(r'^[A-Z][A-Za-z]+_[A-Za-z0-9\-]+_[A-Za-z]+_[A-Z]{2}(?:_v\d+)?\.pdf$', re.I)

def score(r):
    """대표 선정 점수: 높을수록 우선"""
    fn = r['filename']
    s = 0
    if STD_RE.match(fn):
        s += 1000
    # 한글 포함 비율 적은 쪽
    korean = sum(1 for c in fn if '\uac00'<=c<='\ud7a3')
    s -= korean * 2
    # 짧은 이름 선호
    s -= len(fn) * 0.1
    # size 큰 쪽
    s += (r.get('size',0) / 10000)
    # text 많은 쪽
    s += min(len(r.get('text','')), 3000) / 100
    return s

by_md5 = defaultdict(list)
for r in rows:
    by_md5[r['md5']].append(r)

uniques = []
dups = []
for md5, group in by_md5.items():
    if not md5:
        uniques.extend(group)
        continue
    group.sort(key=score, reverse=True)
    uniques.append(group[0])
    for r in group[1:]:
        r['dup_of'] = group[0]['filename']
        dups.append(r)

with open(OUT_UNIQUE,'w',encoding='utf-8') as f:
    for r in uniques:
        f.write(json.dumps(r, ensure_ascii=False)+'\n')
with open(OUT_DUP,'w',encoding='utf-8') as f:
    for r in dups:
        f.write(json.dumps(r, ensure_ascii=False)+'\n')

print(f'입력: {len(rows)}건')
print(f'유니크: {len(uniques)}건')
print(f'중복: {len(dups)}건')
print(f'출력: {OUT_UNIQUE}')
print(f'  중복 리스트: {OUT_DUP}')

# 유니크 중 status별
ok = sum(1 for r in uniques if r['status']=='ok')
docx = sum(1 for r in uniques if r['status']=='docx')
print(f'유니크 상세: ok={ok}, docx={docx}')
