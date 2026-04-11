# -*- coding: utf-8 -*-
"""manuals-v2 청킹 후처리 모듈 (crafter, 2026-04-11)

부서장 B안 승인 파이프라인:
  HierarchicalChunker raw output
    → (1) count_tokens (Qwen3-Embedding-8B tokenizer)
    → (2) promote_empty_sections  (소제목-only 청크 → 상위 section 병합)
    → (3) merge_adjacent          (section_path strict, None-None 예외)
    → (4) split_tables            (HTML <table> 또는 | 3라인 이상, 50행 단위 분할)
    → (5) split_oversize          (max_hard 초과 시 문장/줄 단위 분할)
    → (6) final_filter            (완전 공백 청크 drop)
    → (7) recompute metadata      (page_start/end, figure/table/inline refs union)

파라미터 (issue-manager 리서치 결과 도착 시 교체):
  MIN_CHUNK_TOKENS = 40
  TARGET_MIN       = 150
  TARGET_MAX       = 300
  MAX_HARD         = 1000
  TABLE_ROW_SPLIT  = 50

API:
  postprocess(chunks: list[dict], lang: str) -> list[dict]
    입력 chunk dict 키: chunk_idx, content, section_path(list|None),
                        page_start, page_end, tokens(무시),
                        figure_refs, table_refs, inline_refs (있으면 유지/합집합)

stats(chunks: list[dict]) -> dict
    n, avg_tokens, median_tokens, p10, p90, under_min, over_hard
"""
import os
import re
import sys
from typing import Any, Iterable

# ============ 파라미터 ============
MIN_CHUNK_TOKENS = int(os.environ.get('CPP_MIN', '40'))
TARGET_MIN = int(os.environ.get('CPP_TARGET_MIN', '150'))
TARGET_MAX = int(os.environ.get('CPP_TARGET_MAX', '300'))
MAX_HARD = int(os.environ.get('CPP_MAX_HARD', '1000'))
TABLE_ROW_SPLIT = int(os.environ.get('CPP_TABLE_ROWS', '50'))

# ============ 토크나이저 ============
_TOKENIZER = None
_TOKENIZER_NAME = os.environ.get('CPP_TOKENIZER', 'Qwen/Qwen3-Embedding-8B')


def _get_tokenizer():
    global _TOKENIZER
    if _TOKENIZER is None:
        from transformers import AutoTokenizer
        _TOKENIZER = AutoTokenizer.from_pretrained(_TOKENIZER_NAME)
    return _TOKENIZER


def count_tokens(text: str) -> int:
    if not text:
        return 0
    tok = _get_tokenizer()
    return len(tok.encode(text, add_special_tokens=False))


# ============ 섹션 경계 ============
def _section_key(section_path: Any) -> tuple:
    """section_path 비교용 정규화. None/빈 리스트 → None(특수값)."""
    if section_path is None:
        return None
    if isinstance(section_path, list) and not section_path:
        return None
    if isinstance(section_path, list):
        return tuple(section_path)
    return (str(section_path),)


def _same_section(a, b) -> bool:
    """strict section 비교. None-None은 같은 것으로 허용(병합 가능)."""
    ka = _section_key(a)
    kb = _section_key(b)
    return ka == kb


def _parent_section(section_path: Any) -> Any:
    if section_path is None:
        return None
    if isinstance(section_path, list):
        return section_path[:-1] if len(section_path) > 1 else None
    return None


# ============ 테이블 식별 ============
_TABLE_HTML_RE = re.compile(r'<table[\s>]', re.I)


def _looks_like_table(content: str) -> bool:
    if not content:
        return False
    if _TABLE_HTML_RE.search(content):
        return True
    # fallback: | 라인이 3개 이상 연속
    lines = content.splitlines()
    streak = 0
    for ln in lines:
        if ln.count('|') >= 2:
            streak += 1
            if streak >= 3:
                return True
        else:
            streak = 0
    return False


_TR_RE = re.compile(r'<tr[\s>][\s\S]*?</tr>', re.I)


