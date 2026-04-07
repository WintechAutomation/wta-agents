"""
slack_cs_export.py — 슬랙 #cs 채널 전체 대화 내역 JSONL 추출

저장: reports/slack-cs-history.jsonl
각 라인: {"ts", "thread_ts", "user", "user_id", "text", "files", "reactions", "reply_count"}
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta
from typing import Optional

# ── 경로 설정 ──────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR     = os.path.dirname(os.path.dirname(SCRIPT_DIR))          # wta-agents/
CONFIG_DIR   = os.path.join(ROOT_DIR, "config")
REPORTS_DIR  = os.path.join(ROOT_DIR, "reports")
OUTPUT_FILE  = os.path.join(REPORTS_DIR, "slack-cs-history.jsonl")
KST          = timezone(timedelta(hours=9))

# ── 토큰 로드 ──────────────────────────────────────────────────
def _load_token(filename: str) -> str:
    path = os.path.join(CONFIG_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

BOT_TOKEN = _load_token("slack-token.txt")

# ── Slack API 호출 ─────────────────────────────────────────────
def _slack_get(method: str, params: dict) -> dict:
    """Slack Web API GET 호출. Rate limit 시 재시도."""
    url = f"https://slack.com/api/{method}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {BOT_TOKEN}"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code}: {e.reason}")
        if data.get("ok"):
            return data
        if data.get("error") == "ratelimited":
            wait = int(data.get("retry_after", 60))
            print(f"  Rate limit — {wait}초 대기...", flush=True)
            time.sleep(wait)
            continue
        raise RuntimeError(f"Slack API 오류 ({method}): {data.get('error')}")
    raise RuntimeError(f"Slack API 반복 실패 ({method})")


# ── 채널 ID 조회 ───────────────────────────────────────────────
def find_channel_id(name: str) -> str:
    cursor = ""
    while True:
        params: dict = {"types": "public_channel,private_channel", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        data = _slack_get("conversations.list", params)
        for ch in data.get("channels", []):
            if ch["name"] == name:
                return ch["id"]
        cursor = data.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
    raise RuntimeError(f"채널 '{name}' 을 찾을 수 없습니다.")


# ── 유저 이름 캐시 ─────────────────────────────────────────────
_user_cache: dict[str, str] = {}

def resolve_user(user_id: str) -> str:
    if not user_id:
        return ""
    if user_id in _user_cache:
        return _user_cache[user_id]
    try:
        data = _slack_get("users.info", {"user": user_id})
        profile = data["user"].get("profile", {})
        name = (
            profile.get("real_name_normalized")
            or profile.get("real_name")
            or data["user"].get("real_name")
            or data["user"].get("name")
            or user_id
        )
    except Exception:
        name = user_id
    _user_cache[user_id] = name
    return name


# ── 메시지 정규화 ──────────────────────────────────────────────
def _normalize_message(msg: dict) -> dict:
    user_id = msg.get("user", "")
    bot_id  = msg.get("bot_id", "")
    username = msg.get("username", "")

    if user_id:
        display_name = resolve_user(user_id)
    elif username:
        display_name = username
    elif bot_id:
        display_name = f"[bot:{bot_id}]"
    else:
        display_name = "unknown"

    files = [
        {"name": f.get("name", ""), "url": f.get("url_private", "")}
        for f in msg.get("files", [])
    ]
    reactions = [
        {"name": r.get("name", ""), "count": r.get("count", 0)}
        for r in msg.get("reactions", [])
    ]

    ts = msg.get("ts", "")
    try:
        dt = datetime.fromtimestamp(float(ts), tz=KST)
        dt_str = dt.strftime("%Y-%m-%d %H:%M:%S KST")
    except Exception:
        dt_str = ""

    record: dict = {
        "ts":           ts,
        "datetime":     dt_str,
        "user_id":      user_id,
        "user":         display_name,
        "text":         msg.get("text", ""),
        "thread_ts":    msg.get("thread_ts", ""),
        "reply_count":  msg.get("reply_count", 0),
        "subtype":      msg.get("subtype", ""),
    }
    if files:
        record["files"] = files
    if reactions:
        record["reactions"] = reactions
    return record


# ── 메인 추출 ──────────────────────────────────────────────────
def export_cs_history():
    os.makedirs(REPORTS_DIR, exist_ok=True)

    print("채널 ID 조회 중...", flush=True)
    channel_id = find_channel_id("cs")
    print(f"#cs 채널 ID: {channel_id}", flush=True)

    messages: list[dict] = []
    cursor = ""
    page = 0

    print("메시지 수집 중...", flush=True)
    while True:
        params: dict = {
            "channel": channel_id,
            "limit": 200,
            "inclusive": "true",
        }
        if cursor:
            params["cursor"] = cursor

        data = _slack_get("conversations.history", params)
        batch = data.get("messages", [])
        messages.extend(batch)
        page += 1
        print(f"  페이지 {page}: {len(batch)}건 (누적 {len(messages)}건)", flush=True)

        cursor = data.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
        time.sleep(0.5)  # Rate limit 여유

    # 오래된 순으로 정렬
    messages.sort(key=lambda m: float(m.get("ts", 0)))

    print(f"\n유저 이름 변환 중 ({len(messages)}건)...", flush=True)
    records: list[dict] = []
    for i, msg in enumerate(messages):
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(messages)} 처리 중...", flush=True)
        records.append(_normalize_message(msg))
        time.sleep(0.05)  # users.info rate limit 여유

    # JSONL 저장
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\n완료: {len(records)}건 저장됨", flush=True)
    print(f"경로: {OUTPUT_FILE}", flush=True)
    return len(records)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    count = export_cs_history()
    print(f"\n총 {count}건 추출 완료.")
