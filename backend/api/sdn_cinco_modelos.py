"""Cinco caminos: convencional y uno por modelo. Solo calculo, sin forwarding."""
from collections import OrderedDict
from datetime import datetime
import hashlib
import json
import math
import os
import threading
import time
from urllib.request import Request, ProxyHandler, build_opener

from fastapi import APIRouter, HTTPException
from backend.api.sdn_comparacion import ComparisonRequest, identity
from backend.api.sdn_predicciones_enlace_v1 import SolicitudPrediccionEnlaceV1, _entrada, _validar_salida
from backend.servicios.comparacion_rutas import (
    conventional, compare_four, directional_cost, parameters, route_groups, TARGETS,
)

MODELS = ('polinomial', 'decision_tree', 'random_forest', 'xgboost')
SERVICE = os.environ.get('SDN_MODELOS_URL', 'http://192.168.56.108:8011').rstrip('/')
router = APIRouter(prefix='/api/sdn', tags=['Cinco rutas por modelo'])
_cache, _lock = OrderedDict(), threading.RLock()


def remote(path, body=None):
    request = Request(SERVICE+path, data=None if body is None else json.dumps(body, allow_nan=False).encode(),
                      headers={'Content-Type': 'application/json'})
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=30) as response:
            data = response.read(4*1024*1024+1)
        if len(data) > 4*1024*1024:
            raise ValueError('Respuesta demasiado grande')
        result = json.loads(data)
        if not isinstance(result, dict):
            raise ValueError('JSON inesperado')
        return result
    except (OSError, ValueError):
        raise HTTPException(424, 'El servicio de los cuatro modelos no responde correctamente. Inicia el nuevo servicio de RYU; el anterior se conserva.')


def predictions(snapshot):
    health = remote('/health')
    targets = {k for triple in TARGETS.values() for k in triple}
    features = health.get('features', [])
    ids = health.get('modelos', {})
    if (health.get('schema_version') != 1 or health.get('estado') != 'cuatro_modelos_cargados'
            or health.get('evaluacion') != 'test_descriptivo_completado'
            or health.get('antiguedad_maxima_s') != 120 or len(features) != 60
            or len(set(features)) != 60 or set(health.get('targets', [])) != targets
            or len(health.get('targets', [])) != 6 or set(ids) != set(MODELS)
            or any(not isinstance(v, str) or not v for v in ids.values())
            or not health.get('dataset_sha256')):
        raise HTTPException(424, 'El servicio no confirma los cuatro modelos evaluados y el esquema esperado.')
    entries = []
    profile = snapshot['topology_document']['topologies'][snapshot['topologia']]
    nominal = {e['link_id']:e for e in profile['links']}
    for edge in snapshot['links_runtime']:
        if edge.get('state') != 'up':
            continue
        end = snapshot.get('metrics', {}).get('links', {}).get(edge['id'], {}).get('ml', {}).get('feature_end_epoch_s')
        if isinstance(end, bool) or not isinstance(end, (float,int)) or not math.isfinite(end) or end <= 0:
            raise HTTPException(424, 'Falta una ventana de entrada valida en '+edge['id'])
        request = SolicitudPrediccionEnlaceV1(topology_instance_id=snapshot['topology_instance_id'],
            graph_version=snapshot['graph_version'], link_id=edge['id'], feature_end_epoch_s=end)
        entry = _entrada(snapshot, request, features)
        if entry['features'].get('capacity_mbps') != nominal[edge['id']]['capacity_mbps']:
            raise HTTPException(424, 'La capacidad del modelo no corresponde al enlace')
        entries.append(entry)
    windows = {(e['feature_start_epoch_s'], e['feature_end_epoch_s']) for e in entries}
    if len(windows) != 1:
        raise HTTPException(424, 'Todos los enlaces y modelos requieren la misma ventana temporal')
    entry_digest = hashlib.sha256(json.dumps(entries, sort_keys=True, allow_nan=False).encode()).hexdigest()
    key = (identity(snapshot), tuple(sorted(ids.items())), health['dataset_sha256'], entry_digest)
    with _lock:
        response = _cache.get(key)
    if response is None:
        response = remote('/predict-batch', {'entries': entries})
    if (response.get('schema_version') != 1 or response.get('modelos') != ids
            or response.get('dataset_sha256') != health['dataset_sha256']
            or set(response.get('predicciones', {})) != set(MODELS)):
        raise HTTPException(502, 'El servicio cambio de modelos o dataset durante el calculo')
    for name in MODELS:
        links = response['predicciones'][name]
        if set(links) != {e['link_id'] for e in entries}:
            raise HTTPException(502, 'Inferencia incompleta para '+name)
        for entry in entries:
            out = links[entry['link_id']]
            _validar_salida(out, entry, targets, ids[name])
            raw = out.get('predicciones_crudas', {})
            if set(raw) != targets:
                raise HTTPException(502, 'Faltan predicciones crudas de '+name)
            expected_changes = []
            for target, value in raw.items():
                if isinstance(value, bool) or not isinstance(value, (float,int)) or not math.isfinite(value):
                    raise HTTPException(502, 'Prediccion cruda no finita')
                expected = min(1.0, max(0.0, value)) if target.endswith('_loss_ratio') else max(0.0, value)
                if out['predicciones'][target] != expected:
                    raise HTTPException(502, 'Postproceso no coincide con la politica comun')
                if expected != value:
                    expected_changes.append((target,value,expected))
            changes = out.get('ajustes', [])
            if not isinstance(changes, list) or sorted((c.get('target'),c.get('raw'),c.get('used')) for c in changes) != sorted(expected_changes):
                raise HTTPException(502, 'Registro de ajustes incoherente')
    start, end = next(iter(windows))
    age = time.time()-end
    if not -5 <= age <= 120:
        raise HTTPException(424, 'La ventana caduco durante la inferencia')
    with _lock:
        _cache[key] = response
        while len(_cache) > 8:
            _cache.popitem(last=False)
    return response['predicciones'], dict(status='available', feature_start_epoch_s=start,
        feature_end_epoch_s=end, max_age_s=120, input_age_s=age, modelos=ids,
        dataset_sha256=health['dataset_sha256'], seleccion_validation=health['seleccion_validation'],
        objetivo='siguiente_ventana')


