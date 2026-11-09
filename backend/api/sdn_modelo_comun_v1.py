
import json
from urllib.request import urlopen
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/sdn/ml", tags=["Modelo comun ML"])
SERVICIO = "http://192.168.56.108:8010"

def consultar(ruta):
    try:
        with urlopen(SERVICIO + ruta, timeout=5) as respuesta:
            contenido = respuesta.read(1048577)
        if len(contenido) > 1048576:
            raise ValueError("Respuesta demasiado grande")
        datos = json.loads(contenido.decode("utf-8"))
        if not isinstance(datos, dict):
            raise ValueError("Respuesta inesperada")
        return datos
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="El servicio del modelo en RYU no responde correctamente."
        )

@router.get("/estado")
def estado_modelo():
    datos = consultar("/health")
    if not (
        datos.get("estado") == "modelo_cargado"
        and datos.get("features") == 60
        and datos.get("targets") == 6
        and datos.get("evaluacion") == "test_completado"
    ):
        raise HTTPException(
            status_code=502,
            detail="El servicio no confirma el modelo evaluado esperado."
        )
    return {
        "estado": "disponible",
        "modelo_id": datos.get("modelo_id"),
        "features": datos["features"],
        "targets": datos["targets"],
        "evaluacion": datos["evaluacion"]
    }

@router.get("/evaluacion")
def evaluacion_guardada():
    return consultar("/evaluacion")

@router.get("/esquema")
def esquema_modelo():
    return consultar("/schema")
