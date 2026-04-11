# MCP agent-channel ACK/재시도 설계안

작성: crafter, 2026-04-12
목적: MAX→crafter 메시지 2회 유실 장애 재발 방지. Redis Streams 기반 ACK/재시도 구조 도입.

---

## 1. 현재 아키텍처 분석

### 1.1 메시지 흐름
```
[발신 에이전트 세션]
  └─ send_message(to, message)          # FastMCP tool
       └─ HTTP POST /api/send            # fire-and-forget, 200 OK만 확인
            └─ dashboard agent_inbox[to].append(msg)   # in-memory dict
                 └─ message_history.append(msg)        # JSONL 백업만

[수신 에이전트 세션]
  └─ poll_dashboard()                   # 3초 주기 백그라운드 스레드
       └─ HTTP GET /api/recv/{agent_id}
            └─ agent_inbox.pop(agent_id, [])    # ★파괴적 pop
                 └─ message_queue.put(...)      # in-memory Python Queue
                      └─ <channel> 태그로 Claude 세션에 렌더
```

### 1.2 유실 포인트 (2026-04-11 MAX→crafter 2회 유실 재현)
| # | 구간 | 장애 시나리오 | 영향 |
|---|------|--------------|------|
| L1 | `api_send` | 대시보드 프로세스 재시작 시 `agent_inbox` dict 메모리 증발 | **전량 유실** |
| L2 | `api_recv` | pop 후 poll 스레드가 Queue put 전에 예외 → 메시지 소실 | 단건 유실 |
| L3 | `message_queue` | 세션 종료/재시작 시 Queue 메모리 증발 | **전량 유실** |
| L4 | `send_message` | HTTP timeout/커넥션 실패를 세션에 반환하지만 재시도 없음 | 단건 유실 |
| L5 | Claude 세션 | `<channel>` 렌더 실패/컨텍스트 압축 타이밍에 묻힘 | 드물게 유실 |
| L6 | ACK 부재 | 송신 측은 수신 여부 확인 불가 → 재발송 판단 근거 없음 | 상시 |

**핵심 원인**: `agent_inbox`가 휘발성 dict + 파괴적 pop + ACK 없음. 송신자가 "보냈다고 믿는 상태"와 수신자 실제 도달 상태가 분리 불가능.

---

## 2. 목표

1. **유실 0 보장**: 전달 확인 전까지 Stream에 메시지 잔존
2. **ACK 필수**: 수신 에이전트가 명시적으로 ACK할 때만 소비 완료
3. **3회 자동 재시도**: poll 주기에서 pending 상태 감지 시 재배달
4. **DLQ 격리**: 3회 실패 메시지는 DLQ로 이동, MAX에게 알림
5. **API 하위 호환**: `send_message(to, message)` 시그니처 유지, 내부만 Redis로 교체
6. **24h TTL**: Stream 최대 길이/시간 제한으로 무한 누적 방지
7. **task_queue와 분리**: task_queue(작업 의뢰)는 대시보드 API 유지, 여기서는 에이전트 간 대화만

---

## 3. Redis Streams 아키텍처

### 3.1 신규 컨테이너 — wta_redis
```yaml
# docker-compose (wta-agents 전용, wmes_redis와 분리)
services:
  wta_redis:
    image: redis:7.2-alpine
    container_name: wta_redis
    ports:
      - "6380:6379"       # host 6380 (wmes_redis는 6379 점유)
    volumes:
      - wta_redis_data:/data
    command: >
      redis-server
      --appendonly yes
      --appendfsync everysec
      --maxmemory 512mb
      --maxmemory-policy noeviction
    restart: unless-stopped
volumes:
  wta_redis_data:
```

**wmes_redis와 완전 분리** — 포트(6380), 데이터볼륨(wta_redis_data), 컨테이너명(wta_redis). MES Redis 장애가 에이전트 통신에 영향 없음.

### 3.2 Stream/Key 설계
| Key | 타입 | 용도 |
|-----|------|------|
| `wta:stream:{agent_id}` | Stream | 해당 에이전트 수신함. XADD로 메시지 추가, MAXLEN ~ 10000 |
| `wta:group:{agent_id}` | Consumer Group | 에이전트별 컨슈머 그룹 (이름 고정 `workers`) |
| `wta:dlq:{agent_id}` | Stream | 3회 실패 격리. MAXLEN ~ 1000 |
| `wta:seen:{msg_id}` | String (EX 86400) | idempotency 키, 24h TTL |

### 3.3 메시지 포맷 (XADD fields)
```
msg_id    = uuid4 hex
from      = 발신 agent_id
to        = 수신 agent_id
content   = 본문
ts        = ISO8601 KST
attempt   = 0 (재시도 횟수)
trace     = 선택: 상위 요청 ID
```

