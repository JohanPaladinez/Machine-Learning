"""Activa los fuentes ya probados; solo detener FastAPI/Vite con autorizacion."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]

def find_process(port,marker):
    matches=[]
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args=path.read_bytes().decode().strip('\0').split('\0')
            if marker not in args or '--port' not in args or args[args.index('--port')+1]!=str(port):continue
            matches.append({'pid':int(path.parent.name),'args':args,'cwd':os.readlink(str(path.parent/'cwd'))})
        except (OSError,ValueError,IndexError):continue
    if len(matches)!=1:raise RuntimeError('Se esperaba exactamente un proceso verificado en '+str(port))
    return matches[0]

def http(path):
    with urlopen('http://127.0.0.1:8002'+path,timeout=5) as response:return json.load(response)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--activar',action='store_true',help='Confirma autorizacion para reiniciar solo la interfaz')
    args=parser.parse_args()
    processes={'backend':find_process(8002,'backend.api.sdn_selector_v2:app'),
               'frontend':find_process(5181,'preview')}
    if 'vite.sdn-selector.config.js' not in processes['frontend']['args']:
        raise RuntimeError('El frontend activo no es el selector esperado')
    if any(not Path(p['cwd']).resolve().is_relative_to(ROOT) for p in processes.values()):
        raise RuntimeError('Proceso fuera del proyecto esperado')
    print(json.dumps(processes,indent=2))
    if not args.activar:
        print('Solo consulta. Usar --activar unicamente con autorizacion.');return
    target=ROOT/'frontend/app/dist-rutas-ml/sdn-selector.html'
    if not target.exists():raise RuntimeError('Primero compilar la version de produccion')
    directory=ROOT/'interfaz_rutas_ml_ejecucion';directory.mkdir(exist_ok=True)
    record=directory/('activacion_'+time.strftime('%Y%m%d_%H%M%S')+'.json')
    prior=http('/api/sdn/estado')
    state={'previous':processes,'previous_selection':{k:prior.get(k) for k in ['source_url','ryu_rest_override','selected_topologia','selected_session_id']},'new':{}}
    record.write_text(json.dumps(state,indent=2))
    # Identidad comprobada inmediatamente antes de enviar SIGTERM.
    for name,old in processes.items():
        current=find_process(8002 if name=='backend' else 5181,'backend.api.sdn_selector_v2:app' if name=='backend' else 'preview')
        if current!=old:raise RuntimeError('El proceso cambio; se cancela la activacion')
        os.kill(old['pid'],signal.SIGTERM)
    time.sleep(2)
    for name,command in [('backend',['bash',str(ROOT/'scripts/iniciar_backend.sh')]),
                         ('frontend',['bash',str(ROOT/'scripts/iniciar_frontend.sh')])]:
        with (directory/(name+'.log')).open('ab') as log:
            p=subprocess.Popen(command,cwd=str(ROOT),stdout=log,stderr=log,start_new_session=True)
        state['new'][name]=p.pid
    record.write_text(json.dumps(state,indent=2))
    for attempt in range(30):
        try:
            assert http('/api/salud')['estado']=='ok'
            with urlopen('http://127.0.0.1:5181/sdn-selector.html',timeout=3) as response:
                assert response.status==200
            print('Activada: http://127.0.0.1:5181/sdn-selector.html');print('Registro: '+str(record));return
        except (OSError,AssertionError):time.sleep(.5)
    raise RuntimeError('Revisar logs de activacion; no se han tocado RYU ni Mininet')

if __name__=='__main__':main()
