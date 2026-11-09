"""Casos sinteticos explicitos; las pruebas en vivo se registran aparte."""
import copy
import time
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException
from backend.servicios.comparacion_rutas import parameters, compare, TARGETS, directional_cost
from backend.servicios.fuentes_sdn import MultiNetwork
from backend.api.sdn_comparacion import predict_snapshot
from backend.api.sdn_comparacion import comparison, ComparisonRequest


def fixture():
    end=time.time()-2; start=end-20
    edges=[{'link_id':f'{a}-{b}','switch_u':a,'switch_v':b,'capacity_mbps':c}
           for a,b,c in [('s1','s2',10),('s2','s3',10),('s1','s3',1)]]
    s={'ready':True,'topologia':'nsfnet','source_url':'http://127.0.0.1:8769','session_id':'test',
       'topology_instance_id':'instance','graph_version':'v1','selection_revision':1,
       'topology_document':{'topologies':{'nsfnet':{'nodes':[{'switch':n} for n in ['s1','s2','s3']], 'links':edges}}},
       'links_runtime':[{'id':e['link_id'],'state':'up'} for e in edges],
       'metrics':{'status':'fresh','window_start':datetime.fromtimestamp(start,timezone.utc).isoformat(),
                  'window_end':datetime.fromtimestamp(end,timezone.utc).isoformat(),'links':{}}}
    preds={}
    features={f'f{i}':1.0 for i in range(59)}
    for edge in edges:
        lid=edge['link_id']
        values={}
        for direction,keys in TARGETS.items():
            values.update(dict(zip(keys,[0.0, 1.0 if lid=='s1-s3' and direction=='u_to_v' else 100.0, 0.0])))
        preds[lid]={'predicciones':values}
        s['metrics']['links'][lid]={'method':'af_packet_offered_probes_tx_status_kernel_rx_v3',
            'loss_scope':'offered_including_local_tx_refusals','ml':{'status':'inputs_ready',
            'topologia':'nsfnet','session_id':'test','link_id':lid,'feature_start_epoch_s':start,
            'feature_end_epoch_s':end,'features':dict(features,capacity_mbps=edge['capacity_mbps'])}}
    return s,preds


class ComparisonTests(unittest.TestCase):
    def test_endpoint_unavailable_keeps_reference_and_rejects_selection_race(self):
        from backend.api import sdn_selector_v2 as selector
        snapshot,_=fixture();snapshot['observed_utc']='test'
        req=ComparisonRequest(topology_instance_id='instance',graph_version='v1',selection_revision=1,origen='s1',destino='s3')
        with patch.object(selector.original,'network') as net, patch('backend.api.sdn_comparacion.predict_snapshot',side_effect=HTTPException(424,'sin entradas')):
            net.snapshot.return_value=snapshot
            result=comparison(req)
            self.assertEqual(result['convencional']['ruta'],['s1','s2','s3'])
            self.assertIsNone(result['inteligente'])
            self.assertIsNone(result['convencional']['costo_qos'])
            changed=dict(snapshot,selection_revision=2)
            net.snapshot.side_effect=[snapshot,changed]
            with self.assertRaises(HTTPException) as caught:comparison(req)
            self.assertEqual(caught.exception.status_code,409)

    def test_direction_and_same_formula(self):
        s,p=fixture(); w,sc=parameters()
        req=SimpleNamespace(topology_instance_id='instance',graph_version='v1',origen='s1',destino='s3')
        ref,ml=compare(s,req,p,w,sc)
        self.assertEqual(ref['ruta'],['s1','s2','s3'])
        self.assertEqual(ml['ruta'],['s1','s3'])
        self.assertLess(ml['costo_qos'],ref['costo_qos'])
        self.assertAlmostEqual(ref['costo_referencia'],.2)
        # En el sentido inverso las predicciones favorecen los dos enlaces rapidos.
        for lid in ['s1-s2','s2-s3']:
            p[lid]['predicciones']['target_v_to_u_delay_avg_ms']=1.0
        req.origen,req.destino='s3','s1'
        ref,ml=compare(s,req,p,w,sc)
        self.assertEqual(ml['ruta'],['s3','s2','s1'])
        self.assertEqual(ref['ruta'],ml['ruta'])

    def test_loss_composition_and_no_throughput_sum(self):
        s,p=fixture();w,sc=parameters()
        for v in p.values():
            for keys in TARGETS.values(): v['predicciones'][keys[2]]=.1
        req=SimpleNamespace(topology_instance_id='instance',graph_version='v1',origen='s1',destino='s3')
        ref,_=compare(s,req,p,w,sc)
        self.assertAlmostEqual(ref['loss_previsto_ratio'],.19)
        self.assertEqual(ref['capacidad_minima_mbps'],10)
        self.assertNotIn('throughput_path_mbps',ref)

    def test_bad_weights_and_zero_rx(self):
        for bad in [float('nan'),float('inf'),-1]:
            with self.assertRaises(ValueError): parameters({'delay':bad,'loss':1,'capacity':1,'load':0})
        with self.assertRaises(ValueError): parameters(dict.fromkeys(['delay','loss','capacity','load'],0))
        w,sc=parameters()
        self.assertEqual(directional_cost(1,0,0,0,w,sc)[0],.075)
        snapshot,predictions=fixture()
        for p in predictions.values():
            for keys in TARGETS.values():p['predicciones'][keys[1]]=1e308
        req=SimpleNamespace(topology_instance_id='instance',graph_version='v1',origen='s1',destino='s3')
        with self.assertRaises(ValueError):compare(snapshot,req,predictions,w,sc)

    def test_down_link_excluded(self):
        s,p=fixture();s['links_runtime'][-1]['state']='down';w,sc=parameters()
        req=SimpleNamespace(topology_instance_id='instance',graph_version='v1',origen='s1',destino='s3')
        _,ml=compare(s,req,p,w,sc)
        self.assertEqual(ml['ruta'],['s1','s2','s3'])

    def test_invalid_inputs_never_reach_model(self):
        s,p=fixture()
        schema={'features':list(s['metrics']['links']['s1-s2']['ml']['features']),
                'targets':[k for triple in TARGETS.values() for k in triple],'antiguedad_maxima_s':120}
        health={'estado':'modelo_cargado','evaluacion':'test_completado','features':60,'targets':6,'modelo_id':'test'}
        mutations=[lambda s:s['metrics'].update(status='stale'),
                   lambda s:s['metrics']['links']['s1-s2']['ml'].update(session_id='other'),
                   lambda s:s['metrics']['links']['s1-s2']['ml'].update(topologia='geant2'),
                   lambda s:s['metrics']['links']['s1-s2']['ml']['features'].pop('f0'),
                   lambda s:s['metrics']['links']['s1-s2']['ml'].update(feature_end_epoch_s=time.time()-121),
                   lambda s:s['metrics']['links']['s1-s2']['ml'].update(feature_end_epoch_s=time.time()+20),
                   lambda s:s['metrics']['links']['s1-s2']['ml'].update(feature_end_epoch_s=float('nan'))]
        with patch('backend.api.sdn_comparacion.consultar',side_effect=lambda path:health if path=='/health' else schema), patch('backend.api.sdn_comparacion._predecir') as model:
            for mutate in mutations:
                altered=copy.deepcopy(s);mutate(altered)
                with self.assertRaises(HTTPException):predict_snapshot(altered)
            model.assert_not_called()


