"""Arranca el servicio local y abre el panel en el navegador de Windows."""
import argparse
from pathlib import Path
import sys

from gestion_windows import GestionError, Gestor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sin-navegador", action="store_true")
    args = parser.parse_args()
    gestor = Gestor(Path(__file__).resolve().parent)
    try:
        estado = gestor.iniciar(abrir_navegador=not args.sin_navegador)
    except GestionError as error:
        print("NO SE COMPLETO EL INICIO: " + str(error), flush=True)
        return 1
    print("INTERFAZ LOCAL EN MARCHA", flush=True)
    print("Panel: http://127.0.0.1:8003/sdn-selector.html", flush=True)
    print("API: http://127.0.0.1:8003", flush=True)
    print("Registros: " + estado["carpeta"], flush=True)
    print("Los estados de Mininet y RYU se comprueban por separado en el panel.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
