"""Detiene exclusivamente los servidores propios que se identifican en el registro."""
from pathlib import Path
import sys

from gestion_windows import GestionError, Gestor


def main():
    try:
        estado = Gestor(Path(__file__).resolve().parent).detener()
    except GestionError as error:
        print("NO SE COMPLETO EL CIERRE: " + str(error), flush=True)
        return 1
    if estado["estado"] == "sin_ejecucion":
        print("No hay servidores registrados de esta interfaz.", flush=True)
    else:
        print("No quedan servidores propios identificados en esta ejecucion.", flush=True)
        if estado.get("pid_conservados"):
            print("Se conservaron PID que ya no coinciden con la identidad guardada: " + ", ".join(map(str, estado["pid_conservados"])), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
