@echo off
setlocal
cd /d "%~dp0"
echo Las VMs RYU y Mininet deben estar encendidas.
echo Este paso arranca solo controladores y modelos en RYU, sin entrenar.
echo Puede pedir la contrasena SSH varias veces.
ssh ryu@192.168.56.108 "mkdir -p /home/ryu/proyecto_nsfnet/arranque_diario_sdn"
if errorlevel 1 goto error
scp "arranque_diario_sdn\arrancar_ryu.py" ryu@192.168.56.108:/home/ryu/proyecto_nsfnet/arranque_diario_sdn/
if errorlevel 1 goto error
ssh -t ryu@192.168.56.108 "env PYTHONIOENCODING=utf-8 python3 -B /home/ryu/proyecto_nsfnet/arranque_diario_sdn/arrancar_ryu.py"
if errorlevel 1 goto error
echo.
echo Siguiente: Abrir_consolas_Mininet.cmd. Espera ambas consolas antes del panel.
pause
exit /b 0
:error
echo ARRANQUE INCOMPLETO. Conserva la salida; no inicies otros lanzadores antiguos.
pause
exit /b 1
