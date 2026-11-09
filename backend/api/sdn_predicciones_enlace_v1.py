"""Inferencia por enlace sobre entradas recientes del observador seleccionado."""
import json
import math
import threading
import time
from collections import OrderedDict
from datetime import datetime
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.api.sdn_modelo_comun_v1 import SERVICIO, consultar

router = APIRouter(prefix="/api/sdn/ml", tags=["Predicciones por enlace"])
_cache = OrderedDict()
_lock = threading.RLock()


class SolicitudPrediccionEnlaceV1(BaseModel):
    topology_instance_id: str = Field(min_length=1, max_length=240)
    graph_version: str = Field(min_length=1, max_length=240)
    link_id: str = Field(min_length=1, max_length=240)
    feature_end_epoch_s: float = Field(gt=0)


def _numero(valor):
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _misma_red(snapshot, solicitud):
    if not snapshot.get("ready"):
        raise HTTPException(409, "La red no esta verificada en este momento.")
    if (snapshot.get("topology_instance_id") != solicitud.topology_instance_id
            or snapshot.get("graph_version") != solicitud.graph_version):
        raise HTTPException(409, "Cambio la red seleccionada; espera su actualizacion.")
    activos = [e for e in snapshot.get("links_runtime", [])
               if e.get("id") == solicitud.link_id and e.get("state") == "up"]
    if len(activos) != 1:
        raise HTTPException(409, "El enlace seleccionado no esta disponible.")


def _entrada(snapshot, solicitud, features):
    _misma_red(snapshot, solicitud)
    metricas = snapshot.get("metrics") or {}
    enlace = (metricas.get("links") or {}).get(solicitud.link_id) or {}
    datos = enlace.get("ml") or {}
    if metricas.get("status") != "fresh" or datos.get("status") != "inputs_ready":
        raise HTTPException(424, "Este enlace todavia no tiene una ventana reciente completa para el modelo.")
    if (enlace.get("method") != "af_packet_offered_probes_tx_status_kernel_rx_v3"
            or enlace.get("loss_scope") != "offered_including_local_tx_refusals"):
        raise HTTPException(424, "El metodo de medicion de esta sesion requiere un adaptador compatible.")
    for campo, esperado in (("session_id", snapshot.get("session_id")),
                           ("topologia", snapshot.get("topologia")), ("link_id", solicitud.link_id)):
        if not esperado or datos.get(campo) != esperado:
            raise HTTPException(409, "Las entradas pertenecen a otra sesion o enlace.")
    inicio, fin = datos.get("feature_start_epoch_s"), datos.get("feature_end_epoch_s")
    if not _numero(inicio) or not _numero(fin) or inicio >= fin:
        raise HTTPException(424, "La ventana no tiene fechas validas.")
    if not _numero(solicitud.feature_end_epoch_s) or abs(fin - solicitud.feature_end_epoch_s) > 0.001:
        raise HTTPException(409, "Cambio la ventana; espera la nueva medicion del panel.")
    edad = time.time() - fin
    if edad < -5 or edad > 120:
        raise HTTPException(424, "Las entradas son antiguas o los relojes estan desajustados.")
    try:
        for clave, instante in (("window_start", inicio), ("window_end", fin)):
            fecha = datetime.fromisoformat(metricas[clave].replace("Z", "+00:00"))
            if fecha.tzinfo is None or abs(fecha.timestamp() - instante) > 0.001:
                raise ValueError("Fechas distintas")
    except (KeyError, TypeError, ValueError, AttributeError):
        raise HTTPException(424, "Las fechas de las entradas no corresponden a la ventana medida.")
    valores = datos.get("features")
    if not isinstance(valores, dict) or set(valores) != set(features):
        raise HTTPException(424, "Faltan entradas del modelo en esta sesion.")
    if any(not _numero(v) or v < 0 for v in valores.values()):
        raise HTTPException(424, "Hay entradas invalidas; no se reemplazan por cero.")
    return {k: datos[k] for k in ("session_id", "topologia", "link_id",
                                 "feature_start_epoch_s", "feature_end_epoch_s", "features")}


