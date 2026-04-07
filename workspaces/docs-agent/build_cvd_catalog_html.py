"""
CVD L&UL Machine EN - DOCX->HTML 변환 기반 이미지 카탈로그
mammoth으로 DOCX를 HTML 변환 -> 이미지+텍스트를 문서 순서대로 추출
Figure 캡션 근처의 이미지만 매칭하여 정확한 카탈로그 생성
"""
import re
import base64
import hashlib
import io
import os
from pathlib import Path
from html.parser import HTMLParser
from PIL import Image
import mammoth

# 영문 -> 한글 캡션 번역 (원본 영문은 보존 — 다음 매뉴얼 작성 시 영문 사용)
CAPTION_KR: dict[str, str] = {
    "Figure - Front": "그림 - 전면",
    "Figure - Rear": "그림 - 후면",
    "Figure - Latera": "그림 - 측면",
    "Figure - Emergency Stop Button": "그림 - 비상정지 버튼",
    "Figure - Signal lamps": "그림 - 시그널 램프",
    "Figure - Power on the installation": "그림 - 설비 전원 투입",
    "Figure - Control panel descriptions": "그림 - 조작판 설명",
    "Figure - Main Screen": "그림 - 메인 화면",
    "Figure - Create and set up the model": "그림 - 모델 생성 및 설정",
    "Figure - Pattern Settings": "그림 - 패턴 설정",
    "Figure - Pallet management settings": "그림 - 팔레트 관리 설정",
    "Figure - Bar management settings": "그림 - 바 관리 설정",
    "Figure - Spacer management settings": "그림 - 스페이서 관리 설정",
    "Figure - Manage loads": "그림 - 적재 관리",
    "Figure - Selecting a model and entering lots": "그림 - 모델 선택 및 LOT 입력",
    "Figure - Pallet settings": "그림 - 팔레트 설정",
    "Figure - Setting up indexes": "그림 - 인덱스 설정",
    "Figure - Set up the default task": "그림 - 기본 작업 설정",
    "Figure - Setting up pallet actions": "그림 - 팔레트 동작 설정",
    "Figure - Rotary stacker": "그림 - 로터리 스태커",
    "Figure - Schedule a teaching": "그림 - 티칭 스케줄",
    "Figure - Setting the Position Offset": "그림 - 위치 오프셋 설정",
    "Figure - Reset": "그림 - 리셋",
    "Figure - Pause": "그림 - 일시정지",
    "Figure - Stop a task": "그림 - 작업 정지",
    "Figure - Running Location Compensation": "그림 - 위치 보정 실행",
    "Figure - Image settings": "그림 - 이미지 설정",
    "Figure - Check supplies": "그림 - 소모품 확인",
    "Figure - Managing pallet": "그림 - 팔레트 관리",
    "Figure - Manage bars": "그림 - 바 관리",
    "Figure - Manage spacers": "그림 - 스페이서 관리",
    "Figure - Create a Model File": "그림 - 모델 파일 생성",
    "Figure - Setting up loading": "그림 - 로딩 설정",
    "Figure - Preferences": "그림 - 환경설정",
    "Figure - Select Teaching": "그림 - 티칭 선택",
    "Figure - Start driving": "그림 - 구동 시작",
    "Figure - Vision Settings": "그림 - 비전 설정",
    "Figure - Position of Air Utility": "그림 - 에어 유틸리티 위치",
    "Figure - Position of Cock Push": "그림 - 콕 푸시 위치",
    "Figure - Position of Tension Adjustment": "그림 - 텐션 조정 위치",
    "Figure - Cover Position": "그림 - 커버 위치",
    "Figure - Position of Tension Block": "그림 - 텐션 블록 위치",
    "Figure - Belt Clamp Block Position": "그림 - 벨트 클램프 블록 위치",
    "Figure - Position of Belt": "그림 - 벨트 위치",
    "Figure - Position of Pallet Feeder": "그림 - 팔레트 피더 위치",
    "Figure - Position of Cover": "그림 - 커버 위치",
    "Figure - Positions of Tension Bolts": "그림 - 텐션 볼트 위치",
    "Figure - Grease Injecting Block": "그림 - 그리스 주입 블록",
    "Figure - Injector and Grease Injecting Block": "그림 - 인젝터 및 그리스 주입 블록",
    "Figure - Position of Tension adjusting": "그림 - 텐션 조정 위치",
    "Figure - Position of Belt Clamp Block": "그림 - 벨트 클램프 블록 위치",
    "Figure - Belt Clamp Block": "그림 - 벨트 클램프 블록",
    "Figure - Position of Pallet Gripper": "그림 - 팔레트 그리퍼 위치",
    "Figure - Position of Rot Gripper": "그림 - 회전 그리퍼 위치",
    "Figure - 2jaw Gripper": "그림 - 2조 그리퍼",
    "Figure - 3jaw Gripper": "그림 - 3조 그리퍼",
    "Figure - Precision Driver": "그림 - 정밀 드라이버",
    "Figure - Remove Cover": "그림 - 커버 제거",
    "Figure - Remove the Fixing Pin": "그림 - 고정 핀 제거",
    "Figure - Remove Grip Pin and Spring": "그림 - 그립 핀 및 스프링 제거",
    "Figure - Remove the Pin Holder": "그림 - 핀 홀더 제거",
    "Figure - Remove the Pin": "그림 - 핀 제거",
    "Figure - Pin Direction": "그림 - 핀 방향",
    "Figure - Reassemble Pin Holder": "그림 - 핀 홀더 재조립",
    "Figure - Pin Height Check": "그림 - 핀 높이 확인",
    "Figure - Reversal Position": "그림 - 반전 위치",
    "Figure - Center Pin Plate Position": "그림 - 센터 핀 플레이트 위치",
    "Figure - Remove the Bolt": "그림 - 볼트 제거",
    "Figure - Index Position": "그림 - 인덱스 위치",
    "Figure - Nipple Position": "그림 - 니플 위치",
    "Figure - Position of the Skewer Elevator Gripper": "그림 - 스큐어 엘리베이터 그리퍼 위치",
    "Figure - Position of the Axis": "그림 - 축 위치",
    "Figure - Down Looking Vision Robot": "그림 - 하향 비전 로봇",
    "Figure - Skewer Elevator Robot": "그림 - 스큐어 엘리베이터 로봇",
    "Figure - Pick Up Failure": "그림 - 픽업 실패",
}

