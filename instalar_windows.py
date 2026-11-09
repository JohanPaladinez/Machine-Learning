"""Crea un entorno propio, instala y compila; no modifica Mininet ni RYU."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    if os.name != "nt" or sys.version_info < (3, 10):
        raise SystemExit("Este instalador necesita Windows y Python 3.10 o posterior")
    if not (ROOT / "PROYECTO_WINDOWS.json").is_file():
        raise SystemExit("No se reconoce la carpeta de la interfaz Windows")
    node = shutil.which("node.exe")
    if not node:
        raise SystemExit("Falta Node.js. Instala una version LTS compatible y repite este archivo")
    version = subprocess.check_output([node, "--version"], text=True).strip()
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", version)
    values = tuple(map(int, match.groups())) if match else (0, 0, 0)
    if not (values >= (22, 12, 0) or (20, 19, 0) <= values < (21, 0, 0)):
        raise SystemExit("Node no satisface los requisitos de Vite 8: " + version)
    npm = Path(node).resolve().parent / "node_modules/npm/bin/npm-cli.js"
    if not npm.is_file():
        raise SystemExit("No se encuentra npm junto a Node: " + str(npm))
    entorno = ROOT / ".venv"
    python = entorno / "Scripts/python.exe"
    if not python.is_file():
        print("1/4 Creando entorno Python...", flush=True)
        subprocess.run([sys.executable, "-m", "venv", str(entorno)], check=True)
    print("2/4 Instalando dependencias del backend...", flush=True)
    subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r",
                    str(ROOT / "requirements-windows.txt")], check=True)
    with (ROOT / "requirements.installed.txt").open("w", encoding="utf-8") as salida:
        subprocess.run([str(python), "-m", "pip", "freeze"], stdout=salida, check=True)
    frontend = ROOT / "frontend/app"
    environment = dict(os.environ, PATH=str(Path(node).parent) + os.pathsep + os.environ.get("PATH", ""), VITE_SDN_SELECTOR_API_URL="http://127.0.0.1:8003")
    print("3/4 Instalando dependencias del panel...", flush=True)
    command = "ci" if (frontend / "package-lock.json").is_file() else "install"
    subprocess.run([node, str(npm), command, "--no-audit", "--no-fund"], cwd=str(frontend), env=environment, check=True)
    print("4/4 Compilando la interfaz...", flush=True)
    subprocess.run([node, str(npm), "run", "build", "--", "--config", "vite.sdn-selector.config.js"], cwd=str(frontend), env=environment, check=True)
    (ROOT / "entorno-windows.json").write_text(json.dumps({
        "python": str(python), "node": str(Path(node).resolve()), "node_version": version,
    }, indent=2), encoding="utf-8")
    print("INSTALACION Y COMPILACION COMPLETADAS", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit("Instalacion pendiente: " + str(error))
