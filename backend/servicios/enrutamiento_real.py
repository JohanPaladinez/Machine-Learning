"""Forwarding ICMP explicito y reversible. Nunca borra flujos ajenos ni sondas."""
from collections import OrderedDict
import copy
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.request import Request, ProxyHandler, build_opener

from backend.servicios.sdn_vivo_runtime_v1 import private_url


def utc():
    return datetime.now(timezone.utc).isoformat()


def integer(value):
    if isinstance(value, bool):
        raise ValueError('Booleano en lugar de entero')
    return int(value, 16) if isinstance(value, str) and value.startswith('0x') else int(value)


def same_context(record, snapshot, selection=True, graph=True):
    return bool(snapshot.get('ready') and all(record.get(k) == snapshot.get(k) for k in (
        'topologia', 'session_id', 'topology_instance_id'))
        and record['rest_url'] == snapshot.get('ryu', {}).get('rest_url')
        and (not graph or record['graph_version'] == snapshot.get('graph_version'))
        and (not selection or record['selection_revision'] == snapshot.get('selection_revision')))


def compile_route(snapshot, path, cookie, priority):
    profile = snapshot['topology_document']['topologies'][snapshot['topologia']]
    nodes = {n['switch']: n for n in profile['nodes']}
    if len(path) < 2 or len(path) > 64 or len(set(path)) != len(path) or any(n not in nodes for n in path):
        raise ValueError('El camino no es simple o incluye nodos desconocidos.')
    if len({n['dpid'] for n in nodes.values()}) != len(nodes):
        raise ValueError('Hay DPID duplicados dentro de este controlador.')
    up = {e['id']: e for e in snapshot['links_runtime'] if e.get('state') == 'up'}
    ports = {}
    for a, b in zip(path, path[1:]):
        edges = [e for e in profile['links'] if {e['switch_u'], e['switch_v']} == {a, b}]
        if len(edges) != 1 or edges[0]['link_id'] not in up:
            raise ValueError('Falta un enlace activo y no ambiguo entre {} y {}.'.format(a, b))
        edge = edges[0]
        for source, destination in ((a, b), (b, a)):
            ports[(source, destination)] = int(edge['port_u'] if edge['switch_u'] == source else edge['port_v'])
    origin, destination = nodes[path[0]], nodes[path[-1]]
    ips = [str(ipaddress.IPv4Interface(n['host_ip']).ip) for n in (origin, destination)]
    if ips[0] == ips[1]:
        raise ValueError('Los dos hosts no pueden tener la misma IP.')
    rules, directions = [], []
    for direction, ordered, src, dst in (('ida', path, ips[0], ips[1]), ('regreso', list(reversed(path)), ips[1], ips[0])):
        forward = []
        for index, switch in enumerate(ordered):
            node = nodes[switch]
            port = int(node['host_port']) if index == len(ordered) - 1 else ports[(switch, ordered[index + 1])]
            if not 1 <= port < 0xffffff00:
                raise ValueError('Puerto fisico invalido.')
            runtime = node.get('runtime_switch', switch)
            forward.append({'switch': switch, 'runtime_switch': runtime, 'direction': direction,
                'expected_interface': '{}-eth{}'.format(runtime, port), 'output_port': port,
                'flow': {'dpid': int(node['dpid'], 16), 'cookie': cookie, 'table_id': 0,
                    'priority': priority, 'idle_timeout': 0, 'hard_timeout': 0,
                    'match': {'dl_type': 2048, 'nw_proto': 1, 'nw_src': src, 'nw_dst': dst},
                    'actions': [{'type': 'OUTPUT', 'port': port}]}})
        directions.extend(forward)
        # Primero destino y luego origen; el siguiente salto ya esta preparado.
        rules.extend(reversed(forward))
    return rules, directions, {'source_ip': ips[0], 'destination_ip': ips[1],
        'source_host': origin['host'], 'destination_host': destination['host'],
        'protocol': 'ICMP IPv4 (ip_proto=1)', 'return_path': list(reversed(path))}


