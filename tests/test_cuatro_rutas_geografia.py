import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.servicios.comparacion_rutas import compare_four, parameters, TARGETS, route_groups, classical_routes

def fixture():
    edges=[]
    for a,b,c,d,p in [('s','t',1,50,100),('s','a',2,1,60),('a','t',2,1,60),('s','b',100,5,80),('b','c',100,5,80),('c','t',100,5,80),('s','d',5,10,.1),('d','t',5,10,.1)]:
        edges.append(dict(link_id=a+'-'+b,switch_u=a,switch_v=b,capacity_mbps=c,configured_delay_ms=d,pred=p))
    s={'ready':True,'topologia':'nsfnet','topology_instance_id':'instance','graph_version':'v1',
       'links_runtime':[{'id':e['link_id'],'state':'up'} for e in edges],
       'topology_document':{'topologies':{'nsfnet':{'nodes':[{'switch':n} for n in ['s','a','b','c','d','t']], 'links':edges}}}}
    pred={}
    for e in edges:
        values={}
        for keys in TARGETS.values():values.update(dict(zip(keys,[.05,e['pred'],0.0])))
        pred[e['link_id']]={'predicciones':values}
    req=SimpleNamespace(topology_instance_id='instance',graph_version='v1',origen='s',destino='t')
    return s,pred,req

class FourRoutes(unittest.TestCase):
    def test_four_distinct_paths_and_same_forecast_evaluation(self):
        s,p,r=fixture();w,sc=parameters();routes,errors=compare_four(s,r,p,w,sc)
        self.assertFalse(errors)
        self.assertEqual(routes['hops']['ruta'],['s','t'])
        self.assertEqual(routes['delay']['ruta'],['s','a','t'])
        self.assertEqual(routes['capacity']['ruta'],['s','b','c','t'])
        self.assertEqual(routes['ml']['ruta'],['s','d','t'])
        self.assertEqual(len(route_groups(routes)),4)
        self.assertAlmostEqual(routes['delay']['costo_criterio'],2)
        self.assertAlmostEqual(routes['capacity']['costo_criterio'],.03)
        for route in routes.values():
            self.assertIsNotNone(route['delay_previsto_ms'])
            self.assertEqual(len(route['predicciones_enlaces']),route['saltos'])
            self.assertLessEqual(routes['ml']['costo_qos'],route['costo_qos']+1e-12)
        self.assertEqual(routes['delay']['retardo_configurado_total_ms'],2)
        self.assertEqual(routes['hops']['delay_previsto_ms'],100)
    def test_missing_configured_delay_does_not_invent_values(self):
        s,p,r=fixture();s['topology_document']['topologies']['nsfnet']['links'][0].pop('configured_delay_ms')
        w,sc=parameters();routes,errors=compare_four(s,r,p,w,sc)
        self.assertIsNone(routes['delay']);self.assertIn('delay',errors)
        self.assertIsNotNone(routes['hops']);self.assertIsNotNone(routes['capacity']);self.assertIsNotNone(routes['ml'])
    def test_no_model_keeps_three_real_classical_routes(self):
        s,p,r=fixture();routes,errors=classical_routes(s,r)
        self.assertFalse(errors);self.assertIsNone(routes['ml'])
        self.assertTrue(all(routes[k] for k in ('hops','delay','capacity')))
        self.assertTrue(all(routes[k]['costo_qos'] is None for k in ('hops','delay','capacity')))
    def test_shared_paths_reported_instead_of_forcing_difference(self):
        s,p,r=fixture()
        for e in s['topology_document']['topologies']['nsfnet']['links']:
            e.update(capacity_mbps=1,configured_delay_ms=1)
            for keys in TARGETS.values():p[e['link_id']]['predicciones'][keys[1]]=1
        w,sc=parameters();routes,_=compare_four(s,r,p,w,sc)
        self.assertEqual(len(route_groups(routes)),1)
        self.assertEqual(len(route_groups(routes)[0]['criterios']),4)
    def test_down_link_not_used_by_any_criterion(self):
        s,p,r=fixture();s['links_runtime'][0]['state']='down'
        w,sc=parameters();routes,_=compare_four(s,r,p,w,sc)
        self.assertTrue(all('s-t' not in v['edge_ids'] for v in routes.values() if v))
    def test_reverse_ml_uses_reverse_predictions(self):
        s,p,r=fixture()
        for lid in p:p[lid]['predicciones']['target_v_to_u_delay_avg_ms']=100
        p['s-t']['predicciones']['target_v_to_u_delay_avg_ms']=0
        r.origen,r.destino='t','s';w,sc=parameters();routes,_=compare_four(s,r,p,w,sc)
        self.assertEqual(routes['ml']['ruta'],['t','s'])

if __name__=='__main__':unittest.main()
