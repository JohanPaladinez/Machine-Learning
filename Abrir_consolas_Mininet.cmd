@echo off
setlocal
cd /d "%~dp0"
echo Primero debe haber terminado Arrancar_RYU.cmd con RYU LISTO.
echo Cada consola pedira la contrasena SSH y sudo de Mininet.
start "GEANT2 - Mininet interactivo" cmd /k ssh -t mininet@192.168.56.107 "sudo env PYTHONIOENCODING=utf-8 python3 -B /home/mininet/proyecto_nsfnet/consolas_mininet_v1/iniciar.py geant2 --proyecto /home/mininet/proyecto_nsfnet"
start "NSFNET - Mininet interactivo" cmd /k ssh -t mininet@192.168.56.107 "sudo env PYTHONIOENCODING=utf-8 python3 -B /home/mininet/proyecto_nsfnet/consolas_mininet_v1/iniciar.py nsfnet --proyecto /home/mininet/proyecto_nsfnet"
echo Espera mininet-geant2 y mininet-nsfnet. Manten abiertas ambas ventanas.
echo Despues abre Abrir_interfaz.cmd.
pause
