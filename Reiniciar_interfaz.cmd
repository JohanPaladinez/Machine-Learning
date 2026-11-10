@echo off
setlocal
cd /d "%~dp0"
echo Reiniciando solamente el panel y su API de Windows...
".venv\Scripts\python.exe" "detener_windows.py"
if errorlevel 1 goto error
".venv\Scripts\python.exe" "iniciar_windows.py"
if errorlevel 1 goto error
exit /b 0
:error
echo No se completo el reinicio. Comparte el mensaje de esta ventana.
pause
exit /b 1