def measured_metrics(snapshot, route, weights, scales):
    result = dict(measured_delay_ms=None, measured_loss_ratio=None, measured_qos=None)
    metrics = snapshot.get('metrics', {})
    try:
        end = datetime.fromisoformat(metrics['window_end'].replace('Z', '+00:00'))
        if end.tzinfo is None or metrics.get('status') != 'fresh' or not -5 <= time.time()-end.timestamp() <= 120:
            return result
        profile = snapshot['topology_document']['topologies'][snapshot['topologia']]
        pairs = {(e['switch_u'],e['switch_v']):(e,'u_to_v') for e in profile['links']}
        pairs.update({(e['switch_v'],e['switch_u']):(e,'v_to_u') for e in profile['links']})
        delays, losses, costs = [], [], []
        for a,b in zip(route['ruta'], route['ruta'][1:]):
            edge, direction = pairs[(a,b)]
            sample = metrics['links'][edge['link_id']]['directions'][direction]
            t,d,l = (sample[k] for k in ('throughput_mbps','delay_ms','loss_ratio'))
            cost, _ = directional_cost(edge['capacity_mbps'],t,d,l,weights,scales)
            delays.append(d); losses.append(l); costs.append(cost)
        d, l, q = sum(delays), 1-math.prod(1-l for l in losses), sum(costs)
        if all(math.isfinite(v) for v in (d,l,q)):
            result.update(measured_delay_ms=d, measured_loss_ratio=l, measured_qos=q)
    except (KeyError,ValueError,TypeError,OverflowError):
        pass
    return result


