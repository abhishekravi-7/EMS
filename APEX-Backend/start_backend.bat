@echo off
REM Java APEX Backend - Start Script
cd /d "%~dp0"
set PYTHON=python
if exist "%~dp0venv\Scripts\python.exe" set PYTHON="%~dp0venv\Scripts\python.exe"
echo Starting Java APEX Backend on http://127.0.0.1:8000
echo.
%PYTHON% run.py
pause
