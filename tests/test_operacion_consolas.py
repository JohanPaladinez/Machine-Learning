import ast
import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT
sys.path.insert(0, str(APP))
from backend.servicios.operacion_sdn import OperationalReader
from backend.servicios.fuentes_sdn import MultiNetwork
from backend.api import sdn_operacion as api
from fastapi import HTTPException


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launcher = load('console_launcher', 'consolas_mininet_v1/iniciar.py')
console = load('console_worker', 'consolas_mininet_v1/consola_sdn.py')


def snapshot():
    return {'ready': True, 'topology_instance_id': 'instance', 'graph_version': 'graph', 'topologia': 'nsfnet',
            'protocol_configured': 'OpenFlow 1.3', 'ryu': {'rest_url': 'http://127.0.0.1:18081'},
            'topology_document': {'topologies': {'nsfnet': {'nodes': [
                {'switch': 's1', 'runtime_switch': 'ns1', 'dpid': '0000000000000001', 'host_port': 2, 'host': 'nsh1'}],
                'links': [{'switch_u': 's1', 'switch_v': 's2', 'port_u': 1, 'port_v': 1}]}}}}


class OperationalTests(unittest.TestCase):
    def test_real_counter_semantics_resets_and_missing_values(self):
        count = [1000, 2000]
        duration = [10]
        requests = []
        def transport(url):
            requests.append(url)
            kind = url.split('/')[-2]
            if kind == 'desc':
                return {'1': {'mfr_desc': 'Nicira, Inc.', 'sw_desc': 'fixture OVS'}}
            if kind == 'portdesc':
                return {'1': [{'port_no': 1, 'name': 'ns1-eth1', 'state': 0, 'config': 0},
                              {'port_no': 2, 'name': 'ns1-eth2', 'state': 1, 'config': 0},
                              {'port_no': 'LOCAL', 'name': 'ns1'}]}
            return {'1': [{'port_no': 1, 'rx_bytes': count[0], 'tx_bytes': count[1], 'rx_packets': 10,
                'tx_packets': 20, 'rx_dropped': 2**64 - 1, 'tx_dropped': 2, 'rx_errors': 0,
                'tx_errors': 0, 'duration_sec': duration[0], 'duration_nsec': 0}]}
        reader = OperationalReader()
        clock = [0]
        with patch('backend.servicios.operacion_sdn.time.monotonic', side_effect=lambda: clock[0]):
            first = reader.read(SimpleNamespace(transport=transport), snapshot(), 's1')
            self.assertEqual(first['port_count'], 2)
            self.assertEqual(first['ports'][0]['tx_bits'], '16000')
            self.assertEqual(first['ports'][0]['peer'], 's2')
            self.assertIsNone(first['ports'][0]['counters']['rx_dropped'])
            self.assertEqual(first['ports'][1]['peer'], 'nsh1')
            self.assertEqual(first['ports'][1]['state'], 'down')
            self.assertIsNone(first['ports'][1]['tx_bits'])
            self.assertIsNone(first['openflow_negotiated'])
            self.assertIsNone(first['ports'][0]['rates']['tx_mbps'])
            count[:] = [2000, 4000]
            duration[0] = 20
            clock[0] = 10
            second = reader.read(SimpleNamespace(transport=transport), snapshot(), 's1')
            self.assertAlmostEqual(second['ports'][0]['rates']['tx_mbps'], .0016)
            count[:] = [2, 3]
            duration[0] = 1
            clock[0] = 20
            third = reader.read(SimpleNamespace(transport=transport), snapshot(), 's1')
            self.assertTrue(third['ports'][0]['counter_reset'])
            self.assertIsNone(third['ports'][0]['rates']['tx_mbps'])
            changed = snapshot()
            changed['topology_instance_id'] = 'other'
            clock[0] = 30
            fresh = reader.read(SimpleNamespace(transport=transport), changed, 's1')
            self.assertIsNone(fresh['ports'][0]['rates']['tx_mbps'])
        self.assertTrue(all('/stats/' in url and 'flowentry' not in url for url in requests))

    def test_description_failure_retains_port_data(self):
        def get(url):
            if '/desc/' in url:
                raise OSError('description unavailable')
            return {'1': []}
        result = OperationalReader().read(SimpleNamespace(transport=get), snapshot(), 's1')
        self.assertEqual(result['status'], 'partial')
        self.assertIsNone(result['description']['mfr_desc'])
        self.assertEqual(result['port_count'], 0)

    def test_same_dpid_with_wrong_interface_does_not_leak_other_network_counters(self):
        def get(url):
            if '/portdesc/' in url:
                return {'1': [{'port_no': 1, 'name': 'nc1-eth1', 'state': 0, 'config': 0}]}
            if '/desc/' in url:
                return {'1': {'mfr_desc': 'foreign'}}
            return {'1': [{'port_no': 1, 'rx_bytes': 10, 'tx_bytes': 20}]}
        result = OperationalReader().read(SimpleNamespace(transport=get), snapshot(), 's1')
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['ports'][0]['state'], 'unverified')
        self.assertIsNone(result['ports'][0]['tx_bits'])
        self.assertIsNone(result['description']['mfr_desc'])

    def test_old_session_cannot_query_other_switch(self):
        network = SimpleNamespace(lock=threading.RLock(), snapshot=lambda: snapshot())
        with patch.object(api.live_api, 'network', network), patch.object(api.reader, 'read') as reader:
            with self.assertRaises(HTTPException) as context:
                api.inspect_switch('s1', 'old-instance', 'graph')
            self.assertEqual(context.exception.status_code, 409)
            reader.assert_not_called()

    def test_allowlist_accepts_only_read_only_counter_queries(self):
        sources = {'nsfnet': {'observer_url': 'http://127.0.0.1:8769', 'ryu_rest_url': 'http://127.0.0.1:18081', 'openflow_port': 16654}}
        calls = []
        net = MultiNetwork(sources, transport=lambda url: calls.append(url) or {})
        for path in ('desc/1', 'port/1', 'portdesc/1'):
            net.read_source('http://127.0.0.1:18081/stats/' + path)
        for url in ('http://127.0.0.1:18081/stats/flowentry/add', 'http://127.0.0.2:18081/stats/port/1',
                    'http://127.0.0.1:18081/stats/port/../flow', 'http://127.0.0.1:18081/stats/port/1?x=2'):
            with self.assertRaises(ValueError):
                net.read_source(url)
        self.assertEqual(len(calls), 3)


