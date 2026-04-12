# -*- coding: utf-8 -*-
"""manuals-v2 Step2 — Docling 파싱 + 512 청킹 배치 러너 (재개 가능)

부서장 승인(2026-04-11) 파이프라인에 따라 manuals_v2_parse_docling.process_pdf를
7개 카테고리(extract.jsonl status=ok)에 대해 일괄 실행한다.

특징:
  - state.json + log 2파일로 재개 가능 (md5 단위 체크포인트)
  - 한 파일 처리 후 즉시 atomic 저장
  - V2_EMBED=0 / V2_VLM=0 기본 (이번 단계는 파싱+청킹만)
  - 임베딩 / 인덱싱은 별도 Step3·Step4에서 처리

산출물:
  workspaces/docs-agent/v2_poc/{file_id}/chunks.jsonl   (manual_v2_parse_docling 출력)
  workspaces/docs-agent/manuals_v2_step2_state.json     (상태)
  workspaces/docs-agent/manuals_v2_step2.log            (로그)

사용법:
  python manuals_v2_step2_parse.py                # 전체 (재개)
  python manuals_v2_step2_parse.py --limit 5      # N개만
  python manuals_v2_step2_parse.py --category 1_robot
"""
import os, sys, io, json, time, argparse, traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# 임베딩/VLM은 Step3에서 별도 처리
os.environ.setdefault('V2_EMBED', '0')
os.environ.setdefault('V2_VLM', '0')

WORKSPACE = Path(r'C:\MES\wta-agents\workspaces\docs-agent')
STATE_PATH = WORKSPACE / 'manuals_v2_step2_state.json'
LOG_PATH = WORKSPACE / 'manuals_v2_step2.log'

# 카테고리명 ↔ extract.jsonl 파일명
CATEGORIES = {
    '1_robot':     'manuals_v2_1robot_extract.jsonl',
    '2_sensor':    'manuals_v2_2_sensor_extract.jsonl',
    '3_hmi':       'manuals_v2_3_hmi_extract.jsonl',
    '4_servo':     'manuals_v2_4_servo_extract.jsonl',
    '5_inverter':  'manuals_v2_5_inverter_extract.jsonl',
    '6_plc':       'manuals_v2_6_plc_extract.jsonl',
    '7_pneumatic': 'manuals_v2_7_pneumatic_extract.jsonl',
}

KST = timezone(timedelta(hours=9))


def now_str():
    return datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')


def log(line, also_print=True):
    ts = now_str()
    msg = f'[{ts}] {line}'
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')
    if also_print:
        print(msg, flush=True)


def load_state():
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f'state.json 로드 실패 ({e}) — 새 state 생성')
    return {
        'started_at': now_str(),
        'updated_at': now_str(),
        'files': {},   # md5 → {category, filename, status, file_id, chunks, figures, tables, error, elapsed}
        'totals': {'done': 0, 'error': 0, 'skipped': 0},
    }


def save_state(state):
    state['updated_at'] = now_str()
    tmp = STATE_PATH.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    tmp.replace(STATE_PATH)


def load_targets(only_category=None):
    """7개 extract.jsonl을 읽어 status=ok 항목을 (category, md5, src_path, filename) 리스트로 반환."""
    targets = []
    for cat, jl in CATEGORIES.items():
        if only_category and cat != only_category:
            continue
        p = WORKSPACE / jl
        if not p.exists():
            log(f'WARN extract 누락: {jl}')
            continue
        with open(p, 'r', encoding='utf-8') as f:
            for ln in f:
                try:
                    d = json.loads(ln)
                except Exception:
                    continue
                if d.get('status') != 'ok':
                    continue
                src = d.get('src_path')
                md5 = d.get('md5')
                if not src or not md5:
                    continue
                targets.append({
                    'category': cat,
                    'md5': md5,
                    'src_path': src,
                    'filename': d.get('filename') or Path(src).name,
                    'pages': d.get('pages'),
                    'size': d.get('size'),
                })
    return targets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0, help='처리할 최대 건수 (0=무제한)')
    ap.add_argument('--category', default=None, help='특정 카테고리만')
    ap.add_argument('--retry-error', action='store_true', help='이전에 error로 끝난 항목 재시도')
    args = ap.parse_args()

    # 지연 import (Docling 무거움)
    sys.path.insert(0, str(WORKSPACE))
    from manuals_v2_parse_docling import process_pdf

    state = load_state()
    targets = load_targets(only_category=args.category)
    log(f'=== Step2 시작 — 대상 {len(targets)}건 (category={args.category or "ALL"}) ===')

    processed = 0
    for t in targets:
        md5 = t['md5']
        prev = state['files'].get(md5)
        if prev and prev.get('status') == 'done':
            state['totals']['skipped'] += 1
            continue
        if prev and prev.get('status') == 'error' and not args.retry_error:
            state['totals']['skipped'] += 1
            continue
        if not Path(t['src_path']).exists():
            log(f'SKIP missing file: {t["src_path"]}')
            state['files'][md5] = {**t, 'status': 'error', 'error': 'file_missing'}
            state['totals']['error'] += 1
            save_state(state)
            continue

        log(f'>> [{t["category"]}] {t["filename"]} (md5={md5[:8]}, pages={t.get("pages")})')
        t0 = time.time()
        try:
            r = process_pdf(t['src_path'])
            elapsed = time.time() - t0
            state['files'][md5] = {
                **t,
                'status': 'done',
                'file_id': r.get('file_id'),
                'chunks': r.get('chunks'),
                'figures': r.get('figures'),
                'tables': r.get('tables'),
                'elapsed': round(elapsed, 1),
                'finished_at': now_str(),
            }
            state['totals']['done'] += 1
            log(f'   OK chunks={r.get("chunks")} figures={r.get("figures")} tables={r.get("tables")} elapsed={elapsed:.1f}s')
        except Exception as e:
            elapsed = time.time() - t0
            err = f'{type(e).__name__}: {e}'
            state['files'][md5] = {
                **t,
                'status': 'error',
                'error': err,
                'elapsed': round(elapsed, 1),
                'finished_at': now_str(),
            }
            state['totals']['error'] += 1
            log(f'   ERR {err}')
            log(traceback.format_exc(), also_print=False)
        save_state(state)
        processed += 1
        if args.limit and processed >= args.limit:
            log(f'--limit {args.limit} 도달 → 종료')
            break

    log(f'=== Step2 종료 — done={state["totals"]["done"]} error={state["totals"]["error"]} skipped={state["totals"]["skipped"]} (이번 세션 처리={processed}) ===')


if __name__ == '__main__':
    main()
