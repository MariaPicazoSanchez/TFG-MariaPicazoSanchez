@echo off
setlocal
cd /d %~dp0

if not exist ".pids" (
  echo No hay procesos guardados (.pids). Nada que parar.
  pause
  exit /b 0
)

for /f %%p in (.pids) do (
  echo Matando PID %%p ...
  taskkill /PID %%p /F >nul 2>&1
)

del .pids >nul 2>&1
echo Listo.
pause
