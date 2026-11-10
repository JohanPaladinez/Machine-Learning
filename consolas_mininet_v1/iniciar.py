#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Transicion acotada de una sesion instrumentada a una consola real Mininet."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from urllib.request import ProxyHandler, build_opener

WORKERS = {'geant2': 'telemetria_geant_v1.py', 'nsfnet': 'telemetria_nsf_v1.py'}
PORTS = {'geant2': (16653, 18080, 8768), 'nsfnet': (16654, 18081, 8769)}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def get_json(url):
    with build_opener(ProxyHandler({})).open(url, timeout=5) as response:
        return json.load(response)


def process_identity(pid, proc=Path('/proc')):
    try:
        folder = proc / str(int(pid))
        stat = (folder / 'stat').read_text()
        return ((folder / 'cmdline').read_bytes().decode().strip('\0').split('\0'),
                stat[stat.rfind(')') + 2:].split()[19])
    except (OSError, ValueError, IndexError, UnicodeError):
        return None


def config_valid(cfg, name):
    ofp, rest, _ = PORTS[name]
    return (cfg.get('of_port') == ofp and cfg.get('rest_url') == 'http://192.168.56.108:' + str(rest)
            and cfg.get('ryu_ip') == '192.168.56.108' and len(cfg.get('features', [])) == 60
            and len(cfg.get('targets', [])) == 6 and cfg.get('topologies', {}).get(name, {}).get('nodes'))


def find_source(project, name, explicit=None):
    choices, active = [], []
    folders = [Path(explicit).expanduser().resolve()] if explicit else list(project.glob('en_vivo_*')) + list(project.glob('consola_*'))
    for folder in folders:
        if folder.parent != project:
            continue
        try:
            cfg = read_json(folder / 'config.json')
            if not config_valid(cfg, name) or not (folder / WORKERS[name]).is_file():
                continue
            for file in ('sdn_noche_comun.py', 'sdn_noche_capturar.py', 'sdn_noche_trafico.py', WORKERS[name]):
                compile((folder / file).read_text(encoding='utf-8'), file, 'exec')
            if not Path(cfg['observer_file']).is_file():
                continue
            state = read_json(folder / 'estado.json') if (folder / 'estado.json').exists() else {}
            identity = process_identity(state.get('pid'))
            worker = str(folder / WORKERS[name])
            console_owner = bool(identity and state.get('modo') == 'consola_interactiva' and
                state.get('pid_start_ticks') == identity[1] and
                str(project / 'consolas_mininet_v1' / 'iniciar.py') in identity[0] and name in identity[0])
            if identity and ((str(folder) in identity[0] and worker in identity[0]) or console_owner):
                active.append((folder, cfg, state['pid'], identity))
            choices.append((folder, cfg))
        except (OSError, ValueError, KeyError, SyntaxError, TypeError):
            continue
    if len(active) > 1:
        raise ValueError('Hay varias sesiones propietarias de esta red; no se detiene ninguna: ' + ', '.join(str(a[0]) for a in active))
    if active:
        if any(Path(a).name == 'iniciar.py' for a in active[0][3][0]):
            raise ValueError('Esta red ya tiene consola. Usa su terminal; no se crea otra copia.')
        return active[0][:2], active[0]
    if not choices:
        raise ValueError('No hay fuentes instrumentadas compatibles. Indica --fuente con una carpeta en ~/proyecto_nsfnet.')
    choices.sort(key=lambda c: (c[0] / 'config.json').stat().st_mtime, reverse=True)
    return choices[0], None


def main():
    import fcntl
    import pwd
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('topologia', choices=sorted(WORKERS))
    user_home = Path(pwd.getpwnam(os.environ.get('SUDO_USER', 'mininet')).pw_dir)
    parser.add_argument('--proyecto', default=str(user_home / 'proyecto_nsfnet'))
    parser.add_argument('--fuente')
    args = parser.parse_args()
    if os.geteuid() != 0 or not sys.stdin.isatty():
        raise ValueError('Ejecuta con sudo en una terminal interactiva (SSH con -t); no pegues este archivo dentro de python3 -.')
    project = Path(args.proyecto).expanduser().resolve()
    lock = (project / ('.consola_' + args.topologia + '.lock')).open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise ValueError('Ya hay una consola o una transicion en curso para esta topologia.')
    (source, cfg), active = find_source(project, args.topologia, args.fuente)
    print('Lanzador de consola v1.1: observador con reutilizacion TCP.', flush=True)
    print('Fuente conservada: ' + str(source), flush=True)
    # Validar dependencias y servicios antes de interrumpir una red existente.
    import mininet.cli  # noqa: F401
    health = get_json(cfg['model_url'] + '/health')
    if health.get('modelo_id') != cfg['model_id'] or health.get('evaluacion') != 'test_completado':
        raise ValueError('El modelo anterior no responde como se esperaba. No se detienen redes.')
    schema = get_json(cfg['model_url'] + '/schema')
    if set(schema.get('features', [])) != set(cfg['features']) or set(schema.get('targets', [])) != set(cfg['targets']):
        raise ValueError('El esquema del modelo no coincide con el recolector. No se detienen redes.')
    get_json(cfg['rest_url'] + '/stats/switches')
    folder = Path(tempfile.mkdtemp(prefix='consola_' + args.topologia + '_', dir=str(project)))
    print('Carpeta nueva de esta consola: ' + str(folder), flush=True)
    for file in ('sdn_noche_comun.py', 'sdn_noche_capturar.py', 'sdn_noche_trafico.py', WORKERS[args.topologia]):
        shutil.copy2(str(source / file), str(folder / file))
    # El worker importado es el que ya funciona en la VM: incluye su tratamiento de relojes y ENOBUFS.
    cfg.update(project=str(project), interactive_source=str(source), interactive_topology=args.topologia)
    (folder / 'config.json').write_text(json.dumps(cfg, indent=2, ensure_ascii=True), encoding='utf-8')
    if active:
        _, _, pid, identity = active
        if process_identity(pid) != identity:
            raise ValueError('Cambio el proceso propietario. No se detiene ningun proceso.')
        print('Cerrando solo la sesion anterior de {} (PID {}). La otra red se conserva.'.format(args.topologia, pid), flush=True)
        os.kill(pid, signal.SIGINT)
        deadline = time.monotonic() + 75
        while process_identity(pid) == identity and time.monotonic() < deadline:
            time.sleep(0.5)
        if process_identity(pid) == identity:
            raise ValueError('La sesion anterior aun esta cerrando. No se fuerza su cierre ni se crea otra red.')
    deadline = time.monotonic() + 25
    while get_json(cfg['rest_url'] + '/stats/switches') and time.monotonic() < deadline:
        time.sleep(0.5)
    if get_json(cfg['rest_url'] + '/stats/switches'):
        raise ValueError('El controlador aun tiene switches. No se borran bridges ni se usa mn -c.')
    prefix = 'nc' if args.topologia == 'geant2' else 'ns'
    for node in cfg['topologies'][args.topologia]['nodes']:
        bridge = prefix + node['switch'][1:]
        check = subprocess.run(['ovs-vsctl', 'br-exists', bridge], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check.returncode != 2:
            raise ValueError('Bridge existente o consulta fallida: ' + bridge + '. Se conserva todo.')
    # Importar unicamente despues de escoger la fuente y liberar su sesion.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import consola_sdn
    consola_sdn.run(folder, args.topologia)
    # Mantener el descriptor abierto hasta terminar run conserva el bloqueo de propiedad.
    lock.close()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit('CONSOLA NO INICIADA: ' + str(error))
