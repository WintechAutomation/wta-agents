"""
에이전트 인박스 MCP 서버
각 에이전트의 Claude Code 세션에 메시지를 전달하는 MCP 도구.
대시보드(localhost:5555) REST API로 메시지 송수신.
사용법: python mcp-agent-inbox.py <agent_id>
"""
import json
import logging
import os
import sys
import time
import traceback
import urllib.request

from mcp.server.fastmcp import FastMCP

# ── 에이전트 ID (인자로 받음) ──
if len(sys.argv) < 2:
    print("사용법: python mcp-agent-inbox.py <agent_id>", file=sys.stderr)
    sys.exit(1)

AGENT_ID = sys.argv[1]
DASHBOARD_URL = "http://localhost:5555"
POLL_INTERVAL = 3  # 초
POLL_MAX_WAIT = 60  # 최대 대기 시간 (초)

# ── 로깅 (stderr — stdout은 MCP stdio) ──
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format=f"[inbox:{AGENT_ID}] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(f"inbox-{AGENT_ID}")

# 파일 에러 로그
_fh = logging.FileHandler(os.path.join(LOG_DIR, f"inbox-{AGENT_ID}-error.log"), encoding="utf-8")
_fh.setLevel(logging.WARNING)
_fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log.addHandler(_fh)

# ── MCP 서버 ──
mcp = FastMCP(f"agent-inbox-{AGENT_ID}", log_level="WARNING")


def _api_get(path):
    """대시보드 GET"""
    try:
        resp = urllib.request.urlopen(f"{DASHBOARD_URL}{path}", timeout=5)
        return json.loads(resp.read())
    except Exception as e:
        log.error(f"GET {path} 실패: {e}")
        return None


def _api_post(path, data):
    """대시보드 POST (재시도 1회)"""
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{DASHBOARD_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    for attempt in range(2):
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            return json.loads(resp.read())
        except Exception as e:
            if attempt == 0:
                time.sleep(0.5)
            else:
                log.error(f"POST {path} 실패: {e}")
                return None


# ── 시작 시 하트비트 ──
_api_post(f"/api/heartbeat/{AGENT_ID}", {})


# ── MCP 도구 ──

@mcp.tool()
def inbox_wait(max_wait: int = 60) -> str:
    """메시지가 올 때까지 대기합니다. 메시지가 오면 즉시 반환합니다.

    Args:
        max_wait: 최대 대기 시간(초). 기본 60초. 메시지 없으면 빈 결과 반환.
    """
    # 하트비트
    _api_post(f"/api/heartbeat/{AGENT_ID}", {})

    waited = 0
    while waited < max_wait:
        result = _api_get(f"/api/recv/{AGENT_ID}")
        if result:
            messages = result.get("messages", [])
            if messages:
                lines = []
                for m in messages:
                    lines.append(f"[{m.get('time', '?')}] {m.get('from', '?')}: {m.get('content', '')}")
                log.info(f"메시지 {len(messages)}건 수신")
                return "\n".join(lines)
        time.sleep(POLL_INTERVAL)
        waited += POLL_INTERVAL

    # 하트비트 갱신
    _api_post(f"/api/heartbeat/{AGENT_ID}", {})
    return "(대기 시간 초과, 수신 메시지 없음)"


@mcp.tool()
def inbox_reply(to: str, message: str) -> str:
    """메시지를 전송합니다.

    Args:
        to: 수신자 (MAX, slack-bot, 또는 다른 에이전트 ID)
        message: 전송할 내용
    """
    try:
        _api_post(f"/api/heartbeat/{AGENT_ID}", {})
        result = _api_post("/api/send", {
            "from": AGENT_ID,
            "to": to,
            "content": message,
        })
        if result:
            return f"전송 완료 → {to} (id: {result.get('id', '?')})"
        return "전송 실패"
    except Exception as e:
        log.error(f"inbox_reply 실패: {e}\n{traceback.format_exc()}")
        return f"전송 실패: {e}"


@mcp.tool()
def inbox_status() -> str:
    """대시보드 시스템 상태를 확인합니다."""
    try:
        result = _api_get("/api/status")
        if not result:
            return "상태 조회 실패"
        agents = result.get("agents", [])
        stats = result.get("stats", {})
        lines = [f"온라인 {stats.get('online_count', 0)}/{stats.get('total_agents', 0)}", ""]
        for a in agents:
            status = "ON" if a.get("online") else "OFF"
            lines.append(f"[{status}] {a.get('emoji', '')} {a.get('agent_id', '?')}")
        return "\n".join(lines)
    except Exception as e:
        return f"상태 조회 실패: {e}"


# ── 메인 ──
if __name__ == "__main__":
    log.info(f"인박스 MCP 시작: {AGENT_ID}")
    mcp.run(transport="stdio")
