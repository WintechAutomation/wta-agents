@echo off
chcp 65001 >nul 2>&1
echo ==========================================
echo   WTA Multi-Agent System Start
echo ==========================================
echo.
powershell -ExecutionPolicy Bypass -File "C:\MES\wta-agents\scripts\launch-agents-conemu.ps1"
echo.
echo   All services launched in ConEmu.
echo ==========================================
