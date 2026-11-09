
import importlib.util
import json
import math
import os
import re
import signal
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True
from sdn_noche_capturar import Captura
from sdn_noche_comun import SampleUnavailable, fecha, guardar_json, iso


class RecolectorVivo(Captura):
    def medir(self, *args, **kwargs):
        # La cuota temporal pertenece a la campana; las mediciones se conservan iguales.
        self.inicio = time.monotonic()
        return super().medir(*args, **kwargs)


def http(url, datos=None, timeout=8):
    cuerpo = None if datos is None else json.dumps(datos, allow_nan=False).encode("utf-8")
    req = Request(url, data=cuerpo, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as respuesta:
            contenido = respuesta.read(4 * 1024 * 1024 + 1)
        if len(contenido) > 4 * 1024 * 1024:
            raise ValueError("Respuesta demasiado grande")
        return json.loads(contenido.decode("utf-8"))
    except HTTPError as error:
        raise ValueError("HTTP {}: {}".format(error.code, error.read(1024).decode("utf-8", "replace")))


def construir_metricas(actual, enlaces, sesion, requeridas):
    inicio, fin = fecha(actual["start"]).timestamp(), fecha(actual["end"]).timestamp()
    if inicio >= fin:
        raise SampleUnavailable("Ventana temporal invalida")
    resultado = {}
    for indice, enlace in enumerate(enlaces):
        entrada = actual["features"][indice]
        if set(entrada) != set(requeridas):
            raise SampleUnavailable("Faltan entradas del modelo")
        entrada = {k: float(v) for k, v in entrada.items()}
        if any(not math.isfinite(v) or v < 0 for v in entrada.values()):
            raise SampleUnavailable("Entrada no finita o negativa")
        direcciones = {}
        for sentido, receptor in (("u_to_v", "v"), ("v_to_u", "u")):
            sonda = actual["probes"][(enlace["link_id"], sentido)]
            valores = {"throughput_mbps": actual["sides"][indice][receptor]["rx_mbps"],
                       "delay_ms": sonda["delay_avg_ms"], "loss_ratio": sonda["loss_ratio"]}
            if any(v is None or not math.isfinite(v) or v < 0 for v in valores.values()) or valores["loss_ratio"] > 1:
                raise SampleUnavailable("Medicion invalida")
            valores.update({k: sonda[k] for k in (
                "sent", "accepted", "received", "tx_refused_enobufs", "tx_refused_busy")})
            direcciones[sentido] = valores
        resultado[enlace["link_id"]] = {
            "directions": direcciones,
            "method": "af_packet_offered_probes_tx_status_kernel_rx_v3",
            "loss_scope": "offered_including_local_tx_refusals",
            "ml": {"status": "inputs_ready", "session_id": sesion, "topologia": "nsfnet",
                   "link_id": enlace["link_id"], "feature_start_epoch_s": inicio,
                   "feature_end_epoch_s": fin, "features": entrada}}
    return {"status": "fresh", "links": resultado, "window_start": actual["start"],
            "window_end": actual["end"], "age_s": 0, "source": "telemetria_en_vivo",
            "note": "Sondas del recolector y trafico UDP controlado; no son datos historicos."}


def validar_prediccion(respuesta, entrada, objetivos, modelo_id):
    for campo in ("session_id", "topologia", "link_id", "feature_start_epoch_s", "feature_end_epoch_s"):
        if respuesta.get(campo) != entrada[campo]:
            raise ValueError("La prediccion no corresponde a esta ventana: " + campo)
    if respuesta.get("modelo_id") != modelo_id:
        raise ValueError("Cambio el modelo de inferencia")
    valores = respuesta.get("predicciones")
    if not isinstance(valores, dict) or set(valores) != set(objetivos):
        raise ValueError("Salidas de prediccion inesperadas")
    for nombre, valor in valores.items():
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or valor < 0:
            raise ValueError("Prediccion no valida")
        if nombre.endswith("_loss_ratio") and valor > 1:
            raise ValueError("Perdida predicha fuera de rango")
    return respuesta


def redes_anteriores():
    errores = []
    for url, limite in (("http://192.168.56.103:8768/snapshot", 1.2),
                        ("http://192.168.56.103:8767/snapshot", 0.6)):
        try:
            anterior = http(url, timeout=limite)
            if anterior.get("observer_version") != "sdn-vivo-1":
                raise ValueError("Version de observador inesperada")
            redes = anterior.get("networks")
            if not isinstance(redes, list) or any(not isinstance(r, dict) for r in redes):
                raise ValueError("Lista de sesiones invalida")
            errores.extend(str(e) for e in anterior.get("errors", []))
            return redes, errores
        except Exception as error:
            errores.append(url + ": " + str(error))
    return [], errores


def unir_redes(redes, propia, errores):
    resultado, vistas = [], set()
    for red in list(redes) + ([propia] if propia else []):
        clave = (red.get("session_id"), red.get("topology_instance_id"))
        if any(not isinstance(v, str) or not v for v in clave):
            errores.append("Se omite una sesion sin identidad completa")
            continue
        if clave not in vistas:
            vistas.add(clave)
            resultado.append(red)
    return resultado


def candidata_nsfnet(observador, carpeta, perfil, enlaces, cfg, fase, metricas, activa):
    red = observador.candidate(carpeta.name, "nsfnet", perfil, enlaces,
        {"ip": cfg["ryu_ip"], "of_port": cfg["of_port"], "rest_url": cfg["rest_url"]},
        capture={"state": fase, "alive": activa, "session_id": carpeta.name})
    if red:
        # El observador original usa nc/nh para capturas. Esta instancia usa ns/nsh.
        for nodo in red["topology_document"]["topologies"]["nsfnet"]["nodes"]:
            nodo["runtime_switch"] = "ns" + nodo["switch"][1:]
            nodo["host"] = "nsh" + nodo["switch"][1:]
        if metricas.get("window_end"):
            edad = time.time() - fecha(metricas["window_end"]).timestamp()
            metricas.update(age_s=round(edad, 3), status="fresh" if 0 <= edad <= 120 else "stale")
        red.update(source_kind="instrumented", metrics=metricas)
    return red


def main(carpeta):
    cfg = json.loads((carpeta / "config.json").read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("observador_base", cfg["observer_file"])
    observador_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(observador_mod)
    observador = observador_mod.Observer(cfg["project"])
    captura = RecolectorVivo(str(carpeta))
    parar, bloqueo = threading.Event(), threading.RLock()
    estado = {"estado": "iniciando", "pid": os.getpid(), "carpeta": str(carpeta)}
    datos = {"profile": None, "links": [], "metrics": {"status": "unavailable", "links": {}}}
    servidor, hilo = None, None
    for senal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(senal, lambda *_: parar.set())
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    def publicar(fase, **extra):
        with bloqueo:
            estado.update(estado=fase, actualizado_utc=iso(), **extra)
            guardar_json(str(carpeta / "estado.json"), estado)
        print(fase, json.dumps(extra, ensure_ascii=True), flush=True)

    def snapshot():
        redes, errores = redes_anteriores()
        with bloqueo:
            perfil, enlaces = datos["profile"], datos["links"]
            metricas = json.loads(json.dumps(datos["metrics"], allow_nan=False))
            fase = estado["estado"]
        propia = candidata_nsfnet(observador, carpeta, perfil, enlaces, cfg, fase,
                                  metricas, not parar.is_set()) if perfil is not None else None
        redes = unir_redes(redes, propia, errores)
        salida = {"schema_version": 1, "observer_version": "sdn-vivo-1", "observed_utc": iso(),
                  "read_only": True, "collector_generates_traffic": True, "networks": redes,
                  "errors": errores, "candidates": [{"session_id": r["session_id"], "topologia": r["topologia"]} for r in redes]}
        if len(redes) == 1:
            salida.update(redes[0], status="observed")
        else:
            salida.update(status="ambiguous" if redes else "inactive",
                          message="Selecciona topologia y sesion; hay una NSFNET principal y otra instrumentada.")
        return salida

    class Servidor(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                if self.path == "/health":
                    cuerpo = {"status": "ok", "observer_version": "sdn-vivo-1", "read_only": True,
                              "collector_generates_traffic": True}
                elif self.path == "/snapshot":
                    cuerpo = snapshot()
                else:
                    self.send_error(404)
                    return
                contenido = json.dumps(cuerpo, ensure_ascii=True, allow_nan=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(contenido)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(contenido)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                traceback.print_exc()
                self.send_error(503)

        def log_message(self, *args):
            pass

    try:
        publicar("comprobando_servicios")
        esquema = http(cfg["model_url"] + "/schema")
        salud = http(cfg["model_url"] + "/health")
        if set(esquema["features"]) != set(cfg["features"]) or len(esquema["features"]) != 60 or set(esquema["targets"]) != set(cfg["targets"]):
            raise ValueError("El modelo y el recolector tienen esquemas distintos")
        if salud.get("modelo_id") != cfg["model_id"] or salud.get("evaluacion") != "test_completado":
            raise ValueError("El modelo esperado no esta disponible y evaluado")
        if http(cfg["rest_url"] + "/stats/switches") != []:
            raise ValueError("El controlador dedicado ya tiene switches; no se modifican sus reglas")
        ocupadas = [p.name for p in Path("/sys/class/net").iterdir()
                    if re.fullmatch(r"ns[0-9]+(?:-eth[0-9]+)?", p.name)]
        if ocupadas:
            raise ValueError("Ya hay interfaces de otra NSFNET instrumentada: " + ", ".join(ocupadas))
        for nodo in cfg["topologies"]["nsfnet"]["nodes"]:
            nombre = "ns" + nodo["switch"][1:]
            comprobacion = subprocess.run(["ovs-vsctl", "br-exists", nombre],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if comprobacion.returncode == 0:
                raise ValueError("Ya existe el bridge " + nombre + "; se conserva")
            if comprobacion.returncode != 2:
                raise ValueError("No se pudo consultar OVS: " + comprobacion.stderr.decode("utf-8", "replace"))
        servidor = Servidor(("192.168.56.103", 8769), Handler)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        publicar("creando_nsfnet")
        perfil, enlaces, caminos = captura.crear_red("nsfnet")
        with bloqueo:
            datos.update(profile=perfil, links=enlaces)
        semilla = int(time.time() * 1000)
        while str(semilla) in captura.semillas_usadas:
            semilla += 1
        carga, nivel = captura.plan(perfil, caminos, 0, semilla, baja=True)
        publicar("midiendo_nsfnet", enlaces=len(enlaces), nivel_ofrecido=nivel, semilla=semilla)
        numero, fallos, primera = 0, 0, None
        while not parar.is_set():
            numero += 1
            try:
                actual = captura.medir(perfil, enlaces, 20.0, numero, carga)
                metricas = construir_metricas(actual, enlaces, carpeta.name, cfg["features"])
            except SampleUnavailable as error:
                fallos += 1
                with bloqueo:
                    datos["metrics"] = {"status": "unavailable", "links": {}}
                publicar("ventana_descartada", motivo=str(error), fallos=fallos, ready=False)
                if fallos >= 6:
                    raise ValueError("Seis ventanas invalidas; se cierra solo esta sesion")
                parar.wait(1)
                continue
            fallos = 0
            if primera is None or primera.get("estado") != "ok":
                try:
                    entrada = dict(metricas["links"][enlaces[0]["link_id"]]["ml"])
                    entrada.pop("status")
                    respuesta = validar_prediccion(http(cfg["model_url"] + "/predict", entrada),
                        entrada, cfg["targets"], cfg["model_id"])
                    primera = {"estado": "ok", "link_id": entrada["link_id"], "modelo_id": respuesta["modelo_id"],
                               "predicciones": respuesta["predicciones"], "feature_end_epoch_s": entrada["feature_end_epoch_s"]}
                except Exception as error:
                    primera = {"estado": "error", "detalle": str(error)}
            with bloqueo:
                datos["metrics"] = metricas
            guardar_json(str(carpeta / "ventana_actual.json"), metricas)
            publicar("telemetria_nsfnet", ready=True, ventana=numero, enlaces_con_60_entradas=len(enlaces),
                     prediction_ready=primera.get("estado") == "ok",
                     primera_prediccion=primera, ultimo_fin=actual["end"])
    except Exception as error:
        publicar("error", ready=False, error=str(error))
        traceback.print_exc()
    finally:
        parar.set()
        try:
            captura.cerrar_red()
        finally:
            if servidor:
                if hilo:
                    servidor.shutdown()
                servidor.server_close()
            if estado["estado"] != "error":
                publicar("detenido", ready=False)


if __name__ == "__main__":
    if os.geteuid() != 0:
        raise SystemExit("Se requiere sudo para Mininet y las sondas de medicion")
    main(Path(sys.argv[1]).resolve())
