@echo off
chcp 65001 >nul 2>&1
echo Testing auto-confirm for development channels prompt...
echo.
echo 1| claude --dangerously-skip-permissions --dangerously-load-development-channels server:wta-hub -p "echo test"
echo.
echo Done. Exit code: %ERRORLEVEL%
pause
