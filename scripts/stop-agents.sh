#!/bin/bash
# WTA 에이전트 시스템 종료 스크립트

echo "=========================================="
echo "  WTA 멀티에이전트 시스템 종료"
echo "=========================================="

# 대시보드 종료
echo "대시보드 종료..."
if [ -f /tmp/wta-agents.pids ]; then
    source /tmp/wta-agents.pids
    kill $dashboard 2>/dev/null && echo "  대시보드 종료 (PID: $dashboard)"
    rm /tmp/wta-agents.pids
fi

# Claude 프로세스 종료 (에이전트 세션)
echo "에이전트 세션 종료..."
pkill -f "claude.*dangerously-skip-permissions" 2>/dev/null
echo "  완료"

# Python Flask 프로세스 종료
echo "Flask 프로세스 종료..."
pkill -f "python.*app.py" 2>/dev/null

echo ""
echo "시스템 종료 완료"
