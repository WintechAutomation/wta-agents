#!/bin/bash
# 시스템 상태 점검 — SessionStart 훅에서 호출
DASHBOARD_URL="http://localhost:5555"
PYTHON="C:/Users/Administrator/AppData/Local/Programs/Python/Python311/python.exe"
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$DASHBOARD_URL/" 2>/dev/null)

if [ "$HTTP_CODE" = "200" ]; then
    CONTEXT=$(curl -s "$DASHBOARD_URL/api/status" 2>/dev/null | "$PYTHON" -c "
import sys,json,os
os.environ['PYTHONIOENCODING']='utf-8'
d=json.load(sys.stdin)
s=d['stats']
offline=[a['agent_id'] for a in d['agents'] if not a['online']]
msg=f'[SYSTEM] Dashboard: OK | Agents: {s[\"online_count\"]}/{s[\"total_agents\"]} online | Messages: {s[\"total_messages\"]} | Uptime: {s[\"uptime\"]}'
if offline:
    msg+=f' | Offline: {\", \".join(offline)}'
TEAM_LIST=$("$PYTHON" -c "
import json
with open('C:/MES/wta-agents/config/agents.json', encoding='utf-8') as f:
    agents = json.load(f)
members = [aid for aid, a in agents.items() if a.get('enabled') and aid not in ('MAX', 'boss')]
print(', '.join(members))
" 2>/dev/null || echo "nc-manager, db-manager, cs-agent, crafter")
msg+=" | RULE: Use send_message for team tasks. Do NOT use Agent tool to create sub-agents for team members ($TEAM_LIST). Only Explore/Plan sub-agents are allowed."
print(msg)
" 2>/dev/null)
else
    CONTEXT="[SYSTEM] Dashboard: NOT RUNNING. No team processes. Run start-agents.bat first. Sub-agent usage allowed."
fi

"$PYTHON" -c "
import json,sys
ctx=sys.argv[1]
print(json.dumps({'hookSpecificOutput':{'hookEventName':'SessionStart','additionalContext':ctx}}))" "$CONTEXT"
