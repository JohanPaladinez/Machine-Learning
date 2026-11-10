#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Arranque diario en RYU; reutiliza fuentes y modelos existentes, sin entrenar."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import ProxyHandler, build_opener

PROJECT = Path.home() / 'proyecto_nsfnet'
IP = '192.168.56.108'
MODEL_ID = 'modelo_20261107T205202Z_n4vncu_0'
CLIENT = build_opener(ProxyHandler({}))


def get_json(port, path):
    with CLIENT.open('http://{}:{}{}'.format(IP, port, path), timeout=3) as response:
        return json.load(response)


def free_port(port):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('0.0.0.0', port))
            return True
        except OSError:
            return False


def health(port, expected):
    try:
        data = get_json(port, '/health')
        if not expected(data):
            raise RuntimeError('El servicio {} responde con un contrato distinto.'.format(port))
        return data
    except (OSError, ValueError):
        if not free_port(port):
            raise RuntimeError('Puerto {} ocupado pero sin respuesta valida. No se detuvo ningun proceso.'.format(port))
        return None


def original_valid(data):
    return (data.get('estado') == 'modelo_cargado'
            and data.get('modelo_id') == MODEL_ID
            and data.get('features') == 60 and data.get('targets') == 6
            and data.get('evaluacion') == 'test_completado')


def four_valid(data):
    return (data.get('estado') == 'cuatro_modelos_cargados'
            and len(data.get('features', [])) == 60
            and len(data.get('targets', [])) == 6
            and data.get('evaluacion') == 'test_descriptivo_completado'
            and set(data.get('modelos', {})) == {'polinomial', 'decision_tree', 'random_forest', 'xgboost'})


def load_controller_factory():
    folder = PROJECT / 'datos/nocturna_c064e9fb0ad2_win4e5zw'
    source = folder / 'sdn_noche_ryu.py'
    if not source.is_file() or not (folder / 'sdn_noche_comun.py').is_file():
        raise RuntimeError('Falta la fuente de controlador existente: ' + str(source))
    sys.path.insert(0, str(folder))
    spec = importlib.util.spec_from_file_location('arranque_controlador_existente', str(source))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def controller(name, of_port, rest_port, folder, factory):
    try:
        switches = get_json(rest_port, '/stats/switches')
    except (OSError, ValueError):
        switches = None
    if isinstance(switches, list) and not free_port(of_port):
        print('{}: controlador ya disponible; {} switches registrados.'.format(name, len(switches)), flush=True)
        return {'of_port': of_port, 'rest_port': rest_port, 'reutilizado': True}
    if not free_port(of_port) or not free_port(rest_port):
        raise RuntimeError('{}: los puertos {} / {} estan ocupados sin un controlador comprobable. No se modificaron.'.format(name, of_port, rest_port))
    destination = folder / name
    destination.mkdir()
    original = factory.puerto_libre

    def exact_port(start):
        port = {16653: of_port, 18080: rest_port}[start]
        if not free_port(port):
            raise RuntimeError('Puerto ocupado durante el arranque: ' + str(port))
        return port

    # Solo modifica la seleccion de puertos en memoria durante esta llamada.
    factory.puerto_libre = exact_port
    try:
        result = factory.controlador(str(destination))
    finally:
        factory.puerto_libre = original
    if (result['of_port'], result['rest_port']) != (of_port, rest_port):
        raise RuntimeError('El controlador devolvio puertos inesperados. Revisar ' + str(destination))
    print('{}: controlador listo, OpenFlow {} / REST {}.'.format(name, of_port, rest_port), flush=True)
    return result


def original_service(folder):
    if health(8010, original_valid):
        print('Modelo individual: disponible en 8010.', flush=True)
        return
    python = PROJECT / 'entorno_ml/bin/python'
    model = PROJECT / ('resultados_comun_20261107T205101/' + MODEL_ID + '/modelo_comun.pkl')
    sources = [p for p in PROJECT.glob('inferencia_comun_v1_*/servidor.py') if p.is_file()]
    if not sources or not python.is_file() or not model.is_file():
        raise RuntimeError('Falta el servidor individual, entorno_ml o modelo_comun.pkl. No se entrena nada.')
    source = max(sources, key=lambda p: p.stat().st_mtime)
    log_path = folder / 'modelo_8010.log'
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    with log_path.open('ab') as log:
        process = subprocess.Popen([str(python), '-u', str(source), str(model)],
            cwd=str(PROJECT), env=env, stdin=subprocess.DEVNULL, stdout=log,
            stderr=subprocess.STDOUT, start_new_session=True)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline and process.poll() is None:
        try:
            data = get_json(8010, '/health')
            if original_valid(data) and data.get('pid') == process.pid:
                print('Modelo individual: cargado en 8010.', flush=True)
                return
        except (OSError, ValueError):
            pass
        time.sleep(1)
    raise RuntimeError('No se confirmo el modelo 8010. Registro: ' + str(log_path))


def four_service():
    if health(8011, four_valid):
        print('Cuatro modelos: disponibles en 8011.', flush=True)
        return
    script = PROJECT / 'rutas_cinco_modelos_ryu/iniciar_servicio_modelos.sh'
    if not script.is_file():
        raise RuntimeError('Falta el lanzador ya instalado: ' + str(script))
    subprocess.check_call(['bash', str(script)], cwd=str(PROJECT))
    if not health(8011, four_valid):
        raise RuntimeError('No se confirmaron los cuatro modelos en 8011.')


def main():
    if os.geteuid() == 0 or Path.home().name != 'ryu':
        raise RuntimeError('Ejecutar como usuario ryu, sin sudo, en la VM RYU.')
    if not PROJECT.is_dir():
        raise RuntimeError('No existe ' + str(PROJECT))
    with (PROJECT / '.arranque_diario_sdn.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('Ya hay otro arranque diario en curso. Espera su resultado.')
        folder = Path(tempfile.mkdtemp(prefix='arranque_diario_ryu_', dir=str(PROJECT)))
        print('Registro de este arranque: ' + str(folder), flush=True)
        factory = load_controller_factory()
        configs = {}
        for name, of_port, rest_port in (('geant2', 16653, 18080), ('nsfnet', 16654, 18081)):
            data = controller(name, of_port, rest_port, folder, factory)
            data.update(topologia=name, ryu_ip=IP, rest_url='http://{}:{}'.format(IP, rest_port))
            configs[name] = data
        (folder / 'controladores.json').write_text(json.dumps(configs, indent=2), encoding='utf-8')
        original_service(folder)
        four_service()
        print('\nRYU LISTO: controladores y modelos comprobados.', flush=True)
        print('Ahora abre las dos consolas Mininet; despues abre la interfaz de Windows.', flush=True)
        print('No se cambiaron relojes, datasets ni modelos guardados.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('\nARRANQUE INCOMPLETO: ' + str(error), file=sys.stderr, flush=True)
        print('Conserva esta salida. Los servicios ya arrancados no se cierran automaticamente.', file=sys.stderr)
        sys.exit(1)
