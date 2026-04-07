@echo off
chcp 65001 >nul 2>&1
title WTA Multi-Agent System Stop

echo ==========================================
echo   WTA Multi-Agent System Stop
echo ==========================================
echo.

echo [1/5] Stopping sub-agent polling loops...
powershell -ExecutionPolicy Bypass -Command "$procs = Get-WmiObject Win32_Process -Filter \"Name='python.exe' AND CommandLine LIKE '%%agent-loop.py%%'\"; if ($procs) { foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }; Write-Host \"  Stopped $($procs.Count) agent-loop processes.\" } else { Write-Host '  [SKIP] No agent-loop processes found.' }"
echo.

echo [2/5] Stopping auto-commit...
powershell -ExecutionPolicy Bypass -Command "$procs = Get-WmiObject Win32_Process -Filter \"Name='python.exe' AND CommandLine LIKE '%%auto-commit.py%%'\"; if ($procs) { foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }; Write-Host \"  Stopped auto-commit.\" } else { Write-Host '  [SKIP] Auto-commit - not running' }"
echo.

echo [2b/5] Stopping slack-bot...
powershell -ExecutionPolicy Bypass -Command "$procs = Get-WmiObject Win32_Process -Filter \"Name='python.exe' AND CommandLine LIKE '%%slack-bot.py%%'\"; if ($procs) { foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }; Write-Host \"  Stopped slack-bot.\" } else { Write-Host '  [SKIP] Slack-bot - not running' }"
echo.

echo [3/5] Killing agent claude/bun/node processes...
taskkill /F /IM claude.exe >nul 2>&1
echo   claude.exe killed.
taskkill /F /IM bun.exe >nul 2>&1
echo   bun.exe killed.
powershell -ExecutionPolicy Bypass -Command "$procs = Get-WmiObject Win32_Process | Where-Object { $_.Name -eq 'node.exe' -and ($_.CommandLine -like '*server:agent-channel*' -or $_.CommandLine -like '*agent-channel*' -or $_.CommandLine -like '*mcp-agent*') }; if ($procs) { foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }; Write-Host \"  Stopped $($procs.Count) agent node processes.\" } else { Write-Host '  [SKIP] No agent node processes found.' }"
echo.

echo [4/5] Stopping MAX...
taskkill /F /FI "WINDOWTITLE eq WTA Multi-Agent System*" >nul 2>&1
if not errorlevel 1 (
    echo   MAX stopped.
) else (
    echo   [SKIP] MAX - not running
)
echo.

echo   Waiting 6 seconds for dashboard to detect offline status...
timeout /t 6 /nobreak >nul

echo [5/5] Stopping dashboard...
powershell -ExecutionPolicy Bypass -Command "$procs = Get-WmiObject Win32_Process -Filter \"Name='python.exe' AND CommandLine LIKE '%%app.py%%'\"; if ($procs) { foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }; Write-Host \"  Stopped dashboard (PID: $($procs.ProcessId)).\" } else { Write-Host '  [SKIP] Dashboard - not running' }"
echo.

echo [Cleanup] Closing WTA terminal windows...
powershell -ExecutionPolicy Bypass -Command "$procs = Get-WmiObject Win32_Process | Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -like '*WTA*' }; if ($procs) { foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }; Write-Host \"  Closed $($procs.Count) WTA terminal windows.\" } else { Write-Host '  [SKIP] No WTA terminal windows found.' }"
echo   Done.

echo.
echo ==========================================
echo   WTA Agent System stopped.
echo ==========================================
echo.
pause
