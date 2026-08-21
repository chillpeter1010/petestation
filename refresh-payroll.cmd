@echo off
setlocal
set "PROJECT_ROOT=%~dp0"
"%PROJECT_ROOT%.venv\Scripts\python.exe" "%PROJECT_ROOT%backend\scripts\refresh_payroll.py" --year 2026 --workers 2 %*
pause