DOCX_PATH = Path(r'C:\MES\wta-agents\data\wta-manuals-final\CVD\HAM-CVD_L_UL_Machine_User_Manual_en_v1.0.docx')
PARSED_MD = Path(r'C:\MES\wta-agents\data\wta_parsed\HAM-CVD_L_UL_Machine_User_Manual_en_v1.0.md')
REPORTS = Path(r'C:\MES\wta-agents\reports')
OUTPUT_DIR = Path(r'C:\MES\wta-agents\workspaces\docs-agent\cvd_html_images')

# Figure size threshold (낮게 설정 - HTML 컨텍스트 매칭이므로 크기보다 위치가 중요)
MIN_W, MIN_H = 100, 80
THUMB_MAX = 220
THUMB_QUALITY = 50
HASH_SIZE = 32


def extract_figures_from_md(md_path: Path) -> list[dict]:
    """Extract figure captions with section context from parsed markdown."""
    text = md_path.read_text(encoding='utf-8', errors='replace')
    lines = text.split('\n')

    figures = []
    current_section = ''
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('#'):
            current_section = stripped.lstrip('#').strip()
        m = re.match(r'^Figure\s*-?\s*(.+)', stripped, re.IGNORECASE)
        if m:
            caption = m.group(0).strip()
            figures.append({
                'lineno': i + 1,
                'caption': caption,
                'section': current_section,
            })
    return figures


