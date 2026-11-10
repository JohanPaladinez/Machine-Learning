
import math
from typing import Literal
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import backend.api.sdn_vivo_v1 as original
from backend.servicios.sdn_vivo_runtime_v1 import LiveNetwork, fetch_json

from backend.servicios.fuentes_sdn import MultiNetwork

original.network = MultiNetwork()
old_inputs = original.route_inputs

def checked_inputs(snapshot, session_id, graph_version,
                   origin, destination, policy, capacity_cost):
    current = (
        snapshot.get("ready")
        and snapshot.get("topology_instance_id") == session_id
        and snapshot.get("graph_version") == graph_version
    )
    if current and policy in ("capacity", "delay"):
        profile = snapshot["topology_document"]["topologies"][snapshot["topologia"]]
        available = {
            e["id"] for e in snapshot["links_runtime"]
            if e.get("state") == "up"
        }
        field = "capacity_mbps" if policy == "capacity" else "configured_delay_ms"
        for edge in profile["links"]:
            if edge["link_id"] not in available:
                continue
            try:
                value = float(edge[field])
            except (TypeError, ValueError, KeyError):
                raise ValueError("Falta " + field + ". Elige otro criterio.")
            if not math.isfinite(value) or value < 0 or (
                policy == "capacity" and value == 0
            ):
                raise ValueError("Valor no disponible para " + field)

    return old_inputs(
        snapshot, session_id, graph_version,
        origin, destination, policy, capacity_cost
    )

original.route_inputs = checked_inputs

class Selection(BaseModel):
    topologia: Literal["auto", "nsfnet", "geant2"] = "auto"
    session_id: str = Field(default="", max_length=240)

@original.original_app.post("/api/sdn/seleccionar")
def select_topology(request: Selection):
    try:
        return original.network.select_topology(
            request.topologia, request.session_id
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

app = CORSMiddleware(
    original.original_app,
    allow_origins=[
        "http://127.0.0.1:5181",
        "http://localhost:5181",
        "http://127.0.0.1:5182",
        "http://localhost:5182",
        "http://127.0.0.1:8003",
        "http://localhost:8003"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# SDN_MODELO_COMUN_PANEL_V1
from backend.api.sdn_modelo_comun_v1 import router as modelo_comun_router_v1
original.original_app.include_router(modelo_comun_router_v1)


# SDN_PREDICCIONES_ENLACE_V1
from backend.api.sdn_predicciones_enlace_v1 import router as predicciones_enlace_router_v1
original.original_app.include_router(predicciones_enlace_router_v1)

from backend.api.sdn_comparacion import router as comparacion_router
original.original_app.include_router(comparacion_router)

from backend.api.sdn_operacion import router as operacion_router
original.original_app.include_router(operacion_router)

from backend.api.sdn_enrutamiento_real import router as enrutamiento_router
original.original_app.include_router(enrutamiento_router)
