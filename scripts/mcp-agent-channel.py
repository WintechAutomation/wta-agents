"""
에이전트 채널 MCP 서버
각 에이전트 Claude Code 세션의 통신 채널.
- 대시보드 WebSocket으로 에이전트 간 메시지 수신/발신
- 슬랙 채널 직접 모니터링/응답 (선택)

사용법: python mcp-agent-channel.py <agent_id> [--slack-channel <채널명>]
"""
import json
import logging
import os
import sys
import time
import threading
import traceback
import uuid
import urllib.request
from queue import Queue, Empty
from http.server import HTTPServer, BaseHTTPRequestHandler

from mcp.server.fastmcp import FastMCP

# ── 인자 파싱 ──
args = sys.argv[1:]
if not args:
    print("사용법: python mcp-agent-channel.py <agent_id> [--slack-channel <채널명>]", file=sys.stderr)
    sys.exit(1)

AGENT_ID = args[0]
SLACK_CHANNEL = None
if "--slack-channel" in args:
    idx = args.index("--slack-channel")
    if idx + 1 < len(args):
        SLACK_CHANNEL = args[idx + 1]

HTTP_PORT = None
if "--http-port" in args:
    idx = args.index("--http-port")
    if idx + 1 < len(args):
        HTTP_PORT = int(args[idx + 1])

DASHBOARD_URL = "http://localhost:5555"
POLL_INTERVAL = 3  # 초

# ── 로깅 (stderr) ──
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format=f"[channel:{AGENT_ID}] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
log = logging.getLogger(f"channel-{AGENT_ID}")

_fh = logging.FileHandler(os.path.join(LOG_DIR, f"channel-{AGENT_ID}.log"), encoding="utf-8")
_fh.setLevel(logging.INFO)
_fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log.addHandler(_fh)

# ── 메시지 큐 ──
message_queue = Queue()

# ── 웹채팅 응답 큐 (request_id → Queue) ──
web_response_queues = {}

# ── MCP 서버 ──
mcp = FastMCP(f"agent-channel-{AGENT_ID}", log_level="WARNING")

# ── HTTP 헬퍼 ──
def _http_get(url):
    try:
        resp = urllib.request.urlopen(url, timeout=5)
        return json.loads(resp.read())
    except Exception:
        return None

