"""
매뉴얼 이미지 카탈로그 생성 스크립트
- 장비 매뉴얼 HTML에서 모든 figure 이미지를 추출
- 이미지 디렉토리에서 페이지 이미지 카탈로그 생성
- 구조화된 파일명 부여 (NNN_그림_X-Y_설명.ext)
- 갤러리 HTML 생성

사용법:
  # HTML 매뉴얼에서 figure 추출
  python scripts/manual-image-catalog.py reports/PVD_Unloading_Manual_KR.html

  # 이미지 디렉토리에서 페이지 카탈로그 생성
  python scripts/manual-image-catalog.py --dir "data/manual_images/1. User Manual (PVD Unloading MC)" --title "PVD Unloading"

  # 서버에 이미지 업로드 후 URL 기반 카탈로그
  python scripts/manual-image-catalog.py --dir "data/manual_images/..." --title "..." --upload
"""

import base64
import json
import os
import re
import sys
import html
import argparse
import urllib.request
from pathlib import Path


def extract_figures(html_content: str) -> list[dict]:
    """HTML에서 figure 블록의 이미지와 캡션을 추출"""
    figures = []

    # figure div 블록 추출 (figure class를 가진 div)
    pattern = re.compile(
        r'<div\s+class="figure"[^>]*>(.*?)</div>\s*</div>',
        re.DOTALL
    )
    # 더 유연한 패턴: figure div 내부의 img + figure-caption
    fig_pattern = re.compile(
        r'<div\s+class="figure"[^>]*>.*?'
        r'<img\s+[^>]*src="([^"]*)"[^>]*/?>.*?'
        r'<div\s+class="figure-caption"[^>]*>(.*?)</div>',
        re.DOTALL
    )

    for match in fig_pattern.finditer(html_content):
        src = match.group(1)
        caption = match.group(2).strip()
        # HTML 엔티티 디코딩
        caption = html.unescape(caption)
        # 태그 제거
        caption = re.sub(r'<[^>]+>', '', caption)
        figures.append({
            'src': src,
            'caption': caption,
        })

    return figures


def generate_filename(seq: int, caption: str) -> str:
    """캡션에서 구조화된 파일명 생성"""
    # "그림 X-Y 설명" 패턴 매칭
    fig_match = re.match(r'그림\s*(\d+[-\.]\d+)\s*(.*)', caption)

    if fig_match:
        fig_num = fig_match.group(1).replace('.', '-')
        desc = fig_match.group(2).strip()
        if desc:
            desc = re.sub(r'\s+', '_', desc)
            desc = re.sub(r'[\\/:*?"<>|]', '', desc)
            return f"{seq:03d}_그림_{fig_num}_{desc}"
        else:
            return f"{seq:03d}_그림_{fig_num}"
    else:
        # 그림 번호 없는 경우
        desc = re.sub(r'\s+', '_', caption)
        desc = re.sub(r'[\\/:*?"<>|]', '', desc)
        return f"{seq:03d}_{desc}"


def detect_image_ext(src: str) -> str:
    """이미지 소스에서 확장자 감지"""
    if src.startswith('data:image/'):
        mime = src.split(';')[0].split('/')[1]
        ext_map = {'jpeg': '.jpg', 'png': '.png', 'gif': '.gif', 'webp': '.webp', 'svg+xml': '.svg'}
        return ext_map.get(mime, '.png')
    else:
        ext = Path(src).suffix.lower()
        return ext if ext else '.png'


def detect_issues(src: str, caption: str) -> str | None:
    """이미지 이상 여부 감지"""
    # base64가 매우 짧으면 (빈 이미지 가능성)
    if src.startswith('data:') and len(src) < 200:
        return "이미지 데이터 너무 작음"

    # placeholder 이미지
    if 'placeholder' in caption.lower() or '삽입 위치' in caption:
        return "플레이스홀더"

    return None


