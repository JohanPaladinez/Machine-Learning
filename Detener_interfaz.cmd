@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" "detener_windows.py"
if errorlevel 1 pause