def _validar_salida(respuesta, entrada, targets, modelo_id):
    for campo in ("session_id", "topologia", "link_id", "feature_start_epoch_s", "feature_end_epoch_s"):
        if respuesta.get(campo) != entrada[campo]:
            raise HTTPException(502, "El modelo devolvio otra ventana o sesion.")
    if respuesta.get("modelo_id") != modelo_id:
        raise HTTPException(502, "Cambio el modelo durante la consulta.")
    resultados = respuesta.get("predicciones")
    if not isinstance(resultados, dict) or set(resultados) != set(targets):
        raise HTTPException(502, "La respuesta del modelo esta incompleta.")
    for nombre, valor in resultados.items():
        if not _numero(valor) or valor < 0 or (nombre.endswith("_loss_ratio") and valor > 1):
            raise HTTPException(502, "El modelo devolvio una prediccion invalida.")


def _predecir(entrada):
    peticion = Request(SERVICIO + "/predict", data=json.dumps(entrada, allow_nan=False).encode("utf-8"),
                       headers={"Content-Type": "application/json"})
    try:
        with build_opener(ProxyHandler({})).open(peticion, timeout=8) as respuesta:
            cuerpo = respuesta.read(65537)
        if len(cuerpo) > 65536:
            raise ValueError("Respuesta demasiado grande")
        datos = json.loads(cuerpo.decode("utf-8"))
        if not isinstance(datos, dict):
            raise ValueError("Respuesta inesperada")
        return datos
    except HTTPError as error:
        try:
            detalle = json.loads(error.read(4096).decode("utf-8")).get("error", "Solicitud rechazada")
        except (ValueError, AttributeError):
            detalle = "Solicitud rechazada"
        raise HTTPException(502, "Modelo RYU: " + str(detalle)[:300])
    except (OSError, ValueError):
        raise HTTPException(503, "El servicio del modelo en RYU no responde correctamente.")


@router.post("/predecir")
def predecir_enlace(solicitud: SolicitudPrediccionEnlaceV1):
    from backend.api import sdn_selector_v2 as selector
    network = selector.original.network
    snapshot = network.snapshot(force=True)
    _misma_red(snapshot, solicitud)
    salud = consultar("/health")
    esquema = consultar("/schema")
    if (salud.get("estado") != "modelo_cargado" or salud.get("evaluacion") != "test_completado"
            or not salud.get("modelo_id") or len(esquema.get("features", [])) != 60
            or len(set(esquema["features"])) != 60 or len(esquema.get("targets", [])) != 6
            or len(set(esquema["targets"])) != 6):
        raise HTTPException(503, "El modelo evaluado no confirma su esquema esperado.")
    entrada = _entrada(snapshot, solicitud, esquema["features"])
    clave = (snapshot.get("source_url"), solicitud.topology_instance_id, solicitud.graph_version,
             solicitud.link_id, entrada["feature_start_epoch_s"], entrada["feature_end_epoch_s"],
             salud["modelo_id"], tuple(entrada["features"][f] for f in esquema["features"]))
    with _lock:
        salida = _cache.get(clave)
        if salida is None:
            respuesta = _predecir(entrada)
            _validar_salida(respuesta, entrada, esquema["targets"], salud["modelo_id"])
            salida = {k: respuesta[k] for k in ("modelo_id", "session_id", "topologia", "link_id",
                      "feature_start_epoch_s", "feature_end_epoch_s", "predicciones")}
            salida.update(topology_instance_id=solicitud.topology_instance_id,
                          graph_version=solicitud.graph_version, objetivo="siguiente_ventana",
                          received_epoch_s=time.time())
            _cache[clave] = salida
            while len(_cache) > 256:
                _cache.popitem(last=False)
        else:
            _cache.move_to_end(clave)
    actual = network.snapshot()
    _misma_red(actual, solicitud)
    _entrada(actual, solicitud, esquema["features"])
    return salida
