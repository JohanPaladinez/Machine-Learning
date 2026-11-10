@echo off
setlocal
cd /d "%~dp0"
echo Copiando los dos lanzadores corregidos v1.1 a Mininet.
echo Se pedira la contrasena de Mininet. Las redes no cambian durante la copia.
ssh mininet@192.168.56.107 "mkdir -p /home/mininet/proyecto_nsfnet/consolas_mininet_v1"
if errorlevel 1 goto error
scp "consolas_mininet_v1\iniciar.py" "consolas_mininet_v1\consola_sdn.py" mininet@192.168.56.107:/home/mininet/proyecto_nsfnet/consolas_mininet_v1/
if errorlevel 1 goto error
echo Abriendo las dos consolas interactivas. Cada una pedira SSH y sudo.
start "GEANT2 - Mininet interactivo" cmd /k ssh -t mininet@192.168.56.107 "sudo env PYTHONIOENCODING=utf-8 python3 -B /home/mininet/proyecto_nsfnet/consolas_mininet_v1/iniciar.py geant2 --proyecto /home/mininet/proyecto_nsfnet"
start "NSFNET - Mininet interactivo" cmd /k ssh -t mininet@192.168.56.107 "sudo env PYTHONIOENCODING=utf-8 python3 -B /home/mininet/proyecto_nsfnet/consolas_mininet_v1/iniciar.py nsfnet --proyecto /home/mininet/proyecto_nsfnet"
echo.
echo Espera los prompts mininet-geant2 y mininet-nsfnet en las nuevas ventanas.
echo No cierres esas dos ventanas. exit detiene solamente la red de esa consola.
echo Luego reinicia la interfaz con sus archivos Detener_interfaz y Abrir_interfaz.
echo Si el panel conserva una sesion anterior, pulsa NSFNET o GEANT2 para elegir la nueva.
pause
exit /b 0
:error
echo NO SE COMPLETO LA COPIA. Conserva este mensaje y compartelo en el chat.
pause
exit /b 1
