#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI de Mininet en primer plano y telemetria de la misma red en un hilo."""
import copy
import errno
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn


class ObserverServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    # Reutilizar TIME_WAIT no debe permitir dos observadores escuchando a la vez.
    allow_reuse_port = False


def bind_observer(address, handler):
    try:
        return ObserverServer(address, handler)
    except OSError as error:
        if error.errno != errno.EADDRINUSE:
            raise
        try:
            query = subprocess.run(['ss', '-H', '-ltnp', 'sport = :' + str(address[1])],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=3)
            detail = query.stdout.strip()[:1600] or 'No se encontro un listener en la consulta de ss.'
        except (OSError, subprocess.TimeoutExpired):
            detail = 'No se pudo consultar ss; revisar sudo ss -ltnp.'
        raise ValueError('No se pudo reservar el observador {}:{}; direccion en uso. '
                         'No se creo la red nueva ni se detuvo otro observador. Detalle: {}'.format(
                             address[0], address[1], detail)) from error


def close_observer(server, serving):
    if server is not None:
        # shutdown espera a serve_forever; no llamarlo si la creacion de Mininet fallo antes.
        if serving:
            server.shutdown()
        server.server_close()


def enrich_metrics(metrics, actual, links):
    for i, edge in enumerate(links):
        for direction, sender, receiver in (('u_to_v', 'u', 'v'), ('v_to_u', 'v', 'u')):
            value = metrics['links'][edge['link_id']]['directions'][direction]
            tx, rx = actual['sides'][i][sender], actual['sides'][i][receiver]
            value.update(tx_mbps=tx['tx_mbps'], tx_bits_delta=tx['tx_bytes_delta'] * 8,
                rx_bits_delta=rx['rx_bytes_delta'] * 8,
                tx_packets_delta=tx['tx_packets_delta'], rx_packets_delta=rx['rx_packets_delta'],
                tx_dropped_delta=tx['tx_dropped_delta'], rx_dropped_delta=rx['rx_dropped_delta'],
                tx_errors_delta=tx['tx_errors_delta'], rx_errors_delta=rx['rx_errors_delta'],
                qdisc_drops_delta=tx['qdisc_drops_delta'],
                residual_capacity_estimate_mbps=max(0.0, edge['capacity_mbps'] - tx['tx_mbps']))
            probes = actual['probes'][(edge['link_id'], direction)]
            value.update(delay_min_ms=probes.get('delay_min_ms'), delay_max_ms=probes.get('delay_max_ms'))
    return metrics


