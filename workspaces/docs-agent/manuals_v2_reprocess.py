# -*- coding: utf-8 -*-
"""manuals-v2 PoC 재처리 (crafter, 2026-04-11)

기존 v2_poc/{file_id}/chunks.jsonl을 입력으로:
  1) embedding 제외 로드
  2) chunk_postprocess.postprocess() 수행 (Qwen3 tokenizer 기반)
  3) 각 청크 content 임베딩 재생성 (Qwen3-Embedding-8B, 2000dim)
  4) chunks.jsonl 덮어쓰기 (기존 파일은 .bak 백업)

document.json / images / figures[].vlm_description 보존.
PDF 재파싱 없음, VLM 재호출 없음.

사용법:
  python manuals_v2_reprocess.py              # v2_poc/*/chunks.jsonl 전체
  python manuals_v2_reprocess.py <file_id> ... # 지정 file_id만
"""
import os
import sys
import io
import json
import time
import shutil
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent))

from chunk_postprocess import postprocess, stats  # noqa

WORK_ROOT = Path(r'C:\MES\wta-agents\workspaces\docs-agent\v2_poc')
CRAFTER_OUT = Path(r'C:\MES\wta-agents\workspaces\crafter')
LOG_PATH = CRAFTER_OUT / 'manuals_v2_reprocess.log'

QWEN_URL = 'http://182.224.6.147:11434/api/embed'
QWEN_MODEL = 'qwen3-embedding:8b'
EMBED_DIM = 2000

SKIP_EMBED = os.environ.get('REPROCESS_SKIP_EMBED', '0') == '1'


def log(msg: str):
    ts = time.strftime('%H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def load_chunks(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            r.pop('embedding', None)
            rows.append(r)
    return rows


def embed_batch(texts: list[str]) -> list[list[float] | None]:
    """Qwen3-Embedding-8B 호출. 개별 호출(Ollama embed API는 batch 불완전)."""
    import urllib.request
    out: list[list[float] | None] = []
    for t in texts:
        if not t:
            out.append(None)
            continue
        try:
            body = json.dumps({
                'model': QWEN_MODEL,
                'input': t,
                'keep_alive': '10m',
            }).encode('utf-8')
            req = urllib.request.Request(
                QWEN_URL, data=body,
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read())
            vec = resp.get('embeddings', [[]])[0]
            out.append(vec[:EMBED_DIM] if vec else None)
        except Exception as e:
            log(f'    [embed err] {e}')
            out.append(None)
    return out


def write_chunks(path: Path, processed: list[dict], vectors: list, file_id: str):
    # 백업
    if path.exists():
        bak = path.with_suffix('.jsonl.bak')
        shutil.copy2(path, bak)
    with open(path, 'w', encoding='utf-8') as f:
        for i, ch in enumerate(processed):
            row = {
                'file_id': ch.get('file_id') or file_id,
                'chunk_id': f'{(ch.get("page_start") or 0):04d}_{i:04d}',
                'category': ch.get('category'),
                'mfr': ch.get('mfr'),
                'model': ch.get('model'),
                'doctype': ch.get('doctype'),
                'lang': ch.get('lang'),
                'section_path': ch.get('section_path'),
                'page_start': ch.get('page_start'),
                'page_end': ch.get('page_end'),
                'content': ch.get('content'),
                'tokens': ch.get('tokens'),
                'source_hash': ch.get('source_hash'),
                'embedding': vectors[i] if i < len(vectors) else None,
                'figure_refs': ch.get('figure_refs', []),
                'table_refs': ch.get('table_refs', []),
                'inline_refs': ch.get('inline_refs', []),
            }
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


def reprocess_file(file_id: str) -> dict:
    path = WORK_ROOT / file_id / 'chunks.jsonl'
    if not path.exists():
        log(f'[{file_id}] SKIP — chunks.jsonl 없음')
        return {'file_id': file_id, 'error': 'not found'}

    t0 = time.time()
    raw = load_chunks(path)
    b = stats(raw)
    lang = raw[0].get('lang', 'en') if raw else 'en'
    log(f'[{file_id}] load n={b["n"]} avg={b["avg_tokens"]} med={b["median_tokens"]} lang={lang}')

    processed = postprocess(raw, lang=lang)
    a = stats(processed)
    log(f'[{file_id}] post  n={a["n"]} avg={a["avg_tokens"]} med={a["median_tokens"]} in_target={a["in_target_range"]*100//max(1,a["n"])}% max={a["max_tokens"]}')

    # 임베딩
    if SKIP_EMBED:
        vectors = [None] * len(processed)
        log(f'[{file_id}] embed SKIP (REPROCESS_SKIP_EMBED=1)')
    else:
        log(f'[{file_id}] embed start n={len(processed)}')
        t_emb = time.time()
        vectors = embed_batch([c['content'] for c in processed])
        failed = sum(1 for v in vectors if v is None)
        log(f'[{file_id}] embed done {time.time()-t_emb:.1f}s failed={failed}')

    write_chunks(path, processed, vectors, file_id)
    elapsed = time.time() - t0
    log(f'[{file_id}] write OK elapsed={elapsed:.1f}s')

    # 배치 리포트 (crafter 워크스페이스)
    report = {
        'file_id': file_id,
        'lang': lang,
        'before': b,
        'after': a,
        'elapsed_sec': round(elapsed, 1),
        'embed_failed': sum(1 for v in vectors if v is None),
    }
    rpt_path = CRAFTER_OUT / f'chunk_postprocess_batch_{file_id}.json'
    with open(rpt_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


def main():
    CRAFTER_OUT.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(f'=== manuals_v2_reprocess start {time.strftime("%Y-%m-%d %H:%M:%S")} ===\n', encoding='utf-8')

    if len(sys.argv) > 1:
        file_ids = sys.argv[1:]
    else:
        file_ids = sorted(p.parent.name for p in WORK_ROOT.glob('*/chunks.jsonl'))

    log(f'targets: {len(file_ids)}건')
    reports = []
    for fid in file_ids:
        try:
            reports.append(reprocess_file(fid))
        except Exception as e:
            import traceback
            traceback.print_exc()
            log(f'[{fid}] ERROR {e}')
            reports.append({'file_id': fid, 'error': str(e)})

    # 종합 요약
    summary_path = CRAFTER_OUT / 'chunk_postprocess_poc_summary.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump({'files': reports, 'params': {
            'MIN': 40, 'TARGET_MIN': 150, 'TARGET_MAX': 300,
            'MAX_HARD': 1000, 'TABLE_ROW_SPLIT': 50,
        }}, f, ensure_ascii=False, indent=2)

    total_before = sum(r.get('before', {}).get('n', 0) for r in reports if 'before' in r)
    total_after = sum(r.get('after', {}).get('n', 0) for r in reports if 'after' in r)
    log(f'=== DONE total chunks {total_before}→{total_after} ===')


if __name__ == '__main__':
    main()
