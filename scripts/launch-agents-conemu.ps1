# Launch all WTA services in ConEmu tabs (tab mode)
$ConEmu = "C:\Program Files\ConEmu\ConEmu64.exe"
$ConEmuC = "C:\Program Files\ConEmu\ConEmu\ConEmuC64.exe"
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

# -- Cleanup: existing process cleanup (identical to split version) -----------
Write-Host "Cleaning up existing processes..."

# 1. WTA-Agents ConEmu window kill (/T = child tree)
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

# 2. Remaining claude.exe processes
$claudeProcs = Get-Process -Name "claude" -ErrorAction SilentlyContinue
foreach ($p in $claudeProcs) {
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    Write-Host "  [stop] claude.exe PID $($p.Id)"
}

# 3. Port 5555 (dashboard) + 5600~5618 (MCP servers) cleanup
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

# 4. bun.exe MCP agent-channel server
Get-WmiObject Win32_Process -Filter "Name='bun.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.CommandLine -match "mcp-agent-channel") {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "  [stop] bun MCP PID $($_.ProcessId)"
    }
}

# 5. Python process cleanup: slack-bot, app.py (preserve embedding processes)
$embedPattern = "manual.embed|wta.embed|batch.parse|cs.embed|check.embed|docling"
$targetScripts = @("slack-bot.py", "app.py")
Get-WmiObject Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    $cmd = $_.CommandLine
    if ($cmd -match $embedPattern) { return }
    foreach ($script in $targetScripts) {
        if ($cmd -match [regex]::Escape($script)) {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host "  [stop] python $script PID $($_.ProcessId)"
            break
        }
    }
}

# 6. Node.exe (Claude Code MCP agent) cleanup
Get-WmiObject Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "  [stop] node.exe PID $($_.ProcessId)"
}

# 7. cmd.exe (claude runner) cleanup
Get-WmiObject Win32_Process -Filter "Name='cmd.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    $cmd = $_.CommandLine
    if ($cmd -match "claude.*dangerously-skip-permissions") {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "  [stop] cmd.exe (claude) PID $($_.ProcessId)"
    }
}

Start-Sleep -Milliseconds 3000
Write-Host "  Cleanup done (3s wait)."
Write-Host ""

# -- Background processes: Dashboard / SlackBot ------------------------------
Write-Host "Starting background services..."

# Dashboard (Flask + eventlet) - no stdout redirect (blocks eventlet loop)
$dashProc = Start-Process -FilePath $Python `
    -ArgumentList "app.py" `
    -WorkingDirectory $DashboardDir `
    -WindowStyle Hidden `
    -PassThru
$dashProc.Id | Set-Content "$LogDir\dashboard.pid" -Encoding ASCII
Write-Host "  [bg] Dashboard     PID $($dashProc.Id)"

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

# -- Build tab list ----------------------------------------------------------
$items = @()

# Model mapping
$opusAgents = @("dev-agent", "crafter", "docs-agent", "issue-manager")
$haikuAgents = @("schedule-agent", "cs-agent", "sales-agent")

# Active agents first (MAX last for MCP plugin stability)
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

# MAX agent (last - after all other agents/MCP servers are ready)
$items += @{ Name="MAX"; Dir="C:\MES\wta-agents"; Cmd="cmd /c ""claude --model opus --dangerously-skip-permissions --channels plugin:telegram@claude-plugins-official --dangerously-load-development-channels server:agent-channel""" }

$totalTabs = $items.Count

# -- Build runlist (tabs only, no splits) ------------------------------------
$runlistParts = @()
for ($i = 0; $i -lt $items.Count; $i++) {
    $item = $items[$i]
    $nc = "-new_console:d:""$($item.Dir)"":t:""$($item.Name)"""
    $runlistParts += "$nc $($item.Cmd)"
}
$runlist = $runlistParts -join " ||| "

Write-Host "Launching WTA System in ConEmu (tab mode, maximized)..."
Write-Host "  MAX + $($activeAgents.Count) agents = $totalTabs tabs"
$conemuProc = Start-Process -FilePath $ConEmu -ArgumentList "-Title", "WTA-Agents", "-Max", "-runlist", $runlist -PassThru
$conemuPid = $conemuProc.Id
Write-Host "  ConEmu PID: $conemuPid"

# -- Auto-approve plugins via GuiMacro (Enter key to each tab) ---------------
Write-Host ""
Write-Host "Waiting 15s for agents to start and prompt plugin approval..."
Start-Sleep -Seconds 15

Write-Host "Sending Enter key to each tab via GuiMacro..."

# Find ConEmuC64 child PIDs under the ConEmu process
$conEmuCPids = @()
try {
    $children = Get-WmiObject Win32_Process -Filter "ParentProcessId=$conemuPid AND Name='ConEmuC64.exe'" -ErrorAction SilentlyContinue
    if ($children) {
        $conEmuCPids = @($children | ForEach-Object { $_.ProcessId })
    }
} catch {}

# If no direct children, try finding all ConEmuC64 processes
if ($conEmuCPids.Count -eq 0) {
    try {
        $allConEmuC = Get-WmiObject Win32_Process -Filter "Name='ConEmuC64.exe'" -ErrorAction SilentlyContinue
        if ($allConEmuC) {
            $conEmuCPids = @($allConEmuC | ForEach-Object { $_.ProcessId })
        }
    } catch {}
}

Write-Host "  Found $($conEmuCPids.Count) ConEmuC64 processes"

foreach ($pid in $conEmuCPids) {
    try {
        # Send Enter twice (first: plugin load prompt, second: confirmation)
        & $ConEmuC -GuiMacro:$pid "Keys(Enter)" 2>&1 | Out-Null
        Start-Sleep -Milliseconds 300
        & $ConEmuC -GuiMacro:$pid "Keys(Enter)" 2>&1 | Out-Null
        Write-Host "  [enter] ConEmuC64 PID $pid - 2x Enter sent"
    } catch {
        Write-Host "  [warn] Failed to send Enter to PID $pid"
    }
    Start-Sleep -Milliseconds 200
}

# -- Send /reload-plugins to MAX tab (last tab) ------------------------------
Start-Sleep -Seconds 3
if ($conEmuCPids.Count -gt 0) {
    $maxPid = $conEmuCPids[-1]  # MAX is the last tab
    try {
        # Type /reload-plugins and press Enter
        & $ConEmuC -GuiMacro:$maxPid "Print(""/reload-plugins\n"")" 2>&1 | Out-Null
        Write-Host "  [cmd] /reload-plugins sent to MAX tab (PID $maxPid)"
    } catch {
        Write-Host "  [warn] Failed to send /reload-plugins to MAX"
    }
}

Write-Host ""
Write-Host "  Done. $totalTabs tabs launched."
