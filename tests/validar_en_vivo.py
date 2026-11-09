"""Validacion opt-in contra servicios existentes; solo consultas e inferencia."""
import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen
BASE=os.getenv('SDN_TEST_API','http://127.0.0.1:8003')
def request(path,payload=None):
    r=Request(BASE+path,data=json.dumps(payload).encode() if payload is not None else None,
              headers={'Content-Type':'application/json'})
    with urlopen(r,timeout=90) as response:return json.load(response)
def main():
    results=[]
    for topology,last in [('nsfnet','s14'),('geant2','s24')]:
        request('/api/sdn/seleccionar',{'topologia':topology})
        s=request('/api/sdn/estado')
        assert s['ready'] and s['topologia']==topology,s.get('message')
        assert s['ryu']['identity_verified']
        body={k:s[k] for k in ['topology_instance_id','graph_version','selection_revision']}
        body.update(origen='s1',destino=last)
        start=time.monotonic();comparison=request('/api/sdn/rutas/comparar',body)
        assert comparison['ml']['status']=='available',comparison['ml']
        assert comparison['rules_installed'] is False
        assert comparison['inteligente']['costo_qos'] <= comparison['convencional']['costo_qos']+1e-12
        old=request('/api/sdn/rutas',dict(topology_instance_id=s['topology_instance_id'],
            graph_version=s['graph_version'],origen='s1',destino=last,criterio='capacity'))
        assert old['ruta']==comparison['convencional']['ruta']
        assert abs(old['costo_total']-comparison['convencional']['costo_referencia'])<1e-12
        comparison['validation_elapsed_s']=time.monotonic()-start
        results.append(comparison)
        print(topology,comparison['convencional']['ruta'],comparison['inteligente']['ruta'],comparison['ml'],flush=True)
    request('/api/sdn/seleccionar',{'topologia':'auto'})
    before=request('/api/sdn/estado');time.sleep(5.1);after=request('/api/sdn/estado')
    assert before['topologia']==after['topologia']
    target=Path('validacion_rutas_ml');target.mkdir(exist_ok=True)
    (target/'resultados_reales.json').write_text(json.dumps(results,indent=2,ensure_ascii=False))
    print('Comparaciones reales y compatibilidad convencional verificadas; Auto estable.')
if __name__=='__main__': main()
