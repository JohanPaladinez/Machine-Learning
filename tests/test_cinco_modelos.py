import copy
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT
sys.path.insert(0,str(APP))
from backend.api import sdn_cinco_modelos as api
from backend.api import sdn_selector_v2 as selector
from fastapi import HTTPException
spec=importlib.util.spec_from_file_location('multi_service',ROOT/'rutas_cinco_modelos_ryu/servidor_cuatro_modelos.py')
service=importlib.util.module_from_spec(spec);spec.loader.exec_module(service)
FEATURES=['capacity_mbps']+['f'+str(i) for i in range(59)]

class ConstantEstimator:
    def predict(self,x):
        import numpy as np
        return np.full((len(x),6),.1)


def fixture():
    links=[]
    for a,b,c in [('s','t',1),('s','a',2),('a','t',2),('s','b',100),('b','c',100),('c','t',100),('s','d',5),('d','t',5)]:
        links.append(dict(link_id=a+'-'+b,switch_u=a,switch_v=b,capacity_mbps=c,configured_delay_ms=5))
    end=time.time()-2;start=end-20;iso=lambda v:datetime.fromtimestamp(v,timezone.utc).isoformat()
    metrics={}
    for e in links:
        metrics[e['link_id']]={'method':'af_packet_offered_probes_tx_status_kernel_rx_v3',
            'loss_scope':'offered_including_local_tx_refusals',
            'directions':{d:{'throughput_mbps':.1,'delay_ms':10.,'loss_ratio':.01} for d in ('u_to_v','v_to_u')},
            'ml':{'status':'inputs_ready','topologia':'nsfnet','session_id':'session','link_id':e['link_id'],
                  'feature_start_epoch_s':start,'feature_end_epoch_s':end,
                  'features':{k:(e['capacity_mbps'] if k=='capacity_mbps' else 1) for k in FEATURES}}}
    snapshot={'ready':True,'source_url':'http://127.0.0.1','topologia':'nsfnet','session_id':'session',
        'topology_instance_id':'instance','graph_version':'v1','selection_revision':1,'observed_utc':iso(end),
        'topology_document':{'topologies':{'nsfnet':{'nodes':[{'switch':n} for n in ['s','t','a','b','c','d']], 'links':links}}},
        'links_runtime':[{'id':e['link_id'],'state':'up'} for e in links],
        'metrics':{'status':'fresh','window_start':iso(start),'window_end':iso(end),'links':metrics}}
    ids={n:n+'_hash' for n in api.MODELS}
    health={'schema_version':1,'estado':'cuatro_modelos_cargados','evaluacion':'test_descriptivo_completado',
            'antiguedad_maxima_s':120,'features':FEATURES,'targets':list(service.TARGETS),'modelos':ids,
            'dataset_sha256':'dataset','seleccion_validation':'xgboost'}
    paths={'polinomial':{'s-t'},'decision_tree':{'s-a','a-t'},'random_forest':{'s-d','d-t'},'xgboost':{'s-b','b-c','c-t'}}
    predictions={}
    for name in api.MODELS:
        predictions[name]={}
        for e in links:
            entry=metrics[e['link_id']]['ml']
            raw={k:(.1 if 'throughput' in k else 0. if 'loss' in k else .01 if e['link_id'] in paths[name] else 100.) for k in service.TARGETS}
            if name=='polinomial' and e['link_id']=='s-t':
                raw['target_u_to_v_delay_avg_ms']=-1
            used,adjustments=service.physical(raw)
            out={k:entry[k] for k in ('session_id','topologia','link_id','feature_start_epoch_s','feature_end_epoch_s')}
            out.update(modelo_id=ids[name],predicciones=used,predicciones_crudas=raw,ajustes=adjustments)
            predictions[name][e['link_id']]=out
    response={'schema_version':1,'modelos':ids,'dataset_sha256':'dataset','predicciones':predictions}
    request=api.ComparisonRequest(topology_instance_id='instance',graph_version='v1',selection_revision=1,
                                  origen='s',destino='t',pesos={'delay':1,'loss':0,'capacity':0,'load':0})
    return snapshot,health,response,request


