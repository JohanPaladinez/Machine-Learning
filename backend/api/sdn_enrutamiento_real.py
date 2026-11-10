"""Preparar, aplicar y demostrar un flujo ICMP seleccionado en la GUI."""
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.api.sdn_comparacion import ComparisonRequest
from backend.servicios.enrutamiento_real import RouteInstaller, same_context
from backend.servicios.comparacion_rutas import conventional
import hashlib
import json

router = APIRouter(prefix='/api/sdn/enrutamiento', tags=['Enrutamiento ICMP real'])
installer = RouteInstaller(Path(__file__).resolve().parents[2] / '.ejecucion_windows/enrutamiento_icmp.json')


class Context(BaseModel):
    model_config = ConfigDict(extra='forbid')
    topology_instance_id: str = Field(min_length=1, max_length=240)
    graph_version: str = Field(min_length=1, max_length=240)
    selection_revision: int = Field(ge=0)


class Prepare(ComparisonRequest):
    criterio: Literal['conventional', 'polinomial', 'decision_tree', 'random_forest', 'xgboost']
    ruta_esperada: list[str] = Field(min_length=2, max_length=64)
    modelo_id_esperado: str | None = Field(default=None, max_length=240)


class Apply(Context):
    plan_id: str = Field(min_length=20, max_length=100)


def network():
    from backend.api.sdn_selector_v2 import original
    return original.network


def checked(net, request, graph=True):
    snapshot = net.snapshot(force=True)
    if (not snapshot.get('ready') or snapshot.get('topology_instance_id') != request.topology_instance_id or
            (graph and snapshot.get('graph_version') != request.graph_version) or
            snapshot.get('selection_revision') != request.selection_revision):
        raise HTTPException(409, 'Cambio la seleccion o la identidad de la red. Actualiza el panel.')
    source = net.sources[snapshot['topologia']]
    if snapshot.get('ryu', {}).get('rest_url') != source['ryu_rest_url']:
        raise HTTPException(409, 'El controlador no pertenece a la fuente permitida.')
    return snapshot


def validator(net):
    def validate(record, graph=True):
        actual = net.snapshot(force=True)
        if not same_context(record, actual, selection=False, graph=graph):
            raise ValueError('Cambio la sesion o el grafo durante la operacion OpenFlow.')
    return validate


@router.get('/estado')
def state(topology_instance_id: str, graph_version: str, selection_revision: int):
    net = network()
    with net.lock:
        request = Context(topology_instance_id=topology_instance_id, graph_version=graph_version, selection_revision=selection_revision)
        snapshot = checked(net, request, graph=False)
        return installer.status(snapshot)


@router.post('/preparar')
def prepare(request: Prepare):
    from backend.api.sdn_cinco_modelos import compare_models
    net = network()
    base = ComparisonRequest(**request.model_dump(exclude={'criterio', 'ruta_esperada', 'modelo_id_esperado'}))
    # Recalcular con datos actuales. Una comparacion guardada no autoriza a aplicar una prediccion vieja.
    if request.criterio == 'conventional':
        with net.lock:
            initial = checked(net, request)
            try:
                _, route = conventional(initial, base)
            except ValueError as error:
                raise HTTPException(422, str(error))
        result = {'rutas': {'conventional': route}, 'ml': {},
                  'comparison_id': hashlib.sha256(json.dumps([request.model_dump(), route], sort_keys=True).encode()).hexdigest()[:24]}
    else:
        result = compare_models(base)
    route = result['rutas'].get(request.criterio)
    if route is None:
        raise HTTPException(424, 'El modelo seleccionado no dispone de una ruta actual: ' + str(result.get('ml', {}).get('motivo', '')))
    if route['ruta'] != request.ruta_esperada:
        raise HTTPException(409, 'El camino actual difiere del mostrado. Actualiza la comparacion antes de aplicarlo.')
    if request.criterio != 'conventional' and route.get('modelo_id') != request.modelo_id_esperado:
        raise HTTPException(409, 'Cambio el modelo de la ruta. Actualiza la comparacion.')
    with net.lock:
        snapshot = checked(net, request)
        try:
            metadata = dict(result['ml']) if request.criterio != 'conventional' else {}
            metadata['comparison_id'] = result['comparison_id']
            plan = installer.prepare(snapshot, route['ruta'], request.criterio, metadata)
        except (ValueError, KeyError, TypeError) as error:
            raise HTTPException(409, str(error))
    return dict(plan=plan, rules_installed=False, plan_valid_for_s=90)


@router.post('/aplicar')
def apply(request: Apply):
    net = network()
    with net.lock:
        snapshot = checked(net, request)
        try:
            result = installer.apply(request.plan_id, snapshot, validator(net))
            return dict(active=result, rules_installed=True)
        except (OSError, ValueError, KeyError) as error:
            raise HTTPException(409, str(error))


@router.post('/iniciar-evidencia')
def baseline(request: Context):
    return evidence(request, reset=True)


@router.post('/verificar-trafico')
def verify(request: Context):
    return evidence(request, reset=False)


def evidence(request, reset):
    net = network()
    with net.lock:
        snapshot = checked(net, request)
        try:
            return {'active': installer.evidence(snapshot, reset)}
        except (OSError, ValueError, KeyError) as error:
            raise HTTPException(409, str(error))


@router.post('/retirar')
def remove(request: Context):
    net = network()
    with net.lock:
        snapshot = checked(net, request, graph=False)
        try:
            return installer.remove(snapshot, validator(net))
        except (OSError, ValueError, KeyError) as error:
            raise HTTPException(409, str(error))
