@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Falta el entorno de la interfaz. Ejecuta instalar_windows.py con Python.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "iniciar_windows.py"
if errorlevel 1 pause
