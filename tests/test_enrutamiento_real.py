"""Pruebas de forwarding y fallos con un switch OpenFlow simulado, sin VMs."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT
sys.path.insert(0, str(APP))
from backend.servicios.enrutamiento_real import RouteInstaller, canonical_match
from backend.api import sdn_enrutamiento_real as api
from fastapi import HTTPException
from pydantic import ValidationError


def fixture():
    # Puertos aportados por el usuario: ns1-eth3/ns3-eth2, ns3-eth4/ns6-eth2, ns6-eth5/ns14-eth2.
    nodes = [{'switch': 's' + str(i), 'runtime_switch': 'ns' + str(i), 'host': 'nsh' + str(i),
              'dpid': '{:016x}'.format(i), 'host_ip': '10.0.0.{}/24'.format(i), 'host_port': 1} for i in (1, 3, 6, 14)]
    links = [dict(link_id='s{}-s{}'.format(a, b), switch_u='s'+str(a), switch_v='s'+str(b),
                  port_u=p, port_v=q, capacity_mbps=4.5, configured_delay_ms=5) for a, b, p, q in ((1, 3, 3, 2), (3, 6, 4, 2), (6, 14, 5, 2))]
    return dict(ready=True, topologia='nsfnet', session_id='console1', topology_instance_id='instance1', graph_version='graph1',
                selection_revision=1, source_url='http://192.168.56.107:8769', ryu={'rest_url': 'http://192.168.56.108:18081'},
                topology_document={'topologies': {'nsfnet': {'nodes': nodes, 'links': links}}},
                links_runtime=[{'id': e['link_id'], 'state': 'up'} for e in links])


class FakeRYU:
    def __init__(self):
        self.snapshot = fixture()
        self.entries = {i: [{'cookie': 1396985422, 'priority': 100, 'table_id': 0, 'match': {'dl_dst': '00:00:00:00:00:0e'},
                             'actions': ['OUTPUT:4'], 'packet_count': 99, 'byte_count': 9900}] for i in (1, 3, 6, 14)}
        self.posts, self.adds = [], 0
        self.fail_add, self.fail_delete, self.wrong_output, self.wrong_interface = None, False, False, False

    def __call__(self, rest):
        if rest != self.snapshot['ryu']['rest_url']:
            raise AssertionError('Otro controlador')
        return self

    def request(self, path, body=None):
        if body is None:
            dpid = int(path.split('/')[-1])
            if '/portdesc/' in path:
                ports = {1}
                for e in self.snapshot['topology_document']['topologies']['nsfnet']['links']:
                    if e['switch_u'] == 's'+str(dpid):
                        ports.add(e['port_u'])
                    if e['switch_v'] == 's'+str(dpid):
                        ports.add(e['port_v'])
                return {str(dpid): [dict(port_no=p, name=('nc' if self.wrong_interface else 'ns')+str(dpid)+'-eth'+str(p), state=0, config=0) for p in ports]}
            return {str(dpid): copy.deepcopy(self.entries[dpid])}
        self.posts.append((path, copy.deepcopy(body)))
        if path.endswith('/add'):
            self.adds += 1
            entry = copy.deepcopy(body)
            port = entry['actions'][0]['port']
            entry.update(actions=['OUTPUT:'+str(port+1 if self.wrong_output else port)], packet_count=0, byte_count=0)
            self.entries[entry['dpid']].append(entry)
            if self.adds == self.fail_add:
                raise TimeoutError('Switch acepto el POST pero se perdio la respuesta')
        elif path.endswith('/delete_strict'):
            if self.fail_delete:
                raise TimeoutError('Retiro incierto')
            assert body['cookie_mask'] == 0xffffffffffffffff
            self.entries[body['dpid']] = [f for f in self.entries[body['dpid']] if not (
                f['cookie'] == body['cookie'] and f['priority'] == body['priority'] and f['table_id'] == body['table_id']
                and canonical_match(f['match']) == canonical_match(body['match']))]
        else:
            raise AssertionError('Operacion no permitida')

    def packet(self, source=1, destination=14, protocol=1):
        node, visited = source, []
        profile = self.snapshot['topology_document']['topologies']['nsfnet']
        for _ in range(10):
            candidates = [f for f in self.entries[node] if canonical_match(f['match']) == {
                'eth_type': 2048, 'ip_proto': protocol, 'ipv4_src': '10.0.0.{}/32'.format(source), 'ipv4_dst': '10.0.0.{}/32'.format(destination)}]
            if not candidates:
                return visited, False
            flow = max(candidates, key=lambda f: f['priority'])
            flow['packet_count'] += 1
            flow['byte_count'] += 98
            visited.append(node)
            port = int(flow['actions'][0].split(':')[1])
            if port == 1:
                return visited, node == destination
            next_node = None
            for e in profile['links']:
                if e['switch_u'] == 's'+str(node) and e['port_u'] == port:
                    next_node = int(e['switch_v'][1:])
                elif e['switch_v'] == 's'+str(node) and e['port_v'] == port:
                    next_node = int(e['switch_u'][1:])
            if next_node is None:
                return visited, False
            node = next_node
        return visited, False


class ForwardingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ryu, self.snap = FakeRYU(), fixture()
        self.path = Path(self.temp.name) / 'journal.json'
        self.manager = RouteInstaller(self.path, self.ryu)
        self.route = ['s1', 's3', 's6', 's14']

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, criterion='conventional'):
        return self.manager.prepare(self.snap, self.route, criterion, {'feature_end_epoch_s': time.time() - 2})

    def apply(self, plan=None, validate=lambda record: None):
        return self.manager.apply((plan or self.prepare())['plan_id'], self.snap, validate)

    def test_real_ports_no_posts_during_prepare_and_ping_walk(self):
        plan = self.prepare()
        self.assertEqual(self.ryu.posts, [])
        self.assertEqual([(r['runtime_switch'], r['output_port']) for r in plan['ports']],
                         [('ns1', 3), ('ns3', 4), ('ns6', 5), ('ns14', 1), ('ns14', 2), ('ns6', 2), ('ns3', 2), ('ns1', 1)])
        active = self.apply(plan)
        self.assertEqual(active['status'], 'aplicada')
        self.assertEqual([b['dpid'] for p, b in self.ryu.posts if p.endswith('/add')], [14, 6, 3, 1, 1, 3, 6, 14])
        self.assertEqual(self.ryu.packet(), ([1, 3, 6, 14], True))
        self.assertEqual(self.ryu.packet(14, 1), ([14, 6, 3, 1], True))
        self.assertEqual(self.ryu.packet(protocol=17), ([], False))
        for _, body in self.ryu.posts:
            self.assertEqual(body['match']['nw_proto'], 1)
            self.assertEqual(body['match']['dl_type'], 2048)
            self.assertEqual(body['hard_timeout'], 0)

    def test_evidence_needs_both_directions_and_every_hop(self):
        self.apply()
        self.manager.evidence(self.snap, reset=True)
        self.ryu.packet()
        first = self.manager.evidence(self.snap)
        self.assertFalse(first['verification']['all_hops'])
        self.ryu.packet(14, 1)
        second = self.manager.evidence(self.snap)
        self.assertTrue(second['verification']['all_hops'])
        self.assertTrue(all(int(r['packets_delta']) == 1 for r in second['verification']['rows']))

    def test_lost_post_reply_rolls_back_only_our_cookie(self):
        before = copy.deepcopy(self.ryu.entries)
        self.ryu.fail_add = 3
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.ryu.entries, before)
        self.assertEqual(self.manager.data['pending'], {})

    def test_successful_http_with_wrong_output_is_not_applied(self):
        before = copy.deepcopy(self.ryu.entries)
        self.ryu.wrong_output = True
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.ryu.entries, before)

    def test_switching_models_retires_only_prior_managed_rules(self):
        first = self.apply()
        second = self.apply(self.prepare('xgboost'))
        self.assertGreater(second['priority'], first['priority'])
        for entries in self.ryu.entries.values():
            self.assertFalse(any(hex(f['cookie']) == first['cookie_hex'] for f in entries))
            self.assertTrue(any(f['priority'] == 100 for f in entries))
        self.assertTrue(self.ryu.packet()[1])

    def test_second_prepared_plan_is_invalid_after_another_apply(self):
        first, second = self.prepare(), self.prepare()
        self.apply(first)
        count = len(self.ryu.posts)
        with self.assertRaises(ValueError):
            self.apply(second)
        self.assertEqual(len(self.ryu.posts), count)

    def test_failed_replacement_keeps_old_applied_route(self):
        first = self.apply()
        prior = copy.deepcopy(self.ryu.entries)
        self.ryu.fail_add = self.ryu.adds + 3
        with self.assertRaises(ValueError):
            self.apply(self.prepare('xgboost'))
        self.assertEqual(self.ryu.entries, prior)
        self.assertEqual(self.manager.status(self.snap)['active']['plan_id'], first['plan_id'])

    def test_pending_cleanup_survives_restart_and_can_be_removed(self):
        self.ryu.fail_add, self.ryu.fail_delete = 2, True
        with self.assertRaises(ValueError):
            self.apply()
        reloaded = RouteInstaller(self.path, self.ryu)
        self.assertEqual(reloaded.status(self.snap)['status'], 'limpieza_pendiente')
        with self.assertRaises(ValueError):
            reloaded.prepare(self.snap, self.route, 'conventional')
        self.ryu.fail_delete = False
        reloaded.remove(self.snap, lambda *args, **kwargs: None)
        self.assertEqual(reloaded.data['pending'], {})
        self.assertTrue(all(len(f) == 1 for f in self.ryu.entries.values()))

    def test_remove_restores_baseline_and_keeps_foreign_flows(self):
        before = copy.deepcopy(self.ryu.entries)
        self.apply()
        self.manager.remove(self.snap, lambda *args, **kwargs: None)
        self.assertEqual(self.ryu.entries, before)

    def test_recreated_graph_stale_model_and_wrong_interface_do_not_write(self):
        plan = self.prepare('xgboost')
        self.manager.plans[plan['plan_id']]['metadata']['feature_end_epoch_s'] = time.time() - 121
        with self.assertRaises(ValueError):
            self.apply(plan)
        plan = self.prepare()
        self.snap['graph_version'] = 'other'
        with self.assertRaises(ValueError):
            self.apply(plan)
        self.snap['graph_version'] = 'graph1'
        self.ryu.wrong_interface = True
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.ryu.posts, [])

    def test_mutation_of_network_after_writes_rolls_back(self):
        before = copy.deepcopy(self.ryu.entries)
        def changed(record):
            raise ValueError('Cambio la sesion')
        with self.assertRaises(ValueError):
            self.apply(validate=changed)
        self.assertEqual(self.ryu.entries, before)

    def test_idempotency_reload_and_removed_flow_not_reported_as_verified(self):
        active = self.apply()
        count = len(self.ryu.posts)
        self.manager.apply(active['plan_id'], self.snap, lambda r: None)
        self.assertEqual(len(self.ryu.posts), count)
        reloaded = RouteInstaller(self.path, self.ryu)
        self.assertEqual(reloaded.status(self.snap)['active']['status'], 'aplicada')
        self.ryu.entries[3] = self.ryu.entries[3][:1]
        self.assertEqual(reloaded.status(self.snap)['active']['status'], 'reglas_no_verificadas')

    def test_api_does_not_accept_arbitrary_urls_and_rejects_stale_expected_route(self):
        body = dict(topology_instance_id='instance1', graph_version='graph1', selection_revision=1,
                    origen='s1', destino='s14', criterio='conventional', ruta_esperada=['s1', 's14'])
        with self.assertRaises(ValidationError):
            api.Prepare(**body, rest_url='http://other')
        net = SimpleNamespace(lock=threading.RLock(), snapshot=lambda **kw: copy.deepcopy(self.snap),
                              sources={'nsfnet': {'ryu_rest_url': self.snap['ryu']['rest_url']}})
        with patch.object(api, 'network', return_value=net), patch.object(api, 'installer', self.manager):
            with self.assertRaises(HTTPException) as error:
                api.prepare(api.Prepare(**body))
            self.assertEqual(error.exception.status_code, 409)
            self.assertEqual(self.ryu.posts, [])
            body['ruta_esperada'] = self.route
            prepared = api.prepare(api.Prepare(**body))
            self.assertFalse(prepared['rules_installed'])

    def test_corrupt_journal_cannot_delete_baseline_rules(self):
        active = self.apply()
        key = self.manager.key(self.snap)
        record = self.manager.data['active'][key]
        record['cookie'] = 1396985422
        count = len(self.ryu.posts)
        with self.assertRaises(ValueError):
            self.manager.remove(self.snap, lambda *a, **kw: None)
        self.assertEqual(len(self.ryu.posts), count)
        self.assertTrue(all(any(f['priority'] == 100 for f in entries) for entries in self.ryu.entries.values()))

    def test_foreign_high_priority_does_not_get_overwritten(self):
        self.ryu.entries[1].append({'cookie': 123, 'priority': 40000, 'table_id': 0, 'match': {}, 'actions': []})
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.ryu.posts, [])

    def test_ml_selected_model_and_missing_forecasts_are_checked_before_plan(self):
        body = dict(topology_instance_id='instance1', graph_version='graph1', selection_revision=1,
                    origen='s1', destino='s14', criterio='xgboost', ruta_esperada=self.route, modelo_id_esperado='original')
        net = SimpleNamespace(lock=threading.RLock(), snapshot=lambda **kw: copy.deepcopy(self.snap),
                              sources={'nsfnet': {'ryu_rest_url': self.snap['ryu']['rest_url']}})
        with patch.object(api, 'network', return_value=net), patch.object(api, 'installer', self.manager), patch('backend.api.sdn_cinco_modelos.compare_models') as compare:
            compare.return_value = {'rutas': {'xgboost': {'ruta': self.route, 'modelo_id': 'other'}}}
            with self.assertRaises(HTTPException) as error:
                api.prepare(api.Prepare(**body))
            self.assertEqual(error.exception.status_code, 409)
            compare.return_value = {'rutas': {'xgboost': None}, 'ml': {'motivo': 'sin ventana'}}
            with self.assertRaises(HTTPException) as error:
                api.prepare(api.Prepare(**body))
            self.assertEqual(error.exception.status_code, 424)
        self.assertEqual(self.ryu.posts, [])


if __name__ == '__main__':
    unittest.main()
