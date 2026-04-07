"""
매뉴얼 파싱 텍스트에서 figure 캡션을 추출하고
이미지 디렉토리의 img_NNN 파일과 순서 매칭
"""
import os
import re
import json
import base64
from pathlib import Path

PARSED_DIR = Path(r'C:\MES\wta-agents\data\wta_parsed')
IMG_BASE = Path(r'C:\MES\wta-agents\data\manual_images')
REPORTS = Path(r'C:\MES\wta-agents\reports')


def extract_figure_captions(md_path: Path) -> list[str]:
    """마크다운에서 figure/그림 캡션 추출"""
    content = md_path.read_text(encoding='utf-8', errors='replace')
    captions = []

    # 패턴들: "그림 X-Y ...", "Figure X-Y ...", "Fig. X.Y ...", "图 X-Y ..."
    patterns = [
        r'(?:그림|Figure|Fig\.?|图)\s*(\d+[-\.]\d+)[\.:\s]*([^\n]*)',
        r'!\[([^\]]*)\]',  # markdown image alt text
    ]

    for pat in patterns[:1]:  # 우선 figure caption만
        for m in re.finditer(pat, content):
            fig_num = m.group(1).replace('.', '-')
            desc = m.group(2).strip() if m.lastindex >= 2 else ''
            caption = f"그림 {fig_num}"
            if desc:
                # 불필요한 마크다운 제거
                desc = re.sub(r'[*_`#]', '', desc).strip()
                if desc:
                    caption += f" {desc}"
            if caption not in captions:
                captions.append(caption)

    return captions


def get_image_files(img_dir: Path) -> list[Path]:
    """이미지 디렉토리에서 파일 목록 (자연 정렬)"""
    exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}
    files = [f for f in img_dir.iterdir() if f.is_file() and f.suffix.lower() in exts]

    def natural_key(p):
        parts = re.split(r'(\d+)', p.stem)
        return [int(x) if x.isdigit() else x.lower() for x in parts]

    files.sort(key=natural_key)
    return files


def make_thumbnail_b64(file_path: Path, max_size: int = 250) -> str:
    """썸네일 base64"""
    try:
        from PIL import Image
        import io
        img = Image.open(file_path)
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        buf = io.BytesIO()
        fmt = 'JPEG' if file_path.suffix.lower() in ['.jpg', '.jpeg'] else 'PNG'
        if fmt == 'JPEG' and img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.save(buf, format=fmt, quality=55)
        b64 = base64.b64encode(buf.getvalue()).decode()
        mime = 'jpeg' if fmt == 'JPEG' else 'png'
        return f"data:image/{mime};base64,{b64}"
    except Exception:
        return ""