def canonical_match(match):
    names = {'dl_type': 'eth_type', 'nw_proto': 'ip_proto', 'nw_src': 'ipv4_src', 'nw_dst': 'ipv4_dst'}
    result = {}
    for key, value in match.items():
        key = names.get(key, key)
        if key in ('ipv4_src', 'ipv4_dst'):
            network = ipaddress.ip_network(value, strict=False)
            result[key] = str(network)
        elif key in ('eth_type', 'ip_proto'):
            result[key] = integer(value)
        else:
            result[key] = value
    return result


def output_port(flow):
    actions = flow.get('actions', [])
    if len(actions) != 1:
        return None
    action = actions[0]
    if isinstance(action, dict) and action.get('type') == 'OUTPUT':
        return integer(action['port'])
    match = re.fullmatch(r'OUTPUT:([0-9]+)', str(action))
    return int(match.group(1)) if match else None


def assert_owned(record):
    cookie, priority = integer(record['cookie']), integer(record['priority'])
    if cookie >> 32 != 0x53444e52 or not 30000 <= priority < 31000:
        raise ValueError('El registro no identifica reglas creadas por esta aplicacion.')
    pair = {record['flow']['source_ip'], record['flow']['destination_ip']}
    if len(pair) != 2 or not record['rules']:
        raise ValueError('Registro de flujo incompleto.')
    for rule in record['rules']:
        flow = rule['flow']
        match = canonical_match(flow['match'])
        if (flow['cookie'] != cookie or flow['priority'] != priority or flow['table_id'] != 0 or
                set(match) != {'eth_type', 'ip_proto', 'ipv4_src', 'ipv4_dst'} or
                match['eth_type'] != 2048 or match['ip_proto'] != 1 or
                {match['ipv4_src'], match['ipv4_dst']} != {ip + '/32' for ip in pair} or
                output_port(flow) != rule['output_port']):
            raise ValueError('El registro intenta operar sobre reglas fuera del flujo ICMP autorizado.')


class RyuHTTP:
    def __init__(self, rest):
        self.rest = private_url(rest)
        self.deadline = time.monotonic() + 45

    def request(self, path, body=None):
        allowed = re.fullmatch(r'/stats/(?:flow|portdesc)/[0-9]+', path) if body is None else path in (
            '/stats/flowentry/add', '/stats/flowentry/delete_strict')
        if not allowed:
            raise ValueError('Operacion OpenFlow fuera del alcance permitido.')
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Se agoto el tiempo de la operacion OpenFlow.')
        request = Request(self.rest + path, data=None if body is None else json.dumps(body, allow_nan=False).encode(),
                          headers={'Content-Type': 'application/json'})
        with build_opener(ProxyHandler({})).open(request, timeout=min(3, remaining)) as response:
            data = response.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024:
            raise ValueError('Respuesta RYU demasiado grande.')
        return json.loads(data) if data.strip() else None


