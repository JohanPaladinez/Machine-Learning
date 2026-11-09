from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.algoritmos.dijkstra import calcular_ruta
from backend.algoritmos.pesos import calcular_costo_capacidad


router = APIRouter(
    prefix="/api/rutas",
    tags=["Rutas"]
)


class EnlaceCapacidad(BaseModel):
    origen: str = Field(min_length=1)
    destino: str = Field(min_length=1)
    capacidad_mbps: float = Field(gt=0)


class SolicitudDijkstraConvencional(BaseModel):
    nodos: list[str] = Field(min_length=1)
    enlaces: list[EnlaceCapacidad] = Field(min_length=1)
    origen: str
    destino: str
    dirigido: bool = False


@router.post("/dijkstra/convencional")
def ejecutar_dijkstra_convencional(solicitud: SolicitudDijkstraConvencional):

    try:

        enlaces_con_costo = []

        for enlace in solicitud.enlaces:

            costo = calcular_costo_capacidad(
                enlace.capacidad_mbps
            )

            enlaces_con_costo.append({
                "origen": enlace.origen,
                "destino": enlace.destino,
                "costo": costo
            })

        ruta, costo_total = calcular_ruta(
            nodos=solicitud.nodos,
            enlaces=enlaces_con_costo,
            origen=solicitud.origen,
            destino=solicitud.destino,
            dirigido=solicitud.dirigido
        )

    except ValueError as error:

        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    return {
        "algoritmo": "Dijkstra convencional",
        "criterio": "Inverso de la capacidad nominal",
        "origen": solicitud.origen,
        "destino": solicitud.destino,
        "ruta": ruta,
        "costo_total": costo_total,
        "enlaces": enlaces_con_costo
    }

