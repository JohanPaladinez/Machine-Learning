from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from backend.api.rutas import router as rutas_router

from backend.algoritmos.dijkstra import calcular_ruta
from backend.servicios.topologias import (
    validar_topologia as validar_topologia_datos
)


app = FastAPI(
    title="NSFNET - Service Provider API",
    description="Sistema de enrutamiento SDN con Machine Learning",
    version="0.3.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(rutas_router)

# MODELOS DE DATOS

class EnlaceEntrada(BaseModel):
    origen: str = Field(min_length=1)
    destino: str = Field(min_length=1)
    costo: float = Field(ge=0)


class SolicitudDijkstra(BaseModel):
    nodos: list[str] = Field(min_length=1)
    enlaces: list[EnlaceEntrada] = Field(default_factory=list)
    origen: str = Field(min_length=1)
    destino: str = Field(min_length=1)
    dirigido: bool = False


class EnlaceTopologia(BaseModel):
    origen: str = Field(min_length=1)
    destino: str = Field(min_length=1)
    capacidad_mbps: float | None = Field(default=None, gt=0)


class SolicitudTopologia(BaseModel):
    nombre: str = Field(min_length=1)
    nodos: list[str] = Field(min_length=1)
    enlaces: list[EnlaceTopologia] = Field(default_factory=list)
    dirigido: bool = False


# RUTAS PRINCIPALES

@app.get("/")
def inicio():
    return {
        "proyecto": "NSFNET",
        "servicio": "Service Provider API",
        "estado": "activo"
    }


@app.get("/api/salud")
def verificar_salud():
    return {
        "estado": "ok",
        "mensaje": "Backend funcionando correctamente"
    }


# DIJKSTRA CONVENCIONAL

@app.post("/api/rutas/dijkstra")
def ejecutar_dijkstra(solicitud: SolicitudDijkstra):

    try:
        ruta, costo_total = calcular_ruta(
            nodos=solicitud.nodos,
            enlaces=[
                enlace.model_dump()
                for enlace in solicitud.enlaces
            ],
            origen=solicitud.origen,
            destino=solicitud.destino,
            dirigido=solicitud.dirigido
        )

    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    return {
        "algoritmo": "Dijkstra convencional",
        "origen": solicitud.origen,
        "destino": solicitud.destino,
        "ruta": ruta,
        "costo_total": costo_total
    }


# VALIDACION DE TOPOLOGIAS

@app.post("/api/topologias/validar")
def validar_topologia(solicitud: SolicitudTopologia):

    try:
        resultado = validar_topologia_datos(
            nodos=solicitud.nodos,
            enlaces=[
                enlace.model_dump(exclude_none=True)
                for enlace in solicitud.enlaces
            ],
            dirigido=solicitud.dirigido
        )

    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    return {
        "estado": "topologia_valida",
        "nombre": solicitud.nombre,
        **resultado
    }