### 3.4 송신 (send_message 내부)
```python
def send_message(to: str, message: str) -> str:
    msg_id = uuid.uuid4().hex
    r.xadd(
        f"wta:stream:{to}",
        {
            "msg_id": msg_id, "from": AGENT_ID, "to": to,
            "content": message, "ts": _now_iso(),
            "attempt": "0",
        },
        maxlen=10000, approximate=True,
    )
    return f"전송 완료 → {to} (msg_id: {msg_id})"
```
- MCP tool 시그니처(to, message) 변경 없음
- XADD 실패 시 FastMCP tool이 exception → 세션에 visible error (지금 fire-and-forget 대비 개선)

### 3.5 수신 (poll_dashboard 대체)
```python
# 세션 시작 시 1회
try:
    r.xgroup_create(f"wta:stream:{AGENT_ID}", "workers",
                    id="0", mkstream=True)
except ResponseError:
    pass  # BUSYGROUP

# 백그라운드 루프 (3초 주기 유지)
while True:
    # 1) 신규 메시지
    resp = r.xreadgroup(
        "workers", consumer=AGENT_ID,
        streams={f"wta:stream:{AGENT_ID}": ">"},
        count=32, block=3000,
    )
    # 2) 미ACK 재배달 (pending 5초 초과)
    claimed = r.xautoclaim(
        f"wta:stream:{AGENT_ID}", "workers", AGENT_ID,
        min_idle_time=5000, count=32,
    )
    for stream_msg_id, fields in (resp[0][1] if resp else []) + claimed[1]:
        _deliver_to_session(stream_msg_id, fields)
```

### 3.6 ACK 정책
- **정상 소비**: Claude 세션이 메시지를 `<channel>` 태그로 실제로 수신하면 즉시 `XACK` + `XDEL`
- **재시도**: min_idle_time(5s) 초과 pending은 `XAUTOCLAIM`으로 자동 재배달, `attempt` 필드 증가
- **DLQ**: `attempt >= 3` 시 `wta:dlq:{agent_id}`로 XADD 후 원본 XACK+XDEL, MAX에게 별도 알림 stream 발행

```
attempt 0 → 세션 전달 → ACK
         ↓ 타임아웃 5s
attempt 1 → xautoclaim 재배달 → ACK
         ↓ 타임아웃
attempt 2 → 재배달 → ACK
         ↓ 타임아웃
attempt 3 → DLQ로 이동 + MAX 알림
```

### 3.7 idempotency
수신 측에서 `wta:seen:{msg_id}` SETNX (EX 86400). 이미 존재하면 중복 → XACK만 수행하고 세션에 재노출하지 않음. 재시도 로직이 동일 메시지를 두 번 보여주는 사고 방지.

---

## 4. 마이그레이션 계획

### 4.1 단계
1. **Phase 0 (준비)** — wta_redis 컨테이너 기동, 포트/볼륨 검증, redis-py 설치
2. **Phase 1 (MCP 서버 개편)** — `scripts/mcp-agent-channel.py` 수정
   - `poll_dashboard()` → `poll_redis()` 교체
   - `send_message()` 내부를 HTTP POST → XADD로 교체
   - 시그니처/반환 문자열 포맷 유지 (하위 호환)
3. **Phase 2 (대시보드 연동)** — `dashboard/app.py`
   - `/api/send`, `/api/recv`는 **legacy 호환 모드로 유지** (외부 호출자 있음)
   - 내부적으로 XADD 프록시로 동작 (agent_inbox 제거)
   - `/api/messages` 조회는 `XRANGE`로 래핑
4. **Phase 3 (관측)** — 대시보드 페이지에 Stream length, pending count, DLQ count 표시
5. **Phase 4 (DLQ 자동 알림)** — DLQ 진입 시 MAX에게 자동 send_message

### 4.2 롤백
wta_redis 컨테이너 down → MCP 서버가 HTTP 폴백(기존 경로)로 fallback 모드 가능하도록 환경변수 `WTA_CHANNEL_BACKEND=redis|http` 제공.

### 4.3 영향 범위
- `scripts/mcp-agent-channel.py` (전체 16 에이전트 공통)
- `dashboard/app.py` send/recv/heartbeat/messages 엔드포인트
- `CLAUDE.md` 변경 없음 (시그니처 동일)
- task_queue API는 **손대지 않음** (별개 레이어)

---

## 5. 미결/검토 필요

1. wta_redis 호스트 포트 6380 확정 가능 여부 (다른 서비스 점유 확인 필요)
2. DLQ 유입 시 MAX 알림 채널 — Slack #admin vs 텔레그램 부서장 DM
3. dashboard legacy HTTP API 외부 호출자 존재 여부 (기존 스크립트/크론) — grep 필요
4. Phase 1 배포 시 에이전트 전체 재시작 순서 (MAX→팀원 순)

---

## 6. 요약
- 유실 원인: agent_inbox가 휘발성 + 파괴적 pop + ACK 없음
- 해결: Redis Streams(XADD/XREADGROUP/XACK) + consumer group + xautoclaim 재배달 + DLQ
- wta_redis 컨테이너 신규(포트 6380), wmes_redis와 완전 분리
- send_message API 시그니처 유지, 내부만 교체 → 16개 에이전트 코드 수정 없음
- task_queue와 레이어 분리 유지