def run(folder, name):
    from mininet.cli import CLI
    from mininet.log import setLogLevel
    cfg = json.loads((folder / 'config.json').read_text(encoding='utf-8'))
    sys.path.insert(0, str(folder))
    worker_name = 'telemetria_geant_v1' if name == 'geant2' else 'telemetria_nsf_v1'
    worker = __import__(worker_name)
    common = __import__('sdn_noche_comun')
    # Guardar min/max de las sondas NUEVAS, sin cambiar las 60 entradas ni el modelo.
    summarize = common.resumen_sondas
    def with_extremes(offered, accepted, received, refused):
        result = summarize(offered, accepted, received, refused)
        result.update(delay_min_ms=min(received.values()) if received else None,
                      delay_max_ms=max(received.values()) if received else None)
        return result
    common.resumen_sondas = with_extremes
    spec = importlib.util.spec_from_file_location('observer_console', cfg['observer_file'])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    observer = module.Observer(cfg['project'])
    capture = worker.RecolectorVivo(str(folder))
    stop, lock, measure_lock = threading.Event(), threading.RLock(), threading.Lock()
    state = {'estado': 'creando_' + name, 'pid': os.getpid(), 'carpeta': str(folder),
             'ready': False, 'modo': 'consola_interactiva', 'topologia': name}
    stat = Path('/proc/self/stat').read_text()
    state['pid_start_ticks'] = stat[stat.rfind(')') + 2:].split()[19]
    shared = {'metrics': {'status': 'unavailable', 'links': {}}, 'profile': None, 'links': [],
              'command_revision': 0, 'last_command': None, 'command_active': False}
    log = (folder / 'telemetria.log').open('a', encoding='utf-8')
    server, thread, serving = None, None, False

    def publish(phase, **extra):
        with lock:
            state.update(estado=phase, actualizado_utc=common.iso(), **extra)
            common.guardar_json(str(folder / 'estado.json'), state)
            log.write(common.iso() + ' ' + phase + ' ' + json.dumps(extra, ensure_ascii=True) + '\n')
            log.flush()

    def hosts_runtime():
        # No usar Node.cmd mientras el usuario escribe comandos en esos mismos hosts.
        result = []
        for host in capture.net.hosts:
            interface = host.defaultIntf()
            node = next((n for n in shared['profile']['nodes'] if n['host'] == host.name), None)
            if node is None:
                continue
            peer = interface.link.intf2 if interface.link.intf1 is interface else interface.link.intf1
            switch_intf = observer.interface(peer.name)
            up = switch_intf.get('admin_up') and switch_intf.get('operstate') == 'up'
            result.append({'host': host.name, 'switch': node['switch'], 'interface': interface.name,
                'switch_interface': peer.name, 'port': node['host_port'],
                'ip': interface.ip, 'mac': interface.mac,
                'state': 'up' if up else 'down', 'status_scope': 'switch_access_interface'})
        return result

    def snapshot():
        with lock:
            metrics = copy.deepcopy(shared['metrics'])
            profile, links = shared['profile'], shared['links']
            phase = state['estado']
        network = observer.candidate(folder.name, name, profile, links,
            {'ip': cfg['ryu_ip'], 'of_port': cfg['of_port'], 'rest_url': cfg['rest_url']},
            capture={'state': phase, 'alive': not stop.is_set(), 'session_id': folder.name})
        networks = []
        if network:
            # Nombres reales, extraidos del objeto Mininet que usa esta misma CLI.
            for node in network['topology_document']['topologies'][name]['nodes']:
                runtime = next(s for s in capture.net.switches if s.dpid == node['dpid'])
                node['runtime_switch'] = runtime.name
                node['host'] = next(h.name for h in capture.net.hosts if h.IP() == node['host_ip'].split('/')[0])
            if metrics.get('window_end'):
                age = time.time() - common.fecha(metrics['window_end']).timestamp()
                metrics.update(age_s=round(age, 3), status='fresh' if 0 <= age <= 120 else 'stale')
            network.update(source_kind='instrumented', metrics=metrics, protocol_configured='OpenFlow 1.3',
                hosts_runtime=hosts_runtime(), console={'mode': 'foreground', 'prompt': 'mininet-' + name + '>',
                    'session_id': folder.name})
            networks.append(network)
        result = {'schema_version': 1, 'observer_version': 'sdn-vivo-1', 'observed_utc': common.iso(),
            'read_only': True, 'collector_generates_traffic': True, 'networks': networks, 'errors': [],
            'status': 'observed' if networks else 'inactive',
            'candidates': [{'session_id': n['session_id'], 'topologia': name} for n in networks]}
        if networks:
            result.update(networks[0])
        return result

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                if self.path == '/health':
                    result = {'status': 'ok', 'observer_version': 'sdn-vivo-1', 'read_only': True,
                              'console': True, 'topologia': name, 'session_id': folder.name}
                elif self.path == '/snapshot':
                    result = snapshot()
                else:
                    self.send_error(404)
                    return
                body = json.dumps(result, ensure_ascii=True, allow_nan=False).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                traceback.print_exc(file=log)
                self.send_error(503)
        def log_message(self, *args):
            pass

    def measure(profile, links, load):
        number, failures = 0, 0
        try:
            while not stop.is_set():
                number += 1
                with lock:
                    revision_before = shared['command_revision']
                    command_at_start = shared['command_active']
                try:
                    with measure_lock:
                        actual = capture.medir(profile, links, 20.0, number, load)
                    metrics = enrich_metrics(worker.construir_metricas(actual, links, folder.name, cfg['features']), actual, links)
                except common.SampleUnavailable as error:
                    failures += 1
                    with lock:
                        shared['metrics'] = {'status': 'unavailable', 'links': {}}
                    publish('ventana_descartada', ready=False, motivo=str(error), fallos=failures)
                    if failures >= 6:
                        raise ValueError('Seis ventanas invalidas; la consola se conserva para diagnostico. Escribe telemetria.')
                    stop.wait(1)
                    continue
                failures = 0
                with lock:
                    metrics['console_activity'] = {'commands_during_window': command_at_start or shared['command_active'] or shared['command_revision'] != revision_before,
                                                    'last_command': shared['last_command']}
                    shared['metrics'] = metrics
                common.guardar_json(str(folder / 'ventana_actual.json'), metrics)
                publish('telemetria_' + name, ready=True, ventana=number, enlaces_con_60_entradas=len(links), ultimo_fin=actual['end'])
        except Exception as error:
            with lock:
                shared['metrics'] = {'status': 'unavailable', 'links': {}}
            publish('error_telemetria', ready=False, error=str(error))
            traceback.print_exc(file=log)
            log.flush()

    class Console(CLI):
        prompt = 'mininet-' + name + '> '
        def precmd(self, line):
            with lock:
                shared['command_revision'] += 1
                shared['command_active'] = True
                shared['last_command'] = {'command': line.split()[0] if line.split() else '', 'utc': common.iso()}
            return line
        def postcmd(self, stop, line):
            with lock:
                shared['command_active'] = False
            return stop
        def do_telemetria(self, _line):
            """Mostrar estado y archivo de mediciones sin salir de Mininet."""
            with lock:
                current = copy.deepcopy(state)
            print(json.dumps(current, indent=2, ensure_ascii=True))
            print('Registro: ' + str(folder / 'telemetria.log'))
        def do_links(self, _line):
            """Listar enlaces del mismo objeto Mininet, tambien en versiones antiguas."""
            for link in self.mn.links:
                print(str(link) + ' ' + link.status())

    class CloseConsole(BaseException):
        pass
    def close_signal(*_):
        raise CloseConsole()

    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, close_signal)
    try:
        publish('reservando_observador')
        server = bind_observer(('192.168.56.107', 8768 if name == 'geant2' else 8769), Handler)
        publish('creando_' + name)
        profile, links, paths = capture.crear_red(name)
        # Ajustar la copia del perfil a los nombres reales; no alterar el archivo fuente.
        profile = copy.deepcopy(profile)
        prefix, host_prefix = ('nc', 'nh') if name == 'geant2' else ('ns', 'nsh')
        for n in profile['nodes']:
            n.update(runtime_switch=prefix + n['switch'][1:], host=host_prefix + n['switch'][1:])
        shared.update(profile=profile, links=links)
        seed = int(time.time() * 1000)
        while str(seed) in capture.semillas_usadas:
            seed += 1
        load, _ = capture.plan(profile, paths, 0, seed, baja=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        serving = True
        thread = threading.Thread(target=measure, args=(profile, links, load), daemon=True)
        publish('consola_disponible', ready=False)
        thread.start()
        setLogLevel('info')
        print('\nCONSOLA REAL ' + name.upper() + ' (la telemetria sigue midiendo esta misma red)')
        print('Comandos: nodes | links | net | ports | pingall | telemetria')
        print('exit cierra SOLO esta topologia. Mantener ambas terminales abiertas.')
        print('Sesion nueva: ' + folder.name)
        print('URL del observador: http://192.168.56.107:' + str(8768 if name == 'geant2' else 8769))
        Console(capture.net)
    except CloseConsole:
        pass
    finally:
        # Ignorar señales repetidas durante el cierre acotado de esta unica red.
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, signal.SIG_IGN)
        stop.set()
        print('\nCerrando solo {}. Esperando que termine la ventana de sondas...'.format(name), flush=True)
        if thread:
            thread.join()
        close_observer(server, serving)
        capture.cerrar_red()
        publish('detenido', ready=False)
        log.close()