def _split_table_content(content: str, row_split: int = TABLE_ROW_SPLIT) -> list[str]:
    """테이블 청크를 row_split 행 단위로 나눔. HTML 우선, fallback은 | 라인 단위."""
    m = re.search(r'<table[\s>][\s\S]*?</table>', content, re.I)
    if m:
        table_html = m.group(0)
        prefix = content[:m.start()]
        suffix = content[m.end():]
        rows = _TR_RE.findall(table_html)
        if len(rows) <= row_split:
            return [content]
        # header 추정: 첫 tr
        header = rows[0]
        out: list[str] = []
        for i in range(1, len(rows), row_split):
            group = rows[i:i + row_split]
            piece_rows = [header] + group
            piece = f'<table>\n' + '\n'.join(piece_rows) + '\n</table>'
            if i == 1:
                piece = (prefix + piece).rstrip()
            if i + row_split >= len(rows):
                piece = (piece + suffix).rstrip()
            out.append(piece)
        return out
    # md fallback
    lines = content.splitlines()
    bar_idx = [i for i, ln in enumerate(lines) if ln.count('|') >= 2]
    if len(bar_idx) <= row_split:
        return [content]
    out = []
    cur: list[str] = []
    count = 0
    header_lines: list[str] = []
    for i, ln in enumerate(lines):
        if ln.count('|') >= 2:
            if not header_lines and count == 0:
                header_lines.append(ln)
                cur.append(ln)
                count = 1
                continue
            cur.append(ln)
            count += 1
            if count >= row_split:
                out.append('\n'.join(cur))
                cur = list(header_lines)
                count = len(header_lines)
        else:
            cur.append(ln)
    if cur:
        out.append('\n'.join(cur))
    return out if len(out) >= 2 else [content]


# ============ 오버사이즈 분할 ============
_SENT_RE = re.compile(r'(?<=[.!?。！？\n])\s+')


def _split_oversize_content(content: str, max_tokens: int) -> list[str]:
    """줄바꿈 → 문장 경계 → 강제 슬라이스 순으로 분할."""
    if count_tokens(content) <= max_tokens:
        return [content]
    # 1) 줄바꿈
    paras = [p for p in content.split('\n\n') if p.strip()]
    if len(paras) > 1:
        out: list[str] = []
        cur = ''
        for p in paras:
            cand = (cur + '\n\n' + p) if cur else p
            if count_tokens(cand) <= max_tokens:
                cur = cand
            else:
                if cur:
                    out.append(cur)
                if count_tokens(p) > max_tokens:
                    out.extend(_split_oversize_content(p, max_tokens))
                    cur = ''
                else:
                    cur = p
        if cur:
            out.append(cur)
        if len(out) >= 2:
            return out
    # 2) 문장 경계
    sents = _SENT_RE.split(content)
    if len(sents) > 1:
        out = []
        cur = ''
        for s in sents:
            cand = (cur + ' ' + s) if cur else s
            if count_tokens(cand) <= max_tokens:
                cur = cand
            else:
                if cur:
                    out.append(cur)
                cur = s
        if cur:
            out.append(cur)
        if len(out) >= 2:
            return out
    # 3) 강제 슬라이스 (토크나이저 기준)
    tok = _get_tokenizer()
    ids = tok.encode(content, add_special_tokens=False)
    out = []
    for i in range(0, len(ids), max_tokens):
        sub = ids[i:i + max_tokens]
        out.append(tok.decode(sub, skip_special_tokens=True))
    return out or [content]


# ============ 병합 로직 ============
def _merge_two(a: dict, b: dict) -> dict:
    """두 청크를 하나로 병합 (a가 앞, b가 뒤)."""
    content = a['content']
    if content and b.get('content'):
        content = content + '\n\n' + b['content']
    elif b.get('content'):
        content = b['content']

    def _union_refs(key: str):
        la = a.get(key) or []
        lb = b.get(key) or []
        seen = set()
        out = []
        for x in la + lb:
            k = x.get('figure_id') or x.get('table_id') or str(x) if isinstance(x, dict) else str(x)
            if k in seen:
                continue
            seen.add(k)
            out.append(x)
        return out

    pa_s, pa_e = a.get('page_start'), a.get('page_end')
    pb_s, pb_e = b.get('page_start'), b.get('page_end')
    pages = [p for p in (pa_s, pa_e, pb_s, pb_e) if p is not None]
    page_start = min(pages) if pages else None
    page_end = max(pages) if pages else None

    merged = dict(a)
    merged['content'] = content
    merged['page_start'] = page_start
    merged['page_end'] = page_end
    merged['figure_refs'] = _union_refs('figure_refs')
    merged['table_refs'] = _union_refs('table_refs')
    # inline_refs는 문자열 리스트
    ia = a.get('inline_refs') or []
    ib = b.get('inline_refs') or []
    merged['inline_refs'] = sorted(set(list(ia) + list(ib)))
    merged['tokens'] = count_tokens(merged['content'])
    return merged


