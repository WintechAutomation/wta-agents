#!/usr/bin/env python3
"""
세션 JSONL 파서 — Claude Code 세션 파일에서 메시지를 추출하여 대시보드 로그 업데이트

추출 대상:
  1. 텔레그램 인바운드  : user 레코드, <channel source="plugin:telegram:telegram">
  2. 텔레그램 아웃바운드: assistant 레코드, mcp__plugin_telegram_telegram__reply 도구
  3. 에이전트 채널 수신 : user 레코드, <channel source="agent-channel">
  4. 에이전트 채널 발신 : assistant 레코드, mcp__agent-channel__send_message 도구
"""

import glob
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

CLAUDE_PROJECTS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects")

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_LOG_DIR = os.path.join(os.path.dirname(_THIS_DIR), "dashboard", "logs")

# 프로젝트 경로명 → 에이전트 ID
PROJECT_AGENT_MAP: dict[str, str] = {
    "C--MES-wta-agents":                                 "MAX",
    "C--MES-wta-agents-workspaces-crafter":              "crafter",
    "C--MES-wta-agents-workspaces-db-manager":           "db-manager",
    "C--MES-wta-agents-workspaces-cs-agent":             "cs-agent",
    "C--MES-wta-agents-workspaces-nc-manager":           "nc-manager",
    "C--MES-wta-agents-workspaces-qa-agent":             "qa-agent",
    "C--MES-wta-agents-workspaces-issue-manager":        "issue-manager",
    "C--MES-wta-agents-workspaces-dev-agent":            "dev-agent",
    "C--MES-wta-agents-workspaces-admin-agent":          "admin-agent",
    "C--MES-wta-agents-workspaces-sales-agent":          "sales-agent",
    "C--MES-wta-agents-workspaces-design-agent":         "design-agent",
    "C--MES-wta-agents-workspaces-manufacturing-agent":  "manufacturing-agent",
    "C--MES-wta-agents-workspaces-slack-bot":            "slack-bot",
}


# ── 유틸 ──────────────────────────────────────────────────────────────────────

def ts_to_kst(iso_ts: str) -> str:
    """ISO UTC 타임스탬프 → KST 문자열 (YYYY-MM-DD HH:MM:SS)"""
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_ts


def dedup_key(frm: str, to: str, content: str) -> str:
    """from + to + content 앞 80자 MD5 — 중복 제거용"""
    raw = f"{frm}|{to}|{content[:80]}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


# ── 채널 태그 파서 ──────────────────────────────────────────────────────────

_ATTR_FROM    = re.compile(r'\bfrom="([^"]+)"')
_ATTR_TO      = re.compile(r'\bto="([^"]+)"')
_ATTR_TS      = re.compile(r'\bts="([^"]+)"')
_TAG_TELEGRAM = re.compile(
    r'<channel[^>]*source="plugin:telegram:telegram"[^>]*>(.*?)</channel>',
    re.DOTALL,
)
_TAG_AGENT    = re.compile(
    r'<channel[^>]*source="agent-channel"[^>]*>(.*?)</channel>',
    re.DOTALL,
)


def _parse_telegram_tags(content: str) -> list[dict]:
    results = []
    for m in _TAG_TELEGRAM.finditer(content):
        tag_full = m.group(0)
        text = m.group(1).strip()
        if not text:
            continue
        ts_m = _ATTR_TS.search(tag_full)
        results.append({
            "from": "boss",
            "to":   "MAX",
            "content": text,
            "type": "telegram",
            "ts": ts_m.group(1) if ts_m else "",
        })
    return results


def _parse_agent_channel_tags(content: str, agent_id: str) -> list[dict]:
    results = []
    for m in _TAG_AGENT.finditer(content):
        tag_full = m.group(0)
        text = m.group(1).strip()
        if not text:
            continue
        from_m = _ATTR_FROM.search(tag_full)
        ts_m   = _ATTR_TS.search(tag_full)
        frm    = from_m.group(1) if from_m else "unknown"
        results.append({
            "from": frm,
            "to":   agent_id,
            "content": text,
            "type": "chat",
            "ts": ts_m.group(1) if ts_m else "",
        })
    return results


# ── 세션 파일 파서 ────────────────────────────────────────────────────────────