def _http_post(url, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    for attempt in range(2):
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            return json.loads(resp.read())
        except Exception as e:
            if attempt == 0:
                time.sleep(0.5)
            else:
                log.warning(f"POST 실패: {e}")
                return None

# ── 슬랙 클라이언트 (선택) ──
slack_client = None
slack_channel_id = None

if SLACK_CHANNEL:
    try:
        from slack_sdk import WebClient
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        token = open(os.path.join(config_dir, "slack-token.txt")).read().strip()
        slack_client = WebClient(token=token)
        # 채널 ID 조회
        resp = slack_client.conversations_list(types="public_channel", limit=200)
        for ch in resp["channels"]:
            if ch["name"] == SLACK_CHANNEL:
                slack_channel_id = ch["id"]
                break
        if slack_channel_id:
            log.info(f"슬랙 채널 연결: #{SLACK_CHANNEL} ({slack_channel_id})")
        else:
            log.warning(f"슬랙 채널 #{SLACK_CHANNEL} 찾을 수 없음")
    except Exception as e:
        log.warning(f"슬랙 초기화 실패: {e}")

# ── 백그라운드 폴링: 대시보드 ──
def poll_dashboard():
    """대시보드에서 이 에이전트 앞으로 온 메시지를 폴링"""
    while True:
        try:
            _http_post(f"{DASHBOARD_URL}/api/heartbeat/{AGENT_ID}", {})
            result = _http_get(f"{DASHBOARD_URL}/api/recv/{AGENT_ID}")
            if result:
                for msg in result.get("messages", []):
                    source = f"[{msg.get('from', '?')}]"
                    content = msg.get("content", "")
                    message_queue.put(f"{source} {content}")
                    log.info(f"대시보드 수신: {source} {content[:60]}")
        except Exception as e:
            log.error(f"대시보드 폴링 오류: {e}")
        time.sleep(POLL_INTERVAL)

# ── 백그라운드 폴링: 슬랙 ──
last_slack_ts = str(time.time())

def poll_slack():
    """슬랙 채널에서 새 메시지 폴링"""
    global last_slack_ts
    if not slack_client or not slack_channel_id:
        return
    while True:
        try:
            resp = slack_client.conversations_history(
                channel=slack_channel_id, oldest=last_slack_ts, limit=10
            )
            messages = resp.get("messages", [])
            for msg in reversed(messages):
                # 봇 메시지 무시
                if msg.get("bot_id") or msg.get("subtype"):
                    continue
                user_id = msg.get("user", "unknown")
                text = msg.get("text", "")
                ts = msg.get("ts", "")
                if not text.strip():
                    continue
                # 사용자 이름 조회
                try:
                    user_info = slack_client.users_info(user=user_id)
                    username = user_info["user"]["real_name"] or user_info["user"]["name"]
                except Exception:
                    username = user_id
                message_queue.put(f"[슬랙 #{SLACK_CHANNEL}] {username}: {text}")
                log.info(f"슬랙 수신: {username}: {text[:60]}")
                last_slack_ts = ts
        except Exception as e:
            log.error(f"슬랙 폴링 오류: {e}")
        time.sleep(POLL_INTERVAL)


# ── 웹채팅 HTTP API 핸들러 ──

class ChatAPIHandler(BaseHTTPRequestHandler):
    """웹 채팅 브릿지 HTTP API"""

    def log_message(self, format, *args):
        log.info(f"HTTP {format % args}")

    def _send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(200, {"ok": True})

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "agent": AGENT_ID})
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/api/chat":
            self._send_json(404, {"error": "Not found"})
            return

        # API Key 인증
        api_key = self.headers.get("X-API-Key", "")
        expected_key = os.environ.get("CS_API_KEY", "")
        if not expected_key or api_key != expected_key:
            self._send_json(401, {"error": "Invalid API key"})
            return

        # 요청 파싱
        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON"})
            return

        query = data.get("query", "").strip()
        if not query:
            self._send_json(400, {"error": "query is required"})
            return

        # 요청 ID 생성 및 응답 큐 등록
        request_id = uuid.uuid4().hex[:8]
        response_queue = Queue()
        web_response_queues[request_id] = response_queue

        # cs-agent 세션에 메시지 주입
        chat_payload = json.dumps({
            "type": "web-chat",
            "request_id": request_id,
            "query": query,
            "language": data.get("language", "ko"),
            "equipment_id": data.get("equipment_id"),
            "error_code": data.get("error_code"),
            "message_history": data.get("message_history", []),
        }, ensure_ascii=False)
        message_queue.put(f"[web-chat:{request_id}] {chat_payload}")
        log.info(f"웹채팅 요청: {request_id} - {query[:80]}")

        # 응답 대기 (60초)
        try:
            response = response_queue.get(timeout=60)
            self._send_json(200, {
                "success": True,
                "request_id": request_id,
                "response": response,
            })
        except Empty:
            log.warning(f"웹채팅 타임아웃: {request_id}")
            self._send_json(504, {
                "success": False,
                "error": "cs-agent response timeout (60s)",
                "request_id": request_id,
            })
        finally:
            web_response_queues.pop(request_id, None)


# ── MCP 도구 ──

@mcp.tool()
def wait_for_message(max_wait: int = 60) -> str:
    """메시지가 올 때까지 대기합니다. 메시지가 도착하면 즉시 반환합니다.
    대기 중에도 하트비트를 유지합니다.

    Args:
        max_wait: 최대 대기 시간(초). 기본 60초.
    """
    waited = 0
    while waited < max_wait:
        try:
            msg = message_queue.get_nowait()
            return msg
        except Empty:
            pass
        time.sleep(min(POLL_INTERVAL, max_wait - waited))
        waited += POLL_INTERVAL

    return "(대기 시간 초과, 수신 메시지 없음. 다시 wait_for_message를 호출하세요.)"


_ALLOWED_MSG_TYPES = {
    "report_complete",
    "report_progress",
    "report_blocked",
    "reply",
    "request",
}


