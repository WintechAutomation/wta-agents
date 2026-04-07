# WTA Supervisor — Go 프로세스 매니저 설계서

## 1. 개요

PC 리부팅 후 이 프로그램 하나만 실행하면 WTA 전체 시스템(MES, 에이전트, 대시보드)이 순서대로 기동되고,
프로세스 상태를 모니터링하며 죽으면 자동 재시작하는 단일 exe 프로그램.

**대체 대상**: `launch-agents-conemu.ps1` + `auto-approve-plugins.ahk` + `auto-commit.py` + ConEmu

## 2. 아키텍처

```
wta-supervisor.exe (단일 바이너리)
├── process-manager    -- 프로세스 생명주기 관리 (시작/감시/재시작)
├── auto-commit        -- 10분 주기 git commit+push (내장 goroutine)
├── key-sender         -- Win32 API로 터미널에 키 입력 전송
├── gui                -- 탭 기반 터미널 뷰 (임베드된 pseudo-terminal)
└── config             -- JSON 설정 파일 로드
```

## 3. 기동 순서

| 순서 | 그룹 | 프로세스 | 헬스체크 | 타임아웃 |
|------|------|---------|---------|---------|
| 1 | Dashboard | `python app.py` (포트 5555) | HTTP GET /api/health | 30s |
| 2 | WTA-Agents | MAX + 에이전트 14개 (claude CLI) | MCP 포트 응답 확인 | 60s |
| 3 | AutoCommit | 내장 goroutine (별도 프로세스 아님) | - | - |
| 4 | MES | 백엔드 Go (8100), 프론트엔드 Vite (3100) | HTTP 상태 확인 | 30s |

- 각 그룹 내 프로세스는 병렬 시작 가능
- 그룹 간은 순차 (이전 그룹 헬스체크 통과 후 다음 그룹 시작)
- 에이전트 시작 후 자동 키 입력 시퀀스 실행 (플러그인 승인 엔터)

## 4. 관리 대상 프로세스

### 4.1 MES 탭 (4개)
| 프로세스 | 명령어 | 작업 디렉토리 | 포트 |
|---------|--------|-------------|------|
| MES 백엔드 | `./mes-backend.exe` | `C:\MES\backend` | 8100 |
| MES 프론트엔드 | `npm run dev` | `C:\MES\frontend` | 3100 |
| wMES 백엔드 | `python manage.py runserver 0.0.0.0:8000` | `C:\wMES\backend` | 8000 |
| wMES 프론트엔드 | 확인 필요 (Django 템플릿이면 백엔드에 통합) | `C:\wMES` | - |

### 4.2 AGENTS 탭 (20칸, 4열x5행)
| 슬롯 | 프로세스 |
|------|---------|
| 1 | MAX (opus, 텔레그램 플러그인) |
| 2~15 | 활성 에이전트 (agents.json에서 로드, location=internal만) |
| 16~20 | 여유 빈 터미널 |

각 에이전트 명령어:
```
claude --model {model} --dangerously-skip-permissions --dangerously-load-development-channels server:agent-channel
```
MAX만 추가 플래그: `--channels plugin:telegram@claude-plugins-official`

### 4.3 Dashboard 탭 (1개)
| 프로세스 | 명령어 | 포트 |
|---------|--------|------|
| Dashboard | `python app.py` | 5555 |

## 5. 설정 파일 (`config/supervisor.json`)

```json
{
  "groups": [
    {
      "id": "dashboard",
      "name": "Dashboard",
      "start_order": 1,
      "processes": [
        {
          "id": "dashboard",
          "name": "Dashboard",
          "command": "python",
          "args": ["app.py"],
          "workdir": "C:/MES/wta-agents/dashboard",
          "port": 5555,
          "health_check": { "type": "http", "url": "http://localhost:5555/api/health", "timeout_sec": 30 },
          "auto_restart": true,
          "restart_delay_sec": 5,
          "max_restarts": 3
        }
      ]
    },
    {
      "id": "agents",
      "name": "WTA-Agents",
      "start_order": 2,
      "agents_config": "config/agents.json",
      "processes": [],
      "post_start": {
        "key_sequence": [
          { "delay_ms": 10000, "action": "enter_all", "count": 2 }
        ]
      }
    },
    {
      "id": "mes",
      "name": "MES",
      "start_order": 3,
      "processes": [
        {
          "id": "mes-backend",
          "name": "MES Backend",
          "command": "./mes-backend.exe",
          "workdir": "C:/MES/backend",
          "port": 8100,
          "health_check": { "type": "http", "url": "http://localhost:8100/api/health", "timeout_sec": 30 },
          "auto_restart": true,
          "restart_delay_sec": 5,
          "max_restarts": 5
        },
        {
          "id": "mes-frontend",
          "name": "MES Frontend",
          "command": "npm",
          "args": ["run", "dev"],
          "workdir": "C:/MES/frontend",
          "port": 3100,
          "health_check": { "type": "tcp", "port": 3100, "timeout_sec": 30 },
          "auto_restart": true,
          "restart_delay_sec": 5,
          "max_restarts": 5
        }
      ]
    }
  ],
  "auto_commit": {
    "enabled": true,
    "interval_min": 10,
    "repo_dir": "C:/MES/wta-agents",
    "git_timeout_sec": 60
  }
}
```

