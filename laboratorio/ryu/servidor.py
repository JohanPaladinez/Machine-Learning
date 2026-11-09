import json
import math
import os
import sys
import time
import traceback
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

import joblib
import numpy as np

ruta = Path(sys.argv[1]).resolve()
paquete = joblib.load(str(ruta))
modelo = paquete["modelo"]
features = paquete["features"]
targets = paquete["targets"]
modelo_id = ruta.parent.name

if len(features) != 60 or len(targets) != 6:
    raise RuntimeError("Esquema inesperado del modelo")

with (ruta.parent / "evaluacion_test.json").open(
    encoding="utf-8"
) as archivo:
    evaluacion = json.load(archivo)

if evaluacion["dataset_sha256"] != paquete["dataset_sha256"]:
    raise RuntimeError("Modelo y evaluacion pertenecen a datasets distintos")


class EntradaInvalida(ValueError):
    pass


def numero(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise EntradaInvalida("Se requieren valores numericos")
    try:
        resultado = float(valor)
    except (ValueError, OverflowError):
        raise EntradaInvalida("Valor numerico invalido")
    if not math.isfinite(resultado):
        raise EntradaInvalida("No se permiten NaN ni infinitos")
    return resultado


def validar(datos):
    if not isinstance(datos, dict):
        raise EntradaInvalida("El cuerpo debe ser un objeto JSON")

    topologia = datos.get("topologia")
    if not isinstance(topologia, str):
        raise EntradaInvalida("Falta topologia")
    topologia = topologia.lower()
    if topologia not in ("nsfnet", "geant2"):
        raise EntradaInvalida("Topologia no admitida")

    for campo in ("session_id", "link_id"):
        valor = datos.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            raise EntradaInvalida("Falta " + campo)

    inicio = numero(datos.get("feature_start_epoch_s"))
    fin = numero(datos.get("feature_end_epoch_s"))
    edad = time.time() - fin
    if inicio >= fin or edad < -5 or edad > 120:
        raise EntradaInvalida("Ventana invalida, antigua o reloj desajustado")

    entrada = datos.get("features")
    if not isinstance(entrada, dict):
        raise EntradaInvalida("Falta el objeto features")

    faltantes = [nombre for nombre in features if nombre not in entrada]
    adicionales = sorted(set(entrada) - set(features))
    if faltantes or adicionales:
        raise EntradaInvalida(
            "Faltantes: {}; adicionales: {}".format(faltantes, adicionales)
        )

    fila = [numero(entrada[nombre]) for nombre in features]
    if any(valor < 0 for valor in fila):
        raise EntradaInvalida("Las variables deben ser no negativas")
    return topologia, inicio, fin, fila


class API(BaseHTTPRequestHandler):
    def enviar(self, codigo, contenido):
        cuerpo = json.dumps(
            contenido, ensure_ascii=True, allow_nan=False
        ).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        ruta_http = self.path.split("?", 1)[0]
        if ruta_http == "/health":
            self.enviar(200, {
                "estado": "modelo_cargado",
                "modelo_id": modelo_id,
                "features": len(features),
                "targets": len(targets),
                "evaluacion": "test_completado",
                "pid": os.getpid()
            })
        elif ruta_http == "/schema":
            self.enviar(200, {
                "features": features,
                "targets": targets,
                "campos_contexto": [
                    "topologia", "session_id", "link_id",
                    "feature_start_epoch_s", "feature_end_epoch_s"
                ],
                "antiguedad_maxima_s": 120
            })
        elif ruta_http == "/evaluacion":
            self.enviar(200, {
                "modelo_id": modelo_id,
                "test": evaluacion["test"]
            })
        else:
            self.enviar(404, {"error": "Ruta inexistente"})

    def do_POST(self):
        if self.path != "/predict":
            self.enviar(404, {"error": "Ruta inexistente"})
            return
        try:
            self.connection.settimeout(10)
            try:
                longitud = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise EntradaInvalida("Content-Length invalido")
            if not 0 < longitud <= 65536:
                raise EntradaInvalida("Tamano de solicitud invalido")

            datos = json.loads(self.rfile.read(longitud).decode("utf-8"))
            topologia, inicio, fin, fila = validar(datos)
            salida = np.asarray(
                modelo.predict(np.asarray([fila], dtype=float)),
                dtype=float
            )
            if salida.shape != (1, len(targets)):
                raise RuntimeError("Forma de prediccion inesperada")

            predicciones = {}
            for nombre, valor in zip(targets, salida[0]):
                valor = float(valor)
                if not math.isfinite(valor) or valor < 0:
                    raise RuntimeError("Prediccion invalida")
                if nombre.endswith("_loss_ratio") and valor > 1:
                    raise RuntimeError("Perdida fuera de rango")
                predicciones[nombre] = valor

            self.enviar(200, {
                "modelo_id": modelo_id,
                "topologia": topologia,
                "session_id": datos["session_id"],
                "link_id": datos["link_id"],
                "feature_start_epoch_s": inicio,
                "feature_end_epoch_s": fin,
                "objetivo": "siguiente_ventana",
                "predicciones": predicciones
            })
        except (EntradaInvalida, UnicodeDecodeError, json.JSONDecodeError) as error:
            self.enviar(422, {"error": str(error)})
        except Exception:
            traceback.print_exc()
            self.enviar(500, {"error": "No se pudo calcular la prediccion"})


servidor = HTTPServer(("192.168.56.108", 8010), API)
print("MODELO DISPONIBLE: http://192.168.56.108:8010", flush=True)
servidor.serve_forever()