def generate_gallery_html(
    title: str,
    figures: list[dict],
    source_info: str
) -> str:
    """갤러리 HTML 생성"""
    cards = []
    for i, fig in enumerate(figures, 1):
        fname = generate_filename(i, fig['caption'])
        ext = detect_image_ext(fig['src'])
        full_fname = f"{fname}{ext}"
        issue = detect_issues(fig['src'], fig['caption'])

        card_style = ' style="border: 2px solid #e74c3c;"' if issue else ''
        issue_html = f'\n      <div style="color:#e74c3c; font-size:8pt; margin-top:4px;">⚠ 확인 필요: {issue}</div>' if issue else ''

        # 이미지 src 축약 (base64가 너무 길면)
        img_src = fig['src']

        card = f"""    <div class="card"{card_style}>
      <div class="seq">{i:03d}</div>
      <img src="{img_src}" alt="{html.escape(fig['caption'])}"/>
      <div class="cap">{html.escape(fig['caption'])}</div>
      <div class="fname">{html.escape(full_fname)}</div>{issue_html}
    </div>"""
        cards.append(card)

    cards_html = '\n'.join(cards)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>{html.escape(title)} 이미지 매칭 확인</title>
<style>
  body {{ font-family: '맑은 고딕', sans-serif; background: #f5f5f5; padding: 20px; }}
  h1 {{ font-size: 14pt; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; }}
  .summary {{ color: #555; font-size: 10pt; margin-bottom: 20px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  .card img {{ width: 100%; height: 160px; object-fit: contain; background: #f9f9f9; border: 1px solid #eee; border-radius: 4px; }}
  .seq {{ font-size: 9pt; color: #aaa; margin-bottom: 4px; }}
  .cap {{ font-size: 10pt; font-weight: 700; color: #1a237e; margin-top: 8px; }}
  .fname {{ font-size: 8pt; color: #888; font-family: monospace; margin-top: 2px; word-break: break-all; }}
  .size {{ font-size: 8pt; color: #bbb; margin-top: 2px; }}
</style>
</head>
<body>
<h1>{html.escape(title)} 매뉴얼 — 이미지 매칭 확인</h1>
<div class="summary">총 {len(figures)}개 파일 | {html.escape(source_info)} | 파일명 = HTML figure-caption 기준</div>
<div class="grid">
{cards_html}
</div>
</body>
</html>"""


def upload_image(file_path: str) -> str | None:
    """이미지를 agent 서버에 업로드하고 URL 반환"""
    try:
        boundary = '----FormBoundary7MA4YWxkTrZu0gW'
        filename = os.path.basename(file_path)
        ext = Path(file_path).suffix.lower()
        mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif'}
        content_type = mime_map.get(ext, 'application/octet-stream')

        with open(file_path, 'rb') as f:
            file_data = f.read()

        body = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f'Content-Type: {content_type}\r\n\r\n'
        ).encode() + file_data + f'\r\n--{boundary}--\r\n'.encode()

        req = urllib.request.Request(
            'http://localhost:5555/api/upload',
            data=body,
            headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            if result.get('url'):
                return f"https://agent.mes-wta.com{result['url']}"
    except Exception as e:
        print(f"  업로드 실패 ({filename}): {e}")
    return None


def make_thumbnail_b64(file_path: Path, max_size: int = 300) -> str:
    """이미지를 썸네일로 축소하여 base64 반환 (PIL 없이 원본 사용)"""
    try:
        # PIL 있으면 썸네일 생성
        from PIL import Image
        import io
        img = Image.open(file_path)
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        buf = io.BytesIO()
        fmt = 'JPEG' if file_path.suffix.lower() in ['.jpg', '.jpeg'] else 'PNG'
        if fmt == 'JPEG' and img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.save(buf, format=fmt, quality=60)
        b64 = base64.b64encode(buf.getvalue()).decode()
        mime = 'jpeg' if fmt == 'JPEG' else 'png'
        return f"data:image/{mime};base64,{b64}"
    except ImportError:
        # PIL 없으면 원본 base64 (파일 크기 큰 경우 주의)
        with open(file_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()
        ext = file_path.suffix.lower().replace('.', '')
        if ext == 'jpg':
            ext = 'jpeg'
        return f"data:image/{ext};base64,{b64}"


def scan_directory(dir_path: Path, upload: bool = False) -> list[dict]:
    """이미지 디렉토리에서 파일 목록을 스캔하여 figure 리스트 생성"""
    image_exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
    files = []
    for f in sorted(dir_path.iterdir()):
        if f.is_file() and f.suffix.lower() in image_exts:
            files.append(f)

    # 자연 정렬 (page_2 < page_10)
    def natural_key(p: Path):
        parts = re.split(r'(\d+)', p.stem)
        return [int(x) if x.isdigit() else x.lower() for x in parts]

    files.sort(key=natural_key)

    figures = []
    for i, f in enumerate(files):
        caption = f.stem  # 파일명을 캡션으로
        if upload:
            print(f"  업로드 중 ({i+1}/{len(files)}): {f.name}")
            url = upload_image(str(f))
            if url:
                src = url
            else:
                src = make_thumbnail_b64(f)
        else:
            # 썸네일 base64로 인라인
            print(f"  처리 중 ({i+1}/{len(files)}): {f.name}")
            src = make_thumbnail_b64(f)

        figures.append({
            'src': src,
            'caption': caption,
        })

    return figures


def main():
    parser = argparse.ArgumentParser(description='매뉴얼 이미지 카탈로그 생성')
    parser.add_argument('input', nargs='?', help='매뉴얼 HTML 파일 경로')
    parser.add_argument('--dir', '-d', help='이미지 디렉토리 경로 (HTML 대신 디렉토리 스캔)')
    parser.add_argument('--output', '-o', help='출력 파일명 (기본: {장비명}_이미지_매칭_확인.html)')
    parser.add_argument('--title', '-t', help='장비명/매뉴얼명')
    parser.add_argument('--upload', action='store_true', help='이미지를 agent 서버에 업로드')
    args = parser.parse_args()

    if args.dir:
        # 디렉토리 모드
        dir_path = Path(args.dir)
        if not dir_path.is_dir():
            print(f"오류: 디렉토리를 찾을 수 없습니다: {dir_path}")
            sys.exit(1)

        title = args.title or dir_path.name
        print(f"디렉토리 스캔: {dir_path}")
        print(f"제목: {title}")
        if args.upload:
            print("서버 업로드 모드 활성화")

        figures = scan_directory(dir_path, upload=args.upload)
        source_info = dir_path.name
    elif args.input:
        # HTML 모드
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"오류: 파일을 찾을 수 없습니다: {input_path}")
            sys.exit(1)

        print(f"매뉴얼 읽는 중: {input_path}")
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        title = args.title
        if not title:
            title_match = re.search(r'<title>(.*?)</title>', content)
            if title_match:
                title = title_match.group(1).split('—')[0].strip()
                title = title.replace(' User Manual', '').strip()
            else:
                title = input_path.stem

        figures = extract_figures(content)
        source_info = input_path.name
    else:
        parser.print_help()
        sys.exit(1)

    print(f"제목: {title}")
    print(f"추출된 이미지: {len(figures)}개")

    if not figures:
        print("경고: 이미지를 찾을 수 없습니다.")
        sys.exit(1)

    # 파일명 미리보기
    for i, fig in enumerate(figures, 1):
        fname = generate_filename(i, fig['caption'])
        ext = detect_image_ext(fig['src'])
        issue = detect_issues(fig['src'], fig['caption'])
        marker = " ⚠" if issue else ""
        print(f"  {i:03d}: {fname}{ext}{marker}")

    # 출력 경로
    if args.output:
        output_path = Path(args.output)
    else:
        safe_name = re.sub(r'\s+', '_', title).lower()
        safe_name = re.sub(r'[\\/:*?"<>|(),#]', '', safe_name)
        output_path = Path(r'C:\MES\wta-agents\reports') / f"{safe_name}_이미지_매칭_확인.html"

    # 갤러리 HTML 생성
    gallery = generate_gallery_html(title, figures, source_info)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(gallery)

    print(f"\n갤러리 저장: {output_path}")
    print(f"총 {len(figures)}개 이미지 카탈로그 생성 완료")


if __name__ == '__main__':
    main()
