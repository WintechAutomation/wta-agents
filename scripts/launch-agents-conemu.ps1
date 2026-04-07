# Launch all WTA services in ConEmu tabs
$ConEmu = "C:\Program Files\ConEmu\ConEmu64.exe"
$AgentsDir = "C:\MES\wta-agents\workspaces"
$DashboardDir = "C:\MES\wta-agents\dashboard"
$ScriptsDir = "C:\MES\wta-agents\scripts"
$Python = "C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe"
$LogDir = "C:\MES\wta-agents\logs"

# config/agents.json에서 활성 서브에이전트 목록 로드 (MAX/boss 제외)
$agentsJson = Get-Content "C:\MES\wta-agents\config\agents.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$agents = @($agentsJson.PSObject.Properties | Where-Object {
    $_.Value.enabled -eq $true -and $_.Name -notin @("MAX", "boss") -and $_.Value.location -ne "external"
} | ForEach-Object { $_.Name })
$activeAgents = $agents | Where-Object { Test-Path (Join-Path $AgentsDir "$_\CLAUDE.md") }

# ── Cleanup: 기존 프로세스 전체 정리 ───────────────────────────────────────
Write-Host "Cleaning up existing processes..."

# 1. WTA-Agents ConEmu 창 종료 (taskkill /T로 자식 프로세스 트리 전체 종료)
$conemuProcs = Get-Process -Name "ConEmu64" -ErrorAction SilentlyContinue
foreach ($p in $conemuProcs) {
    try {
        if ($p.MainWindowTitle -match "WTA-Agents") {
            & taskkill /F /T /PID $p.Id 2>&1 | Out-Null
            Write-Host "  [stop] ConEmu64 PID $($p.Id) + child tree ($($p.MainWindowTitle))"
        }
    } catch {}
}
Start-Sleep -Milliseconds 2000

# 2. 잔존 claude.exe 프로세스 모두 종료
$claudeProcs = Get-Process -Name "claude" -ErrorAction SilentlyContinue
foreach ($p in $claudeProcs) {
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    Write-Host "  [stop] claude.exe PID $($p.Id)"
}

# 3. 포트 5555 (대시보드) + 5600~5614 (MCP 서버) 잔존 프로세스 종료
foreach ($port in @(5555) + (5600..5618)) {
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        try {
            $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
            if ($proc -and $proc.Id -ne $PID) {
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                Write-Host "  [stop] port $port -> $($proc.Name) PID $($proc.Id)"
            }
        } catch {}
    }
}

# 4. bun.exe 중 MCP agent-channel 서버 종료
Get-WmiObject Win32_Process -Filter "Name='bun.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.CommandLine -match "mcp-agent-channel") {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "  [stop] bun MCP PID $($_.ProcessId)"
    }
}

# 5. Python 프로세스 정리: slack-bot, auto-commit, app.py 강제 종료 (임베딩 프로세스만 보존)
$embedPattern = "manual.embed|wta.embed|batch.parse|cs.embed|check.embed|docling"
$targetScripts = @("slack-bot.py", "app.py")
Get-WmiObject Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    $cmd = $_.CommandLine
    # 임베딩 프로세스는 절대 정리하지 않음
    if ($cmd -match $embedPattern) {
        return
    }
    # 대상 스크립트 중 하나면 정리
    foreach ($script in $targetScripts) {
        if ($cmd -match [regex]::Escape($script)) {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host "  [stop] python $script PID $($_.ProcessId)"
            break
        }
    }
}

# 6. Node.exe (Claude Code MCP 에이전트) 정리
Get-WmiObject Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "  [stop] node.exe PID $($_.ProcessId)"
}

# 7. ConEmu 내부 cmd.exe 잔존 프로세스 정리 (claude 실행하던 것들)
Get-WmiObject Win32_Process -Filter "Name='cmd.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    $cmd = $_.CommandLine
    if ($cmd -match "claude.*dangerously-skip-permissions") {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "  [stop] cmd.exe (claude) PID $($_.ProcessId)"
    }
}

Start-Sleep -Milliseconds 3000
Write-Host "  Cleanup done (3초 대기 완료)."
Write-Host ""

# ── Background processes: Dashboard / AutoCommit / SlackBot ──────────────
Write-Host "Starting background services..."