# ============ 단계 함수 ============
def _step_count_tokens(chunks: list[dict]) -> list[dict]:
    for c in chunks:
        c['tokens'] = count_tokens(c.get('content') or '')
    return chunks


def _step_promote_empty_sections(chunks: list[dict]) -> list[dict]:
    """소제목-only(작고 section_path 깊은) 청크 → 다음 청크로 병합.

    판단: tokens<MIN_CHUNK_TOKENS AND content가 실질적으로 헤딩만일 때
    현재는 단순화: tokens<MIN_CHUNK_TOKENS 이면 상위 section으로 section_path를 낮춤만 수행.
    실제 병합은 merge_adjacent 단계에서 처리.
    """
    for c in chunks:
        if c['tokens'] < MIN_CHUNK_TOKENS and c.get('section_path'):
            c['_promoted'] = True
            # section_path는 유지하되, 병합 시 상위까지 허용하는 플래그
    return chunks


def _step_merge_adjacent(chunks: list[dict]) -> list[dict]:
    """순차 병합. 같은 section_path 내에서 TARGET_MAX까지 합침.

    규칙:
      1. tokens >= TARGET_MIN 이고 다음 청크와 합쳐도 TARGET_MAX 초과하면 중단
      2. tokens < MIN 이면 강제 병합 시도 (next 우선, prev fallback)
      3. 같은 section_path(또는 None-None) 에서만 병합
      4. _promoted=True 이면 부모 section과도 병합 허용
    """
    if not chunks:
        return chunks
    out: list[dict] = []
    buf = dict(chunks[0])
    buf['tokens'] = count_tokens(buf.get('content') or '')

    for nxt in chunks[1:]:
        nxt = dict(nxt)
        nxt['tokens'] = count_tokens(nxt.get('content') or '')

        same = _same_section(buf.get('section_path'), nxt.get('section_path'))
        promoted = buf.get('_promoted') or nxt.get('_promoted')

        can_merge_section = same
        if not same and promoted:
            # 부모 section 동일 여부 확인
            pa = _parent_section(buf.get('section_path'))
            pb = _parent_section(nxt.get('section_path'))
            if _section_key(pa) == _section_key(nxt.get('section_path')) or \
               _section_key(buf.get('section_path')) == _section_key(pb) or \
               _section_key(pa) == _section_key(pb):
                can_merge_section = True

        if not can_merge_section:
            out.append(buf)
            buf = nxt
            continue

        combined_tokens = buf['tokens'] + nxt['tokens']

        # 병합 판단
        if buf['tokens'] < MIN_CHUNK_TOKENS or nxt['tokens'] < MIN_CHUNK_TOKENS:
            # 강제 병합 (작은 쪽 구제) — 단 결과가 MAX_HARD 초과면 중단
            if combined_tokens <= MAX_HARD:
                buf = _merge_two(buf, nxt)
                continue
        elif combined_tokens <= TARGET_MAX:
            buf = _merge_two(buf, nxt)
            continue

        # 병합 실패 → 확정하고 이동
        out.append(buf)
        buf = nxt

    out.append(buf)

    # 마지막 청크가 아직 MIN 미만이면 이전 청크에 흡수 시도
    if len(out) >= 2 and out[-1]['tokens'] < MIN_CHUNK_TOKENS:
        last = out.pop()
        prev = out[-1]
        if _same_section(prev.get('section_path'), last.get('section_path')):
            if prev['tokens'] + last['tokens'] <= MAX_HARD:
                out[-1] = _merge_two(prev, last)
            else:
                out.append(last)
        else:
            out.append(last)
    return out