@mcp.tool()
def send_message(
    to: str,
    message: str,
    msg_type: str = "reply",
    task_id: str | None = None,
) -> str:
    """에이전트 또는 슬랙에 메시지를 전송합니다.

    Args:
        to: 수신자. 에이전트ID(MAX, nc-manager 등) 또는 "slack"(담당 슬랙 채널로 전송)
        message: 전송할 내용
        msg_type: 메시지 타입 (필수 명시 권장).
            - report_complete: 받은 작업을 완료했을 때 (task_id 필수)
            - report_progress: 진행 중간 보고 (task_id 필수)
            - report_blocked: 막힘/승인 대기 (task_id 필수)
            - reply: 단순 답변/질의 (task_id 불필요, 기본값)
            - request: 다른 팀원에게 작업 요청 (새 task 자동 생성)
        task_id: 작업큐 task_id. report_* 유형일 때 필수.
    """
    if msg_type not in _ALLOWED_MSG_TYPES:
        raise ValueError(
            f"잘못된 msg_type={msg_type}. 허용값: {sorted(_ALLOWED_MSG_TYPES)}"
        )
    if msg_type.startswith("report_") and not task_id:
        raise ValueError(f"msg_type={msg_type}에는 task_id가 필수입니다.")

    # 웹채팅 응답 라우팅
    if to.startswith("web-chat:"):
        request_id = to.split(":", 1)[1]
        rq = web_response_queues.get(request_id)
        if rq:
            rq.put(message)
            log.info(f"웹채팅 응답 전달: {request_id}")
            return f"웹채팅 응답 전송 완료 (request_id: {request_id})"
        log.warning(f"웹채팅 요청 ID 없음: {request_id}")
        return f"웹채팅 요청 ID를 찾을 수 없음: {request_id} (타임아웃 또는 이미 응답됨)"

    if to == "slack":
        # 슬랙 채널로 직접 전송
        if slack_client and slack_channel_id:
            try:
                slack_client.chat_postMessage(channel=slack_channel_id, text=message)
                log.info(f"슬랙 전송: #{SLACK_CHANNEL}: {message[:60]}")
                return f"슬랙 #{SLACK_CHANNEL}에 전송 완료"
            except Exception as e:
                log.error(f"슬랙 전송 실패: {e}")
                return f"슬랙 전송 실패: {e}"
        else:
            return "슬랙 채널 미설정"
    else:
        # 대시보드를 통해 에이전트에 전송
        payload = {
            "from": AGENT_ID,
            "to": to,
            "content": message,
            "msg_type": msg_type,
        }
        if task_id:
            payload["task_id"] = task_id
        result = _http_post(f"{DASHBOARD_URL}/api/send", payload)
        if result:
            return f"전송 완료 → {to} (id: {result.get('id', '?')}, type: {msg_type})"
        return f"전송 실패 → {to}"


@mcp.tool()
def check_status() -> str:
    """시스템 상태를 확인합니다."""
    result = _http_get(f"{DASHBOARD_URL}/api/status")
    if not result:
        return "상태 조회 실패"
    agents = result.get("agents", [])
    stats = result.get("stats", {})
    lines = [f"온라인 {stats.get('online_count', 0)}/{stats.get('total_agents', 0)}"]
    for a in agents:
        s = "ON" if a.get("online") else "OFF"
        lines.append(f"  [{s}] {a.get('emoji', '')} {a.get('agent_id', '?')}")
    return "\n".join(lines)


# ── 메인 ──
if __name__ == "__main__":
    log.info(f"에이전트 채널 시작: {AGENT_ID} (슬랙: #{SLACK_CHANNEL or '없음'})")

    # 하트비트
    _http_post(f"{DASHBOARD_URL}/api/heartbeat/{AGENT_ID}", {})

    # 대시보드 폴링 시작
    t1 = threading.Thread(target=poll_dashboard, daemon=True)
    t1.start()

    # 슬랙 폴링 시작 (설정된 경우)
    if SLACK_CHANNEL and slack_client and slack_channel_id:
        t2 = threading.Thread(target=poll_slack, daemon=True)
        t2.start()

    # HTTP API 서버 시작 (--http-port 지정 시)
    if HTTP_PORT:
        http_server = HTTPServer(("0.0.0.0", HTTP_PORT), ChatAPIHandler)
        t_http = threading.Thread(target=http_server.serve_forever, daemon=True)
        t_http.start()
        log.info(f"HTTP API 서버 시작: 포트 {HTTP_PORT}")

    # MCP 서버 시작
    mcp.run(transport="stdio")
