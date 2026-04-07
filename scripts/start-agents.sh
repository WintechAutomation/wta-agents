#!/bin/bash
# WTA 에이전트 시스템 시작 스크립트
# MAX가 서브에이전트를 백그라운드로 시작합니다

DASHBOARD_URL="http://localhost:5555"
AGENTS_DIR="C:/MES/wta-agents/workspaces"
PYTHON="/c/Users/Administrator/AppData/Local/Programs/Python/Python311/python.exe"
CLAUDE="claude"

echo "=========================================="
echo "  WTA 멀티에이전트 시스템 시작"
echo "=========================================="

# 1. 대시보드 서버 시작
echo "[1/3] 대시보드 서버 시작 (포트 5555)..."
cd C:/MES/wta-agents/dashboard
$PYTHON app.py &
DASHBOARD_PID=$!
echo "  PID: $DASHBOARD_PID"
sleep 3

# 대시보드 헬스체크
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" $DASHBOARD_URL/ 2>/dev/null)
if [ "$HTTP_CODE" != "200" ]; then
    echo "  [ERROR] 대시보드 시작 실패!"
    exit 1
fi
echo "  대시보드 OK (HTTP $HTTP_CODE)"

# 2. 서브에이전트 시작
echo ""
echo "[2/3] 서브에이전트 시작..."

AGENT_LIST=(nc-manager db-manager cs-agent issue-manager qa-agent crafter dev-agent sales-agent)

for agent_id in "${AGENT_LIST[@]}"; do
    workspace="$AGENTS_DIR/$agent_id"
    if [ -f "$workspace/CLAUDE.md" ]; then
        echo "  시작: $agent_id..."
        cd "$workspace"
        MODEL="sonnet"
        if [ "$agent_id" = "dev-agent" ] || [ "$agent_id" = "cs-agent" ]; then
            MODEL="opus"
        fi
        $CLAUDE --model $MODEL -p "시작합니다. CLAUDE.md를 읽고 하트비트를 전송한 후 MAX에게 준비 완료를 보고하세요." --dangerously-skip-permissions &
        echo "  PID: $!"
        sleep 2
    else
        echo "  [SKIP] $agent_id — CLAUDE.md 없음"
    fi
done

# 3. 상태 확인
echo ""
echo "[3/3] 상태 확인..."
sleep 5
curl -s $DASHBOARD_URL/api/status | python3 -c "
import sys, json
data = json.load(sys.stdin)
stats = data['stats']
print(f'  온라인: {stats[\"online_count\"]}/{stats[\"total_agents\"]}')
print(f'  메시지: {stats[\"total_messages\"]}')
" 2>/dev/null || echo "  상태 확인 실패"

echo ""
echo "=========================================="
echo "  시스템 시작 완료"
echo "  대시보드: $DASHBOARD_URL"
echo "  PID 파일: /tmp/wta-agents.pids"
echo "=========================================="

# PID 파일 저장
echo "dashboard=$DASHBOARD_PID" > /tmp/wta-agents.pids
