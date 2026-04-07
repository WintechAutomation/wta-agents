# restart-dashboard-slackbot.ps1
# 대시보드 + 슬랙봇: 기존 프로세스 종료 후 ConEmu 탭으로 재시작

$ConEmu      = "C:\Program Files\ConEmu\ConEmu64.exe"
$Python      = "C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe"
$DashboardDir = "C:\MES\wta-agents\dashboard"
$ScriptsDir  = "C:\MES\wta-agents\scripts"

# 1. 기존 대시보드 종료
$dashProcs = Get-WmiObject Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*app.py*" }
if ($dashProcs) {
    foreach ($p in $dashProcs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    Write-Host "  [OK] 대시보드 종료 ($($dashProcs.Count)개)"
} else {
    Write-Host "  [SKIP] 대시보드 - 실행 중 아님"
}

# 2. 기존 슬랙봇 종료
$slackProcs = Get-WmiObject Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*slack-bot.py*" }
if ($slackProcs) {
    foreach ($p in $slackProcs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    Write-Host "  [OK] 슬랙봇 종료 ($($slackProcs.Count)개)"
} else {
    Write-Host "  [SKIP] 슬랙봇 - 실행 중 아님"
}

# 3. ConEmu 탭으로 재시작 (runlist 방식 — launch-agents-conemu.ps1 동일 패턴)
$tabCmds = @()
$tabCmds += "-new_console:d:""$DashboardDir"":t:""Dashboard"" ""$Python"" app.py"
$tabCmds += "-new_console:d:""$ScriptsDir"":t:""SlackBot"" ""$Python"" slack-bot.py"

$runlist = $tabCmds -join " ||| "

Write-Host "  [OK] ConEmu 탭 시작 (Dashboard + SlackBot)"
Start-Process -FilePath $ConEmu -ArgumentList "-Single", "-runlist", $runlist

Write-Host "완료."
