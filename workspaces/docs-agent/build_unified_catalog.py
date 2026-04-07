"""
WTA 장비 이미지 통합 카탈로그
장비별/언어별 탭으로 전환하는 단일 HTML 파일 생성
두 가지 처리 모드:
  - mammoth: DOCX -> HTML -> Figure 캡션 컨텍스트 매칭
  - image_folder: page_NNN_full.png 이미지 + MD Figure 순차 매칭
"""
import re
import base64
import hashlib
import io
import os
from pathlib import Path
from html.parser import HTMLParser
from PIL import Image

REPORTS = Path(r'C:\MES\wta-agents\reports')
OUTPUT_DIR_BASE = Path(r'C:\MES\wta-agents\workspaces\docs-agent')

THUMB_MAX = 220
THUMB_QUALITY = 50
HASH_SIZE = 32
MIN_W, MIN_H = 100, 80

# ========== 장비 설정 ==========
EQUIPMENT_LIST = [
    {
        'tab_name': 'CVD L&UL (EN)',
        'tab_id': 'cvd-en',
        'mode': 'mammoth',
        'docx': Path(r'C:\MES\wta-agents\data\wta-manuals-final\CVD\HAM-CVD_L_UL_Machine_User_Manual_en_v1.0.docx'),
        'parsed_md': Path(r'C:\MES\wta-agents\data\wta_parsed\HAM-CVD_L_UL_Machine_User_Manual_en_v1.0.md'),
        'img_dir_name': 'cvd_html_images',
        'captions_kr': {
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
        },
    },
    {
        'tab_name': 'PVD Loading (EN)',
        'tab_id': 'pvd-load-en',
        'mode': 'image_folder',
        'image_dir': Path(r'C:\MES\wta-agents\data\manual_images\HAM-PVD Loading User Manual en_v1.2'),
        'parsed_md': Path(r'C:\MES\wta-agents\data\wta_parsed\HAM-PVD_Loading_User_Manual_en_v1.2.md'),
        'captions_kr': {},
    },
    {
        'tab_name': 'PVD Unloading (EN)',
        'tab_id': 'pvd-ul-en',
        'mode': 'mammoth',
        'docx': Path(r'C:\MES\wta-agents\data\wta-manuals-final\PVD\HAM-PVD_Unloading_User_Manual_en_v1.3_Copied_00.docx'),
        'parsed_md': Path(r'C:\MES\wta-agents\data\wta_parsed\HAM-PVD_Unloading_User_Manual_en_v1.3.md'),
        'img_dir_name': 'pvd_ul_html_images',
        'captions_kr': {},
    },
    {
        'tab_name': 'Labeling (KR)',
        'tab_id': 'labeling-kr',
        'mode': 'mammoth',
        'docx': Path(r'C:\MES\wta-agents\data\wta-manuals-final\Labeling\HAM-Labeling_User_Manual_v1.1_KR.docx'),
        'parsed_md': Path(r'C:\MES\wta-agents\data\manual_parsed\HAM-Labeling_User_Manual_v1.1_KR.md'),
        'img_dir_name': 'labeling_html_images',
        'captions_kr': {},
    },
    {
        'tab_name': 'YG1 CVD (KR)',
        'tab_id': 'yg1-cvd-kr',
        'mode': 'mammoth',
        'docx': Path(r'C:\MES\wta-agents\data\wta-manuals-final\CVD\WT1724_YG1_CVD_Manual.docx'),
        'parsed_md': Path(r'C:\MES\wta-agents\data\wta_parsed\WT1724_YG1_CVD_Manual.md'),
        'img_dir_name': 'yg1_cvd_html_images',
        'captions_kr': {},
    },
    {
        'tab_name': 'Double Side (KR)',
        'tab_id': 'double-side-kr',
        'mode': 'mammoth',
        'docx': Path(r'C:\MES\wta-agents\data\wta-manuals-final\Double_Side_Grinder\Double_Side_Handler_Manual_Revised.docx'),
        'parsed_md': Path(r'C:\MES\wta-agents\data\manual_parsed\Double_Side_Handler_Manual_Revised.md'),
        'img_dir_name': 'double_side_html_images',
        'captions_kr': {},
    },
    {
        'tab_name': 'Press Handler (KR)',
        'tab_id': 'press-kr',
        'mode': 'mammoth',
        'docx': Path(r'C:\MES\wta-agents\data\wta-manuals-final\Press\PressHandler.docx'),
        'parsed_md': Path(r'C:\MES\wta-agents\data\wta_parsed\1._User_Manual_Press_Handler_MC.md'),
        'img_dir_name': 'press_html_images',
        'captions_kr': {},
    },
]


