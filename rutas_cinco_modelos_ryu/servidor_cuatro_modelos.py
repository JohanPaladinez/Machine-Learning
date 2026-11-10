#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inferencia de cuatro modelos ya entrenados. No instala reglas ni entrena."""
import os
for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
from pathlib import Path
import time

MODELS = ('polinomial', 'decision_tree', 'random_forest', 'xgboost')
TARGETS = ('target_throughput_u_to_v_mbps', 'target_throughput_v_to_u_mbps',
           'target_u_to_v_loss_ratio', 'target_v_to_u_loss_ratio',
           'target_u_to_v_delay_avg_ms', 'target_v_to_u_delay_avg_ms')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Numero no finito o invalido')
    return float(value)


def physical(raw):
    values, changes = {}, []
    if set(raw) != set(TARGETS):
        raise ValueError('Se requieren las seis salidas')
    for name in TARGETS:
        v = number(raw[name])
        used = min(1.0, max(0.0, v)) if name.endswith('_loss_ratio') else max(0.0, v)
        values[name] = used
        if used != v:
            changes.append({'target': name, 'raw': v, 'used': used})
    return values, changes


class Models:
    def __init__(self, folder):
        import joblib
        self.folder = Path(folder).resolve()
        protocol = json.loads((self.folder/'protocolo.json').read_text(encoding='utf-8'))
        validation = json.loads((self.folder/'comparacion_validation.json').read_text(encoding='utf-8'))
        test = json.loads((self.folder/'comparacion_test.json').read_text(encoding='utf-8'))
        self.features = protocol['features']
        if len(self.features) != 60 or len(set(self.features)) != 60 or set(protocol['targets']) != set(TARGETS):
            raise ValueError('Esquema de 60 entradas y seis salidas incompatible')
        if test['dataset_sha256'] != protocol['dataset_sha256'] or test['seleccion_previa_validation'] != validation['seleccion_validation']:
            raise ValueError('Los informes no pertenecen a la misma comparacion')
        if set(test['modelos']) != set(MODELS) or set(validation['modelos']) != set(MODELS):
            raise ValueError('Faltan modelos evaluados')
        self.models, self.ids = {}, {}
        for name in MODELS:
            path = self.folder/(name+'.pkl')
            sha = digest(path)
            if sha != validation['huellas_modelos'][name]:
                raise ValueError('Modelo modificado desde validation: '+name)
            package = joblib.load(str(path))
            if (package['features'] != self.features or set(package['targets']) != set(TARGETS)
                    or package['dataset_sha256'] != protocol['dataset_sha256'] or package['nombre'] != name):
                raise ValueError('Paquete incompatible: '+name)
            self.models[name] = package
            self.ids[name] = name+'_'+sha[:16]
        self.dataset_sha256 = protocol['dataset_sha256']
        self.selected = validation['seleccion_validation']

    def health(self):
        return {'schema_version': 1, 'estado': 'cuatro_modelos_cargados', 'modelos': self.ids,
                'features': self.features, 'targets': list(TARGETS), 'antiguedad_maxima_s': 120,
                'dataset_sha256': self.dataset_sha256, 'seleccion_validation': self.selected,
                'evaluacion': 'test_descriptivo_completado',
                'postproceso': 'Todos: throughput y delay >=0; loss en [0,1]. Se devuelven valores crudos y ajustes.',
                'pid': os.getpid()}

    def predict(self, entries):
        import numpy as np
        if not isinstance(entries, list) or not 1 <= len(entries) <= 128:
            raise ValueError('Lote requerido de 1 a 128 enlaces')
        contexts, rows, ids = set(), [], set()
        for e in entries:
            if not isinstance(e, dict) or e.get('topologia') not in ('nsfnet', 'geant2'):
                raise ValueError('Topologia invalida')
            if any(not isinstance(e.get(k), str) or not e[k].strip() for k in ('session_id', 'link_id')):
                raise ValueError('Falta sesion o enlace')
            start, end = number(e.get('feature_start_epoch_s')), number(e.get('feature_end_epoch_s'))
            if start >= end or not -5 <= time.time()-end <= 120:
                raise ValueError('Ventana invalida, antigua o reloj desajustado')
            contexts.add((e['topologia'], e['session_id'], start, end))
            if e['link_id'] in ids:
                raise ValueError('Enlace duplicado')
            ids.add(e['link_id'])
            if not isinstance(e.get('features'), dict) or set(e['features']) != set(self.features):
                raise ValueError('Entradas incompletas; no se sustituyen por cero')
            row = [number(e['features'][k]) for k in self.features]
            if any(v < 0 for v in row):
                raise ValueError('Entradas negativas')
            rows.append(row)
        if len(contexts) != 1:
            raise ValueError('El lote mezcla sesiones o ventanas')
        result = {}
        for name in MODELS:
            package = self.models[name]
            prediction = np.asarray(package['modelo'].predict(np.asarray(rows, dtype=float)))
            if prediction.shape != (len(entries), 6):
                raise ValueError('Salidas incompletas de '+name)
            links = {}
            for entry, row in zip(entries, prediction):
                raw = {k: number(float(v)) for k, v in zip(package['targets'], row)}
                values, changes = physical(raw)
                item = {k: entry[k] for k in ('session_id','topologia','link_id','feature_start_epoch_s','feature_end_epoch_s')}
                item.update(modelo_id=self.ids[name], predicciones=values, predicciones_crudas=raw,
                            ajustes=changes, objetivo='siguiente_ventana')
                links[entry['link_id']] = item
            result[name] = links
        if not -5 <= time.time()-entries[0]['feature_end_epoch_s'] <= 120:
            raise ValueError('La ventana caduco durante la inferencia')
        return {'schema_version': 1, 'modelos': self.ids, 'predicciones': result,
                'dataset_sha256': self.dataset_sha256}


def handler(models):
    class API(BaseHTTPRequestHandler):
        def reply(self, status, data):
            body = json.dumps(data, allow_nan=False, ensure_ascii=True).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/health':
                self.reply(200, models.health())
            else:
                self.reply(404, {'error': 'Ruta inexistente'})

        def do_POST(self):
            if self.path != '/predict-batch':
                self.reply(404, {'error': 'Ruta inexistente'})
                return
            try:
                self.connection.settimeout(15)
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 2*1024*1024:
                    raise ValueError('Tamano de lote invalido')
                body = json.loads(self.rfile.read(size).decode('utf-8'))
                self.reply(200, models.predict(body.get('entries')))
            except (ValueError, TypeError, KeyError, UnicodeError) as e:
                self.reply(422, {'error': str(e)})
            except Exception:
                import traceback
                traceback.print_exc()
                self.reply(500, {'error': 'No se pudo obtener inferencia de los cuatro modelos'})
    return API


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--carpeta', required=True)
    p.add_argument('--host', default='192.168.56.108')
    p.add_argument('--puerto', type=int, default=8011)
    args = p.parse_args()
    models = Models(args.carpeta)
    server = HTTPServer((args.host, args.puerto), handler(models))
    print('CUATRO MODELOS DISPONIBLES: http://{}:{}'.format(args.host, args.puerto), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
