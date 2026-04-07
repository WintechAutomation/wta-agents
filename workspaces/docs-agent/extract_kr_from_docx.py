# -*- coding: utf-8 -*-
"""
docx에서 한국어 컨텍스트를 가진 이미지만 추출해서 pvd_images_named/에 올바르게 저장
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from docx import Document
import os, re, shutil, zipfile

DOCX_PATH  = r'C:\MES\wta-agents\data\wta-manuals-final\PVD\PVD_Unloading_Manual_Revised_20220328.docx'
OUT_DIR    = r'C:\MES\wta-agents\workspaces\docs-agent\pvd_images_named'
HTML_PATH  = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'

from bs4 import BeautifulSoup

# HTML caption 목록 (순서대로)
with open(HTML_PATH, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')
captions = [c.get_text(strip=True) for c in soup.find_all('div', class_='figure-caption')]
print(f"HTML caption 수: {len(captions)}개")

def safe_name(text):
    name = re.sub(r'[\\/:*?"<>|]', '', text).strip()
    return re.sub(r'\s+', '_', name)[:80]

def is_korean(text):
    return bool(re.search(r'[가-힣]', text))

# docx에서 문단 순서대로 이미지 등장 위치와 컨텍스트 수집
doc = Document(DOCX_PATH)
NS_W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
NS_A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
NS_R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

paras = list(doc.element.body.iter(f'{NS_W}p'))
text_buf = []
all_imgs = []  # [(seq, rId, rel, ctx_texts)]

for p in paras:
    t = ''.join(x.text or '' for x in p.iter(f'{NS_W}t')).strip()
    if t:
        text_buf = (text_buf + [t])[-5:]

    for blip in p.findall(f'.//{NS_A}blip'):
        rId = blip.get(f'{NS_R}embed')
        if not rId:
            continue
        rel = doc.part.rels.get(rId)
        seq = len(all_imgs) + 1
        all_imgs.append((seq, rId, rel, list(text_buf)))

print(f"docx 총 이미지: {len(all_imgs)}개")

# 한국어 컨텍스트를 가진 이미지 필터
kr_imgs = [(seq, rId, rel, ctx) for seq, rId, rel, ctx in all_imgs
           if any(is_korean(t) for t in ctx)]
print(f"한국어 컨텍스트 이미지: {len(kr_imgs)}개")

# 앞부분 출력 (확인용)
print("\n--- 한국어 이미지 처음 10개 ---")
for seq, rId, rel, ctx in kr_imgs[:10]:
    print(f"  docx순번 {seq}: {' / '.join(ctx[-2:])[:60]}")

# docx zip에서 실제 이미지 바이트 추출 함수
def get_img_bytes(rel):
    if rel is None:
        return None, None
    # rel.target_ref 예: word/media/image1.jpeg
    target = rel.target_ref
    fname = os.path.basename(target)
    ext = fname.rsplit('.', 1)[-1].lower()
    with zipfile.ZipFile(DOCX_PATH, 'r') as z:
        path_in_zip = 'word/' + target if not target.startswith('word/') else target
        try:
            data = z.read(path_in_zip)
        except KeyError:
            # 다른 경로 시도
            for name in z.namelist():
                if os.path.basename(name) == fname:
                    data = z.read(name)
                    break
            else:
                return None, None
    return data, ext

# caption 수와 한국어 이미지 수 맞추기
# HTML caption 39개 - 한국어 이미지 수가 맞는지 확인
if len(kr_imgs) < len(captions):
    print(f"\n경고: 한국어 이미지({len(kr_imgs)})가 caption({len(captions)})보다 적음")
    print("전체 이미지 뒤에서부터 caption 수만큼 사용")
    kr_imgs = all_imgs[-(len(captions)):]
elif len(kr_imgs) > len(captions):
    print(f"\n한국어 이미지({len(kr_imgs)})가 caption({len(captions)})보다 많음 — 뒤에서부터 매핑")
    kr_imgs = kr_imgs[-len(captions):]

print(f"\n매핑 대상: {len(kr_imgs)}개")

# 기존 파일 백업 후 새 이미지 저장
backup_dir = OUT_DIR + '_backup'
if not os.path.exists(backup_dir):
    shutil.copytree(OUT_DIR, backup_dir)
    print(f"기존 파일 백업: {backup_dir}")

saved = 0
for i, (seq, rId, rel, ctx) in enumerate(kr_imgs):
    if i >= len(captions):
        break
    cap = captions[i]
    data, ext = get_img_bytes(rel)
    if data is None:
        print(f"  [{i+1:02d}] 이미지 읽기 실패: {cap}")
        continue
    if ext == 'jpeg':
        ext = 'jpg'
    fname = f"{i+1:03d}_{safe_name(cap)}.{ext}"
    fpath = os.path.join(OUT_DIR, fname)
    with open(fpath, 'wb') as f:
        f.write(data)
    kb = round(len(data) / 1024)
    ctx_str = ' / '.join(ctx[-2:])[:50]
    print(f"  [{i+1:02d}] {cap} ({kb}KB) | docx{seq} | {ctx_str}")
    saved += 1

print(f"\n총 {saved}개 저장 완료 → {OUT_DIR}")

# 기존 파일 중 새로 저장되지 않은 것 삭제
new_fnames = set()
for i, cap in enumerate(captions[:saved]):
    new_fnames.add(f"{i+1:03d}_")
for fname in os.listdir(OUT_DIR):
    seq_prefix = fname[:4]
    if not any(fname.startswith(f"{i+1:03d}_") for i in range(saved)):
        old_path = os.path.join(OUT_DIR, fname)
        print(f"  삭제: {fname}")
        os.remove(old_path)
