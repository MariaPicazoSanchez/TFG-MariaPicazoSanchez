@echo off
chcp 65001 >nul
setlocal
cd /d %~dp0

if not exist "logs" mkdir logs

echo ===== START %date% %time% =====
echo ===== START %date% %time% =====>> logs\launcher_console.log

echo [DEBUG] where python:
where python
where python >> logs\launcher_console.log 2>&1

echo [DEBUG] python --version:
python --version
python --version >> logs\launcher_console.log 2>&1

echo [DEBUG] launching launcher.py...
python launcher.py >> logs\launcher_console.log 2>&1

echo ===== END %date% %time% =====
echo ===== END %date% %time% =====>> logs\launcher_console.log

pause
