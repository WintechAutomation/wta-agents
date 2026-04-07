"""
Confluence RAG 파이프라인 2단계: HTML 원문에서 파생 데이터 생성

입력: reports/MAX/confluence-경상연구개발/{주제}/{pageId}-{title}/index.html
출력 (동일 폴더):
  - content.md          : 본문 MD (이미지 인라인 참조 포함)
  - meta.json           : 페이지 메타 (pageId, title, breadcrumb, source_url, image_count 등)
  - image-meta.json     : 이미지별 메타 (filename, alt, caption, parent_section, context_before/after)
"""
import json
import re
import sys
from pathlib import Path
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding='utf-8', errors='replace')


class ConfluenceHTMLParser(HTMLParser):
    """HTML → 구조화된 블록 리스트로 변환"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []          # [(type, text, extra)]
        self.current_text = []
        self.tag_stack = []
        self.in_breadcrumb = False
        self.breadcrumb = ''
        self.in_title = False
        self.title = ''
        self.in_meta = False
        self.meta_text = []
        self.in_source = False
        self.source_url = ''
        self.in_figcaption = False
        self.figcaption_text = []
        self.last_figcaption = ''
        self.list_depth = 0
        self.in_table = False
        self.in_cell = False
        self.cell_text = []
        self.row_cells = []
        self.table_rows = []

    def _flush_text(self):
        if self.current_text:
            t = ''.join(self.current_text).strip()
            if t:
                self.blocks.append(('text', t, None))
            self.current_text = []

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        cls = attrs_d.get('class', '')

        if tag == 'div' and 'breadcrumb' in cls:
            self.in_breadcrumb = True
            return
        if tag == 'div' and 'meta' in cls:
            self.in_meta = True
            return
        if tag == 'p' and 'source-link' in cls:
            self.in_source = True
            return
        if tag == 'a' and self.in_source:
            href = attrs_d.get('href', '')
            if href.startswith('http'):
                self.source_url = href
            return

        if tag == 'h1':
            self._flush_text()
            self.in_title = True
            self.tag_stack.append('h1')
            return
        if tag in ('h2', 'h3', 'h4', 'h5'):
            self._flush_text()
            self.tag_stack.append(tag)
            return
        if tag == 'p':
            self._flush_text()
            self.tag_stack.append('p')
            return
        if tag == 'br':
            self.current_text.append('\n')
            return
        if tag in ('ul', 'ol'):
            self._flush_text()
            self.list_depth += 1
            self.tag_stack.append(tag)
            return
        if tag == 'li':
            self._flush_text()
            indent = '  ' * max(0, self.list_depth - 1)
            self.current_text.append(f'\n{indent}- ')
            return
        if tag == 'strong' or tag == 'b':
            self.current_text.append('**')
            return
        if tag == 'em' or tag == 'i':
            self.current_text.append('*')
            return
        if tag == 'code':
            self.current_text.append('`')
            return
        if tag == 'img':
            # image block
            src = attrs_d.get('src', '')
            alt = attrs_d.get('alt', '')
            filename = src.split('/')[-1] if src else ''
            # 근접 heading 기록
            parent_section = ''
            for b in reversed(self.blocks):
                if b[0] in ('h1', 'h2', 'h3', 'h4', 'h5'):
                    parent_section = b[1]
                    break
            self._flush_text()
            self.blocks.append((
                'img',
                filename,
                {'alt': alt, 'src': src, 'parent_section': parent_section}
            ))
            return
        if tag == 'figcaption':
            self.in_figcaption = True
            self.figcaption_text = []
            return
        if tag == 'table':
            self._flush_text()
            self.in_table = True
            self.table_rows = []
            return
        if tag == 'tr' and self.in_table:
            self.row_cells = []
            return
        if tag in ('td', 'th') and self.in_table:
            self.in_cell = True
            self.cell_text = []
            return

    def handle_endtag(self, tag):
        if tag == 'div':
            if self.in_breadcrumb:
                self.in_breadcrumb = False
            if self.in_meta:
                self.in_meta = False
            return
        if tag == 'p' and self.in_source:
            self.in_source = False
            return
        if tag == 'h1' and self.in_title:
            self.in_title = False
            t = ''.join(self.current_text).strip()
            self.title = t
            self.blocks.append(('h1', t, None))
            self.current_text = []
            if self.tag_stack and self.tag_stack[-1] == 'h1':
                self.tag_stack.pop()
            return
        if tag in ('h2', 'h3', 'h4', 'h5'):
            t = ''.join(self.current_text).strip()
            if t:
                self.blocks.append((tag, t, None))
            self.current_text = []
            if self.tag_stack and self.tag_stack[-1] == tag:
                self.tag_stack.pop()
            return
        if tag == 'p':
            t = ''.join(self.current_text).strip()
            if t:
                self.blocks.append(('p', t, None))
            self.current_text = []
            if self.tag_stack and self.tag_stack[-1] == 'p':
                self.tag_stack.pop()
            return
        if tag in ('ul', 'ol'):
            self._flush_text()
            self.list_depth = max(0, self.list_depth - 1)
            if self.tag_stack and self.tag_stack[-1] == tag:
                self.tag_stack.pop()
            return
        if tag == 'strong' or tag == 'b':
            self.current_text.append('**')
            return
        if tag == 'em' or tag == 'i':
            self.current_text.append('*')
            return
        if tag == 'code':
            self.current_text.append('`')
            return
        if tag == 'figcaption':
            self.in_figcaption = False
            cap = ''.join(self.figcaption_text).strip()
            self.last_figcaption = cap
            # 마지막 img 블록에 caption 병합
            for i in range(len(self.blocks) - 1, -1, -1):
                if self.blocks[i][0] == 'img':
                    extra = self.blocks[i][2] or {}
                    extra['caption'] = cap
                    self.blocks[i] = ('img', self.blocks[i][1], extra)
                    break
            return
        if tag == 'td' or tag == 'th':
            self.in_cell = False
            self.row_cells.append(''.join(self.cell_text).strip())
            self.cell_text = []
            return
        if tag == 'tr' and self.in_table:
            if self.row_cells:
                self.table_rows.append(self.row_cells)
            self.row_cells = []
            return
        if tag == 'table':
            self.in_table = False
            if self.table_rows:
                self.blocks.append(('table', '', {'rows': self.table_rows}))
            self.table_rows = []
            return

    def handle_data(self, data):
        if self.in_breadcrumb:
            self.breadcrumb += data
            return
        if self.in_meta:
            self.meta_text.append(data)
            return
        if self.in_source:
            return
        if self.in_figcaption:
            self.figcaption_text.append(data)
            return
        if self.in_cell:
            self.cell_text.append(data)
            return
        self.current_text.append(data)


def blocks_to_md(blocks):
    """구조화 블록 → Markdown 문자열"""
    lines = []
    for btype, text, extra in blocks:
        if btype == 'h1':
            lines.append(f'# {text}\n')
        elif btype == 'h2':
            lines.append(f'\n## {text}\n')
        elif btype == 'h3':
            lines.append(f'\n### {text}\n')
        elif btype == 'h4':
            lines.append(f'\n#### {text}\n')
        elif btype == 'h5':
            lines.append(f'\n##### {text}\n')
        elif btype == 'p':
            lines.append(f'{text}\n')
        elif btype == 'text':
            lines.append(f'{text}\n')
        elif btype == 'img':
            filename = text
            alt = (extra or {}).get('alt', '')
            caption = (extra or {}).get('caption', '')
            label = caption or alt or filename
            lines.append(f'\n![{label}](images/{filename})\n')
            if caption and caption != filename:
                lines.append(f'*{caption}*\n')
        elif btype == 'table':
            rows = (extra or {}).get('rows', [])
            if not rows:
                continue
            # MD table
            cols = len(rows[0])
            lines.append('')
            lines.append('| ' + ' | '.join(c.replace('|', '\\|').replace('\n', ' ') for c in rows[0]) + ' |')
            lines.append('| ' + ' | '.join(['---'] * cols) + ' |')
            for row in rows[1:]:
                padded = row + [''] * (cols - len(row))
                lines.append('| ' + ' | '.join(c.replace('|', '\\|').replace('\n', ' ') for c in padded[:cols]) + ' |')
            lines.append('')
    return '\n'.join(lines)


def _strip_tags(s: str) -> str:
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'&nbsp;', ' ', s)
    s = re.sub(r'&lt;', '<', s)
    s = re.sub(r'&gt;', '>', s)
    s = re.sub(r'&amp;', '&', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def extract_image_contexts_from_html(html: str, page_title: str):
    """HTML 원문에서 이미지 태그 직접 탐색 + 주변 500자 문맥 추출.

    테이블 셀 내 이미지도 표 구조 맥락을 일부 포함하므로 HTML 레벨에서 처리.
    상위 헤딩(h1~h5) 추적 + 이미지 바로 앞 표제(td/th 첫 컬럼) 추적.
    """
    # 헤딩 위치 인덱스
    headings = []  # [(pos, level, text)]
    for m in re.finditer(r'<h([1-5])[^>]*>(.*?)</h\1>', html, re.DOTALL):
        headings.append((m.start(), int(m.group(1)), _strip_tags(m.group(2))))

    def parent_section(pos: int) -> str:
        last = ''
        for hpos, _lv, htext in headings:
            if hpos < pos:
                last = htext
            else:
                break
        return last or page_title

    # 이미지 태그 탐색 (figure 블록 우선 — figcaption 확보용)
    image_metas = []

    # figure 블록 단위로 먼저
    figure_pattern = re.compile(
        r'<figure[^>]*>(.*?)</figure>', re.DOTALL)
    img_pattern = re.compile(
        r'<img\s+([^>]*?)/?>', re.IGNORECASE)
    figcap_pattern = re.compile(
        r'<figcaption[^>]*>(.*?)</figcaption>', re.DOTALL)

    seen_positions = set()

    # figure 내부 img
    for fm in figure_pattern.finditer(html):
        fpos = fm.start()
        fblock = fm.group(1)
        im = img_pattern.search(fblock)
        if not im:
            continue
        attrs = im.group(1)
        src_m = re.search(r'src\s*=\s*"([^"]+)"', attrs)
        alt_m = re.search(r'alt\s*=\s*"([^"]*)"', attrs)
        src = src_m.group(1) if src_m else ''
        alt = alt_m.group(1) if alt_m else ''
        filename = src.split('/')[-1] if src else ''

        cap_m = figcap_pattern.search(fblock)
        caption = _strip_tags(cap_m.group(1)) if cap_m else ''

        # 주변 500자
        before = _strip_tags(html[max(0, fpos - 600):fpos])[-400:]
        after = _strip_tags(html[fm.end():fm.end() + 600])[:400]

        seen_positions.add(fpos)
        image_metas.append({
            'filename': filename,
            'src': src,
            'alt': alt if alt != filename else '',
            'caption': caption if caption != filename else '',
            'parent_section': parent_section(fpos),
            'context_before': before,
            'context_after': after,
        })

    # figure 밖 단독 img
    for im in img_pattern.finditer(html):
        ipos = im.start()
        # 이미 figure 내부 처리된 것 스킵 (인접 fpos 탐지)
        inside_figure = any(abs(ipos - sp) < 200 for sp in seen_positions)
        if inside_figure:
            continue
        attrs = im.group(1)
        src_m = re.search(r'src\s*=\s*"([^"]+)"', attrs)
        alt_m = re.search(r'alt\s*=\s*"([^"]*)"', attrs)
        src = src_m.group(1) if src_m else ''
        alt = alt_m.group(1) if alt_m else ''
        filename = src.split('/')[-1] if src else ''

        before = _strip_tags(html[max(0, ipos - 600):ipos])[-400:]
        after = _strip_tags(html[im.end():im.end() + 600])[:400]

        image_metas.append({
            'filename': filename,
            'src': src,
            'alt': alt if alt != filename else '',
            'caption': '',
            'parent_section': parent_section(ipos),
            'context_before': before,
            'context_after': after,
        })

    return image_metas


def extract_image_contexts(blocks, context_window=3):
    """(legacy) 블록 기반 추출 — HTML 버전으로 대체됨."""
    return []


def parse_breadcrumb(bc):
    parts = [p.strip() for p in bc.replace('>', '>').split('>') if p.strip()]
    return parts


def derive_page(page_dir: Path):
    html_path = page_dir / 'index.html'
    if not html_path.exists():
        return None

    html = html_path.read_text(encoding='utf-8', errors='replace')

    # <head>...</head>, <style>...</style>, <script>...</script> 제거
    html_body = re.sub(r'<head>.*?</head>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html_body = re.sub(r'<style[^>]*>.*?</style>', '', html_body, flags=re.DOTALL | re.IGNORECASE)
    html_body = re.sub(r'<script[^>]*>.*?</script>', '', html_body, flags=re.DOTALL | re.IGNORECASE)

    parser = ConfluenceHTMLParser()
    parser.feed(html_body)

    # 메타 파싱
    meta_text = ''.join(parser.meta_text)
    m_pid = re.search(r'페이지 ID:\s*(\d+)', meta_text)
    m_ver = re.search(r'버전:\s*(\d+)', meta_text)
    m_img = re.search(r'이미지:\s*(\d+)', meta_text)

    folder_name = page_dir.name
    fm = re.match(r'(\d+)-(.+)', folder_name)
    pid_from_folder = fm.group(1) if fm else ''

    # images 폴더 실제 파일 리스트
    images_dir = page_dir / 'images'
    actual_images = sorted([p.name for p in images_dir.iterdir()]) if images_dir.exists() else []

    # MD 생성
    md_content = blocks_to_md(parser.blocks)
    # 후처리: 빈 bullet, 빈 strong, 과다 빈 줄 정리
    md_content = re.sub(r'^\s*-\s*$', '', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'^\s*\*+\s*$', '', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'\n{3,}', '\n\n', md_content)

    # image-meta 생성 (HTML 원문 기반)
    image_metas = extract_image_contexts_from_html(html, parser.title)

    # 실제 파일과 대조 (누락된 이미지도 리스트에 추가)
    referenced = {im['filename'] for im in image_metas}
    for fn in actual_images:
        if fn not in referenced:
            image_metas.append({
                'filename': fn,
                'src': f'images/{fn}',
                'alt': '',
                'caption': '',
                'parent_section': '',
                'context_before': '',
                'context_after': '',
                '_unreferenced': True,
            })

    # meta.json
    meta = {
        'pageId': m_pid.group(1) if m_pid else pid_from_folder,
        'title': parser.title or (fm.group(2) if fm else ''),
        'breadcrumb': parse_breadcrumb(parser.breadcrumb.strip()),
        'source_url': parser.source_url,
        'version': int(m_ver.group(1)) if m_ver else None,
        'image_count_declared': int(m_img.group(1)) if m_img else None,
        'image_count_actual': len(actual_images),
        'image_count_referenced_in_html': len(referenced),
        'folder': folder_name,
    }

    # 저장
    (page_dir / 'content.md').write_text(md_content, encoding='utf-8')
    (page_dir / 'meta.json').write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    (page_dir / 'image-meta.json').write_text(
        json.dumps(image_metas, ensure_ascii=False, indent=2), encoding='utf-8')

    return meta, len(image_metas), len(md_content)


def main():
    base = Path('C:/MES/wta-agents/reports/MAX/confluence-경상연구개발/장비물류')
    if not base.exists():
        print(f'ERR: {base} 없음')
        sys.exit(1)

    page_dirs = sorted([p for p in base.iterdir() if p.is_dir()])
    print(f'=== 2단계 파생 데이터 생성 ===')
    print(f'대상: {base}')
    print(f'페이지: {len(page_dirs)}개\n')

    for pd in page_dirs:
        result = derive_page(pd)
        if result is None:
            print(f'  SKIP {pd.name}')
            continue
        meta, img_cnt, md_len = result
        print(f'  ✓ {pd.name}')
        print(f'    MD: {md_len:,}자 | 이미지 meta: {img_cnt}개 | 실제 이미지: {meta["image_count_actual"]}개 | 참조: {meta["image_count_referenced_in_html"]}개')

    print('\n완료.')


if __name__ == '__main__':
    main()
