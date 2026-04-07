#!/bin/bash
# PreToolUse — Agent tool usage warning
DASHBOARD_URL="http://localhost:5555"
PYTHON="C:/Users/Administrator/AppData/Local/Programs/Python/Python311/python.exe"
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$DASHBOARD_URL/" 2>/dev/null)

if [ "$HTTP_CODE" = "200" ]; then
    ONLINE=$(curl -s "$DASHBOARD_URL/api/status" 2>/dev/null | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin)['stats']['online_count'])" 2>/dev/null)
    if [ "$ONLINE" -gt 1 ] 2>/dev/null; then
        "$PYTHON" -c "
import json
msg='[WARNING] ${ONLINE} team agents are online via agent-loop.py. Do NOT create sub-agents for team members. Use: python C:/MES/wta-agents/scripts/delegate.py <agent_id> <message>. Only Explore/Plan/general-purpose sub-agents are allowed via Agent tool.'
print(json.dumps({'hookSpecificOutput':{'hookEventName':'PreToolUse','additionalContext':msg}}))"
        exit 0
    fi
fi

echo '{}'