## 6. 핵심 모듈 설계

### 6.1 프로세스 매니저 (`internal/procmgr/`)
```go
type Process struct {
    ID          string
    Name        string
    Command     string
    Args        []string
    WorkDir     string
    Port        int
    HealthCheck *HealthCheck
    AutoRestart bool
    MaxRestarts int

    // 런타임 상태
    cmd         *exec.Cmd
    pty         *ConPTY        // Windows pseudo-terminal
    status      ProcessStatus  // Starting, Running, Stopped, Failed
    restarts    int
    lastStart   time.Time
}

type ProcessStatus int
const (
    StatusStopped ProcessStatus = iota
    StatusStarting
    StatusRunning
    StatusFailed
)
```

핵심 동작:
- `Start()` — ConPTY로 프로세스 시작, stdout/stderr 캡처
- `Monitor()` — goroutine, 프로세스 종료 감지 → auto_restart이면 재시작
- `Stop()` — graceful shutdown (SIGTERM → 5초 대기 → SIGKILL)
- `HealthCheck()` — HTTP/TCP 포트 확인

### 6.2 오토커밋 (`internal/autocommit/`)
```go
type AutoCommitter struct {
    RepoDir    string
    Interval   time.Duration
    GitTimeout time.Duration
    ticker     *time.Ticker
}
```

핵심 동작:
- 10분 ticker goroutine
- `git add -A` → `git diff --cached` → `git commit` → `git push`
- **좀비 방지**: 모든 git 명령에 `context.WithTimeout(gitTimeout)` 적용
- 타임아웃 시 `cmd.Process.Kill()` 강제 종료
- git lock 파일(`index.lock`) 존재 시 삭제 후 재시도

### 6.3 키 입력 전송 (`internal/keysender/`)
```go
// Win32 API (SendInput / PostMessage) 사용
func SendKey(ptyHandle HANDLE, key Key) error
func SendText(ptyHandle HANDLE, text string) error
func SendEnterToAll(processes []*Process) error
```

- ConPTY 핸들에 직접 입력 전송 (AHK 좌표 클릭 방식 대체)
- 시작 시 자동 키 시퀀스: 에이전트 로드 대기(10초) → 각 터미널에 Enter 2회

### 6.4 GUI (`internal/gui/`)

**기술 선택지**:
| 옵션 | 장점 | 단점 |
|------|------|------|
| A. Wails v2 (WebView2) | 풍부한 UI, HTML/CSS/JS | 번들 크기 큼, WebView2 의존 |
| B. Fyne | 순수 Go, 크로스플랫폼 | 터미널 임베딩 어려움 |
| **C. Win32 API 직접** | **경량, 터미널 임베딩 용이, 단일 exe** | **Windows 전용, UI 코드 많음** |
| D. Bubble Tea (TUI) | 가벼움, 터미널 네이티브 | GUI 아님 |

**권장: C (Win32 API 직접)** — Windows 서버 전용이고 터미널 임베딩이 핵심 요구사항.

또는 **하이브리드: Wails v2 + xterm.js** — 웹 기반 터미널 뷰로 구현하면 UI가 깔끔하고 xterm.js가 ANSI 색상/스크롤 완벽 지원.

```
┌─────────────────────────────────────────────────────────┐
│  [MES]  [AGENTS]  [Dashboard]  [ERP]                    │
├─────────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│ │MES BE    │ │MES FE    │ │wMES BE   │ │wMES FE   │    │
│ │ > ...    │ │ > ...    │ │ > ...    │ │ > ...    │    │
│ │          │ │          │ │          │ │          │    │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
│                    (MES 탭: 2x2 분할)                    │
├─────────────────────────────────────────────────────────┤
│ 상태바: ● MES(4/4) ● Agents(15/15) ● Dashboard(1/1)   │
└─────────────────────────────────────────────────────────┘
```