class FiveRoutes(unittest.TestCase):
    def setUp(self):api._cache.clear()
    def call(self,s,h,r,request,actual=None):
        network=SimpleNamespace(snapshot=lambda **kw:s)
        if actual is not None:
            network=SimpleNamespace(snapshot=unittest.mock.Mock(side_effect=[s,actual]))
        def remote(path,body=None):
            if path=='/health':return h
            self.assertEqual(path,'/predict-batch');self.assertEqual(len(body['entries']),len(s['links_runtime']))
            return r
        with patch.object(selector.original,'network',network),patch.object(api,'remote',side_effect=remote):
            return api.compare_models(request)

    def test_five_real_computations_and_common_measurements(self):
        s,h,r,q=fixture();result=self.call(s,h,r,q)
        self.assertEqual(result['criterios_disponibles'],5);self.assertFalse(result['rules_installed'])
        self.assertEqual(result['rutas']['conventional']['ruta'],['s','b','c','t'])
        for name,path in [('polinomial',['s','t']),('decision_tree',['s','a','t']),('random_forest',['s','d','t']),('xgboost',['s','b','c','t'])]:
            route=result['rutas'][name];self.assertEqual(route['ruta'],path)
            self.assertEqual(route['measured_delay_ms'],10*(len(path)-1))
            self.assertAlmostEqual(route['measured_loss_ratio'],1-.99**(len(path)-1))
        poly=result['rutas']['polinomial'];self.assertEqual(poly['ajustes_ruta'][0]['raw'],-1)
        self.assertEqual(poly['delay_previsto_ms'],0)
        self.assertEqual(result['caminos_distintos'],4)

    def test_missing_service_keeps_only_conventional(self):
        s,h,r,q=fixture()
        with patch.object(selector.original,'network',SimpleNamespace(snapshot=lambda **kw:s)),patch.object(api,'remote',side_effect=HTTPException(424,'not available')):
            result=api.compare_models(q)
        self.assertIsNotNone(result['rutas']['conventional']);self.assertTrue(all(result['rutas'][m] is None for m in api.MODELS))

    def test_race_returns_409(self):
        s,h,r,q=fixture();actual=copy.deepcopy(s);actual['selection_revision']=2
        with self.assertRaises(HTTPException) as caught:self.call(s,h,r,q,actual)
        self.assertEqual(caught.exception.status_code,409)

    def test_response_wrong_session_is_rejected(self):
        s,h,r,q=fixture();r['predicciones']['xgboost']['s-t']['session_id']='other'
        result=self.call(s,h,r,q)
        self.assertEqual(result['ml']['status'],'unavailable')
        self.assertTrue(all(result['rutas'][m] is None for m in api.MODELS))

    def test_unrecorded_projection_not_used(self):
        s,h,r,q=fixture();r['predicciones']['polinomial']['s-t']['ajustes']=[]
        result=self.call(s,h,r,q);self.assertEqual(result['ml']['status'],'unavailable')
        self.assertIsNone(result['rutas']['polinomial'])

    def test_common_window_and_expiry(self):
        s,h,r,q=fixture();s['metrics']['links']['s-t']['ml']['feature_end_epoch_s']-=1
        result=self.call(s,h,r,q);self.assertEqual(result['ml']['status'],'unavailable')
        s,h,r,q=fixture();s['metrics']['links']['s-t']['ml']['feature_end_epoch_s']-=200
        result=self.call(s,h,r,q);self.assertEqual(result['ml']['status'],'unavailable')

    def test_physical_policy_and_nonfinite(self):
        raw={k:-2 for k in service.TARGETS};raw['target_u_to_v_loss_ratio']=2
        used,changes=service.physical(raw)
        self.assertEqual(used['target_u_to_v_loss_ratio'],1);self.assertEqual(len(changes),6)
        raw['target_u_to_v_loss_ratio']=float('nan')
        with self.assertRaises(ValueError):service.physical(raw)

    def test_live_api_route_registered(self):
        import servir_api_windows
        # Este caso comprueba registro de API; un clon no trae bundles compilados.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'configuracion_windows.json').write_text((APP/'configuracion_windows.json').read_text(), encoding='utf-8')
            (root/'frontend/app/dist-sdn-selector-v2').mkdir(parents=True)
            app=servir_api_windows.crear_app(root)
        self.assertIn('/api/sdn/rutas/comparar-modelos',selector.original.original_app.openapi()['paths'])

    def test_batch_service_uses_all_models_and_preserves_raw(self):
        import numpy as np
        class Constant:
            def predict(self,x):return np.full((len(x),6),-.5)
        models=service.Models.__new__(service.Models)
        models.features=FEATURES;models.ids={n:n+'_id' for n in service.MODELS}
        models.dataset_sha256='dataset';models.selected='xgboost'
        models.models={n:{'modelo':Constant(),'targets':list(service.TARGETS)} for n in service.MODELS}
        s,_,_,_=fixture();entries=[v['ml'] for v in s['metrics']['links'].values()]
        output=models.predict(entries)
        self.assertEqual(set(output['predicciones']),set(service.MODELS))
        poly=output['predicciones']['polinomial']['s-t']
        self.assertEqual(poly['predicciones_crudas'][service.TARGETS[0]],-.5)
        self.assertEqual(poly['predicciones'][service.TARGETS[0]],0)
        self.assertEqual(len(poly['ajustes']),6)
        with self.assertRaisesRegex(ValueError,'duplicado'):models.predict(entries+[entries[0]])
        missing=copy.deepcopy(entries);missing[0]['features'].pop(FEATURES[-1])
        with self.assertRaisesRegex(ValueError,'incompletas'):models.predict(missing)

    def test_model_files_loaded_only_with_matching_hashes_and_reports(self):
        import joblib
        with tempfile.TemporaryDirectory(dir=None) as td:
            p=Path(td);hashes={}
            for name in service.MODELS:
                package={'modelo':ConstantEstimator(),'features':FEATURES,'targets':list(service.TARGETS),
                         'dataset_sha256':'dataset','nombre':name}
                joblib.dump(package,str(p/(name+'.pkl')))
                hashes[name]=service.digest(p/(name+'.pkl'))
            def write(name,value):(p/name).write_text(json.dumps(value),encoding='utf-8')
            write('protocolo.json',{'features':FEATURES,'targets':list(service.TARGETS),'dataset_sha256':'dataset'})
            write('comparacion_validation.json',{'modelos':{n:{} for n in service.MODELS},'seleccion_validation':'xgboost','huellas_modelos':hashes})
            write('comparacion_test.json',{'modelos':{n:{} for n in service.MODELS},'seleccion_previa_validation':'xgboost','dataset_sha256':'dataset'})
            loaded=service.Models(p)
            self.assertEqual(len(loaded.health()['modelos']),4)
            s,_,_,_=fixture();entries=[v['ml'] for v in s['metrics']['links'].values()]
            self.assertEqual(len(loaded.predict(entries)['predicciones']),4)
            with (p/'polinomial.pkl').open('ab') as f:f.write(b'cambio')
            with self.assertRaisesRegex(ValueError,'modificado'):service.Models(p)


if __name__=='__main__':unittest.main()
