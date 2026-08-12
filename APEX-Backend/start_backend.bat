@echo off
REM Java APEX Backend - Start Script
cd /d "%~dp0"
set PYTHON="%~dp0venv\Scripts\python.exe"
echo Starting Java APEX Backend on http://127.0.0.1:8000
echo.
%PYTHON% -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info --reload
pause
