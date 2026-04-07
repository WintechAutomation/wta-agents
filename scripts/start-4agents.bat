@echo off
chcp 65001 >nul 2>&1

set "AGENTS_DIR=C:\MES\wta-agents\workspaces"

cd /d "%AGENTS_DIR%\db-manager"
start "WTA-db-manager" cmd /k "claude --model sonnet --dangerously-skip-permissions --dangerously-load-development-channels server:agent-channel"
timeout /t 3 /nobreak >nul

cd /d "%AGENTS_DIR%\crafter"
start "WTA-crafter" cmd /k "claude --model sonnet --dangerously-skip-permissions --dangerously-load-development-channels server:agent-channel"
timeout /t 3 /nobreak >nul

cd /d "%AGENTS_DIR%\dev-agent"
start "WTA-dev-agent" cmd /k "claude --model sonnet --dangerously-skip-permissions --dangerously-load-development-channels server:agent-channel"
timeout /t 3 /nobreak >nul

cd /d "%AGENTS_DIR%\issue-manager"
start "WTA-issue-manager" cmd /k "claude --model sonnet --dangerously-skip-permissions --dangerously-load-development-channels server:agent-channel"
timeout /t 3 /nobreak >nul

echo Done. 4 agents started.