AGENTS 탭 (4열 x 5행 = 20칸):
```
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│ MAX  │ │cs-agt│ │dev   │ │admin │
├──────┤ ├──────┤ ├──────┤ ├──────┤
│db-mgr│ │sales │ │craft │ │nc-mgr│
├──────┤ ├──────┤ ├──────┤ ├──────┤
│qa-agt│ │issue │ │slack │ │sched │
├──────┤ ├──────┤ ├──────┤ ├──────┤
│docs  │ │ctrl  │ │purch │ │(여유)│
├──────┤ ├──────┤ ├──────┤ ├──────┤
│(여유)│ │(여유)│ │(여유)│ │(여유)│
└──────┘ └──────┘ └──────┘ └──────┘
```

### 6.5 싱글 인스턴스 (`internal/singleton/`)
```go
// Named Mutex로 이중 실행 방지
func AcquireLock() (release func(), err error)
```
Windows Named Mutex `Global\WTASupervisor` 사용.

## 7. 프로젝트 구조

```
C:\MES\wta-supervisor\
├── main.go
├── go.mod
├── internal/
│   ├── config/       -- 설정 파일 로드
│   ├── procmgr/      -- 프로세스 관리 (ConPTY, 모니터링, 재시작)
│   ├── autocommit/   -- git 자동 커밋 (좀비 방지)
│   ├── keysender/    -- Win32 키 입력 전송
│   ├── gui/          -- GUI (Wails 또는 Win32)
│   └── singleton/    -- 이중 실행 방지
├── config/
│   └── supervisor.json
└── build/
    └── wta-supervisor.exe
```

## 8. GUI 기술 결정 필요

두 가지 방향 중 선택 필요:

### 방안 A: Wails v2 + xterm.js (권장)
- 프론트: HTML/CSS/JS + xterm.js 터미널 위젯
- 백엔드: Go (Wails 바인딩)
- 장점: 터미널 렌더링 완벽 (ANSI 색상, 스크롤, 복사/붙여넣기), UI 커스텀 자유도
- 단점: WebView2 런타임 필요 (Windows 10/11 기본 포함, Server 2022는 설치 필요할 수 있음)
- 빌드: `wails build` → 단일 exe (~15MB)

### 방안 B: Win32 API + ConPTY 직접
- 순수 Go + win32 syscall
- 장점: 외부 의존 없음, 초경량
- 단점: UI 코드 대량, ANSI 렌더링 직접 구현 필요, 개발 시간 3~5배

## 9. Windows 서비스

```go
// golang.org/x/sys/windows/svc 패키지 사용
// 설치: wta-supervisor.exe install
// 제거: wta-supervisor.exe uninstall
// 서비스 모드에서는 GUI 없이 프로세스 관리만 수행
```

- `wta-supervisor.exe` — GUI 모드 (기본)
- `wta-supervisor.exe --service` — 서비스 모드 (headless)
- `wta-supervisor.exe install` — Windows 서비스 등록
- `wta-supervisor.exe uninstall` — 서비스 제거

## 10. 주의사항 / 리스크

| 항목 | 대응 |
|------|------|
| git 좀비 프로세스 | 모든 git 명령 60초 timeout + Kill, index.lock 자동 정리 |
| 이중 실행 | Named Mutex `Global\WTASupervisor` |
| 에이전트 크래시 루프 | max_restarts 초과 시 Failed 상태, 수동 개입 필요 |
| ConPTY 호환성 | Windows 10 1809+ 필수 (Server 2022 OK) |
| 임베딩 프로세스 보호 | 프로세스 정리 시 embedPattern 매칭 프로세스 제외 |
| 대시보드 eventlet | stdout 리다이렉트 없이 실행 (eventlet 블로킹 방지) |

## 11. 구현 우선순위

| Phase | 범위 | 산출물 |
|-------|------|--------|
| P1 | 프로세스 매니저 + 오토커밋 + 싱글 인스턴스 (CLI) | headless 동작 |
| P2 | GUI (Wails + xterm.js) MES/AGENTS/Dashboard 탭 | 시각화 |
| P3 | 키 입력 전송 (AHK 대체) | 자동 승인 |
| P4 | Windows 서비스 등록 | 부팅 자동 시작 |

---

**결정 요청 사항**:
1. GUI 기술: Wails v2 + xterm.js (방안 A) vs Win32 직접 (방안 B)?
2. wMES 프론트엔드: Django 템플릿 통합인지 별도 서버인지 확인 필요
3. 프로젝트 위치: `C:\MES\wta-supervisor\` 신규 생성 vs `C:\MES\wta-agents\supervisor\`?
