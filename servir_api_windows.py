"""API y panel del repositorio revisado, ejecutados en Windows."""
import argparse
import json
import os
from pathlib import Path
import sys


def crear_app(raiz):
    configuracion = json.loads((raiz / "configuracion_windows.json").read_text(encoding="utf-8"))
    for nombre, valor in configuracion.items():
        if not nombre.startswith("SDN_") or not isinstance(valor, str):
            raise ValueError("Configuracion Windows inesperada")
        os.environ[nombre] = valor
    os.environ["SDN_MININET_URL"] = ""
    from fastapi.staticfiles import StaticFiles
    from backend.api import sdn_selector_v2 as selector
    from backend.servicios.comparacion_rutas import CRITERIA
    aplicacion = selector.original.original_app
    from backend.api.sdn_cinco_modelos import router as cinco_router
    aplicacion.include_router(cinco_router)

    @aplicacion.get("/api/windows/salud")
    def salud_windows():
        return {"estado": "ok", "servicio": "SDN/KDN Windows Rutas ML", "version": "1.2.0",
                "comparacion_modelos_version": 1,
                "criterios_comparacion": list(CRITERIA)}

    aplicacion.mount("/", StaticFiles(directory=str(raiz / "frontend/app/dist-sdn-selector-v2"), html=True), name="panel_windows")
    return selector.app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sesion", required=True)
    parser.parse_args()
    raiz = Path(__file__).resolve().parent
    os.chdir(raiz)
    sys.path.insert(0, str(raiz))
    import uvicorn
    uvicorn.run(crear_app(raiz), host="127.0.0.1", port=8003,
                log_level="info", access_log=False, workers=1, reload=False)


if __name__ == "__main__":
    main()
