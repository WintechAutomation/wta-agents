#!/usr/bin/env python3
"""전 에이전트 settings.json에 permissions.allow 일괄 추가"""
import json
import sys

ALLOW_RULES = [
    r"Read(C:\MES\**)",
    r"Edit(C:\MES\**)",
    r"Write(C:\MES\**)",
    r"Read(C:\wMES\**)",
    r"Edit(C:\wMES\**)",
    r"Write(C:\wMES\**)",
    r"Read(C:\Users\Administrator\.claude\**)",
    r"Edit(C:\Users\Administrator\.claude\**)",
    r"Write(C:\Users\Administrator\.claude\**)",
    r"Read(C:\Users\Administrator\.ssh\**)",
    r"Read(D:\csagent\**)",
    r"Edit(D:\csagent\**)",
    r"Write(D:\csagent\**)",
    r"Read(D:\wMES_FILES\**)",
    r"Edit(D:\wMES_FILES\**)",
    r"Write(D:\wMES_FILES\**)",
    r"Read(\\192.168.1.6\**)",
    r"Read(\\192.168.0.210\**)",
    "Bash(*)",
]

AGENTS = [
    "admin-agent", "crafter", "cs-agent", "db-manager",
    "dev-agent", "issue-manager", "nc-manager", "qa-agent", "sales-agent",
]

BASE = r"C:/MES/wta-agents/workspaces"

for agent in AGENTS:
    path = f"{BASE}/{agent}/.claude/settings.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["permissions"] = {"allow": ALLOW_RULES}

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[OK] {agent}")
    except Exception as e:
        print(f"[ERR] {agent}: {e}", file=sys.stderr)
