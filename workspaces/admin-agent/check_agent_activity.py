"""
팀원 작업 활성도 체크 도구
사용법: python check_agent_activity.py [agent_id]
         python check_agent_activity.py all
"""
import sys
import os
import json
import socket
import time
import glob
import subprocess
from datetime import datetime, timezone

sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', errors='replace', buffering=1)

BASE_DIR = r"C:\MES\wta-agents"
LOGS_DIR = os.path.join(BASE_DIR, "logs")
WORKSPACES_DIR = os.path.join(BASE_DIR, "workspaces")
AGENTS_JSON = os.path.join(BASE_DIR, "config", "agents.json")


def load_agents():
    with open(AGENTS_JSON, encoding="utf-8") as f:
        d = json.load(f)
    agents = {}
    for k, v in d.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and v.get("enabled") and v.get("port"):
            agents[v["id"]] = v
    return agents


def ping_port(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def get_recent_logs(agent_id: str, limit: int = 5):
    """로그 파일 목록 + 마지막 수정 시각"""
    patterns = [
        os.path.join(LOGS_DIR, f"channel-{agent_id}.log"),
        os.path.join(LOGS_DIR, f"{agent_id}*.log"),
        os.path.join(WORKSPACES_DIR, agent_id, "*.log"),
    ]
    found = []
    for pattern in patterns:
        for f in glob.glob(pattern):
            if os.path.isfile(f):
                mtime = os.path.getmtime(f)
                size = os.path.getsize(f)
                found.append({
                    "file": os.path.basename(f),
                    "mtime": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "mtime_ts": mtime,
                    "size_kb": round(size / 1024, 1),
                })
    # 중복 제거 후 최신순 정렬
    seen = set()
    unique = []
    for item in sorted(found, key=lambda x: x["mtime_ts"], reverse=True):
        if item["file"] not in seen:
            seen.add(item["file"])
            unique.append(item)
    return unique[:limit]


def get_state_files(agent_id: str):
    """state.json / progress.json 목록 + last_update"""
    patterns = [
        os.path.join(LOGS_DIR, f"{agent_id}*state*.json"),
        os.path.join(WORKSPACES_DIR, agent_id, "*state*.json"),
        os.path.join(WORKSPACES_DIR, agent_id, "*progress*.json"),
        os.path.join(LOGS_DIR, f"{agent_id}*progress*.json"),
    ]
    # 특수: imap-monitor-state.json
    if agent_id in ("MAX", "admin-agent"):
        patterns.append(os.path.join(LOGS_DIR, "imap-monitor-state.json"))

    found = []
    for pattern in patterns:
        for f in glob.glob(pattern):
            if os.path.isfile(f):
                mtime = os.path.getmtime(f)
                last_update = None
                try:
                    with open(f, encoding="utf-8") as fp:
                        data = json.load(fp)
                    if isinstance(data, dict):
                        last_update = (
                            data.get("last_update")
                            or data.get("updated_at")
                            or data.get("timestamp")
                            or data.get("last_run")
                        )
                except Exception:
                    pass
                found.append({
                    "file": os.path.basename(f),
                    "mtime": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "mtime_ts": mtime,
                    "last_update": str(last_update) if last_update else None,
                })
    return sorted(found, key=lambda x: x["mtime_ts"], reverse=True)


def get_background_processes(agent_id: str):
    """실행 중인 Python 스크립트 힌트 (wmic 사용)"""
    hints = []
    try:
        result = subprocess.run(
            ["wmic", "process", "get", "CommandLine,ProcessId", "/format:csv"],
            capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace"
        )
        agent_keywords = {
            "crafter": ["crafter", "playwright", "npm run", "vite", "welec"],
            "db-manager": ["db-manager", "embed", "graphrag", "neo4j"],
            "docs-agent": ["docs-agent", "docling", "wta-docling"],
            "research-agent": ["research-agent"],
            "cs-agent": ["cs-agent", "cs-wta"],
            "admin-agent": ["admin-agent", "health-check", "imap-monitor"],
            "slack-bot": ["slack-bot", "slack_bot"],
            "nc-manager": ["nc-manager"],
            "dev-agent": ["dev-agent"],
        }
        keywords = agent_keywords.get(agent_id, [agent_id.replace("-", "_"), agent_id])
        for line in result.stdout.splitlines():
            line_lower = line.lower()
            if any(kw.lower() in line_lower for kw in keywords):
                if "python" in line_lower or "node" in line_lower:
                    # PID 추출
                    parts = line.split(",")
                    cmd = parts[1] if len(parts) > 1 else line
                    pid = parts[-1].strip() if len(parts) > 1 else "?"
                    # 너무 긴 커맨드 축약
                    cmd_short = cmd.strip()[:120]
                    hints.append({"pid": pid.strip(), "cmd": cmd_short})
    except Exception as e:
        hints.append({"error": str(e)})
    return hints[:5]


def check_agent(agent_id: str, agents: dict) -> dict:
    now = time.time()

    agent_info = agents.get(agent_id)
    if not agent_info:
        return {"error": f"에이전트 '{agent_id}' 를 찾을 수 없음"}

    port = agent_info.get("port")
    host = "192.168.0.220" if agent_info.get("location") == "external" else "localhost"

    # 1. 포트 ping
    port_alive = ping_port(host, port) if port else False

    # 2. 최근 로그
    logs = get_recent_logs(agent_id)

    # 3. state.json
    states = get_state_files(agent_id)

    # 4. 백그라운드 프로세스
    procs = get_background_processes(agent_id)

    # 마지막 로그 갱신 시간
    last_log_age_sec = None
    last_log_time = None
    if logs:
        last_log_age_sec = int(now - logs[0]["mtime_ts"])
        last_log_time = logs[0]["mtime"]

    # 활성도 판단
    active_score = 0
    if port_alive:
        active_score += 2
    if last_log_age_sec is not None and last_log_age_sec < 300:  # 5분 내
        active_score += 2
    elif last_log_age_sec is not None and last_log_age_sec < 1800:  # 30분 내
        active_score += 1
    if procs:
        active_score += 1

    if active_score >= 4:
        status = "🟢 활성"
    elif active_score >= 2:
        status = "🟡 대기"
    else:
        status = "🔴 비활성"

    # 3줄 요약
    port_str = f"포트 {port} {'열림' if port_alive else '닫힘'}"
    log_str = f"마지막 로그: {last_log_time} ({last_log_age_sec}초 전)" if last_log_time else "로그 없음"
    proc_str = f"백그라운드 프로세스 {len(procs)}개" if procs else "백그라운드 없음"

    return {
        "agent_id": agent_id,
        "status": status,
        "summary": [
            f"{status} | {port_str}",
            log_str,
            proc_str,
        ],
        "detail": {
            "port": port,
            "port_alive": port_alive,
            "recent_logs": logs,
            "state_files": states,
            "background_processes": procs,
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    }


def main():
    agents = load_agents()

    if len(sys.argv) < 2:
        print("사용법: python check_agent_activity.py <agent_id|all>")
        print("에이전트 목록:", ", ".join(sorted(agents.keys())))
        return

    target = sys.argv[1]
    targets = list(agents.keys()) if target == "all" else [target]

    results = {}
    for agent_id in targets:
        print(f"\n{'='*50}")
        print(f"[{agent_id}] 활성도 점검 중...")
        result = check_agent(agent_id, agents)
        results[agent_id] = result

        if "error" in result:
            print(f"오류: {result['error']}")
            continue

        # 3줄 요약 출력
        for line in result["summary"]:
            print(f"  {line}")

    # JSON 상세 저장
    output_path = os.path.join(
        r"C:\MES\wta-agents\workspaces\admin-agent",
        "activity_result.json"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"상세 결과: {output_path}")

    # 전체 요약 (all 모드)
    if target == "all":
        print("\n[전체 요약]")
        for aid, r in results.items():
            if "summary" in r:
                print(f"  {aid}: {r['summary'][0]}")


if __name__ == "__main__":
    main()
