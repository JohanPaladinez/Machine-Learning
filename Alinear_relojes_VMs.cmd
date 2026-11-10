@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "%~dp0alinear_relojes_vms.py"
) else (
  python "%~dp0alinear_relojes_vms.py"
)
if errorlevel 1 pause