class ConsoleTests(unittest.TestCase):
    def test_new_measures_have_correct_direction_and_preserve_ml_inputs(self):
        metrics = {'links': {'e1': {'ml': {'features': {str(k): k for k in range(60)}},
                                  'directions': {'u_to_v': {'sent': 100, 'received': 90}, 'v_to_u': {}}}}}
        before = copy.deepcopy(metrics['links']['e1']['ml'])
        def side(base):
            return dict(tx_mbps=base, tx_bytes_delta=base * 10, rx_bytes_delta=base * 20,
                tx_packets_delta=base * 2, rx_packets_delta=base * 3,
                tx_dropped_delta=1, rx_dropped_delta=2, tx_errors_delta=0, rx_errors_delta=0, qdisc_drops_delta=3)
        actual = {'sides': {0: {'u': side(1), 'v': side(2)}},
                  'probes': {('e1', 'u_to_v'): {'delay_min_ms': 1, 'delay_max_ms': 4}, ('e1', 'v_to_u'): {}}}
        result = console.enrich_metrics(metrics, actual, [{'link_id': 'e1', 'capacity_mbps': 5}])
        u, v = result['links']['e1']['directions'].values()
        self.assertEqual((u['tx_bits_delta'], u['rx_bits_delta']), (80, 320))
        self.assertEqual((v['tx_bits_delta'], v['rx_bits_delta']), (160, 160))
        self.assertEqual(u['residual_capacity_estimate_mbps'], 4)
        self.assertEqual(u['delay_min_ms'], 1)
        self.assertIsNone(v['delay_min_ms'])
        self.assertEqual(before, result['links']['e1']['ml'])
        self.assertEqual(u['sent'] - u['received'], 10)

    def test_source_is_owner_not_latest_unrelated_folder(self):
        with tempfile.TemporaryDirectory(dir=None) as temporary:
            project = Path(temporary)
            for index in range(2):
                folder = project / ('en_vivo_nsf_v1_' + str(index))
                folder.mkdir()
                cfg = dict(of_port=16654, rest_url='http://192.168.56.108:18081', ryu_ip='192.168.56.108',
                    features=list(range(60)), targets=list(range(6)), observer_file=str(folder / 'observer.py'),
                    topologies={'nsfnet': {'nodes': [1]}})
                import json
                (folder / 'config.json').write_text(json.dumps(cfg))
                (folder / 'estado.json').write_text(json.dumps({'pid': 100 + index}))
                for file in ('sdn_noche_comun.py', 'sdn_noche_capturar.py', 'sdn_noche_trafico.py', 'telemetria_nsf_v1.py', 'observer.py'):
                    (folder / file).write_text('# fixture')
            owner = project / 'en_vivo_nsf_v1_0'
            identity = ([str(owner / 'telemetria_nsf_v1.py'), str(owner)], '1234')
            with patch.object(launcher, 'process_identity', side_effect=lambda pid: identity if pid == 100 else None):
                (source, _), active = launcher.find_source(project, 'nsfnet')
            self.assertEqual(source, owner)
            self.assertEqual(active[2], 100)
            with patch.object(launcher, 'process_identity', return_value=identity):
                # El segundo PID no se atribuye al segundo folder: sus argumentos no coinciden.
                (source, _), _ = launcher.find_source(project, 'nsfnet')
                self.assertEqual(source, owner)

    def test_worker_is_compatible_with_ubuntu_python_and_has_no_global_cleanup(self):
        for file in ('iniciar.py', 'consola_sdn.py'):
            code = (ROOT / 'consolas_mininet_v1' / file).read_text(encoding='utf-8')
            ast.parse(code, feature_version=(3, 6))
            self.assertNotIn('del-br', code)
            self.assertNotIn('pkill', code)
            self.assertNotIn('killall', code)


if __name__ == '__main__':
    unittest.main()