class RouteInstaller:
    def __init__(self, journal, client_factory=RyuHTTP):
        self.lock, self.plans = threading.RLock(), OrderedDict()
        self.journal, self.client_factory = Path(journal), client_factory
        self.data = {'schema_version': 1, 'active': {}, 'pending': {}, 'residuals': {}}
        self.load_error = None
        if self.journal.exists():
            try:
                if self.journal.stat().st_size > 4 * 1024 * 1024:
                    raise ValueError('Registro demasiado grande')
                value = json.loads(self.journal.read_text(encoding='utf-8'))
                if value.get('schema_version') != 1 or not all(isinstance(value.get(k), dict) for k in ('active', 'pending', 'residuals')):
                    raise ValueError('Registro no compatible')
                self.data = value
            except (OSError, ValueError) as error:
                self.load_error = str(error)

    def save(self):
        if self.load_error:
            raise ValueError('El registro de rutas necesita revision: ' + self.load_error)
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.journal.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(self.data, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.journal)

    @staticmethod
    def key(snapshot):
        return hashlib.sha256(json.dumps([snapshot['ryu']['rest_url'], snapshot['topology_instance_id']]).encode()).hexdigest()[:24]

    def prepare(self, snapshot, path, criterion, metadata=None):
        with self.lock:
            if self.load_error or not snapshot.get('ready'):
                raise ValueError('La red o el registro de rutas no esta disponible.')
            key = self.key(snapshot)
            if key in self.data['pending'] or self.data['residuals'].get(key):
                raise ValueError('Hay una limpieza pendiente. Retira las reglas de esta aplicacion antes de aplicar otra ruta.')
            prior = self.data['active'].get(key)
            if prior and prior.get('status') not in ('aplicada', 'trafico_verificado'):
                raise ValueError('La ruta anterior requiere retiro antes de continuar.')
            priority = int(prior['priority']) + 1 if prior else 30000
            if priority >= 31000:
                raise ValueError('Retira la ruta actual antes de iniciar una nueva serie de cambios.')
            token = secrets.token_urlsafe(24)
            cookie = (0x53444e52 << 32) | secrets.randbits(32)
            rules, display, flow = compile_route(snapshot, path, cookie, priority)
            plan = {k: copy.deepcopy(snapshot[k]) for k in ('topologia', 'session_id', 'topology_instance_id', 'graph_version', 'selection_revision')}
            plan.update(plan_id=token, rest_url=snapshot['ryu']['rest_url'], route=list(path), criterio=criterion,
                rules=rules, display=display, flow=flow, cookie=cookie, cookie_hex=hex(cookie), priority=priority,
                prepared_monotonic=time.monotonic(), creado_utc=utc(), metadata=metadata or {},
                parent_id=prior['plan_id'] if prior else None, status='preparada', key=key)
            self.plans[token] = plan
            while len(self.plans) > 32:
                self.plans.popitem(last=False)
            return self.public(plan)

    @staticmethod
    def public(record):
        if record is None:
            return None
        fields = ('plan_id', 'topologia', 'session_id', 'topology_instance_id', 'graph_version', 'selection_revision',
            'rest_url', 'route', 'criterio', 'flow', 'cookie_hex', 'priority', 'creado_utc', 'aplicado_utc',
            'status', 'metadata', 'baseline_utc', 'verification', 'warning')
        result = {k: copy.deepcopy(record[k]) for k in fields if k in record}
        result['ports'] = [{k: rule[k] for k in ('switch', 'runtime_switch', 'direction', 'output_port', 'expected_interface')}
                           for rule in record['display']]
        result['ping_command'] = '{} ping -c 3 {}'.format(record['flow']['source_host'], record['flow']['destination_host'])
        result['scope'] = 'Solo ICMP IPv4 entre las dos IP, ida y regreso por el mismo recorrido invertido. UDP, ARP y sondas no cambian.'
        return result

    def status(self, snapshot):
        with self.lock:
            if not snapshot.get('ready'):
                return {'status': 'red_no_verificada', 'active': None, 'pending': None, 'error': self.load_error}
            key = self.key(snapshot)
            active = self.public(self.data['active'].get(key))
            if active and not same_context(self.data['active'][key], snapshot, selection=False):
                active['status'] = 'grafo_cambiado'
            elif active:
                try:
                    current = self.readback(self.client_factory(active['rest_url']), self.data['active'][key])
                    previous = self.data['active'][key].get('verification', {}).get('rows') or self.data['active'][key].get('baseline', [])
                    if len(current) != len(previous) or any(a['packets'] < int(b['packets']) for a, b in zip(current, previous)):
                        active.update(status='contadores_reiniciados', warning='Inicia una evidencia nueva: los contadores cambiaron de base.')
                    active['rules_checked_utc'] = utc()
                except Exception as error:
                    active.update(status='reglas_no_verificadas', warning=str(error))
            return {'status': 'limpieza_pendiente' if key in self.data['pending'] or self.data['residuals'].get(key) else 'ok',
                    'active': active, 'pending': self.public(self.data['pending'].get(key)), 'error': self.load_error}

    def flows(self, client, rules):
        result = {}
        for dpid in sorted({r['flow']['dpid'] for r in rules}):
            payload = client.request('/stats/flow/' + str(dpid))
            if not isinstance(payload, dict) or not isinstance(payload.get(str(dpid)), list):
                raise ValueError('RYU no devolvio las reglas del DPID ' + str(dpid))
            result[dpid] = payload[str(dpid)]
        return result

    def readback(self, client, record):
        assert_owned(record)
        flows = self.flows(client, record['rules'])
        result = []
        for rule in record['display']:
            expected = rule['flow']
            matches = [f for f in flows[expected['dpid']] if integer(f.get('cookie', -1)) == expected['cookie']
                       and integer(f.get('priority', -1)) == expected['priority']
                       and integer(f.get('table_id', 0)) == 0
                       and canonical_match(f.get('match', {})) == canonical_match(expected['match'])]
            if len(matches) != 1 or output_port(matches[0]) != rule['output_port']:
                raise ValueError('Falta o cambio la regla {} de {}.'.format(rule['direction'], rule['runtime_switch']))
            count = integer(matches[0].get('packet_count', -1))
            byte_count = integer(matches[0].get('byte_count', -1))
            if not 0 <= count < 2**64 - 1 or not 0 <= byte_count < 2**64 - 1:
                raise ValueError('El switch no publica contadores verificables.')
            result.append({'switch': rule['runtime_switch'], 'direction': rule['direction'],
                'output_port': rule['output_port'], 'packets': count, 'bytes': byte_count})
        return result

    def preflight(self, client, plan, prior):
        flows = self.flows(client, plan['rules'])
        old_cookie = prior['cookie'] if prior else None
        for entries in flows.values():
            if any(integer(f.get('cookie', 0)) == plan['cookie'] for f in entries):
                raise ValueError('La cookie de este plan ya existe. Prepara otro plan; no se sobrescribe.')
            if any(integer(f.get('priority', 0)) >= plan['priority'] and integer(f.get('cookie', 0)) != old_cookie for f in entries):
                raise ValueError('Otra regla de prioridad alta podria ocultar el recorrido. Se conserva y no se instala esta ruta.')
        for dpid in flows:
            payload = client.request('/stats/portdesc/' + str(dpid))
            if not isinstance(payload, dict) or not isinstance(payload.get(str(dpid)), list):
                raise ValueError('Falta la descripcion de puertos de RYU.')
            ports = {}
            for entry in payload[str(dpid)]:
                try:
                    ports[integer(entry['port_no'])] = entry
                except (ValueError, TypeError, KeyError):
                    continue
            for rule in plan['rules']:
                if rule['flow']['dpid'] != dpid:
                    continue
                port = ports.get(rule['output_port'])
                if not port or str(port.get('name', '')).rstrip('\x00') != rule['expected_interface'] or (
                        integer(port.get('state', 1)) & 3 or integer(port.get('config', 1)) & 37):
                    raise ValueError('Puerto no verificado/activo: ' + rule['expected_interface'])

    def delete(self, client, record):
        assert_owned(record)
        errors = []
        for rule in reversed(record['rules']):
            flow = rule['flow']
            body = {k: flow[k] for k in ('dpid', 'cookie', 'table_id', 'priority', 'match')}
            body['cookie_mask'] = 0xffffffffffffffff
            try:
                client.request('/stats/flowentry/delete_strict', body)
            except Exception as error:
                errors.append(str(error))
        # Una respuesta de POST no prueba que el switch retiro la regla.
        for attempt in range(3):
            try:
                flows = self.flows(client, record['rules'])
                if not any(integer(f.get('cookie', 0)) == record['cookie'] for entries in flows.values() for f in entries):
                    return
            except Exception as error:
                errors.append(str(error))
            time.sleep(0.15)
        raise ValueError('No se pudo confirmar el retiro completo de las reglas propias. ' + '; '.join(errors[-2:]))

    def apply(self, token, snapshot, validate):
        with self.lock:
            key = self.key(snapshot)
            current = self.data['active'].get(key)
            if current and current['plan_id'] == token:
                if not same_context(current, snapshot):
                    raise ValueError('La ruta registrada pertenece a otro contexto de red.')
                self.readback(self.client_factory(current['rest_url']), current)
                return self.public(current)
            plan = self.plans.get(token)
            if not plan or time.monotonic() - plan['prepared_monotonic'] > 90 or not same_context(plan, snapshot):
                raise ValueError('El plan caduco o cambio la red. Prepara de nuevo la ruta.')
            if self.data['pending'].get(key) or self.data['residuals'].get(key):
                raise ValueError('Primero retira las reglas pendientes de esta aplicacion.')
            if plan['parent_id'] != (current['plan_id'] if current else None):
                raise ValueError('Otra operacion cambio la ruta aplicada. Prepara un plan nuevo.')
            end = plan['metadata'].get('feature_end_epoch_s')
            if plan['criterio'] != 'conventional' and (end is None or not -5 <= time.time() - end <= 120):
                raise ValueError('La entrada ML ya no es reciente. Vuelve a preparar la ruta.')
            client = self.client_factory(plan['rest_url'])
            self.preflight(client, plan, current)
            record = copy.deepcopy(plan)
            record['status'] = 'instalando'
            self.data['pending'][key] = record
            self.save()  # Intento registrado ANTES de cualquier POST, incluidos los de respuesta incierta.
            try:
                for rule in record['rules']:
                    client.request('/stats/flowentry/add', rule['flow'])
                validate(record)
                for attempt in range(3):
                    try:
                        counters = self.readback(client, record)
                        break
                    except ValueError:
                        if attempt == 2:
                            raise
                        time.sleep(0.15)
            except Exception as error:
                client.deadline = time.monotonic() + 30
                try:
                    self.delete(client, record)
                    self.data['pending'].pop(key, None)
                except Exception as rollback:
                    record.update(status='retiro_pendiente', warning=str(rollback))
                self.save()
                raise ValueError('No se confirmo la aplicacion: {}. Revisa el estado antes de reintentar.'.format(error)) from error
            record.update(status='aplicada', aplicado_utc=utc(), baseline=counters, baseline_utc=utc())
            self.data['active'][key] = record
            self.data['pending'].pop(key, None)
            if current:
                self.data['residuals'][key] = [current]
            self.save()  # La nueva ruta esta verificada; conservar la anterior hasta retirarla estrictamente.
            if current:
                client.deadline = time.monotonic() + 30
                try:
                    self.delete(client, current)
                    self.data['residuals'].pop(key, None)
                except Exception as error:
                    record['warning'] = 'Ruta nueva aplicada; quedan reglas propias anteriores de menor prioridad: ' + str(error)
                self.save()
            return self.public(record)

    def evidence(self, snapshot, reset=False):
        with self.lock:
            key = self.key(snapshot)
            record = self.data['active'].get(key)
            if not record or not same_context(record, snapshot, selection=False):
                raise ValueError('No hay una ruta aplicada de esta sesion y grafo para verificar.')
            counters = self.readback(self.client_factory(record['rest_url']), record)
            if reset:
                record.update(baseline=counters, baseline_utc=utc(), status='aplicada')
                record.pop('verification', None)
            else:
                rows = []
                for before, after in zip(record['baseline'], counters):
                    delta = after['packets'] - before['packets']
                    if delta < 0 or after['bytes'] < before['bytes']:
                        raise ValueError('Se reiniciaron contadores. Inicia una evidencia nueva.')
                    rows.append(dict(after, packets_before=str(before['packets']), packets_after=str(after['packets']),
                                     packets_delta=str(delta), bytes_delta=str(after['bytes'] - before['bytes'])))
                verified = all(int(row['packets_delta']) > 0 for row in rows)
                record.update(status='trafico_verificado' if verified else 'aplicada',
                    verification={'utc': utc(), 'all_hops': verified, 'rows': rows,
                        'note': 'Contadores del flujo ICMP en todos los saltos y ambos sentidos; no es una comparacion de rendimiento ni identifica quien genero ese ICMP.'})
            self.save()
            return self.public(record)

    def remove(self, snapshot, validate):
        with self.lock:
            key = self.key(snapshot)
            records = [r for r in (self.data['pending'].get(key), self.data['active'].get(key)) if r]
            records += self.data['residuals'].get(key, [])
            for record in records:
                if not same_context(record, snapshot, selection=False, graph=False):
                    raise ValueError('La identidad de la sesion cambio; no se envian borrados a otro laboratorio.')
                validate(record, graph=False)
            if records:
                client = self.client_factory(records[0]['rest_url'])
                client.deadline = time.monotonic() + 45
                for record in records:
                    try:
                        self.delete(client, record)
                    except Exception as error:
                        record.update(status='retiro_pendiente', warning=str(error))
                        self.save()
                        raise
                self.data['active'].pop(key, None)
                self.data['pending'].pop(key, None)
                self.data['residuals'].pop(key, None)
                self.save()
            return {'status': 'retirada', 'message': 'Retiro confirmado de las reglas de esta aplicacion. Las reglas previas de arranque se conservaron.'}