class SourceTests(unittest.TestCase):
    def make(self):
        sources={name:{'observer_url':f'http://127.0.0.1:{port}','ryu_rest_url':f'http://127.0.0.1:{port+100}',
                       'openflow_port':port+200} for name,port in [('nsfnet',8769),('geant2',8768)]}
        docs={}
        for name in sources:
            docs[name]={'schema_version':1,'observer_version':'sdn-vivo-1','networks':[
                {'topologia':n,'session_id':n,'capture':{'alive':True},'controller':{
                    'ip':'127.0.0.1','rest_url':sources[n]['ryu_rest_url'],'of_port':sources[n]['openflow_port']},
                 'topology_document':{'topologies':{n:{'nodes':[],'links':[]}}}} for n in sources]}
        def fetch(url):
            name=next(n for n,c in sources.items() if url==c['observer_url']+'/snapshot')
            if docs[name] is None:raise OSError('offline')
            return docs[name]
        with patch.dict('os.environ',{'SDN_MININET_URL':''}): net=MultiNetwork(sources,fetch)
        return net,docs

    def test_sources_auto_sticky_and_failover(self):
        net,docs=self.make();net._discover()
        self.assertEqual(len(net.choices),2)  # La fuente mixta se filtra.
        net.select_topology('geant2');net._discover()
        self.assertEqual(net.read_source(net.source_url+'/snapshot')['topologia'],'geant2')
        net.select_topology('auto'); self.assertEqual(net.auto_name,'geant2')
        with patch.object(MultiNetwork.__bases__[0],'_snapshot',return_value={}):
            net._snapshot(0);self.assertEqual(net.auto_name,'geant2')
            docs['geant2']=None;net._snapshot(0);self.assertEqual(net.auto_name,'nsfnet')
        with self.assertRaises(ValueError):net.configure('http://127.0.0.1:9999')

    def test_wrong_controller_and_session(self):
        net,docs=self.make();net.select_topology('nsfnet','missing');net._discover()
        self.assertEqual(net.read_source(net.source_url+'/snapshot')['status'],'inactive')
        net.select_topology('nsfnet');docs['nsfnet']['networks'][0]['controller']['of_port']=1;net._discover()
        self.assertEqual(net.read_source(net.source_url+'/snapshot')['status'],'controller_mismatch')


if __name__=='__main__': unittest.main()