# Dashboard (Flask + eventlet) — WindowStyle Hidden, stdout/stderr 리다이렉트 없음
# (리다이렉트 파이프가 eventlet 이벤트루프를 블로킹하므로 반드시 생략)
$dashProc = Start-Process -FilePath $Python `
    -ArgumentList "app.py" `
    -WorkingDirectory $DashboardDir `
    -WindowStyle Hidden `
    -PassThru
$dashProc.Id | Set-Content "$LogDir\dashboard.pid" -Encoding ASCII
Write-Host "  [bg] Dashboard     PID $($dashProc.Id)"

# AutoCommit: APScheduler(jobs.json) --once 모드로 단일화됨. 데몬 프로세스 불필요.

# SlackBot (port 5612 release wait)
Start-Sleep -Seconds 3
$sbProc = Start-Process -FilePath $Python `
    -ArgumentList "slack-bot.py" `
    -WorkingDirectory $ScriptsDir `
    -WindowStyle Hidden `
    -PassThru
$sbProc.Id | Set-Content "$LogDir\slack-bot.pid" -Encoding ASCII
Write-Host "  [bg] SlackBot      PID $($sbProc.Id)"

Write-Host ""

# ── Build 4행x4열 split layout (가로 4, 세로 4) ──────────────────────────────
# 배치 순서 (열 우선, 위→아래):
#   순번:  1   |  5   |  9   | 13   (1행)
#         ─────┼─────┼─────┼─────
#   순번:  2   |  6   | 10   | 14   (2행)
#         ─────┼─────┼─────┼─────
#   순번:  3   |  7   | 11   | 15   (3행)
#         ─────┼─────┼─────┼─────
#   순번:  4   |  8   | 12   | 16   (4행)
#
# ConEmu split 생성 순서 (열 우선):
#   Pane 1 (1행1열) → Pane 2-4 (1열 수평분할) → Pane 5-8 (2열) → Pane 9-12 (3열) → Pane 13-16 (4열)

$items = @()

# Model mapping
$opusAgents = @("dev-agent", "crafter", "docs-agent", "issue-manager")
$haikuAgents = @("schedule-agent", "cs-agent", "sales-agent")
# sonnet: 나머지 모두

# 활성 에이전트 먼저 추가 (MAX는 맨 마지막에 배치 — MCP 플러그인 안정성)
foreach ($agent in $activeAgents) {
    $dir = Join-Path $AgentsDir $agent
    if ($agent -in $opusAgents) {
        $cmd = "cmd /c ""claude --model opus --dangerously-skip-permissions --dangerously-load-development-channels server:agent-channel"""
    } elseif ($agent -in $haikuAgents) {
        $cmd = "cmd /c ""claude --model haiku --dangerously-skip-permissions --dangerously-load-development-channels server:agent-channel"""
    } else {
        $cmd = "cmd /c ""claude --model sonnet --dangerously-skip-permissions --dangerously-load-development-channels server:agent-channel"""
    }
    $items += @{ Name=$agent; Dir=$dir; Cmd=$cmd }
}

# MAX 에이전트 (맨 마지막 — 다른 에이전트/MCP 서버가 먼저 준비된 후 시작)
$items += @{ Name="MAX"; Dir="C:\MES\wta-agents"; Cmd="cmd /c ""claude --model opus --dangerously-skip-permissions --channels plugin:telegram@claude-plugins-official --dangerously-load-development-channels server:agent-channel""" }

# 16개까지 채우기 (빈 터미널)
while ($items.Count -lt 16) {
    $items += @{ Name="Terminal"; Dir="C:\MES\wta-agents"; Cmd="cmd" }
}
$items = @($items[0..15])

# ConEmu split 순서 (생성 순서 = 열 우선)
# Pane 1 (base), Pane 2-4 (1열), Pane 5-8 (2열), Pane 9-12 (3열), Pane 13-16 (4열)
# 배열 인덱스: [0]=1행1열, [1]=2행1열, [2]=3행1열, [3]=4행1열, [4]=1행2열, ...
$creationOrder = @(
    0,              # Pane 1: 1행1열 (base)
    1, 2, 3,        # Pane 2-4: 2행1열, 3행1열, 4행1열
    4, 5, 6, 7,     # Pane 5-8: 1행2열, 2행2열, 3행2열, 4행2열
    8, 9, 10, 11,   # Pane 9-12: 1행3열, 2행3열, 3행3열, 4행3열
    12, 13, 14, 15  # Pane 13-16: 1행4열, 2행4열, 3행4열, 4행4열
)