def _step_split_tables(chunks: list[dict]) -> list[dict]:
    out: list[dict] = []
    for c in chunks:
        content = c.get('content') or ''
        if not _looks_like_table(content):
            out.append(c)
            continue
        if c['tokens'] <= MAX_HARD:
            out.append(c)
            continue
        pieces = _split_table_content(content)
        if len(pieces) <= 1:
            out.append(c)
            continue
        for i, p in enumerate(pieces):
            sub = dict(c)
            sub['content'] = p
            sub['tokens'] = count_tokens(p)
            sub['_split_from'] = c.get('chunk_idx')
            sub['_split_part'] = i
            out.append(sub)
    return out


def _step_split_oversize(chunks: list[dict]) -> list[dict]:
    out: list[dict] = []
    for c in chunks:
        if c['tokens'] <= MAX_HARD:
            out.append(c)
            continue
        if _looks_like_table(c.get('content') or ''):
            # 테이블 분할 단계에서 처리 못한 건은 그대로 둠
            out.append(c)
            continue
        pieces = _split_oversize_content(c['content'], MAX_HARD)
        if len(pieces) <= 1:
            out.append(c)
            continue
        for i, p in enumerate(pieces):
            sub = dict(c)
            sub['content'] = p
            sub['tokens'] = count_tokens(p)
            sub['_split_from'] = c.get('chunk_idx')
            sub['_split_part_ov'] = i
            out.append(sub)
    return out


def _step_final_filter(chunks: list[dict]) -> list[dict]:
    out = []
    for c in chunks:
        content = (c.get('content') or '').strip()
        if not content:
            continue
        # 완전히 제어문자/공백만인 경우
        if not re.sub(r'\s+', '', content):
            continue
        out.append(c)
    return out


def _step_reindex(chunks: list[dict]) -> list[dict]:
    for i, c in enumerate(chunks):
        c['chunk_idx'] = i
        c.pop('_promoted', None)
    return chunks


# ============ 공개 API ============
def postprocess(chunks: list[dict], lang: str = 'en') -> list[dict]:
    """전체 후처리 파이프라인."""
    if not chunks:
        return chunks
    chunks = [dict(c) for c in chunks]
    chunks = _step_count_tokens(chunks)
    chunks = _step_promote_empty_sections(chunks)
    chunks = _step_merge_adjacent(chunks)
    chunks = _step_split_tables(chunks)
    chunks = _step_split_oversize(chunks)
    chunks = _step_final_filter(chunks)
    chunks = _step_reindex(chunks)
    return chunks


def stats(chunks: list[dict]) -> dict:
    if not chunks:
        return {'n': 0}
    toks = sorted(c.get('tokens') or count_tokens(c.get('content') or '') for c in chunks)
    n = len(toks)
    avg = sum(toks) / n

    def _pct(p):
        idx = max(0, min(n - 1, int(n * p)))
        return toks[idx]

    return {
        'n': n,
        'avg_tokens': round(avg, 1),
        'median_tokens': toks[n // 2],
        'p10': _pct(0.10),
        'p90': _pct(0.90),
        'min_tokens': toks[0],
        'max_tokens': toks[-1],
        'under_min': sum(1 for t in toks if t < MIN_CHUNK_TOKENS),
        'over_hard': sum(1 for t in toks if t > MAX_HARD),
        'target_min': TARGET_MIN,
        'target_max': TARGET_MAX,
        'in_target_range': sum(1 for t in toks if TARGET_MIN <= t <= TARGET_MAX),
    }


# ============ CLI (단위 테스트용) ============
if __name__ == '__main__':
    import io
    import json
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    if len(sys.argv) < 2:
        print('Usage: python chunk_postprocess.py <chunks.jsonl>')
        sys.exit(1)

    path = sys.argv[1]
    raw = []
    for line in open(path, encoding='utf-8'):
        row = json.loads(line)
        # 임베딩은 후처리에 불필요 — 메모리 절약
        row.pop('embedding', None)
        raw.append(row)

    print(f'[input] {path}')
    print(f'  before: {stats(raw)}')
    processed = postprocess(raw, lang=raw[0].get('lang', 'en') if raw else 'en')
    print(f'  after : {stats(processed)}')
