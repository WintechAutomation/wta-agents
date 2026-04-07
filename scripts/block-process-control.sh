#!/bin/bash
# 팀원 에이전트 — 멀티에이전트 프로세스 제어 차단 훅
# PreToolUse(Bash): 에이전트 프로세스 kill/start 명령 시 차단
# 일반 시스템 명령(빌드, 서버 재시작, taskkill 일반 등)은 허용
# 허용 주체: MAX, admin-agent (이 훅은 나머지 팀원에게만 적용)

TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"

# command 필드 추출
CMD=$(echo "$TOOL_INPUT" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
if [ -z "$CMD" ]; then
  CMD="$TOOL_INPUT"
fi

CMD_LOWER=$(echo "$CMD" | tr '[:upper:]' '[:lower:]')

BLOCKED=0
REASON=""

# 차단 패턴: 에이전트 시작/종료 스크립트 직접 실행
case "$CMD_LOWER" in
  *start-agents*|*stop-agents*|*start-4agents*)
    BLOCKED=1; REASON="에이전트 시작/종료 스크립트" ;;
esac

# 차단 패턴: 에이전트 포트(5600~5612) 프로세스를 직접 kill
if [ "$BLOCKED" -eq 0 ]; then
  for port in 5600 5601 5602 5603 5604 5605 5606 5607 5608 5609 5610 5611 5612; do
    if echo "$CMD_LOWER" | grep -q "$port"; then
      # 포트 언급 + kill/taskkill/stop-process 조합
      if echo "$CMD_LOWER" | grep -qE "taskkill|stop-process|kill"; then
        BLOCKED=1
        REASON="에이전트 포트($port) 프로세스 강제 종료"
        break
      fi
    fi
  done
fi

# 차단 패턴: claude 프로세스 직접 kill
if [ "$BLOCKED" -eq 0 ]; then
  if echo "$CMD_LOWER" | grep -qE "(taskkill|stop-process|kill).*(claude|slack.bot|mcp.agent|mcp.wta)"; then
    BLOCKED=1; REASON="에이전트 프로세스(claude/slack-bot/mcp) 강제 종료"
  fi
fi

if [ "$BLOCKED" -eq 1 ]; then
  echo "BLOCK: 에이전트 프로세스 제어 권한 없음 — $REASON"
  echo "에이전트 시작/종료는 MAX 또는 admin-agent만 가능합니다."
  echo "요청 방법: send_message(to=\"MAX\", message=\"[재시작 요청 내용]\")"
  exit 2
fi

exit 0
