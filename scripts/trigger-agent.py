"""
에이전트 메시지 트리거 스크립트
cron job에서 호출하여 특정 에이전트에게 메시지를 전송한다.

사용법:
  python trigger-agent.py <agent_id> "<메시지>"

예시:
  python trigger-agent.py nc-manager "주간 부적합 리포트 생성해서 #품질관리 슬랙에 발송해주세요"
"""
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

AGENT_PORTS = {
    "MAX": 5600,
    "db-manager": 5601,
    "cs-agent": 5602,
    "sales-agent": 5603,
    "design-agent": 5604,
    "manufacturing-agent": 5605,
    "dev-agent": 5606,
    "admin-agent": 5607,
    "crafter": 5608,
    "nc-manager": 5609,
    "qa-agent": 5610,
    "issue-manager": 5611,
    "slack-bot": 5612,
}

DASHBOARD_URL = "http://localhost:5555"
FROM_AGENT = "scheduler"


def send_to_agent(agent_id: str, message: str) -> bool:
    port = AGENT_PORTS.get(agent_id)
    if not port:
        print(f"[ERROR] 알 수 없는 에이전트: {agent_id}", file=sys.stderr)
        return False

    payload = json.dumps({
        "from": FROM_AGENT,
        "to": agent_id,
        "content": message,
        "ts": datetime.now(timezone.utc).isoformat(),
    }).encode("utf-8")

    # 1) 에이전트 MCP 포트로 직접 전송
    try:
        req = urllib.request.Request(
            f"http://localhost:{port}/message",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print(f"[OK] {agent_id} 메시지 전송 성공")
            else:
                print(f"[WARN] {agent_id} 응답 이상: {result}")
    except urllib.error.URLError as e:
        print(f"[ERROR] {agent_id} 포트 {port} 연결 실패: {e}", file=sys.stderr)
        return False

    # 2) 대시보드 로깅 (fire-and-forget)
    try:
        log_payload = json.dumps({
            "from": FROM_AGENT,
            "to": agent_id,
            "content": message,
        }).encode("utf-8")
        log_req = urllib.request.Request(
            f"{DASHBOARD_URL}/api/send",
            data=log_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(log_req, timeout=2)
    except Exception:
        pass  # 로깅 실패는 무시

    return True


def main():
    if len(sys.argv) < 3:
        print("사용법: trigger-agent.py <agent_id> <message>", file=sys.stderr)
        sys.exit(1)

    agent_id = sys.argv[1]
    message = sys.argv[2]
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    print(f"[{now}] 트리거: {agent_id} ← {message[:80]}")

    success = send_to_agent(agent_id, message)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
