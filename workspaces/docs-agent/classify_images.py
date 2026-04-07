"""
이미지 자동 분류 - 크기/비율로 카테고리 추정
외관도: 가로>세로, 400+ (machine exterior)
HMI 화면: 정사각형에 가까움, 500+ (hmi screen)
3D CAD: 다양한 크기 (3d_cad)
사진: JPEG 포맷 (photo)
아이콘: 작은 크기 (icon)
"""
import os
import hashlib
from pathlib import Path
from PIL import Image
from collections import defaultdict

IMG_BASE = Path(r'C:\MES\wta-agents\data\manual_images')

DIRS = [
    'HAM-CVD L&UL Machine User Manual en_v1.0',
    'HAM-PVD_Unloading_User_Manual_en_v1.3',
]


def img_hash(path):
    """간단한 이미지 해시 (크기+첫 1KB)"""
    try:
        with open(path, 'rb') as f:
            data = f.read(1024)
        return hashlib.md5(data).hexdigest()
    except:
        return None


def classify(path):
    try:
        img = Image.open(path)
        w, h = img.size
        ext = path.suffix.lower()
        ratio = w / h if h > 0 else 1

        if w < 200 or h < 150:
            return 'icon'
        if ext in ['.jpg', '.jpeg']:
            return 'photo'
        if w > 900 and h > 500:
            return 'full_view'
        if ratio > 1.3 and w > 500:
            return 'wide_diagram'
        if 0.7 < ratio < 1.3 and w > 400:
            return 'screen_or_square'
        return 'diagram'
    except:
        return 'error'


def main():
    for dir_name in DIRS:
        img_dir = IMG_BASE / dir_name
        if not img_dir.is_dir():
            continue

        print(f'\n=== {dir_name} ===')
        cats = defaultdict(list)
        hashes = defaultdict(list)

        for f in sorted(img_dir.iterdir()):
            if not f.is_file() or not f.stem.startswith('img_'):
                continue
            cat = classify(f)
            img = Image.open(f)
            w, h = img.size
            cats[cat].append((f.stem, w, h))

            h_val = img_hash(f)
            if h_val:
                hashes[h_val].append(f.stem)

        for cat in ['full_view', 'wide_diagram', 'screen_or_square', 'photo', 'diagram', 'icon']:
            items = cats.get(cat, [])
            if items:
                print(f'\n[{cat}] ({len(items)}):')
                for name, w, h in items[:20]:
                    print(f'  {name}: {w}x{h}')
                if len(items) > 20:
                    print(f'  ... +{len(items)-20} more')

        # 중복 이미지
        dupes = {h: names for h, names in hashes.items() if len(names) > 1}
        if dupes:
            print(f'\n[duplicates] ({len(dupes)} groups):')
            for h, names in list(dupes.items())[:10]:
                print(f'  {", ".join(names)}')


if __name__ == '__main__':
    main()
