"""Alineacion manual de dos VMs con la hora de la API Windows. Ejecutar en Windows.

No configura NTP. SSH crea un tunel temporal exclusivamente loopback durante
cada ajuste. La autenticacion SSH y sudo se completa en la terminal del usuario.
"""
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from urllib.request import build_opener, ProxyHandler

REMOTE_CODE = r'''
import getpass, json, socket, subprocess, time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.request import build_opener, ProxyHandler

client=build_opener(ProxyHandler({}))
def reference():
    start=time.monotonic()
    with client.open('http://127.0.0.1:19443/api/windows/salud',timeout=5) as r:
        header=r.headers.get('Date')
        health=json.load(r)
    elapsed=time.monotonic()-start
    if health.get('servicio') != 'SDN/KDN Windows Rutas ML' or health.get('estado') != 'ok':
        raise ValueError('El tunel no llega a la API Windows esperada')
    if elapsed>2:
        raise ValueError('La referencia tardo demasiado; no se ajusta el reloj')
    date=parsedate_to_datetime(header)
    if date.tzinfo is None:
        raise ValueError('La referencia no declara zona horaria')
    # Date HTTP tiene precision de un segundo. Se toma el punto medio de ese segundo.
    return date.timestamp()+0.5+elapsed/2

print('VM: '+socket.gethostname()+' / usuario: '+getpass.getuser(),flush=True)
print('UTC ANTES: '+datetime.now(timezone.utc).isoformat(),flush=True)
ref=reference()
subprocess.check_call(['sudo','-n','date','-u','-s','@{:.6f}'.format(ref)])
print('UTC DESPUES: '+datetime.now(timezone.utc).isoformat(),flush=True)
ref=reference()
delta=time.time()-ref
print('DIFERENCIA ESTIMADA RESPECTO A WINDOWS: {:.3f} s'.format(delta),flush=True)
if abs(delta)>2.5:
    raise SystemExit('No se confirmo la precision esperada; comparte esta salida')
print('AJUSTE MANUAL CONFIRMADO',flush=True)
'''


def main():
    ssh=shutil.which('ssh.exe') or shutil.which('ssh')
    if not ssh:
        raise SystemExit('No se encontro OpenSSH en Windows')
    client=build_opener(ProxyHandler({}))
    with client.open('http://127.0.0.1:8003/api/windows/salud',timeout=5) as response:
        health=json.load(response)
    if health.get('servicio') != 'SDN/KDN Windows Rutas ML' or health.get('estado') != 'ok':
        raise SystemExit('Primero abre la aplicacion Windows del puerto 8003')
    print('Se alinean RYU y Mininet con la hora de Windows.',flush=True)
    print('Puede pedir las contrasenas SSH y sudo de cada VM.',flush=True)
    print('El acceso temporal a la referencia solo escucha en loopback y se cierra al terminar SSH.',flush=True)
    for name,target in [('RYU','ryu@192.168.56.108'),('MININET','mininet@192.168.56.107')]:
        print('\nAjustando '+name+'...',flush=True)
        command='sudo -v && python3 -c '+shlex.quote(REMOTE_CODE)
        result=subprocess.run([ssh,'-tt','-o','ExitOnForwardFailure=yes',
            '-R','127.0.0.1:19443:127.0.0.1:8003',target,command])
        if result.returncode:
            raise SystemExit('No se confirmo el ajuste de '+name+'. Comparte la salida anterior.')
    print('\nAMBAS VMS ALINEADAS CON WINDOWS.',flush=True)
    print('Espera 60 segundos para nuevas ventanas; despues pulsa Comparar las 5 rutas.',flush=True)
    print('Una ventana descartada por salto del reloj durante el ajuste es esperada.',flush=True)
    print('No se reentrenan modelos, no se modifican datasets finales ni se reinician redes.',flush=True)


if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError) as error:
        raise SystemExit('ERROR: '+str(error))
