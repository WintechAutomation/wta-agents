"""update_progress.py — 매뉴얼 임베딩 진행 상황 업데이트 스크립트.

사용법:
  py update_progress.py "1_robot/597-0027-06KO.pdf" embedded
  py update_progress.py "4_servo/CSD5.pdf" skipped "카탈로그/가격표"
  py update_progress.py "2_sensor/EX-10.pdf" in_progress --agent dev-agent
  py update_progress.py --status        # 현재 진행 상황 출력
  py update_progress.py --init          # manual_progress.json 초기화 (전체 파일 스캔)
  py update_progress.py --chunks "파일경로" 120  # 청크 수만 업데이트
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROGRESS_FILE = Path("C:/MES/wta-agents/data/manual_progress.json")
MANUALS_BASE = Path("C:/MES/wta-agents/data/manuals-filtered")
VALID_STATUSES = {"pending", "in_progress", "parsed", "embedded", "skipped", "error"}

KST = timezone(timedelta(hours=9))


def now_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S")


LOCK_FILE = PROGRESS_FILE.with_suffix(".json.lock")


def _acquire_lock(lock_fd, timeout: float = 10) -> bool:
    import msvcrt, time as _time
    deadline = _time.time() + timeout
    while _time.time() < deadline:
        try:
            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except (IOError, OSError):
            _time.sleep(0.1)
    return False


def _release_lock(lock_fd) -> None:
    import msvcrt
    try:
        lock_fd.seek(0)
        msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
    except (IOError, OSError):
        pass


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        for _ in range(3):
            try:
                with PROGRESS_FILE.open(encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                import time as _time; _time.sleep(0.2)
    return {}


def save_progress(data: dict) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = now_kst()
    tmp = PROGRESS_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(str(tmp), str(PROGRESS_FILE))


def rebuild_counts(data: dict) -> dict:
    """files 딕셔너리를 기반으로 상태별 카운트 재계산."""
    files = data.get("files", {})
    counts = {s: 0 for s in VALID_STATUSES}
    for info in files.values():
        status = info.get("status", "pending")
        counts[status] = counts.get(status, 0) + 1
    data["parsed"] = counts.get("parsed", 0)
    data["embedded"] = counts["embedded"]
    data["skipped"] = counts["skipped"]
    data["in_progress"] = counts["in_progress"]
    data["error"] = counts.get("error", 0)
    data["pending"] = counts["pending"]
    data["total"] = len(files)
    return data


def init_progress() -> dict:
    """manuals-filtered 전체 파일 스캔하여 progress.json 초기화."""
    existing = load_progress()
    existing_files = existing.get("files", {})

    files: dict[str, dict] = {}
    for cat_dir in sorted(MANUALS_BASE.iterdir()):
        if not cat_dir.is_dir():
            continue
        cat = cat_dir.name
        for pdf in sorted(cat_dir.glob("*.pdf")):
            rel = f"{cat}/{pdf.name}"
            # 기존 상태 보존
            if rel in existing_files:
                files[rel] = existing_files[rel]
            else:
                files[rel] = {"status": "pending"}

    data: dict = {
        "files": files,
    }
    data = rebuild_counts(data)
    save_progress(data)
    return data


def update_file_status(
    rel_path: str,
    status: str,
    reason: str = "",
    agent: str = "",
    chunks: int | None = None,
) -> dict:
    """단일 파일 상태 업데이트 (파일 락 사용)."""
    if status not in VALID_STATUSES:
        print(f"오류: 유효하지 않은 상태 '{status}'. 허용값: {', '.join(sorted(VALID_STATUSES))}")
        sys.exit(1)

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(LOCK_FILE, "a+")
    try:
        if not _acquire_lock(lock_fd):
            print(f"경고: 락 획득 실패 ({rel_path})")
            return {}

        data = load_progress()
        if not data:
            print("manual_progress.json 없음 — --init으로 초기화 먼저 실행하세요")
            sys.exit(1)

        files = data.setdefault("files", {})

        # 경로 정규화 (역슬래시 → 슬래시)
        rel_path = rel_path.replace("\\", "/")
        # manuals-filtered/ 접두어 제거
        for prefix in ("data/manuals-filtered/", "manuals-filtered/", "C:/MES/wta-agents/data/manuals-filtered/"):
            if rel_path.startswith(prefix):
                rel_path = rel_path[len(prefix):]
                break

        entry = files.get(rel_path, {})
        entry["status"] = status
        entry["updated_at"] = now_kst()
        if agent:
            entry["agent"] = agent
        if reason:
            entry["reason"] = reason
        if chunks is not None:
            entry["chunks"] = chunks

        files[rel_path] = entry
        data = rebuild_counts(data)
        save_progress(data)
    finally:
        _release_lock(lock_fd)
        lock_fd.close()
    return data


def update_chunks(rel_path: str, chunks: int) -> dict:
    """청크 수만 업데이트 (상태 변경 없음, 파일 락 사용)."""
    lock_fd = open(LOCK_FILE, "a+")
    try:
        if not _acquire_lock(lock_fd):
            print(f"경고: 락 획득 실패 ({rel_path})")
            return {}

        data = load_progress()
        if not data:
            print("manual_progress.json 없음")
            sys.exit(1)

        rel_path = rel_path.replace("\\", "/")
        files = data.setdefault("files", {})
        entry = files.get(rel_path, {})
        entry["chunks"] = chunks
        entry["updated_at"] = now_kst()
        files[rel_path] = entry
        save_progress(data)
    finally:
        _release_lock(lock_fd)
        lock_fd.close()
    return data


def print_status(data: dict) -> None:
    total = data.get("total", 0)
    embedded = data.get("embedded", 0)
    skipped = data.get("skipped", 0)
    in_progress = data.get("in_progress", 0)
    error = data.get("error", 0)
    pending = data.get("pending", 0)
    last = data.get("last_updated", "-")

    parsed = data.get("parsed", 0)
    done = embedded + skipped + parsed
    pct = round(done / total * 100, 1) if total else 0

    print(f"[매뉴얼 파싱 진행 현황]  최종 업데이트: {last}")
    print(f"  전체:       {total}개")
    print(f"  파싱 완료:   {parsed}개")
    print(f"  임베딩 완료: {embedded}개")
    print(f"  스킵:        {skipped}개")
    print(f"  처리 중:     {in_progress}개")
    print(f"  오류:        {error}개")
    print(f"  대기 중:     {pending}개")
    print(f"  완료율:      {done}/{total} ({pct}%)")

    # 카테고리별 요약
    files = data.get("files", {})
    cat_stats: dict[str, dict] = {}
    for rel, info in files.items():
        cat = rel.split("/")[0] if "/" in rel else "unknown"
        s = cat_stats.setdefault(cat, {s: 0 for s in VALID_STATUSES})
        s[info.get("status", "pending")] += 1

    if cat_stats:
        print("\n  카테고리별:")
        for cat in sorted(cat_stats):
            s = cat_stats[cat]
            t = sum(s.values())
            print(f"    {cat}: {s['parsed']}파싱 / {s['embedded']}임베딩 / {s['skipped']}스킵 / {s['in_progress']}진행중 / {s['pending']}대기  (총 {t})")


def main() -> None:
    parser = argparse.ArgumentParser(description="매뉴얼 임베딩 진행 상황 업데이트")
    parser.add_argument("file_path", nargs="?", help="파일 경로 (상대: 1_robot/xxx.pdf)")
    parser.add_argument("status", nargs="?", help="상태: pending|in_progress|embedded|skipped|error")
    parser.add_argument("reason", nargs="?", default="", help="스킵/오류 사유")
    parser.add_argument("--agent", default="", help="처리한 에이전트 이름")
    parser.add_argument("--chunks", type=int, default=None, help="임베딩된 청크 수")
    parser.add_argument("--init", action="store_true", help="manuals-filtered 전체 스캔하여 초기화")
    parser.add_argument("--status-only", dest="show_status", action="store_true", help="현재 진행 상황 출력")

    args = parser.parse_args()

    if args.init:
        data = init_progress()
        print(f"초기화 완료: {data['total']}개 파일 등록")
        print_status(data)
        return

    if args.show_status or (args.file_path is None and args.status is None):
        data = load_progress()
        if not data:
            print("manual_progress.json 없음 — py update_progress.py --init 으로 초기화하세요")
            sys.exit(1)
        print_status(data)
        return

    if args.file_path and args.chunks is not None and args.status is None:
        data = update_chunks(args.file_path, args.chunks)
        print(f"청크 수 업데이트: {args.file_path} → {args.chunks}건")
        return

    if not args.file_path or not args.status:
        parser.print_help()
        sys.exit(1)

    data = update_file_status(
        args.file_path,
        args.status,
        reason=args.reason,
        agent=args.agent,
        chunks=args.chunks,
    )
    print(f"업데이트: {args.file_path} → {args.status}")
    if args.reason:
        print(f"  사유: {args.reason}")
    print(f"  임베딩: {data['embedded']} / 스킵: {data['skipped']} / 대기: {data['pending']} / 총: {data['total']}")


if __name__ == "__main__":
    main()