def normalize_caption(cap: str) -> str:
    return re.sub(r'[\u2010\u2011\u2012\u2013\u2014]', '-', cap).strip()


def extract_figures_from_md(md_path: Path) -> list[dict]:
    """MD에서 Figure/그림 캡션 추출."""
    text = md_path.read_text(encoding='utf-8', errors='replace')
    lines = text.split('\n')
    figures = []
    current_section = ''
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('#'):
            current_section = stripped.lstrip('#').strip()
        m = re.match(r'^(Figure|그림)\s*[\-\u2010\u2011\u2012\u2013]?\s*.+', stripped, re.IGNORECASE)
        if m:
            figures.append({
                'lineno': i + 1,
                'caption': stripped,
                'section': current_section,
            })
    return figures


def extract_sections_from_md(md_path: Path) -> list[dict]:
    """MD에서 섹션 헤더 추출 (Figure 캡션 없는 매뉴얼용)."""
    text = md_path.read_text(encoding='utf-8', errors='replace')
    sections = []
    for line in text.split('\n'):
        stripped = line.strip()
        if stripped.startswith('#'):
            level = len(stripped) - len(stripped.lstrip('#'))
            title = stripped.lstrip('#').strip()
            if title:
                sections.append({'level': level, 'title': title})
    return sections


# ========== mammoth 처리 ==========
def extract_images_via_mammoth(docx_path: Path, output_dir: Path) -> tuple[str, dict]:
    import mammoth
    output_dir.mkdir(parents=True, exist_ok=True)
    image_index = [0]
    image_map = {}

    def handle_image(image):
        with image.open() as s:
            data = s.read()
        idx = image_index[0]
        image_index[0] += 1
        ct = image.content_type or 'image/png'
        ext_map = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/gif': '.gif',
                    'image/bmp': '.bmp', 'image/x-emf': '.emf', 'image/x-wmf': '.wmf'}
        ext = ext_map.get(ct, '.png')
        fname = f"doc_{idx:03d}{ext}"
        fpath = output_dir / fname
        with open(fpath, 'wb') as f:
            f.write(data)
        src = f"__IMG_{idx:03d}__"
        image_map[src] = {'index': idx, 'filename': fname, 'path': str(fpath), 'content_type': ct}
        return {"src": src}

    with open(docx_path, 'rb') as f:
        result = mammoth.convert_to_html(f, convert_image=mammoth.images.img_element(handle_image))
    return result.value, image_map