class DocxHtmlImageExtractor:
    """DOCX -> HTML 변환 후 Figure 캡션과 이미지를 문서 순서대로 매칭."""

    def __init__(self, docx_path: Path, output_dir: Path):
        self.docx_path = docx_path
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.image_index = 0
        self.image_map: dict[str, dict] = {}  # src -> image info

    def _handle_image(self, image):
        """mammoth image handler - 이미지를 파일로 저장하고 src를 반환."""
        with image.open() as img_stream:
            img_data = img_stream.read()

        idx = self.image_index
        self.image_index += 1

        content_type = image.content_type or 'image/png'
        ext_map = {
            'image/png': '.png',
            'image/jpeg': '.jpg',
            'image/gif': '.gif',
            'image/bmp': '.bmp',
            'image/x-emf': '.emf',
            'image/x-wmf': '.wmf',
        }
        ext = ext_map.get(content_type, '.png')
        fname = f"doc_order_{idx:03d}{ext}"
        fpath = self.output_dir / fname

        with open(fpath, 'wb') as f:
            f.write(img_data)

        src = f"__IMG_{idx:03d}__"
        self.image_map[src] = {
            'index': idx,
            'filename': fname,
            'path': str(fpath),
            'content_type': content_type,
            'size': len(img_data),
        }

        return {"src": src}

    def convert(self) -> str:
        """DOCX를 HTML로 변환, 이미지는 __IMG_NNN__ placeholder src."""
        with open(self.docx_path, 'rb') as docx_file:
            result = mammoth.convert_to_html(
                docx_file,
                convert_image=mammoth.images.img_element(self._handle_image)
            )
        return result.value

    def extract_figure_image_pairs(self, html: str) -> list[dict]:
        """HTML에서 Figure 캡션과 가장 가까운 이전 이미지를 매칭.

        문서 흐름: ... <img src="__IMG_042__"> ... Figure - Front ...
        -> Figure - Front 캡션에 img 042를 매칭
        """
        # HTML을 순서대로 파싱하여 이미지와 텍스트 이벤트 추출
        events = []  # ('img', src) or ('text', content)

        class EventParser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if tag == 'img':
                    src = dict(attrs).get('src', '')
                    if src.startswith('__IMG_'):
                        events.append(('img', src))

            def handle_data(self, data):
                stripped = data.strip()
                if stripped:
                    events.append(('text', stripped))

        parser = EventParser()
        parser.feed(html)

        # Figure 캡션을 찾고, 바로 직전의 이미지와 매칭
        pairs = []
        last_img_src = None
        used_srcs: set[str] = set()

        for evt_type, evt_data in events:
            if evt_type == 'img':
                last_img_src = evt_data
            elif evt_type == 'text':
                # \u2011 = non-breaking hyphen, \u2010 = hyphen, - = regular
                m = re.match(r'^Figure\s*[\-\u2010\u2011\u2012\u2013]?\s*.+', evt_data, re.IGNORECASE)
                if m and last_img_src and last_img_src not in used_srcs:
                    img_info = self.image_map.get(last_img_src)
                    if img_info:
                        pairs.append({
                            'caption': evt_data.strip(),
                            'img': img_info,
                        })
                        used_srcs.add(last_img_src)
                        last_img_src = None  # 사용 후 리셋

        return pairs


def classify_image(img_path: str) -> bool:
    """FIGURE 크기 기준 충족 여부 확인."""
    try:
        img = Image.open(img_path)
        w, h = img.size
        return w >= MIN_W and h >= MIN_H
    except Exception:
        return False


def get_image_dims(img_path: str) -> tuple[int, int]:
    try:
        img = Image.open(img_path)
        return img.size
    except Exception:
        return (0, 0)


def pixel_hash(img_path: str) -> str:
    try:
        img = Image.open(img_path)
        small = img.resize((HASH_SIZE, HASH_SIZE), Image.LANCZOS).convert('RGB')
        return hashlib.md5(small.tobytes()).hexdigest()
    except Exception:
        return ''


def make_thumbnail_base64(img_path: str) -> str:
    """Create JPEG thumbnail and return base64 data URI."""
    img = Image.open(img_path).convert('RGB')
    img.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=THUMB_QUALITY)
    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    return f"data:image/jpeg;base64,{b64}"


def normalize_caption(cap: str) -> str:
    """Normalize dashes for comparison."""
    return re.sub(r'[\u2010\u2011\u2012\u2013\u2014]', '-', cap).strip()