@router.post('/rutas/comparar-modelos')
def compare_models(request: ComparisonRequest):
    from backend.api import sdn_selector_v2 as selector
    network = selector.original.network
    snapshot = network.snapshot(force=True)
    if not snapshot.get('ready') or snapshot.get('selection_revision') != request.selection_revision:
        raise HTTPException(409, 'Cambio la seleccion o la red no esta verificada')
    try:
        weights, scales = parameters(request.pesos.model_dump(), request.escalas.model_dump())
        _, base = conventional(snapshot, request)
    except ValueError as e:
        mismatch = snapshot.get('topology_instance_id') != request.topology_instance_id or snapshot.get('graph_version') != request.graph_version
        raise HTTPException(409 if mismatch else 422, str(e))
    base.update(criterio='conventional', nombre='Convencional · 1/capacidad',
                unidad_costo='Σ 1/Mbps', costo_criterio=base['costo_referencia'])
    base.update(measured_metrics(snapshot, base, weights, scales))
    routes = {'conventional': base, **{name: None for name in MODELS}}
    result = {k:snapshot[k] for k in ('topologia','session_id','topology_instance_id','graph_version','selection_revision','observed_utc')}
    result.update(comparacion_modelos_version=1, rutas=routes, ml={'status':'unavailable'},
        errores_criterios={}, pesos=weights, escalas=scales, rules_installed=False,
        formula='wd*d/(d+D) + wl*l/(l+L) + wc*C/(C+c) + wt*t/(t+c)',
        advertencias=[
            'Los cinco caminos se calculan con Dijkstra; cambia el origen de sus pesos.',
            'Indicadores comunes: mismos valores medidos por enlace y ventana para todos los caminos.',
            'Las previsiones de cada modelo no son mediciones; comparar su propio QoS no demuestra superioridad.',
            'La suma de delay y la perdida compuesta por enlace son aproximaciones, no mediciones extremo a extremo.',
            'Loss ofrecido incluye rechazos locales. Throughput RX no es ancho de banda disponible.',
            'Postproceso comun: throughput/delay >=0 y loss en [0,1]; se muestran ajustes y predicciones crudas. Las evaluaciones ML guardadas no se recortan.',
            'No se instalan reglas ni se modifica el trafico al comparar.'])
    try:
        forecast, metadata = predictions(snapshot)
        for name in MODELS:
            computed, _ = compare_four(snapshot, request, forecast[name], weights, scales)
            route = computed['ml']
            route.update(criterio=name, nombre=name, modelo_id=metadata['modelos'][name])
            route.update(measured_metrics(snapshot, route, weights, scales))
            changes = []
            for item in route['predicciones_enlaces']:
                out = forecast[name][item['link_id']]
                direction_targets = set(TARGETS[item['direccion']])
                item['predicciones_crudas'] = {k:v for k,v in out['predicciones_crudas'].items() if k in direction_targets}
                item['ajustes'] = [c for c in out['ajustes'] if c['target'] in direction_targets]
                changes.extend(dict(c, link_id=item['link_id'], direccion=item['direccion']) for c in item['ajustes'])
            route['ajustes_ruta'] = changes
            route['ajustes_total_grafo'] = sum(len(p['ajustes']) for p in forecast[name].values())
            routes[name] = route
        result['ml'] = metadata
    except HTTPException as e:
        if e.status_code == 409:
            raise
        result['ml'] = {'status':'unavailable', 'motivo':str(e.detail)}
    except (ValueError,KeyError,TypeError,OverflowError) as e:
        result['ml'] = {'status':'unavailable', 'motivo':'No se pudieron validar las predicciones: '+str(e)}
    actual = network.snapshot(force=True)
    if not actual.get('ready') or identity(actual) != identity(snapshot):
        raise HTTPException(409, 'Cambio la sesion, seleccion o grafo durante la comparacion')
    if result['ml']['status'] == 'available':
        age = time.time()-result['ml']['feature_end_epoch_s']
        if not -5 <= age <= 120:
            result['ml'] = {'status':'unavailable','motivo':'La ventana caduco durante la validacion final'}
        else:
            result['ml']['input_age_s'] = age
    if result['ml']['status'] != 'available':
        for name in MODELS:
            routes[name] = None
            result['errores_criterios'][name] = result['ml'].get('motivo', 'Inferencia no disponible')
    result['coincidencias'] = route_groups(routes)
    result['caminos_distintos'] = len(result['coincidencias'])
    result['criterios_disponibles'] = sum(v is not None for v in routes.values())
    result['comparison_id'] = hashlib.sha256(json.dumps(result, sort_keys=True, allow_nan=False).encode()).hexdigest()[:24]
    return result