def find_figure_image_pairs_mammoth(html: str, image_map: dict) -> list[dict]:
    """HTML에서 Figure/그림 캡션과 직전 이미지 매칭."""
    events = []

    class P(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag == 'img':
                src = dict(attrs).get('src', '')
                if src.startswith('__IMG_'):
                    events.append(('img', src))
        def handle_data(self, data):
            s = data.strip()
            if s:
                events.append(('text', s))

    P().feed(html)

    pairs = []
    last_img = None
    used = set()
    for t, d in events:
        if t == 'img':
            last_img = d
        elif t == 'text':
            m = re.match(r'^(Figure|그림)\s*[\-\u2010\u2011\u2012\u2013]?\s*.+', d, re.IGNORECASE)
            if m and last_img and last_img not in used:
                info = image_map.get(last_img)
                if info:
                    pairs.append({'caption': d.strip(), 'img': info})
                    used.add(last_img)
                    last_img = None
    return pairs


def find_all_images_mammoth(html: str, image_map: dict) -> list[dict]:
    """Figure 캡션 없는 매뉴얼: 모든 이미지를 순서대로 추출, 근처 텍스트를 캡션으로."""
    events = []

    class P(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag == 'img':
                src = dict(attrs).get('src', '')
                if src.startswith('__IMG_'):
                    events.append(('img', src))
        def handle_data(self, data):
            s = data.strip()
            if s and len(s) > 2:
                events.append(('text', s))

    P().feed(html)

    pairs = []
    last_texts = []
    for t, d in events:
        if t == 'text':
            last_texts.append(d)
            if len(last_texts) > 3:
                last_texts.pop(0)
        elif t == 'img':
            info = image_map.get(d)
            if info:
                # nearest text before image as context
                context = last_texts[-1] if last_texts else ''
                if len(context) > 80:
                    context = context[:77] + '...'
                pairs.append({'caption': context, 'img': info})
    return pairs


# ========== image_folder 처리 ==========
def process_image_folder(equip: dict) -> list[dict]:
    """page_NNN_full.png 이미지를 순서대로 읽고 MD Figure 캡션과 순차 매칭."""
    img_dir = equip['image_dir']
    md_figs = extract_figures_from_md(equip['parsed_md'])

    # page_NNN_full.png 정렬
    exts = {'.png', '.jpg', '.jpeg'}
    files = sorted(
        [f for f in img_dir.iterdir() if f.suffix.lower() in exts],
        key=lambda f: int(re.search(r'(\d+)', f.stem).group(1)) if re.search(r'(\d+)', f.stem) else 0
    )

    # 크기 필터
    valid_files = []
    for f in files:
        try:
            w, h = Image.open(f).size
            if w >= MIN_W and h >= MIN_H:
                valid_files.append({'path': str(f), 'filename': f.name, 'width': w, 'height': h})
        except Exception:
            pass

    # Figure 캡션과 순차 매칭
    pairs = []
    fig_idx = 0
    for img_info in valid_files:
        cap = ''
        section = ''
        if fig_idx < len(md_figs):
            cap = md_figs[fig_idx]['caption']
            section = md_figs[fig_idx]['section']
            fig_idx += 1
        else:
            cap = f"Image {len(pairs)+1}"
        pairs.append({
            'caption': cap,
            'img': img_info,
            'section': section,
        })

    return pairs


# ========== 공통 유틸 ==========
def make_thumb_b64(path: str) -> str:
    img = Image.open(path).convert('RGB')
    img.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=THUMB_QUALITY)
    return base64.b64encode(buf.getvalue()).decode('ascii')


def get_dims(path: str) -> tuple[int, int]:
    try:
        return Image.open(path).size
    except Exception:
        return (0, 0)


def build_equipment_cards(equip: dict) -> tuple[list[str], dict]:
    """하나의 장비에 대해 카드 HTML 리스트와 통계를 반환."""
    mode = equip.get('mode', 'mammoth')
    tab_name = equip['tab_name']
    print(f"\n  [{mode}] {tab_name}")

    captions_kr = equip.get('captions_kr', {})
    md_figs = extract_figures_from_md(equip['parsed_md'])
    has_figure_captions = len(md_figs) > 0
    print(f"    MD figure captions: {len(md_figs)}")

    if mode == 'image_folder':
        all_pairs = process_image_folder(equip)
        valid = all_pairs
        print(f"    Image folder pairs: {len(valid)}")

    elif mode == 'mammoth':
        img_dir = OUTPUT_DIR_BASE / equip['img_dir_name']
        html, image_map = extract_images_via_mammoth(equip['docx'], img_dir)
        print(f"    DOCX images extracted: {len(image_map)}")

        if has_figure_captions:
            pairs = find_figure_image_pairs_mammoth(html, image_map)
        else:
            pairs = find_all_images_mammoth(html, image_map)

        # Filter: skip EMF/WMF, check size
        valid = []
        for p in pairs:
            ct = p['img'].get('content_type', '')
            if ct in ('image/x-emf', 'image/x-wmf'):
                continue
            w, h = get_dims(p['img']['path'])
            if w >= MIN_W and h >= MIN_H:
                p['img']['width'] = w
                p['img']['height'] = h
                valid.append(p)
        print(f"    Valid pairs: {len(valid)}")

    # Part 분류 (Figure 캡션 있을 때만)
    if has_figure_captions and md_figs:
        max_gap = 0
        max_idx = -1
        for i in range(1, len(md_figs)):
            gap = md_figs[i]['lineno'] - md_figs[i-1]['lineno']
            if gap > max_gap:
                max_gap = gap
                max_idx = i
        if max_gap > 200 and max_idx > 0:
            user_caps = {normalize_caption(f['caption']) for f in md_figs[:max_idx]}
            maint_caps = {normalize_caption(f['caption']) for f in md_figs[max_idx:]}
        else:
            user_caps = {normalize_caption(f['caption']) for f in md_figs}
            maint_caps = set()
        cap_to_section = {normalize_caption(f['caption']): f['section'] for f in md_figs}
    else:
        user_caps = set()
        maint_caps = set()
        cap_to_section = {}

    cards = []
    fig_idx = 0
    matched = 0
    seen = set()

    def add_card(p, title_needed=None):
        nonlocal fig_idx, matched
        if title_needed:
            cards.append(f'<h2 class="part-title">{title_needed}</h2>')

        fig_idx += 1
        cap_en = p['caption']
        cn = normalize_caption(cap_en)
        cap = captions_kr.get(cn, cap_en)
        sec = p.get('section', '') or cap_to_section.get(cn, '')
        img = p['img']

        try:
            ph = hashlib.md5(
                Image.open(img['path']).resize((HASH_SIZE, HASH_SIZE), Image.LANCZOS).convert('RGB').tobytes()
            ).hexdigest()
        except Exception:
            ph = ''

        is_dup = ph in seen if ph else False
        if ph:
            seen.add(ph)

        try:
            thumb = f"data:image/jpeg;base64,{make_thumb_b64(img['path'])}"
        except Exception:
            return  # 썸네일 생성 실패 시 스킵

        matched += 1
        opacity = ' style="opacity:0.6;"' if is_dup else ''
        ref = ' (ref)' if is_dup else ''
        w = img.get('width', 0)
        h = img.get('height', 0)
        fname = img.get('filename', '')
        cards.append(f"""<div class="card"{opacity}>
  <div class="seq">Fig {fig_idx:02d}{ref}</div>
  <img src="{thumb}" alt="{cap}"/>
  <div class="cap">{cap}</div>
  <div class="fname">{fname} ({w}x{h})</div>
</div>""")

    if has_figure_captions:
        user_pairs = []
        maint_pairs = []
        other_pairs = []
        for p in valid:
            cn = normalize_caption(p['caption'])
            if cn in user_caps:
                user_pairs.append(p)
            elif cn in maint_caps:
                maint_pairs.append(p)
            else:
                other_pairs.append(p)

        if user_pairs:
            cards.append('<h2 class="part-title">Part 1: 사용자 매뉴얼</h2>')
            last_sec = ''
            for p in user_pairs:
                cn = normalize_caption(p['caption'])
                sec = cap_to_section.get(cn, '')
                if sec and sec != last_sec:
                    cards.append(f'<h3 class="section-title">{sec}</h3>')
                    last_sec = sec
                add_card(p)
        if maint_pairs:
            cards.append('<h2 class="part-title">Part 2: 유지보수 매뉴얼</h2>')
            last_sec = ''
            for p in maint_pairs:
                cn = normalize_caption(p['caption'])
                sec = cap_to_section.get(cn, '')
                if sec and sec != last_sec:
                    cards.append(f'<h3 class="section-title">{sec}</h3>')
                    last_sec = sec
                add_card(p)
        if other_pairs:
            cards.append('<h2 class="part-title">기타</h2>')
            for p in other_pairs:
                add_card(p)
    else:
        # Figure 캡션 없는 매뉴얼: 전체 이미지를 순차 표시
        cards.append(f'<h2 class="part-title">{tab_name} - 전체 이미지</h2>')
        for p in valid:
            add_card(p)

    stats = {'matched': matched, 'total': len(md_figs) if md_figs else matched}
    return cards, stats


def main():
    print("=== WTA 장비 통합 이미지 카탈로그 ===")

    all_tabs = []
    for equip in EQUIPMENT_LIST:
        try:
            cards, stats = build_equipment_cards(equip)
            all_tabs.append({
                'tab_name': equip['tab_name'],
                'tab_id': equip['tab_id'],
                'cards_html': '\n'.join(cards),
                'stats': stats,
            })
            print(f"    -> {stats['matched']}/{stats['total']} matched")
        except Exception as e:
            print(f"    ERROR: {e}")

    # Tab buttons
    tab_buttons = []
    for i, t in enumerate(all_tabs):
        active = ' active' if i == 0 else ''
        tab_buttons.append(
            f'<button class="tab-btn{active}" data-tab="{t["tab_id"]}">'
            f'{t["tab_name"]} ({t["stats"]["matched"]})</button>'
        )

    # Tab contents
    tab_contents = []
    for i, t in enumerate(all_tabs):
        display = 'grid' if i == 0 else 'none'
        tab_contents.append(
            f'<div id="tab-{t["tab_id"]}" class="tab-content grid" style="display:{display};">\n'
            f'{t["cards_html"]}\n</div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>WTA 장비 이미지 카탈로그</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Malgun Gothic', 'Pretendard Variable', sans-serif; background: #f5f5f5; padding: 20px; margin: 0; }}
  h1 {{ font-size: 16pt; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; margin-bottom: 4px; }}
  .subtitle {{ font-size: 9pt; color: #666; margin-bottom: 16px; }}
  .tab-bar {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 16px; position: sticky; top: 0; background: #f5f5f5; padding: 8px 0; z-index: 10; }}
  .tab-btn {{ padding: 8px 16px; border: 1px solid #ccc; background: #fff; border-radius: 6px 6px 0 0;
    cursor: pointer; font-size: 10pt; font-family: 'Malgun Gothic', sans-serif; transition: all 0.2s; }}
  .tab-btn.active {{ background: #1a237e; color: #fff; border-color: #1a237e; }}
  .tab-btn:hover:not(.active) {{ background: #e8eaf6; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }}
  .part-title {{ color: #fff; font-size: 13pt; margin: 16px 0 8px; padding: 10px 16px;
    background: #1a237e; border-radius: 6px; grid-column: 1 / -1; }}
  .section-title {{ color: #1a237e; font-size: 11pt; margin: 12px 0 6px; padding: 6px 12px;
    background: #e8eaf6; border-left: 4px solid #1a237e; border-radius: 0 4px 4px 0; grid-column: 1 / -1; }}
  .card {{ background: #fff; border-radius: 8px; padding: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.1);
    transition: transform 0.15s; }}
  .card:hover {{ transform: translateY(-3px); box-shadow: 0 4px 12px rgba(0,0,0,.15); }}
  .card img {{ width: 100%; height: 150px; object-fit: contain; background: #f9f9f9;
    border: 1px solid #eee; border-radius: 4px; cursor: pointer; }}
  .seq {{ font-size: 9pt; color: #1a237e; font-weight: 700; margin-bottom: 3px; }}
  .cap {{ font-size: 9pt; font-weight: 700; color: #333; margin-top: 6px; line-height: 1.3; }}
  .fname {{ font-size: 7.5pt; color: #888; font-family: monospace; margin-top: 2px; word-break: break-all; }}
  .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 100; justify-content: center; align-items: center; cursor: pointer; }}
  .modal img {{ max-width: 90%; max-height: 90%; object-fit: contain; }}
  .modal.show {{ display: flex; }}
  .total-stats {{ font-size: 10pt; color: #333; margin-bottom: 12px; padding: 8px 12px; background: #e8eaf6; border-radius: 6px; }}
</style>
</head>
<body>
<h1>WTA 장비 매뉴얼 이미지 카탈로그</h1>
<p class="subtitle">(주)윈텍오토메이션 생산관리팀 | {len(all_tabs)}개 장비 | 총 {sum(t['stats']['matched'] for t in all_tabs)}개 이미지</p>
<div class="tab-bar">
{''.join(tab_buttons)}
</div>
{''.join(tab_contents)}
<div id="modal" class="modal" onclick="this.classList.remove('show')">
  <img id="modal-img" src="" alt=""/>
</div>
<script>
document.querySelectorAll('.tab-btn').forEach(btn => {{
  btn.addEventListener('click', function() {{
    document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.getElementById('tab-' + this.dataset.tab).style.display = 'grid';
    this.classList.add('active');
  }});
}});
document.querySelectorAll('.card img').forEach(img => {{
  img.addEventListener('click', function(e) {{
    e.stopPropagation();
    document.getElementById('modal-img').src = this.src;
    document.getElementById('modal').classList.add('show');
  }});
}});
</script>
</body>
</html>"""

    output = REPORTS / '\uae40\uadfc\ud615' / 'wta_\uc7a5\ube44_\uc774\ubbf8\uc9c0_\uce74\ud0c8\ub85c\uadf8.html'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding='utf-8')
    size_mb = output.stat().st_size / 1024 / 1024
    print(f"\nSaved: {output} ({size_mb:.1f} MB)")
    print(f"URL: https://agent.mes-wta.com/wta_\uc7a5\ube44_\uc774\ubbf8\uc9c0_\uce74\ud0c8\ub85c\uadf8")


if __name__ == '__main__':
    main()