def generate_matched_catalog(
    title: str,
    images: list[Path],
    captions: list[str],
    source_info: str,
) -> str:
    """figure 캡션과 매칭된 카탈로그 HTML 생성"""
    cards = []
    for i, img_path in enumerate(images):
        seq = i + 1
        # 캡션 매칭: 이미지 수보다 캡션이 적으면 "미매칭"
        if i < len(captions):
            caption = captions[i]
        else:
            caption = f"(미매칭) {img_path.stem}"

        # 구조화 파일명
        fig_match = re.match(r'그림\s*(\d+[-\.]\d+)\s*(.*)', caption)
        if fig_match:
            fig_num = fig_match.group(1)
            desc = fig_match.group(2).strip()
            desc_safe = re.sub(r'\s+', '_', desc)
            desc_safe = re.sub(r'[\\/:*?"<>|]', '', desc_safe)
            fname = f"{seq:03d}_그림_{fig_num}_{desc_safe}{img_path.suffix}"
        else:
            fname = f"{seq:03d}_{img_path.stem}{img_path.suffix}"

        thumb = make_thumbnail_b64(img_path)
        is_unmatched = '미매칭' in caption
        border = ' style="border: 2px solid #ff9800;"' if is_unmatched else ''
        warn = '\n      <div style="color:#ff9800; font-size:8pt;">⚠ 캡션 미매칭 — 확인 필요</div>' if is_unmatched else ''

        card = f"""    <div class="card"{border}>
      <div class="seq">{seq:03d}</div>
      <img src="{thumb}" alt="{caption}"/>
      <div class="cap">{caption}</div>
      <div class="fname">{fname}</div>
      <div class="orig">원본: {img_path.name}</div>{warn}
    </div>"""
        cards.append(card)

    matched = len([c for c in captions if c and '미매칭' not in c])
    total = len(images)
    match_rate = (min(matched, total) / total * 100) if total > 0 else 0

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>{title} 이미지 매칭 확인</title>
<style>
  body {{ font-family: '맑은 고딕', sans-serif; background: #f5f5f5; padding: 20px; }}
  h1 {{ font-size: 14pt; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; }}
  .summary {{ color: #555; font-size: 10pt; margin-bottom: 20px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  .card img {{ width: 100%; height: 150px; object-fit: contain; background: #f9f9f9; border: 1px solid #eee; border-radius: 4px; }}
  .seq {{ font-size: 8pt; color: #aaa; margin-bottom: 3px; }}
  .cap {{ font-size: 9pt; font-weight: 700; color: #1a237e; margin-top: 6px; }}
  .fname {{ font-size: 7.5pt; color: #888; font-family: monospace; margin-top: 2px; word-break: break-all; }}
  .orig {{ font-size: 7pt; color: #bbb; margin-top: 1px; }}
</style>
</head>
<body>
<h1>{title} — 이미지 매칭 확인</h1>
<div class="summary">총 {total}개 이미지 | 캡션 매칭 {min(matched,total)}/{total} ({match_rate:.0f}%) | 출처: {source_info}</div>
<div class="grid">
{''.join(cards)}
</div>
</body>
</html>"""


# 매뉴얼별 매핑: (이미지 디렉토리, 파싱 파일, 출력 제목)
MANUAL_MAP = [
    {
        'img_dir': 'HAM-CVD L&UL Machine User Manual en_v1.0',
        'parsed': 'HAM-CVD_L_UL_Machine_User_Manual_en_v1.0.md',
        'title': 'CVD L&UL Machine (EN)',
    },
    {
        'img_dir': 'HAM-PVD_Unloading_User_Manual_en_v1.3',
        'parsed': 'HAM-PVD_Unloading_User_Manual_en_v1.3.md',
        'title': 'PVD Unloading (EN)',
    },
    {
        'img_dir': '(완성본)유지보수 메뉴얼 - 한국야금 PVD Loading Handler',
        'parsed': 'Final_Maintenance_Manual_-_Korea_Tungsten_PVD_Loading_Handler.md',
        'title': 'PVD Loading Handler (KR)',
    },
    {
        'img_dir': '[WT1724]YG1  CVD 매뉴얼',
        'parsed': 'WT1724_YG1_CVD_Manual.md',
        'title': 'YG1 CVD',
    },
    {
        'img_dir': 'HAM-Labeling_User_Manual_v1.1_KR',
        'parsed': 'HAM-Labeling_User_Manual_v1.1_KR.md',
        'title': 'Labeling Machine (KR)',
    },
    {
        'img_dir': 'PressHandler',
        'parsed': '1._User_Manual_Press_Handler_MC.md',
        'title': 'Press Handler',
    },
    {
        'img_dir': 'Double_Side_Handler_Manual_Revised',
        'parsed': 'Double_Side_Handler_Manual_Revised.md',
        'title': 'Double Side Handler',
    },
    {
        'img_dir': 'PVD 언로딩 매뉴얼(수정 완료)_20220328',
        'parsed': 'PVD_Manual_Revised_20220328.md',  # or PVD_Unloading_Manual_Revised_20220328
        'title': 'PVD Unloading (KR원본)',
    },
]


def main():
    results = []

    for entry in MANUAL_MAP:
        img_dir = IMG_BASE / entry['img_dir']
        parsed_file = PARSED_DIR / entry['parsed']
        title = entry['title']

        if not img_dir.is_dir():
            print(f"건너뜀 (디렉토리 없음): {entry['img_dir']}")
            continue

        images = get_image_files(img_dir)
        if not images:
            print(f"건너뜀 (이미지 없음): {entry['img_dir']}")
            continue

        # figure 캡션 추출
        captions = []
        if parsed_file.exists():
            captions = extract_figure_captions(parsed_file)
            print(f"{title}: {len(images)} imgs, {len(captions)} captions from {parsed_file.name}")
        else:
            # 파싱 파일 없으면 비슷한 이름 찾기
            alt_files = [f for f in os.listdir(PARSED_DIR) if entry['parsed'].split('.')[0].lower() in f.lower()]
            if alt_files:
                alt_path = PARSED_DIR / alt_files[0]
                captions = extract_figure_captions(alt_path)
                print(f"{title}: {len(images)} imgs, {len(captions)} captions from {alt_files[0]}")
            else:
                print(f"{title}: {len(images)} imgs, 파싱 파일 없음")

        # 카탈로그 생성
        safe_name = re.sub(r'\s+', '_', title).lower()
        safe_name = re.sub(r'[\\/:*?"<>|()&]', '', safe_name)
        output = REPORTS / f"{safe_name}_이미지_매칭_확인.html"

        html = generate_matched_catalog(title, images, captions, entry['img_dir'])
        output.write_text(html, encoding='utf-8')
        size_mb = output.stat().st_size / 1024 / 1024
        print(f"  → {output.name} ({size_mb:.1f} MB)")

        results.append({
            'title': title,
            'file': output.name,
            'images': len(images),
            'captions': len(captions),
        })

    print(f"\n완료: {len(results)}개 카탈로그")
    for r in results:
        rate = min(r['captions'], r['images']) / r['images'] * 100 if r['images'] > 0 else 0
        print(f"  {r['title']}: {r['images']}개 이미지, {r['captions']}개 캡션 ({rate:.0f}% 매칭)")


if __name__ == '__main__':
    main()
