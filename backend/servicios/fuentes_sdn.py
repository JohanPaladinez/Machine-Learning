"""Fuentes permitidas y seleccion estable; no inicia ni detiene redes."""
import os
import hashlib
import json
from urllib.parse import urlsplit
from backend.servicios.sdn_vivo_runtime_v1 import LiveNetwork, fetch_json, private_url


def configured_sources():
    result = {}
    for name, observer, rest, port in [('nsfnet', 8769, 18081, 16654), ('geant2', 8768, 18080, 16653)]:
        prefix = 'SDN_' + name.upper()
        result[name] = {
            'observer_url': private_url(os.getenv(prefix + '_OBSERVER_URL', f'http://192.168.56.103:{observer}')),
            'ryu_rest_url': private_url(os.getenv(prefix + '_RYU_REST_URL', f'http://192.168.56.108:{rest}')),
            'openflow_port': int(os.getenv(prefix + '_OPENFLOW_PORT', str(port))),
        }
        if not 1 <= result[name]['openflow_port'] <= 65535:
            raise ValueError('Puerto OpenFlow invalido')
    return result


class MultiNetwork(LiveNetwork):
    def __init__(self, sources=None, transport=fetch_json):
        self.sources = sources or configured_sources()
        self.fetch = transport
        self.selected_topologia, self.selected_session_id = 'auto', ''
        self.auto_name = 'nsfnet'
        self.selection_revision = 0
        self.choices, self.source_status, self.documents = [], {}, {}
        # La configuracion heredada se admite solo si pertenece a la lista permitida.
        super().__init__(transport=self.read_source)
        if not self.source_url:
            self.source_url = self.sources[self.auto_name]['observer_url']

    def select_topology(self, name, session_id=''):
        if name not in ('auto', *self.sources):
            raise ValueError('Topologia no admitida')
        with self.lock:
            if name == 'auto' and self.selected_topologia != 'auto':
                self.auto_name = self.selected_topologia
            self.selected_topologia = name
            self.selected_session_id = '' if name == 'auto' else session_id
            self.selection_revision += 1
            self.source_url = self.sources[self.auto_name if name == 'auto' else name]['observer_url']
            self.ryu_override = ''
            self.cached, self.cached_at = None, 0
            self.ports_cache.clear()
            return {'selected_topologia': name, 'selected_session_id': self.selected_session_id,
                    'selection_revision': self.selection_revision, 'source_url': self.source_url}

    def configure(self, source, ryu_override=''):
        source = private_url(source)
        for name, conf in self.sources.items():
            if source == conf['observer_url']:
                if ryu_override and private_url(ryu_override) != conf['ryu_rest_url']:
                    raise ValueError('El REST no pertenece a la fuente configurada')
                return self.select_topology(name)
        raise ValueError('Fuente no permitida. Usa NSFNET o GEANT2; configura otras fuentes en el servidor.')

    def _discover(self):
        self.documents, self.choices, self.source_status = {}, [], {}
        for name, conf in self.sources.items():
            try:
                data = self.fetch(conf['observer_url'] + '/snapshot')
                if data.get('schema_version') != 1 or data.get('observer_version') != 'sdn-vivo-1' or not isinstance(data.get('networks'), list):
                    raise ValueError('Contrato de observador no compatible')
                self.documents[name] = data
                matches = [n for n in data['networks'] if n.get('topologia') == name
                           and n.get('capture', {}).get('alive') is not False]
                self.source_status[name] = 'observable' if matches else 'inactive'
                for n in matches:
                    profile = n['topology_document']['topologies'][name]
                    self.choices.append({'topologia': name, 'session_id': n['session_id'],
                        'node_count': len(profile['nodes']), 'link_count': len(profile['links']),
                        'of_port': conf['openflow_port']})
            except (OSError, ValueError, KeyError, TypeError) as error:
                self.source_status[name] = 'unavailable'
                self.documents[name] = {'error': str(error)}

    def read_source(self, url):
        if not url.endswith('/snapshot'):
            name = self.auto_name if self.selected_topologia == 'auto' else self.selected_topologia
            base = self.sources[name]['ryu_rest_url']
            suffix = url.removeprefix(base)
            if not (url.startswith(base + '/stats/') and
                    (suffix == '/stats/switches' or suffix.startswith('/stats/portdesc/'))):
                raise ValueError('Consulta fuera del controlador configurado')
            return self.fetch(url)
        name = self.auto_name if self.selected_topologia == 'auto' else self.selected_topologia
        data = self.documents[name]
        if 'error' in data:
            raise ValueError(data['error'])
        matches = [n for n in data['networks'] if n.get('topologia') == name
                   and n.get('capture', {}).get('alive') is not False]
        if self.selected_session_id:
            matches = [n for n in matches if n.get('session_id') == self.selected_session_id]
        result = {key: data[key] for key in ('schema_version','observer_version','observed_utc','read_only','errors') if key in data}
        if len(matches) != 1:
            result.update(status='ambiguous' if matches else 'inactive',
                          message='Selecciona una sesion activa.' if matches else 'La topologia seleccionada no esta disponible.')
            return result
        network = matches[0]
        controller = network.get('controller', {})
        conf = self.sources[name]
        if (controller.get('rest_url') != conf['ryu_rest_url'] or
                controller.get('ip') != urlsplit(conf['ryu_rest_url']).hostname or
                controller.get('of_port', controller.get('port')) != conf['openflow_port']):
            result.update(status='controller_mismatch', message='El controlador publicado no corresponde a esta fuente.')
            return result
        result.update(network, status='observed')
        return result

    def _snapshot(self, now, force=False):
        self._discover()
        if self.selected_topologia == 'auto':
            available = {n['topologia'] for n in self.choices}
            if self.auto_name not in available:
                # Prioridad fija solo al perder disponibilidad: NSFNET, despues GEANT2.
                self.auto_name = next((n for n in ('nsfnet','geant2') if n in available), self.auto_name)
        name = self.auto_name if self.selected_topologia == 'auto' else self.selected_topologia
        self.source_url = self.sources[name]['observer_url']
        result = super()._snapshot(now, force)
        if result.get('ready'):
            # Tambien invalida rutas al cambiar capacidades, extremos o puertos del perfil.
            profile = result['topology_document']['topologies'][name]
            payload = [result['graph_version'], profile, result.get('session_id')]
            result['graph_version'] = hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:24]
        result.update(network_choices=self.choices, source_status=self.source_status,
                      selected_topologia=self.selected_topologia, selected_session_id=self.selected_session_id,
                      selection_revision=self.selection_revision, resolved_topologia=name,
                      auto_policy='Conserva la seleccion; al perder la sesion: NSFNET, despues GEANT2.')
        return result
