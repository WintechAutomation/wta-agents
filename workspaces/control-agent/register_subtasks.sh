#!/bin/bash
# MES 세부사항 등록: 메이써루이 프레스 12~14호기 전장배선
# project_id=93, task_id=4842

set -e

ENV_FILE="/c/MES/backend/.env"
BASE_URL="http://localhost:8100"

# .env에서 자격증명 읽기
USERNAME=$(grep "^MES_SERVICE_USERNAME=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '\r')
PASSWORD=$(grep "^MES_SERVICE_PASSWORD=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '\r')

# 로그인 → 토큰 획득
RESP=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}")
TOKEN=$(echo "$RESP" | grep -o '"access":"[^"]*"' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "로그인 실패" >&2
  exit 1
fi

echo "로그인 성공. 세부사항 등록 시작..."

PROJECT_ID=93
TASK_ID=4842

declare -a ITEMS=(
  "속판 제작 (장비 부착 전)"
  "속판 하네스 배선 (장비 부착 후)"
  "상부 유닛 작업"
  "CONV 유닛 작업"
  "LIFT 유닛 작업"
  "샘플링 유닛 작업"
  "디버링 유닛 작업"
  "저울 유닛 작업"
  "스테이션 유닛 작업"
  "상부 케이블 연장 및 포설"
  "Y축 작업"
  "SOL 판 작업"
  "SOL 이콘 배선"
  "ATC 이콘 배선"
  "ETC 이콘 배선"
  "CONV 이콘 배선"
  "트랜스 작업"
  "PDU 브라켓 작업"
  "메인스위치 브라켓 작업"
  "PC 배선"
  "OP 판넬"
  "메인도어 모니터 작업"
  "도어락"
  "타워램프"
  "JAW 툴 작업"
)

for i in "${!ITEMS[@]}"; do
  NUM=$(printf "%03d" $((i + 1)))
  CODE="CM-HP3C-$NUM"
  NAME="${ITEMS[$i]}"

  RESULT=$(curl -s -X POST "$BASE_URL/api/production/project-detailed-schedules/append_subtask" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"task_id\":$TASK_ID,\"project_id\":$PROJECT_ID,\"task_item_code\":\"$CODE\",\"task_item_name\":\"$NAME\",\"status\":\"pending\",\"order\":$((i+1))}")

  echo "[$NUM] $NAME → $RESULT"
done

echo "등록 완료"
