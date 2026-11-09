"""Entrada adicional: conserva la API original y añade la red activa."""
from typing import Literal
from fastapi import APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from backend.api.main import app as original_app
from backend.algoritmos.dijkstra import calcular_ruta
from backend.algoritmos.pesos import calcular_costo_capacidad
from backend.servicios.sdn_vivo_runtime_v1 import LiveNetwork, route_inputs

network = LiveNetwork()
router = APIRouter(prefix="/api/sdn", tags=["Red activa"])


class Source(BaseModel):
    url: str = Field(min_length=1)
    ryu_rest_url: str = ""


class RouteRequest(BaseModel):
    topology_instance_id: str
    graph_version: str
    origen: str
    destino: str
    criterio: Literal["hops", "delay", "capacity"] = "capacity"


@router.post("/fuente")
def configure(source: Source):
    try:
        return network.configure(source.url, source.ryu_rest_url)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.get("/estado")
def state():
    return network.snapshot()


@router.post("/rutas")
def route(request: RouteRequest):
    snapshot = network.snapshot(force=True)
    try:
        args = route_inputs(snapshot, request.topology_instance_id, request.graph_version,
                            request.origen, request.destino, request.criterio, calcular_costo_capacidad)
        path, cost = calcular_ruta(**args)
    except ValueError as error:
        raise HTTPException(status_code=409 if not snapshot.get("ready") or snapshot.get("graph_version") != request.graph_version else 422, detail=str(error))
    return {"algoritmo": "Dijkstra sobre red activa", "criterio": request.criterio,
            "ruta": path, "costo_total": cost, "topology_instance_id": snapshot["topology_instance_id"],
            "graph_version": snapshot["graph_version"], "observed_utc": snapshot["observed_utc"],
            "rules_installed": False}


original_app.include_router(router)
# El original permanece en disco y en su puerto. Esta entrada se sirve en 8001.
app = CORSMiddleware(original_app, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:5174", "http://127.0.0.1:5174", "http://localhost:5180", "http://127.0.0.1:5180"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"])
