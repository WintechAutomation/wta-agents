#!/usr/bin/env python3
"""
작업 큐 점검 스크립트 — MAX 크론 점검용
- config/task-queue.json 읽기
- in_progress 상태 15분 초과 무응답 stalled 탐지
- 팀원 MCP 포트 ping (온/오프라인 확인)
- 결과를 JSON stdout 출력 + /api/task-queue/check-result 에 저장
"""
import json
import os
import sys
import socket
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

# Windows cp949 인코딩 에러 방지
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK_QUEUE_FILE = os.path.join(BASE_DIR, "config", "task-queue.json")
AGENTS_CONFIG_FILE = os.path.join(BASE_DIR, "config", "agents.json")
DASHBOARD_URL = "http://localhost:5555"
STALL_THRESHOLD_MIN = 15
KST = timezone(timedelta(hours=9))


def now_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


def load_tasks() -> list:
    if not os.path.exists(TASK_QUEUE_FILE):
        return []
    try:
        with open(TASK_QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("tasks", [])
    except Exception:
        return []


def load_agents() -> dict:
    if not os.path.exists(AGENTS_CONFIG_FILE):
        return {}
    try:
        with open(AGENTS_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def is_stalled(task: dict) -> bool:
    if task.get("status") != "in_progress":
        return False
    updated_at = task.get("updated_at")
    if not updated_at:
        return False
    try:
        dt = datetime.fromisoformat(updated_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KST)
        elapsed = (datetime.now(KST) - dt).total_seconds()
        return elapsed > STALL_THRESHOLD_MIN * 60
    except Exception:
        return False


def ping_port(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def check_agent_ports(agents: dict) -> dict:
    results = {}
    for agent_id, cfg in agents.items():
        port = cfg.get("port")
        if not port or not cfg.get("enabled", False):
            continue
        host = cfg.get("host", "127.0.0.1")
        online = ping_port(host, port)
        results[agent_id] = {
            "port": port,
            "online": online,
            "name": cfg.get("name", agent_id),
            "emoji": cfg.get("emoji", "🤖"),
        }
    return results


def post_check_result(result: dict) -> bool:
    try:
        payload = json.dumps(result).encode("utf-8")
        req = urllib.request.Request(
            f"{DASHBOARD_URL}/api/task-queue/check-result",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception:
        return False


def send_to_max(result: dict) -> bool:
    """점검 결과를 MAX에게 전송하여 분석/조치 요청."""
    stalled = result.get("stalled", [])
    offline = result.get("offline_agents", [])
    active = result.get("active_tasks", 0)
    total = result.get("total_tasks", 0)
    checked_at = result.get("checked_at", "")

    # 요약 메시지 생성
    lines = [
        f"[작업큐 자동 점검] {checked_at}",
        f"전체 {total}건 / 활성 {active}건 / 무응답 {len(stalled)}건 / 오프라인 {len(offline)}건",
    ]

    if stalled:
        lines.append("")
        lines.append("⚠️ 무응답 (15분 초과):")
        for s in stalled:
            lines.append(f"  - {s['agent']}: {s['task']} (마지막 업데이트: {s.get('updated_at', '?')})")

    if offline:
        lines.append("")
        lines.append("🔴 오프라인 팀원:")
        for o in offline:
            lines.append(f"  - {o.get('name', o['id'])} (포트 {o.get('port', '?')})")

    # 이슈가 없으면 MAX에게 보내지 않음 (부하 절감)
    if not stalled and not offline:
        print("[INFO] 이슈 없음 — MAX 전송 생략")
        return True

    lines.append("")
    lines.append("위 현황을 분석하고 판단해서 조치해주세요:")
    if stalled:
        lines.append("- 무응답 팀원: 상태 확인 후 필요시 부서장에게 보고")
    if offline:
        lines.append("- 오프라인 팀원: 재시작 필요 여부 판단 후 부서장 알림")

    message = "\n".join(lines)

    try:
        payload = json.dumps({
            "from": "scheduler",
            "to": "MAX",
            "content": message,
            "ts": datetime.now(timezone.utc).isoformat(),
        }).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:5600/message",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
        print("[OK] MAX에게 분석 요청 전송 완료")
        return True
    except Exception as e:
        print(f"[WARN] MAX 전송 실패: {e}", file=sys.stderr)
        return False


def main():
    tasks = load_tasks()
    agents = load_agents()

    stalled = []
    active = []
    for t in tasks:
        if t.get("status") in ("pending", "in_progress"):
            active.append(t)
        if is_stalled(t):
            stalled.append({
                "id": t["id"],
                "agent": t.get("agent", "unknown"),
                "task": t.get("task", ""),
                "status": t.get("status"),
                "updated_at": t.get("updated_at"),
                "last_report_at": t.get("last_report_at"),
                "message": "⚠️ {agent} '{task}' 15분 무응답 — 터미널 승인 대기 가능성".format(
                    agent=t.get("agent", "unknown"),
                    task=t.get("task", ""),
                ),
            })

    agent_status = check_agent_ports(agents)
    offline_agents = [
        {"id": aid, **info}
        for aid, info in agent_status.items()
        if not info["online"]
    ]

    result = {
        "checked_at": now_kst(),
        "total_tasks": len(tasks),
        "active_tasks": len(active),
        "stalled_count": len(stalled),
        "stalled": stalled,
        "agent_status": agent_status,
        "offline_agents": offline_agents,
        "offline_count": len(offline_agents),
    }

    # stdout 출력
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 대시보드 API에 저장
    post_check_result(result)

    # MAX에게 분석 요청 전송
    send_to_max(result)

    # 점검 자체는 항상 성공 (exit 0)
    sys.exit(0)


if __name__ == "__main__":
    main()
