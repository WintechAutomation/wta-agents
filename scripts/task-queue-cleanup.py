"""
작업큐 자동 정리 스크립트
매시 정각 실행 — done 24시간 이상 삭제, in_progress 2시간 이상 MAX 알림, 중복 정리
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8")

KST = timezone(timedelta(hours=9))
TASK_QUEUE_URL = "http://localhost:5555/api/task-queue"
DONE_TTL_HOURS = 24
STALE_INPROGRESS_HOURS = 2


def now_kst():
    return datetime.now(KST)


def parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(s[:19], fmt[:len(fmt)])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=KST)
            return dt
        except ValueError:
            continue
    return None


def fetch_tasks() -> list[dict]:
    req = urllib.request.Request(TASK_QUEUE_URL)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def delete_task(task_id: str) -> bool:
    req = urllib.request.Request(
        f"{TASK_QUEUE_URL}/{task_id}",
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status in (200, 204)
    except Exception:
        return False


def send_to_max(message: str):
    """agent-channel send_message — MAX에게 알림"""
    try:
        payload = json.dumps({"to": "MAX", "message": message}).encode()
        req = urllib.request.Request(
            "http://localhost:5600/send",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception as e:
        print(f"[알림] MAX 전송 실패 (MCP 직접 전송 불가): {e}")
        print(f"[알림 내용] {message}")


def main():
    now = now_kst()
    print(f"[task-queue-cleanup] {now.strftime('%Y-%m-%d %H:%M')} 시작")

    try:
        tasks = fetch_tasks()
    except Exception as e:
        print(f"[오류] 작업큐 조회 실패: {e}")
        sys.exit(1)

    deleted_done = 0
    stale_inprogress = []
    seen_keys: dict[str, str] = {}  # (agent+task) → first task_id
    duplicates = []

    for t in tasks:
        tid = t.get("id", "")
        status = t.get("status", "")
        agent = t.get("agent", "")
        task_name = (t.get("task") or t.get("message", ""))[:80]
        updated_at = parse_dt(t.get("updated_at") or t.get("completed_at"))
        created_at = parse_dt(t.get("created_at"))

        # 1. done 24시간 이상 → 삭제
        if status == "done" and updated_at:
            age = now - updated_at
            if age > timedelta(hours=DONE_TTL_HOURS):
                if delete_task(tid):
                    deleted_done += 1
                    print(f"  [삭제] {tid} (done {int(age.total_seconds()//3600)}h 경과)")
                continue

        # 2. in_progress 2시간 이상 → 알림 대상 수집
        if status == "in_progress" and (updated_at or created_at):
            ref_dt = updated_at or created_at
            age = now - ref_dt
            if age > timedelta(hours=STALE_INPROGRESS_HOURS):
                stale_inprogress.append({
                    "id": tid,
                    "agent": agent,
                    "task": task_name,
                    "hours": int(age.total_seconds() // 3600),
                })

        # 3. 중복 감지 (동일 agent + task명 + pending)
        if status == "pending":
            dedup_key = f"{agent}||{task_name[:40]}"
            if dedup_key in seen_keys:
                duplicates.append(tid)
                print(f"  [중복] {tid} (원본: {seen_keys[dedup_key]})")
            else:
                seen_keys[dedup_key] = tid

    # 중복 삭제
    deleted_dup = 0
    for tid in duplicates:
        if delete_task(tid):
            deleted_dup += 1

    # 결과 출력
    print(f"[task-queue-cleanup] 완료:")
    print(f"  done 삭제: {deleted_done}건")
    print(f"  중복 삭제: {deleted_dup}건")
    print(f"  장기 in_progress: {len(stale_inprogress)}건")

    # 장기 in_progress가 있으면 MAX 알림
    if stale_inprogress:
        lines = ["[작업큐 경고] 장기 in_progress 작업 감지"]
        for s in stale_inprogress:
            lines.append(f"- {s['agent']} ({s['hours']}h): {s['task'][:60]}")
        send_to_max("\n".join(lines))


if __name__ == "__main__":
    main()
