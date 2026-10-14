@echo off
set "PETEHUB_ROOT=%~dp0"
cd /d "%PETEHUB_ROOT%backend"
if exist "%PETEHUB_ROOT%backend\.venv\Scripts\python.exe" (
  "%PETEHUB_ROOT%backend\.venv\Scripts\python.exe" scripts\daily_update.py
) else (
  "%PETEHUB_ROOT%.venv\Scripts\python.exe" scripts\daily_update.py
)