# Split 파라미터 (4행×4열 그리드)
# H = 수평분할(행 분리), V = 수직분할(열 분리), Tn = 너비/높이 비율(%)
# 4등분: 75%→66%→50% = 각 25%씩
$splits = @(
    "",           # Pane 1: 전체 (1행1열)
    "s1T75H",    # Pane 2: Pane 1을 수평 분할, 아래 75% (2행1열)
    "s2T66H",    # Pane 3: Pane 2를 수평 분할, 아래 66% (3행1열)
    "s3T50H",    # Pane 4: Pane 3을 수평 분할, 아래 50% (4행1열)
    "s1T75V",    # Pane 5: Pane 1을 수직 분할, 오른쪽 75% (1행2열)
    "s2T75V",    # Pane 6: Pane 2를 수직 분할, 오른쪽 75% (2행2열)
    "s3T75V",    # Pane 7: Pane 3을 수직 분할, 오른쪽 75% (3행2열)
    "s4T75V",    # Pane 8: Pane 4를 수직 분할, 오른쪽 75% (4행2열)
    "s5T66V",    # Pane 9: Pane 5를 수직 분할, 오른쪽 66% (1행3열)
    "s6T66V",    # Pane 10: Pane 6을 수직 분할, 오른쪽 66% (2행3열)
    "s7T66V",    # Pane 11: Pane 7을 수직 분할, 오른쪽 66% (3행3열)
    "s8T66V",    # Pane 12: Pane 8을 수직 분할, 오른쪽 66% (4행3열)
    "s9T50V",    # Pane 13: Pane 9를 수직 분할, 오른쪽 50% (1행4열)
    "s10T50V",   # Pane 14: Pane 10을 수직 분할, 오른쪽 50% (2행4열)
    "s11T50V",   # Pane 15: Pane 11을 수직 분할, 오른쪽 50% (3행4열)
    "s12T50V"    # Pane 16: Pane 12를 수직 분할, 오른쪽 50% (4행4열)
)

# Runlist 조립
$runlistParts = @()
for ($i = 0; $i -lt 16; $i++) {
    $item = $items[$creationOrder[$i]]
    $dir  = $item.Dir
    $name = $item.Name
    $cmd  = $item.Cmd
    if ($splits[$i]) {
        $nc = "-new_console:$($splits[$i]):d:""$dir"":t:""$name"""
    } else {
        $nc = "-new_console:d:""$dir"":t:""$name"""
    }
    $runlistParts += "$nc $cmd"
}

$runlist = $runlistParts -join " ||| "
$totalTabs = 16

Write-Host "Launching WTA System in ConEmu (4행x4열 split, maximized)..."
Write-Host "  MAX + $($activeAgents.Count) agents = $totalTabs panes"
Start-Process -FilePath $ConEmu -ArgumentList "-Title", "WTA-Agents", "-Max", "-runlist", $runlist

# AHK auto-approve: 플러그인 승인 프롬프트 자동 엔터
$ahkScript = "$ScriptsDir\auto-approve-plugins.ahk"
$ahkExePaths = @(
    "C:\Program Files\AutoHotkey\v2\AutoHotkey.exe",
    "C:\Program Files\AutoHotkey\AutoHotkey.exe",
    "C:\Program Files\AutoHotkey\AutoHotkey64.exe"
)
$ahkExe = $ahkExePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($ahkExe -and (Test-Path $ahkScript)) {
    # 초기 대기 8초, 탭 수 전달
    Start-Process -FilePath $ahkExe -ArgumentList $ahkScript, $totalTabs, 10000
    Write-Host "  Auto-approve script started ($totalTabs tabs, 10s delay)."
} else {
    if (-not $ahkExe)    { Write-Host "  [skip] AutoHotkey not found." }
    if (-not (Test-Path $ahkScript)) { Write-Host "  [skip] auto-approve-plugins.ahk not found." }
}
Write-Host "  Done."
