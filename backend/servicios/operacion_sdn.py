"""Inspeccion OFCTL de solo lectura, por switch y por instancia verificada."""
import concurrent.futures
from datetime import datetime, timezone
import threading
import time

COUNTERS = ('rx_bytes', 'tx_bytes', 'rx_packets', 'tx_packets',
            'rx_dropped', 'tx_dropped', 'rx_errors', 'tx_errors')


def counter(value):
    try:
        result = int(value)
        return result if not isinstance(value, bool) and 0 <= result < 2**64 - 1 else None
    except (ValueError, TypeError):
        return None


def port_number(value):
    try:
        return int(value, 0) if isinstance(value, str) and value.startswith('0x') else int(value)
    except (ValueError, TypeError):
        return None


class OperationalReader:
    def __init__(self):
        self.lock = threading.RLock()
        self.cache, self.previous = {}, {}

    def read(self, network, snapshot, switch):
        profile = snapshot['topology_document']['topologies'][snapshot['topologia']]
        node = next((n for n in profile['nodes'] if n['switch'] == switch), None)
        if node is None:
            raise ValueError('El switch no pertenece a esta red.')
        rest = snapshot['ryu']['rest_url']
        dpid = str(int(node['dpid'], 16))
        key = (rest, snapshot['topology_instance_id'], switch)
        with self.lock:
            now = time.monotonic()
            saved = self.cache.get(key)
            if saved and now - saved[0] < 5:
                return dict(saved[1], query_age_s=round(now - saved[0], 3))
            errors, replies = {}, {}
            # La falta de descripcion no invalida una topologia ya verificada.
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                pending = {kind: pool.submit(network.transport, rest + '/stats/' + kind + '/' + dpid)
                           for kind in ('desc', 'portdesc', 'port')}
                for kind, future in pending.items():
                    try:
                        payload = future.result()
                        if not isinstance(payload, dict) or dpid not in payload:
                            raise ValueError('RYU no devolvio datos para este DPID.')
                        replies[kind] = payload[dpid]
                    except Exception as error:
                        errors[kind] = str(error)
            sample_time = time.monotonic()
            description = replies.get('desc') or {}
            if isinstance(description, list):
                description = description[0] if description else {}
            if not isinstance(description, dict):
                description = {}
            stats = {port_number(p.get('port_no')): p for p in (replies.get('port') or [])
                     if isinstance(p, dict)}
            ports, local = [], None
            for item in (replies.get('portdesc') or []):
                number = port_number(item.get('port_no'))
                if item.get('port_no') == 'LOCAL' or number == 0xfffffffe:
                    local = item.get('name')
                    continue
                if number is None or not 1 <= number < 0xffffff00:
                    continue
                raw = stats.get(number, {})
                current = {c: counter(raw.get(c)) for c in COUNTERS}
                prior_key = key + (number,)
                prior = self.previous.get(prior_key)
                duration = (raw.get('duration_sec'), raw.get('duration_nsec'))
                try:
                    duration = float(duration[0]) + float(duration[1] or 0) / 1e9
                except (TypeError, ValueError):
                    duration = None
                elapsed, reset, rates = None, False, {'rx_mbps': None, 'tx_mbps': None}
                if prior:
                    elapsed = sample_time - prior[0]
                    reset = (duration is not None and prior[2] is not None and duration < prior[2]) or any(
                        current[c] is not None and prior[1][c] is not None and current[c] < prior[1][c]
                        for c in COUNTERS)
                    if not reset and elapsed > 0:
                        for direction in ('rx', 'tx'):
                            c = direction + '_bytes'
                            if current[c] is not None and prior[1][c] is not None:
                                rates[direction + '_mbps'] = (current[c] - prior[1][c]) * 8 / elapsed / 1e6
                if raw:
                    self.previous[prior_key] = (sample_time, current, duration)
                state, config = port_number(item.get('state')), port_number(item.get('config'))
                expected_name = '{}-eth{}'.format(node.get('runtime_switch', switch), number)
                identity = str(item.get('name', '')).rstrip('\x00') == expected_name
                if not identity:
                    errors['identity'] = 'Un puerto no coincide con la interfaz de esta sesion; se ocultan sus contadores.'
                    current = {c: None for c in COUNTERS}
                    rates = {'rx_mbps': None, 'tx_mbps': None}
                    self.previous.pop(prior_key, None)
                neighbor = next((e for e in profile['links'] if
                    (e['switch_u'] == switch and int(e['port_u']) == number) or
                    (e['switch_v'] == switch and int(e['port_v']) == number)), None)
                peer = node.get('host') if number == int(node['host_port']) else (
                    neighbor['switch_v'] if neighbor and neighbor['switch_u'] == switch else
                    neighbor['switch_u'] if neighbor else None)
                ports.append({'port_no': number, 'name': item.get('name'), 'mac': item.get('hw_addr'),
                    'peer': peer, 'identity_verified': identity,
                    'state': 'up' if identity and state is not None and config is not None and
                             not state & 3 and not config & 37 else 'down' if identity else 'unverified',
                    'state_bits': state, 'config_bits': config,
                    'counters': {c: None if v is None else str(v) for c, v in current.items()},
                    'rx_bits': None if current['rx_bytes'] is None else str(current['rx_bytes'] * 8),
                    'tx_bits': None if current['tx_bytes'] is None else str(current['tx_bytes'] * 8),
                    'duration_s': duration, 'rates': rates, 'rate_interval_s': elapsed,
                    'counter_reset': reset})
            result = {'status': 'partial' if errors else 'ok', 'switch': switch,
                'topology_instance_id': snapshot['topology_instance_id'], 'graph_version': snapshot['graph_version'],
                'source': 'RYU OFCTL REST: desc, portdesc, port (GET)', 'query_age_s': 0,
                'queried_utc': datetime.now(timezone.utc).isoformat(),
                'description': {k: description.get(k) if 'identity' not in errors else None for k in ('mfr_desc', 'hw_desc', 'sw_desc', 'serial_num', 'dp_desc')},
                'port_count': len(ports) if 'portdesc' not in errors else None,
                'local_port': local, 'ports': sorted(ports, key=lambda p: p['port_no']), 'errors': errors,
                'openflow_configured': snapshot.get('protocol_configured'),
                'openflow_negotiated': None,
                'note': 'Contadores acumulados del puerto; drops y errores no son la perdida de sondas. '
                        'Las tasas necesitan dos consultas de esta misma instancia. LOCAL no cuenta como puerto de datos.'}
            # Conservar memoria acotada y no reutilizar muestras de otra instancia.
            self.cache = {k: v for k, v in self.cache.items() if k[:2] == key[:2]}
            self.previous = {k: v for k, v in self.previous.items() if k[:2] == key[:2]}
            self.cache[key] = (sample_time, result)
            return result
