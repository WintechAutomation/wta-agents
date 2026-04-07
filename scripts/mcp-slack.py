"""
WTA Slack MCP 서버
슬랙 Bot API 연동 — Socket Mode로 메시지 수신, MCP 도구로 메시지 발신.
구조: Claude Code <-MCP stdio-> 이 서버 <-Socket Mode-> Slack <-> 대시보드(localhost:5555)
"""

import json
import logging
import os
import sys
import threading
import time
import urllib3
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# ── 설정 ──
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
BOT_TOKEN_FILE = CONFIG_DIR / "slack-token.txt"
APP_TOKEN_FILE = CONFIG_DIR / "slack-app-token.txt"
DASHBOARD_URL = "http://localhost:5555"
AGENT_ID = "slack-bridge"
MAX_RETRIES = 2
RETRY_DELAY = 0.5

# ── 로깅 (stderr — stdout은 MCP stdio transport가 사용) ──
logging.basicConfig(
    level=logging.INFO,
    format="[mcp-slack] %(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("mcp-slack")

# ── 토큰 로드 ──
def _load_token(path: Path, name: str) -> str:
    """토큰 파일에서 첫 줄 읽기"""
    if not path.exists():
        log.error("%s 파일 없음: %s", name, path)
        return ""
    token = path.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    if not token:
        log.error("%s 파일이 비어있음: %s", name, path)
    return token


BOT_TOKEN = _load_token(BOT_TOKEN_FILE, "Bot Token")
APP_TOKEN = _load_token(APP_TOKEN_FILE, "App-Level Token")

# ── HTTP 연결 풀 ──
_http = urllib3.PoolManager(
    num_pools=2,
    maxsize=4,
    timeout=urllib3.Timeout(connect=3, read=5),
    retries=False,
)

# ── MCP 서버 ──
mcp = FastMCP("slack-bridge", log_level="WARNING")

# ── Slack 클라이언트 (지연 초기화) ──
_slack_client = None
_users_cache: dict[str, str] = {}  # user_id -> display_name


def _get_slack_client():
    """Slack WebClient 싱글턴"""
    global _slack_client
    if _slack_client is None:
        from slack_sdk import WebClient
        _slack_client = WebClient(token=BOT_TOKEN)
    return _slack_client


def _resolve_user(user_id: str) -> str:
    """슬랙 user_id → 표시 이름 변환 (캐시)"""
    if user_id in _users_cache:
        return _users_cache[user_id]
    try:
        client = _get_slack_client()
        resp = client.users_info(user=user_id)
        if resp["ok"]:
            profile = resp["user"].get("profile", {})
            name = (
                profile.get("display_name")
                or profile.get("real_name")
                or resp["user"].get("name", user_id)
            )
            _users_cache[user_id] = name
            return name
    except Exception as e:
        log.warning("사용자 이름 조회 실패 (%s): %s", user_id, e)
    _users_cache[user_id] = user_id
    return user_id


# ── 대시보드 API ──
def _api_request(method: str, url: str, body: bytes | None = None) -> dict:
    """HTTP 요청 + 자동 재시도"""
    headers = {"Content-Type": "application/json"} if body else {}
    last_error = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            resp = _http.request(method, url, body=body, headers=headers)
            return json.loads(resp.data)
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                log.warning("API %s %s 실패 (%d/%d): %s",
                            method, url, attempt + 1, 1 + MAX_RETRIES, e)
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                log.error("API %s %s 최종 실패: %s", method, url, e)
    raise last_error  # type: ignore[misc]


def _dashboard_send(from_id: str, to: str, content: str) -> dict:
    """대시보드에 메시지 전달"""
    return _api_request(
        "POST",
        f"{DASHBOARD_URL}/api/send",
        json.dumps({"from": from_id, "to": to, "content": content}).encode(),
    )


def _dashboard_heartbeat():
    """대시보드에 하트비트 전송"""
    try:
        _api_request("POST", f"{DASHBOARD_URL}/api/heartbeat/{AGENT_ID}", b"{}")
    except Exception as e:
        log.warning("하트비트 실패: %s", e)


# ── Socket Mode 리스너 (백그라운드 스레드) ──
_socket_thread = None
_socket_running = False


def _start_socket_listener():
    """Socket Mode로 슬랙 메시지 수신 → 대시보드 전달 (백그라운드)"""
    global _socket_thread, _socket_running
    if _socket_running:
        return "이미 실행 중"
    if not APP_TOKEN:
        return "App-Level Token(xapp-) 없음. config/slack-app-token.txt에 저장 필요"
    if not BOT_TOKEN:
        return "Bot Token(xoxb-) 없음. config/slack-token.txt에 저장 필요"

    def _run():
        global _socket_running
        _socket_running = True
        try:
            from slack_bolt import App
            from slack_bolt.adapter.socket_mode import SocketModeHandler

            app = App(token=BOT_TOKEN)

            @app.event("message")
            def handle_message(event, say):
                """채널 메시지 수신 → 대시보드 전달"""
                # 봇 자신의 메시지 무시
                if event.get("bot_id") or event.get("subtype") == "bot_message":
                    return

                user_id = event.get("user", "unknown")
                user_name = _resolve_user(user_id)
                channel = event.get("channel", "unknown")
                text = event.get("text", "")
                ts = event.get("ts", "")

                # 채널 이름 조회
                channel_name = channel
                try:
                    client = _get_slack_client()
                    ch_info = client.conversations_info(channel=channel)
                    if ch_info["ok"]:
                        channel_name = ch_info["channel"].get("name", channel)
                except Exception:
                    pass

                # 대시보드에 전달 (슬랙 메시지임을 표시)
                content = f"[슬랙 #{channel_name}] {user_name}: {text}"
                try:
                    _dashboard_send(AGENT_ID, "MAX", content)
                    log.info("슬랙→대시보드: #%s %s: %s", channel_name, user_name, text[:50])
                except Exception as e:
                    log.error("대시보드 전달 실패: %s", e)

            handler = SocketModeHandler(app, APP_TOKEN)
            log.info("Socket Mode 리스너 시작")
            handler.start()  # 블로킹
        except Exception as e:
            log.error("Socket Mode 오류: %s", e)
            _socket_running = False

    _socket_thread = threading.Thread(target=_run, daemon=True)
    _socket_thread.start()
    # 연결 대기
    time.sleep(2)
    return "Socket Mode 리스너 시작됨"


# ── MCP 도구 ──

@mcp.tool()
def slack_send(channel: str, message: str) -> str:
    """슬랙 채널에 메시지를 전송합니다.

    Args:
        channel: 슬랙 채널 이름(#general) 또는 채널 ID (C0123456789)
        message: 전송할 메시지 내용
    """
    if not BOT_TOKEN:
        return "오류: Bot Token 없음"
    try:
        client = _get_slack_client()
        # #접두어 제거
        ch = channel.lstrip("#")
        resp = client.chat_postMessage(channel=ch, text=message)
        if resp["ok"]:
            return f"전송 완료: #{ch} ← {message[:50]}..."
        return f"전송 실패: {resp.get('error', '알 수 없는 오류')}"
    except Exception as e:
        return f"전송 실패: {e}"


@mcp.tool()
def slack_channels() -> str:
    """봇이 참여 중인 슬랙 채널 목록을 반환합니다."""
    if not BOT_TOKEN:
        return "오류: Bot Token 없음"
    try:
        client = _get_slack_client()
        resp = client.conversations_list(types="public_channel,private_channel", limit=100)
        if not resp["ok"]:
            return f"조회 실패: {resp.get('error')}"
        channels = resp.get("channels", [])
        if not channels:
            return "참여 중인 채널 없음"
        lines = []
        for ch in channels:
            member = "참여" if ch.get("is_member") else "미참여"
            lines.append(f"#{ch['name']} ({ch['id']}) [{member}] — {ch.get('topic', {}).get('value', '')[:40]}")
        return "\n".join(lines)
    except Exception as e:
        return f"채널 조회 실패: {e}"


@mcp.tool()
def slack_history(channel: str, count: int = 10) -> str:
    """슬랙 채널의 최근 메시지를 조회합니다.

    Args:
        channel: 채널 이름 또는 ID
        count: 조회할 메시지 수 (기본 10, 최대 50)
    """
    if not BOT_TOKEN:
        return "오류: Bot Token 없음"
    count = min(count, 50)
    try:
        client = _get_slack_client()
        ch = channel.lstrip("#")

        # 채널명이면 ID로 변환
        if not ch.startswith("C"):
            resp = client.conversations_list(types="public_channel,private_channel", limit=200)
            ch_id = None
            for c in resp.get("channels", []):
                if c["name"] == ch:
                    ch_id = c["id"]
                    break
            if not ch_id:
                return f"채널 #{ch} 를 찾을 수 없음"
            ch = ch_id

        resp = client.conversations_history(channel=ch, limit=count)
        if not resp["ok"]:
            return f"조회 실패: {resp.get('error')}"
        messages = resp.get("messages", [])
        if not messages:
            return "메시지 없음"

        lines = []
        for m in reversed(messages):
            user = _resolve_user(m.get("user", "bot"))
            text = m.get("text", "")[:200]
            ts = m.get("ts", "")
            lines.append(f"[{ts}] {user}: {text}")
        return "\n".join(lines)
    except Exception as e:
        return f"히스토리 조회 실패: {e}"


@mcp.tool()
def slack_listen_start() -> str:
    """Socket Mode 리스너를 시작합니다. 슬랙 채널 메시지를 실시간으로 수신하여 대시보드에 전달합니다."""
    return _start_socket_listener()


@mcp.tool()
def slack_listen_status() -> str:
    """Socket Mode 리스너의 현재 상태를 반환합니다."""
    if _socket_running:
        return "Socket Mode 리스너: 실행 중"
    if not APP_TOKEN:
        return "Socket Mode 리스너: 중지 (App-Level Token 없음)"
    return "Socket Mode 리스너: 중지"


# ── 메인 ──
if __name__ == "__main__":
    log.info("Slack MCP 서버 시작 (Bot Token: %s)", "있음" if BOT_TOKEN else "없음")
    log.info("App-Level Token: %s", "있음" if APP_TOKEN else "없음 — Socket Mode 비활성")

    # 대시보드 하트비트
    _dashboard_heartbeat()

    # App Token이 있으면 자동으로 Socket Mode 시작
    if APP_TOKEN:
        result = _start_socket_listener()
        log.info("Socket Mode: %s", result)

    # MCP stdio transport 시작
    mcp.run(transport="stdio")
