#!/usr/bin/env python3
"""Recuperacion opt-in tras apagar las VMs. No ejecutar en una sesion activa."""
import argparse
import datetime
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import uuid
from urllib.request import urlopen

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('topologia',choices=['nsfnet','geant2'])
    parser.add_argument('--arrancar-red',action='store_true',help='Crea la red, su forwarding convencional y la telemetria de baja carga existente')
    args=parser.parse_args()
    base=Path(__file__).resolve().parent
    cfg=json.loads((base/args.topologia/'perfil.json').read_text())
    port=8769 if args.topologia=='nsfnet' else 8768
    try:
        with urlopen('http://192.168.56.103:{}/snapshot'.format(port),timeout=3) as response:
            data=json.load(response)
        print(json.dumps({'observador':'disponible','sesiones':[n.get('session_id') for n in data.get('networks',[]) if n.get('topologia')==args.topologia]},indent=2))
        if args.arrancar_red:raise SystemExit('El observador ya responde. No se inicia otra red.')
        return
    except OSError:
        if not args.arrancar_red:
            print('Observador no disponible. Esta consulta no inicia nada.');return
    if os.geteuid()!=0:raise SystemExit('El arranque de Mininet necesita sudo.')
    addresses=json.loads(subprocess.check_output(['ip','-j','addr'],universal_newlines=True))
    if '192.168.56.103' not in [a.get('local') for i in addresses for a in i.get('addr_info',[])]:
        raise SystemExit('La IP de Mininet cambio. Revisar la configuracion y los observadores antes de arrancar.')
    with urlopen(cfg['rest_url']+'/stats/switches',timeout=4) as response:
        if json.load(response):raise SystemExit('RYU ya tiene switches. Se conserva la sesion existente.')
    # No se limpian bridges ni se detienen procesos para liberar puertos.
    sock=socket.socket()
    try:sock.bind(('192.168.56.103',port))
    finally:sock.close()
    cfg['project']=str(base/'sesiones')
    cfg['observer_file']=str(base/'observador_sdn.py')
    stamp=datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    session=base/'sesiones'/('vivo_{}_{}_{}'.format(args.topologia,stamp,uuid.uuid4().hex[:8]))
    session.mkdir(parents=True)
    (session/'config.json').write_text(json.dumps(cfg,indent=2))
    (base/('ultima_'+args.topologia+'.txt')).write_text(str(session))
    worker=base/args.topologia/('telemetria_nsf_v1.py' if args.topologia=='nsfnet' else 'telemetria_geant_v1.py')
    print('Sesion nueva: '+str(session),flush=True)
    os.execv(sys.executable,[sys.executable,'-u',str(worker),str(session)])

if __name__=='__main__':main()