def split_into_parts(figures: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split figures into User Manual / Maintenance Manual by line gap."""
    if not figures:
        return figures, []

    max_gap = 0
    max_gap_idx = -1
    for i in range(1, len(figures)):
        gap = figures[i]['lineno'] - figures[i - 1]['lineno']
        if gap > max_gap:
            max_gap = gap
            max_gap_idx = i

    if max_gap > 200 and max_gap_idx > 0:
        return figures[:max_gap_idx], figures[max_gap_idx:]

    return figures, []


def generate_html(cards: list[str], stats: dict, output_path: Path) -> None:
    """Generate the HTML catalog file."""
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>CVD L&UL Machine - 이미지 카탈로그</title>
<style>
  body {{ font-family: 'Malgun Gothic', sans-serif; background: #f5f5f5; padding: 20px; margin: 0; }}
  h1 {{ font-size: 16pt; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; margin-bottom: 4px; }}
  .info {{ color: #555; font-size: 10pt; margin-bottom: 16px; }}
  .part-title {{ color: #fff; font-size: 13pt; margin: 24px 0 12px; padding: 10px 16px;
    background: #1a237e; border-radius: 6px; grid-column: 1 / -1; }}
  .section-title {{ color: #1a237e; font-size: 11pt; margin: 16px 0 8px; padding: 6px 12px;
    background: #e8eaf6; border-left: 4px solid #1a237e; border-radius: 0 4px 4px 0; grid-column: 1 / -1; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.1);
    transition: transform 0.15s; }}
  .card:hover {{ transform: translateY(-3px); box-shadow: 0 4px 12px rgba(0,0,0,.15); }}
  .card img {{ width: 100%; height: 150px; object-fit: contain; background: #f9f9f9;
    border: 1px solid #eee; border-radius: 4px; }}
  .card.missing {{ border: 2px dashed #ff9800; }}
  .placeholder {{ height: 150px; display: flex; align-items: center; justify-content: center;
    background: #fafafa; color: #ccc; border: 1px dashed #ddd; border-radius: 4px; }}
  .seq {{ font-size: 9pt; color: #1a237e; font-weight: 700; margin-bottom: 3px; }}
  .cap {{ font-size: 9pt; font-weight: 700; color: #333; margin-top: 6px; line-height: 1.3; }}
  .fname {{ font-size: 7.5pt; color: #888; font-family: monospace; margin-top: 2px; word-break: break-all; }}
  .section {{ font-size: 7pt; color: #aaa; margin-top: 1px; }}
  .badge {{ display: inline-block; background: #4caf50; color: #fff; font-size: 8pt; padding: 2px 6px;
    border-radius: 3px; margin-left: 6px; }}
</style>
</head>
<body>
<h1>CVD L&UL Machine - 매뉴얼 이미지 카탈로그
  <span class="badge">HTML 컨텍스트 매칭</span>
</h1>
<div class="info">
  HAM-CVD_L_UL_Machine_User_Manual_en_v1.0 |
  DOCX->HTML Figure 캡션 근접 매칭 |
  {stats['matched']}/{stats['total_figs']}개 매칭 |
  미매칭 {stats['unmatched']}개
</div>
<div class="grid">
{''.join(cards)}
</div>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding='utf-8')


def main():
    print("=== CVD L&UL Machine (EN) - HTML Context Match Catalog ===\n")

    # Step 1: Extract figure captions from parsed markdown (for section context)
    print("[1/4] Extracting figure captions from parsed markdown...")
    md_figures = extract_figures_from_md(PARSED_MD)
    print(f"  Found {len(md_figures)} figure captions in markdown")

    # Step 2: Convert DOCX to HTML and extract image-figure pairs
    print("[2/4] Converting DOCX to HTML via mammoth...")
    extractor = DocxHtmlImageExtractor(DOCX_PATH, OUTPUT_DIR)
    html = extractor.convert()
    print(f"  Extracted {len(extractor.image_map)} images total")

    # Step 3: Find Figure caption + nearest image pairs from HTML
    print("[3/4] Matching Figure captions to nearest images in HTML...")
    pairs = extractor.extract_figure_image_pairs(html)
    print(f"  Found {len(pairs)} Figure-Image pairs from HTML context")

    # Check which pairs have valid FIGURE-sized images
    valid_pairs = []
    for p in pairs:
        img_path = p['img']['path']
        content_type = p['img'].get('content_type', '')
        if content_type in ('image/x-emf', 'image/x-wmf'):
            continue
        w, h = get_image_dims(img_path)
        if w >= MIN_W and h >= MIN_H:
            p['img']['width'] = w
            p['img']['height'] = h
            valid_pairs.append(p)
        else:
            print(f"  [SKIP small] {p['img']['filename']} ({w}x{h}) for '{p['caption'][:40]}'")

    print(f"  Valid FIGURE-sized pairs: {len(valid_pairs)}")

    # Step 4: Build HTML catalog
    print("[4/4] Generating HTML catalog...")

    # Build section lookup from md_figures (normalized captions)
    caption_to_section: dict[str, str] = {}
    for fig in md_figures:
        caption_to_section[normalize_caption(fig['caption'])] = fig['section']

    # Determine part split
    user_figs, maint_figs = split_into_parts(md_figures)
    user_captions = {f['caption'] for f in user_figs}
    maint_captions = {f['caption'] for f in maint_figs}

    # Build normalized lookup
    user_captions_norm = {normalize_caption(c) for c in user_captions}
    maint_captions_norm = {normalize_caption(c) for c in maint_captions}

    # Separate pairs into User/Maintenance
    user_pairs = []
    maint_pairs = []
    other_pairs = []
    for p in valid_pairs:
        cap_norm = normalize_caption(p['caption'])
        if cap_norm in user_captions_norm:
            user_pairs.append(p)
        elif cap_norm in maint_captions_norm:
            maint_pairs.append(p)
        else:
            other_pairs.append(p)

    cards: list[str] = []
    fig_idx = 0
    matched = 0

    # Dedup by pixel hash
    seen_hashes: set[str] = set()

    def add_pair_cards(pairs_list: list[dict], part_title: str):
        nonlocal fig_idx, matched
        cards.append(f'<h2 class="part-title">{part_title}</h2>')
        last_section = ''

        for p in pairs_list:
            fig_idx += 1
            cap_en = p['caption']
            cap_norm = normalize_caption(cap_en)
            # 한글 캡션 적용 (영문 원본 fallback)
            cap = CAPTION_KR.get(cap_norm, cap_en)
            img = p['img']
            section = caption_to_section.get(cap_norm, '')

            if section and section != last_section:
                cards.append(f'<h3 class="section-title">{section}</h3>')
                last_section = section

            # Dedup check
            ph = pixel_hash(img['path'])
            if ph and ph in seen_hashes:
                # Show caption but mark as duplicate reference
                thumb = make_thumbnail_base64(img['path'])
                cards.append(f"""<div class="card" style="opacity:0.6;">
  <div class="seq">Fig {fig_idx:02d} (ref)</div>
  <img src="{thumb}" alt="{cap}"/>
  <div class="cap">{cap}</div>
  <div class="fname">{img['filename']} ({img.get('width',0)}x{img.get('height',0)})</div>
  <div class="section">{section}</div>
</div>""")
                matched += 1
                continue

            if ph:
                seen_hashes.add(ph)

            thumb = make_thumbnail_base64(img['path'])
            matched += 1
            cards.append(f"""<div class="card">
  <div class="seq">Fig {fig_idx:02d}</div>
  <img src="{thumb}" alt="{cap}"/>
  <div class="cap">{cap}</div>
  <div class="fname">{img['filename']} ({img.get('width',0)}x{img.get('height',0)})</div>
  <div class="section">{section}</div>
</div>""")

    add_pair_cards(user_pairs, "Part 1: 사용자 매뉴얼")
    add_pair_cards(maint_pairs, "Part 2: 유지보수 매뉴얼")

    if other_pairs:
        add_pair_cards(other_pairs, "기타 그림")

    # Check for unmatched md figures (normalize dashes for comparison)
    matched_captions_norm = {normalize_caption(p['caption']) for p in valid_pairs}
    unmatched = [f for f in md_figures if normalize_caption(f['caption']) not in matched_captions_norm]

    if unmatched:
        cards.append(f'<h2 class="part-title">Unmatched Captions ({len(unmatched)})</h2>')
        for f in unmatched:
            fig_idx += 1
            cards.append(f"""<div class="card missing">
  <div class="seq">Fig {fig_idx:02d}</div>
  <div class="placeholder">No image matched</div>
  <div class="cap">{f['caption']}</div>
  <div class="section">{f.get('section', '')}</div>
</div>""")

    stats = {
        'matched': matched,
        'total_figs': len(md_figures),
        'unmatched': len(unmatched),
    }

    output = REPORTS / '김근형' / 'cvd_lul_en_이미지_카탈로그.html'
    generate_html(cards, stats, output)

    size_mb = output.stat().st_size / 1024 / 1024
    print(f"\n=== Results ===")
    print(f"  MD figure captions: {len(md_figures)}")
    print(f"  HTML Figure-Image pairs: {len(valid_pairs)}")
    print(f"  Matched: {matched}/{len(md_figures)}")
    print(f"  Unmatched captions: {len(unmatched)}")
    print(f"  Output: {output} ({size_mb:.1f} MB)")
    print(f"  URL: https://agent.mes-wta.com/김근형/cvd_lul_en_이미지_카탈로그")


if __name__ == '__main__':
    main()
