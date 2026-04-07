@echo off
chcp 65001 > nul
echo Starting Slack Bot...
cd /d C:\MES\wta-agents\scripts
C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe slack-bot.py
pause
