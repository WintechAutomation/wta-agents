#!/bin/bash
# WTA 인프라 헬스체크 스크립트
# 실행 주기: 30분 (cron)
# 이상 감지 시 MCP 채널을 통해 MAX에게 자동 알림

CLAUDE_BIN="claude"
SEND_MSG_SCRIPT="C:/MES/wta-agents/scripts/send-alert.py"
PYTHON="/c/Users/Administrator/AppData/Local/Programs/Python/Python311/python.exe"

ALERT=""

check_http() {
  local name="$1"
  local url="$2"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$url" 2>/dev/null)
  if [ "$code" != "200" ]; then
    ALERT="${ALERT}\n- ${name} 응답 이상 (HTTP ${code:-timeout}) → ${url}"
  fi
}

check_port() {
  local name="$1"
  local host="$2"
  local port="$3"
  if ! curl -s --connect-timeout 5 "http://${host}:${port}" -o /dev/null 2>/dev/null; then
    # 포트 열려있는지만 확인
    if ! powershell.exe -Command "Test-NetConnection -ComputerName ${host} -Port ${port} -InformationLevel Quiet" 2>/dev/null | grep -qi "true"; then
      ALERT="${ALERT}\n- ${name} 포트 응답 없음 (${host}:${port})"
    fi
  fi
}

# --- 헬스체크 항목 ---

# MES 백엔드
check_http "MES 백엔드(8100)" "http://localhost:8100/health"

# MES 프론트엔드 서버
check_http "MES 프론트엔드(3100)" "http://localhost:3100/"

# 대시보드
check_http "대시보드(5555)" "http://localhost:5555/api/status"

# control-agent: 런처 재시작 전까지 세션 없음 — 임시 suppress (2026-04-02)
# check_port "control-agent(5616)" "localhost" 5616

check_port "purchase-agent(5617)" "localhost" 5617

# slack-bot: 수동 운영으로 변경됨 (2026-04-01) — 헬스체크 제외

# Ollama
check_http "Ollama(182.224.6.147)" "http://182.224.6.147:11434/"

# Docker 컨테이너 비정상 종료 감지
EXITED=$(docker ps -a --filter "status=exited" --filter "status=dead" --format "{{.Names}}" 2>/dev/null | grep -v "^$")
if [ -n "$EXITED" ]; then
  ALERT="${ALERT}\n- Docker 컨테이너 다운: $(echo $EXITED | tr '\n' ', ')"
fi

# --- 알림 전송 ---
if [ -n "$ALERT" ]; then
  TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
  MSG="⚠️ [헬스체크 ${TIMESTAMP}] 이상 감지:\n${ALERT}"
  "$PYTHON" "$SEND_MSG_SCRIPT" "MAX" "$MSG" 2>/dev/null
fi