def parse_session_file(filepath: str, agent_id: str) -> list[dict]:
    """단일 세션 JSONL 파일에서 메시지 목록 반환"""
    try:
        with open(filepath, encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]
    except Exception:
        return []

    messages: list[dict] = []

    for rec in records:
        rtype = rec.get("type")
        ts    = rec.get("timestamp", "")

        if rtype == "user":
            content = rec.get("message", {}).get("content", "")
            if not isinstance(content, str):
                continue

            # 텔레그램 인바운드 (MAX 세션 전용)
            if agent_id == "MAX" and "plugin:telegram:telegram" in content:
                for msg in _parse_telegram_tags(content):
                    if not msg["ts"]:
                        msg["ts"] = ts
                    messages.append(msg)

            # 에이전트 채널 수신
            if "agent-channel" in content:
                for msg in _parse_agent_channel_tags(content, agent_id):
                    if not msg["ts"]:
                        msg["ts"] = ts
                    messages.append(msg)

        elif rtype == "assistant":
            content_list = rec.get("message", {}).get("content", [])
            if not isinstance(content_list, list):
                continue

            for item in content_list:
                if not isinstance(item, dict) or item.get("type") != "tool_use":
                    continue

                name = item.get("name", "")
                inp  = item.get("input", {})

                # 텔레그램 아웃바운드 (MAX 세션 전용)
                if name == "mcp__plugin_telegram_telegram__reply" and agent_id == "MAX":
                    text = inp.get("text", "")
                    if text:
                        messages.append({
                            "from": "MAX",
                            "to":   "boss",
                            "content": text,
                            "type": "telegram",
                            "ts": ts,
                        })

                # 에이전트 채널 발신
                elif name == "mcp__agent-channel__send_message":
                    to_agent = inp.get("to", "")
                    message  = inp.get("message", "")
                    if to_agent and message:
                        messages.append({
                            "from": agent_id,
                            "to":   to_agent,
                            "content": message,
                            "type": "chat",
                            "ts": ts,
                        })

    return messages


# ── 메인 ─────────────────────────────────────────────────────────────────────

def run(target_date: date | None = None) -> int:
    """세션 JSONL 파싱 → 대시보드 로그 업데이트. 추가된 메시지 수 반환."""
    if target_date is None:
        target_date = datetime.now(KST).date()

    date_str  = target_date.strftime("%Y-%m-%d")
    log_file  = os.path.join(DASHBOARD_LOG_DIR, f"messages_{date_str}.json")

    # 기존 로그 로드
    existing: list[dict] = []
    if os.path.exists(log_file):
        try:
            with open(log_file, encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []

    # 기존 dedup 키 수집
    seen_keys: set[str] = {
        dedup_key(m.get("from", ""), m.get("to", ""), m.get("content", ""))
        for m in existing
    }

    new_messages: list[dict] = []

    for proj_name, agent_id in PROJECT_AGENT_MAP.items():
        proj_dir = os.path.join(CLAUDE_PROJECTS_DIR, proj_name)
        if not os.path.isdir(proj_dir):
            continue

        for filepath in glob.glob(os.path.join(proj_dir, "*.jsonl")):
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath), tz=KST)
            if mtime.date() != target_date:
                continue

            for msg in parse_session_file(filepath, agent_id):
                key = dedup_key(msg["from"], msg["to"], msg["content"])
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                new_messages.append(msg)

    if not new_messages:
        return 0

    # 타임스탬프 기준 정렬 (오래된 것부터)
    new_messages.sort(key=lambda m: m.get("ts", ""))

    max_id = max((m.get("id", 0) for m in existing), default=0)

    combined = list(existing)
    for i, msg in enumerate(new_messages, start=1):
        combined.append({
            "id":      max_id + i,
            "from":    msg["from"],
            "to":      msg["to"],
            "content": msg["content"],
            "type":    msg.get("type", "chat"),
            "time":    ts_to_kst(msg["ts"]) if msg.get("ts") else date_str + " 00:00:00",
        })

    os.makedirs(DASHBOARD_LOG_DIR, exist_ok=True)
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    return len(new_messages)


if __name__ == "__main__":
    added = run()
    print(f"동기화 완료: {added}건 추가")
    sys.exit(0)
