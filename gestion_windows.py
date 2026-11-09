"""Ciclo de vida del servidor local de API y panel en Windows."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import ProxyHandler, build_opener
import uuid
import webbrowser

import psutil


class GestionError(RuntimeError):
    pass


def normalizar(path):
    return os.path.normcase(os.path.realpath(os.fspath(path)))


def dentro(path, parent):
    try:
        return os.path.commonpath([normalizar(path), normalizar(parent)]) == normalizar(parent)
    except (ValueError, TypeError):
        return False


def instante():
    return datetime.now(timezone.utc).isoformat()


class Gestor:
    def __init__(self, proyecto, process_factory=psutil.Process, popen=subprocess.Popen):
        self.proyecto = Path(proyecto).resolve()
        self.frontend = self.proyecto / "frontend" / "app"
        self.runtime = self.proyecto / ".ejecucion_windows"
        self.archivo_estado = self.runtime / "estado.json"
        self.python = self.proyecto / ".venv" / "Scripts" / "python.exe"
        self.proceso = process_factory
        self.popen = popen
        self.creados = []

    def python_permitidos(self):
        valores = {normalizar(self.python), normalizar(sys.executable)}
        base = getattr(sys, "_base_executable", None)
        if base:
            valores.add(normalizar(base))
        cfg = self.proyecto / ".venv" / "pyvenv.cfg"
        try:
            for linea in cfg.read_text(encoding="utf-8").splitlines():
                clave, _, valor = linea.partition("=")
                if clave.strip() == "executable" and valor.strip():
                    valores.add(normalizar(valor.strip()))
                elif clave.strip() == "home" and valor.strip():
                    valores.add(normalizar(Path(valor.strip()) / "python.exe"))
        except OSError:
            pass
        return valores

    @contextmanager
    def bloqueo(self):
        if os.name != "nt":
            raise GestionError("Estos lanzadores se ejecutan en Windows.")
        import msvcrt
        self.runtime.mkdir(parents=True, exist_ok=True)
        with (self.runtime / "gestor.lock").open("a+b") as archivo:
            archivo.seek(0, 2)
            if archivo.tell() == 0:
                archivo.write(b"0")
                archivo.flush()
            archivo.seek(0)
            try:
                msvcrt.locking(archivo.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise GestionError("Ya hay otra accion de inicio o cierre en curso. Espera a que termine.") from error
            try:
                yield
            finally:
                archivo.seek(0)
                msvcrt.locking(archivo.fileno(), msvcrt.LK_UNLCK, 1)

    def leer_estado(self):
        if not self.archivo_estado.exists():
            return None
        try:
            estado = json.loads(self.archivo_estado.read_text(encoding="utf-8"))
            if (estado.get("schema_version") != 1 or normalizar(estado["proyecto"]) != normalizar(self.proyecto)
                    or not isinstance(estado.get("sesion"), str) or not estado["sesion"]
                    or not isinstance(estado.get("componentes"), dict)):
                raise ValueError("Estado de otra instalacion")
            carpeta = Path(estado["carpeta"])
            if normalizar(carpeta.parent) != normalizar(self.runtime) or not carpeta.name.startswith("sesion_"):
                raise ValueError("Carpeta de ejecucion fuera del proyecto")
            return estado
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise GestionError("El registro de ejecucion no se puede verificar. Se conserva sin detener procesos: " + str(self.archivo_estado)) from error

    def guardar_estado(self, estado):
        estado["actualizado_utc"] = instante()
        self.runtime.mkdir(parents=True, exist_ok=True)
        carpeta = Path(estado["carpeta"])
        if normalizar(carpeta.parent) != normalizar(self.runtime):
            raise GestionError("Carpeta de ejecucion invalida.")
        for destino in (carpeta / "estado.json", self.archivo_estado):
            temporal = destino.with_name(destino.name + ".tmp_" + uuid.uuid4().hex)
            with temporal.open("x", encoding="utf-8") as archivo:
                json.dump(estado, archivo, ensure_ascii=True, indent=2, allow_nan=False)
                archivo.write("\n")
            os.replace(str(temporal), str(destino))

    def capturar(self, proceso):
        return {"pid": int(proceso.pid), "create_time": float(proceso.create_time()),
                "exe": str(proceso.exe()), "cwd": str(proceso.cwd()), "cmdline": list(proceso.cmdline())}

    def contexto_propio(self, registro, componente, sesion):
        try:
            if (int(registro["pid"]) <= 1 or not math.isfinite(float(registro["create_time"]))
                    or not isinstance(registro["cmdline"], list)):
                return False
            args = registro["cmdline"]
            rutas = {normalizar(v) for v in args if isinstance(v, str) and v}
            if componente == "api":
                if (normalizar(registro["exe"]) not in self.python_permitidos()
                        or normalizar(registro["cwd"]) != normalizar(self.proyecto)
                        or normalizar(self.proyecto / "servir_api_windows.py") not in rutas):
                    return False
                return "--sesion" in args and args[args.index("--sesion") + 1] == sesion
            return False
        except (ValueError, TypeError, KeyError, IndexError, OSError):
            return False

    def verificar(self, registro, componente, sesion):
        if not self.contexto_propio(registro, componente, sesion):
            return None
        try:
            actual = self.proceso(int(registro["pid"]))
            observado = self.capturar(actual)
            if (abs(observado["create_time"] - float(registro["create_time"])) > 0.001
                    or normalizar(observado["exe"]) != normalizar(registro["exe"])
                    or normalizar(observado["cwd"]) != normalizar(registro["cwd"])
                    or observado["cmdline"] != registro["cmdline"]):
                return None
            return actual
        except (psutil.Error, OSError, ValueError, TypeError, KeyError):
            return None

    def refrescar_arboles(self, estado):
        for nombre, componente in estado["componentes"].items():
            registros = componente.setdefault("procesos", [])
            conocidos = {(p["pid"], p["create_time"]) for p in registros}
            for registro in list(registros):
                padre = self.verificar(registro, nombre, estado["sesion"])
                if padre is None:
                    continue
                try:
                    hijos = padre.children(recursive=True)
                except psutil.Error:
                    continue
                for hijo in hijos:
                    try:
                        identidad = self.capturar(hijo)
                        clave = (identidad["pid"], identidad["create_time"])
                        if clave not in conocidos and self.contexto_propio(identidad, nombre, estado["sesion"]):
                            identidad["profundidad"] = int(registro.get("profundidad", 0)) + 1
                            registros.append(identidad)
                            conocidos.add(clave)
                    except (psutil.Error, OSError, ValueError):
                        continue

    def vivos(self, estado, nombre=None):
        resultado = []
        for componente, datos in estado.get("componentes", {}).items():
            if nombre is not None and componente != nombre:
                continue
            for registro in datos.get("procesos", []):
                actual = self.verificar(registro, componente, estado["sesion"])
                if actual is not None:
                    resultado.append((componente, registro, actual))
        return resultado

    def comprobar_puertos(self):
        for puerto in (8003,):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as prueba:
                try:
                    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                        prueba.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                    prueba.bind(("127.0.0.1", puerto))
                except OSError as error:
                    raise GestionError("No se puede reservar el puerto local {}. Puede estar ocupado o bloqueado; no se detuvo ningun servicio ajeno. Detalle: {}".format(puerto, error)) from error

    def comprobar_archivos(self):
        archivos = (self.python, self.proyecto / "servir_api_windows.py",
                    self.proyecto / "backend/api/sdn_selector_v2.py",
                    self.frontend / "dist-sdn-selector-v2/sdn-selector.html")
        for archivo in archivos:
            if not archivo.is_file():
                raise GestionError("Falta un archivo de la instalacion: {}. Ejecuta primero el instalador de esta carpeta.".format(archivo))

    def comprobar_http(self):
        cliente = build_opener(ProxyHandler({}))
        try:
            with cliente.open("http://127.0.0.1:8003/api/windows/salud", timeout=1.5) as respuesta:
                salud = json.loads(respuesta.read(65536).decode("utf-8"))
            if salud.get("estado") != "ok" or salud.get("servicio") != "SDN/KDN Windows Rutas ML":
                return False
            if salud.get("criterios_comparacion") != ["hops", "delay", "capacity", "ml"]:
                return False
            with cliente.open("http://127.0.0.1:8003/sdn-selector.html", timeout=1.5) as respuesta:
                pagina = respuesta.read(131072).decode("utf-8")
            return 'id="root"' in pagina and "SDN / KDN" in pagina
        except (OSError, ValueError, UnicodeError):
            return False

    def detener_estado(self, estado):
        self.refrescar_arboles(estado)
        registros = self.vivos(estado)
        registros.sort(key=lambda item: item[1].get("profundidad", 0), reverse=True)
        preservados = []
        for nombre, datos in estado["componentes"].items():
            for registro in datos.get("procesos", []):
                if self.verificar(registro, nombre, estado["sesion"]) is None and psutil.pid_exists(int(registro.get("pid", -1))):
                    preservados.append(int(registro["pid"]))
        for nombre, registro, proceso in registros:
            actual = self.verificar(registro, nombre, estado["sesion"])
            if actual is not None:
                try:
                    actual.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        limite = time.monotonic() + 5
        while time.monotonic() < limite and self.vivos(estado):
            time.sleep(0.1)
        for nombre, registro, _ in self.vivos(estado):
            actual = self.verificar(registro, nombre, estado["sesion"])
            if actual is not None:
                try:
                    actual.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        limite = time.monotonic() + 3
        while time.monotonic() < limite and self.vivos(estado):
            time.sleep(0.1)
        quedan = self.vivos(estado)
        estado.update(estado="cierre_pendiente" if quedan else "detenido", pid_conservados=sorted(set(preservados)))
        self.guardar_estado(estado)
        if quedan:
            raise GestionError("Algun proceso propio sigue cerrandose. Revisa los registros antes de volver a iniciar.")
        return estado

    def detener(self):
        with self.bloqueo():
            estado = self.leer_estado()
            if estado is None:
                return {"estado": "sin_ejecucion", "pid_conservados": []}
            return self.detener_estado(estado)

    def iniciar(self, abrir_navegador=True):
        with self.bloqueo():
            self.comprobar_archivos()
            anterior = self.leer_estado()
            if anterior:
                self.refrescar_arboles(anterior)
                if self.vivos(anterior, "api") and self.comprobar_http():
                    anterior["estado"] = "en_marcha"
                    self.guardar_estado(anterior)
                    if abrir_navegador:
                        webbrowser.open("http://127.0.0.1:8003/sdn-selector.html", new=2)
                    return anterior
                if self.vivos(anterior):
                    self.detener_estado(anterior)
            self.comprobar_puertos()
            sesion = uuid.uuid4().hex
            carpeta = self.runtime / ("sesion_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_") + sesion[:8])
            carpeta.mkdir(parents=True, exist_ok=False)
            estado = {"schema_version": 1, "proyecto": str(self.proyecto), "sesion": sesion,
                      "carpeta": str(carpeta), "estado": "iniciando", "creado_utc": instante(), "componentes": {}}
            self.guardar_estado(estado)
            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1")
            comandos = (
                ("api", [str(self.python), "-u", str(self.proyecto / "servir_api_windows.py"), "--sesion", sesion], self.proyecto),
            )
            self.creados = []
            try:
                for nombre, comando, cwd in comandos:
                    log = carpeta / (nombre + ".log")
                    with log.open("xb") as salida:
                        proceso = self.popen(comando, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                            stdout=salida, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
                    self.creados.append(proceso)
                    estado["componentes"][nombre] = {"pid": proceso.pid, "registro": str(log), "procesos": []}
                    limite_identidad = time.monotonic() + 3
                    while time.monotonic() < limite_identidad:
                        if proceso.poll() is not None:
                            raise GestionError("El servidor {} termino al arrancar. Revisa {}".format(nombre, log))
                        try:
                            identidad = self.capturar(self.proceso(proceso.pid))
                            if self.contexto_propio(identidad, nombre, sesion):
                                identidad["profundidad"] = 0
                                estado["componentes"][nombre]["procesos"].append(identidad)
                                break
                        except (psutil.Error, OSError, ValueError):
                            pass
                        time.sleep(0.05)
                    else:
                        raise GestionError("No se pudo identificar de forma segura el servidor " + nombre)
                    self.refrescar_arboles(estado)
                    self.guardar_estado(estado)
                limite = time.monotonic() + 25
                while time.monotonic() < limite:
                    self.refrescar_arboles(estado)
                    self.guardar_estado(estado)
                    if not self.vivos(estado, "api"):
                        raise GestionError("El servidor termino antes de estar listo. Registros: " + str(carpeta))
                    if self.comprobar_http():
                        estado["estado"] = "en_marcha"
                        self.guardar_estado(estado)
                        if abrir_navegador:
                            webbrowser.open("http://127.0.0.1:8003/sdn-selector.html", new=2)
                        return estado
                    time.sleep(0.2)
                raise GestionError("El servicio local no respondio a tiempo. Pueden existir restricciones de red local. Registros: " + str(carpeta))
            except Exception as error:
                try:
                    self.detener_estado(estado)
                finally:
                    # Los handles de Popen solo pertenecen a procesos que este inicio creo.
                    for proceso in self.creados:
                        if proceso.poll() is None:
                            try:
                                proceso.terminate()
                                proceso.wait(timeout=3)
                            except (OSError, subprocess.TimeoutExpired):
                                pass
                    estado.update(estado="error", error=str(error))
                    self.guardar_estado(estado)
                if isinstance(error, GestionError):
                    raise
                raise GestionError("No se completo el arranque: {}. Registros: {}".format(error, carpeta)) from error
