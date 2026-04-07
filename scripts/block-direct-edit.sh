#!/bin/bash
# MAX(오케스트레이터)가 직접 코드 수정하는 것을 차단
# PreToolUse 훅: Edit, Write 도구 사용 시 경고 메시지 출력 후 차단
# 허용 대상: 설정 파일(.claude/, CLAUDE.md, memory/, MEMORY.md)

TOOL_INPUT="$CLAUDE_TOOL_INPUT"

# tool_input에서 file_path 추출
FILE_PATH=$(echo "$TOOL_INPUT" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# 허용 경로: 설정/메모리 파일은 MAX가 직접 수정 가능
case "$FILE_PATH" in
  */.claude/*|*/CLAUDE.md|*/memory/*|*/MEMORY.md|*settings*.json)
    exit 0
    ;;
esac

# 그 외 코드 파일 수정 차단
echo "BLOCK: MAX는 코드를 직접 수정하지 않습니다. 팀원(crafter 등)에게 위임하세요."
echo "대상 파일: $FILE_PATH"
exit 2
