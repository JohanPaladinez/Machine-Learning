#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Predictor comun NSFNET/GEANT2. Compatible por API con Python 3.6/sklearn 0.24.

Preparar este archivo no inicia entrenamiento. El comando entrenar exige el
dataset final y su resumen_final.json. No modifica los modelos anteriores.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import platform
import sys
import tempfile

FEATURES = [
    "capacity_mbps", "configured_delay_ms", "queue_limit_packets", "queue_budget_packets",
    "propagation_budget_packets", "offered_u_to_v_mbps", "offered_v_to_u_mbps",
    "traffic_datagram_bytes", "cpu_busy_fraction", "mem_available_kb",
    "cpu_peak_core_fraction", "swap_used_kb"
]
for _lado in ("u", "v"):
    FEATURES.append(_lado+"_interval_s")
    FEATURES.extend(_lado+"_"+_campo for _campo in [
        "rx_bytes_delta", "tx_bytes_delta", "rx_packets_delta", "tx_packets_delta",
        "rx_dropped_delta", "tx_dropped_delta", "rx_errors_delta", "tx_errors_delta",
        "rx_mbps", "rx_load_ratio", "tx_mbps", "tx_load_ratio", "rx_pps", "tx_pps",
        "qdisc_drops_delta", "qdisc_bytes_delta", "qdisc_packets_delta",
        "queue_backlog_bytes", "queue_packets"])
    for _metrica in ("tx_mbps", "rx_mbps"):
        for _tipo in ("short_std", "short_peak"):
            FEATURES.append(_lado+"_"+_metrica+"_"+_tipo)

TARGETS = ["target_throughput_u_to_v_mbps", "target_throughput_v_to_u_mbps",
           "target_u_to_v_loss_ratio", "target_v_to_u_loss_ratio",
           "target_u_to_v_delay_avg_ms", "target_v_to_u_delay_avg_ms"]
PARTICIONES = ("train", "validation", "test")
TOPOLOGIAS = {"NSFNET", "GEANT2"}


def sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1024*1024), b""):
            h.update(bloque)
    return h.hexdigest()


def guardar_json(ruta, datos):
    with open(ruta, "x", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")


def fecha(s):
    s = s.strip().replace("Z", "+00:00")
    if s[-3] == ":":
        s = s[:-3]+s[-2:]
    for formato in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(s, formato)
        except ValueError:
            pass
    raise ValueError("Fecha no reconocida: "+s)


def exigir_final(ruta):
    ruta = os.path.realpath(os.path.expanduser(ruta))
    resumen_path = os.path.join(os.path.dirname(ruta), "resumen_final.json")
    if not os.path.isfile(ruta) or not os.path.isfile(resumen_path):
        raise ValueError("Falta el CSV final o resumen_final.json. Espera a que termine la captura.")
    with open(resumen_path, encoding="utf-8") as f:
        resumen = json.load(f)
    if os.path.realpath(resumen["dataset_final_en_ryu"]) != ruta:
        raise ValueError("El resumen final corresponde a otro CSV")
    horas = float(resumen["cobertura_documentada_total_h"])
    if not math.isfinite(horas) or horas < 20-1e-9:
        raise ValueError("El resumen no acredita al menos 20 h de cobertura documentada")
    return ruta, resumen


def cargar(ruta):
    import numpy as np
    temporal = {p: {"x": [], "y": [], "weights": [], "metadata": []} for p in PARTICIONES}
    propietarios, claves = {}, set()
    requeridas = set(FEATURES+TARGETS+[
        "topologia", "particion", "run_id", "scenario_id", "seed", "cycle", "link_id",
        "feature_start", "feature_end", "label_start", "label_end"])
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        lector = csv.DictReader(f)
        if not requeridas.issubset(lector.fieldnames or []):
            raise ValueError("Faltan columnas: "+repr(sorted(requeridas-set(lector.fieldnames or []))))
        if len(lector.fieldnames) != len(set(lector.fieldnames)):
            raise ValueError("Encabezados CSV repetidos")
        for numero, r in enumerate(lector, 2):
            if None in r:
                raise ValueError("Fila CSV irregular: "+str(numero))
            t, p = r["topologia"].upper(), r["particion"]
            if t not in TOPOLOGIAS or p not in PARTICIONES:
                raise ValueError("Topologia o particion invalida en fila "+str(numero))
            clave = (t, r["run_id"], r["cycle"], r["link_id"])
            if clave in claves:
                raise ValueError("Registro duplicado: "+repr(clave))
            claves.add(clave)
            for campo in ("run_id", "scenario_id", "seed"):
                if not r[campo] or propietarios.setdefault((t, campo, r[campo]), p) != p:
                    raise ValueError("Cruce de particiones o identificador vacio: "+campo)
            a, b, c, d = [fecha(r[k]) for k in ("feature_start", "feature_end", "label_start", "label_end")]
            if not a <= b < c <= d:
                raise ValueError("Orden temporal invalido en fila "+str(numero))
            x, y = [float(r[k]) for k in FEATURES], [float(r[k]) for k in TARGETS]
            if not all(math.isfinite(v) for v in x+y):
                raise ValueError("Metrica no finita en fila "+str(numero))
            if any(v < 0 or ("loss_ratio" in k and v > 1) for k, v in zip(TARGETS, y)):
                raise ValueError("Objetivo fuera de rango en fila "+str(numero))
            peso = float(r.get("training_weight") or "1")
            if not math.isfinite(peso) or peso < 0:
                raise ValueError("Peso de entrenamiento invalido en fila "+str(numero))
            destino = temporal[p]
            destino["x"].append(x)
            destino["y"].append(y)
            destino["weights"].append(peso)
            destino["metadata"].append({
                "topologia": t, "run_id": r["run_id"], "cycle": r["cycle"],
                "link_id": r["link_id"], "label_start": r["label_start"],
                "measurement_method": r.get("measurement_method") or "historical_csv_method_not_recovered",
                "probe_loss_scope": r.get("probe_loss_scope") or "not_recorded_in_csv",
                "sample_status": r.get("sample_status") or "no_indicado"})
    for p, datos in temporal.items():
        if {r["topologia"] for r in datos["metadata"]} != TOPOLOGIAS:
            raise ValueError("La particion {} no incluye ambas topologias".format(p))
        for k in ("x", "y", "weights"):
            datos[k] = np.asarray(datos[k], dtype=float)
    return temporal


def pesos_comunes(datos):
    import numpy as np
    pesos = datos["weights"].copy()
    for t in sorted(TOPOLOGIAS):
        mascara = np.asarray([m["topologia"] == t for m in datos["metadata"]], dtype=bool)
        suma = float(pesos[mascara].sum())
        if suma <= 0:
            raise ValueError("No hay peso de entrenamiento positivo para "+t)
        pesos[mascara] *= len(pesos)/(2.0*suma)
    return pesos


def metricas(real, predicho):
    import numpy as np
    salida = {}
    for j, objetivo in enumerate(TARGETS):
        y, p = real[:, j], predicho[:, j]
        error = p-y
        sse = float(np.dot(error, error))
        centrado = y-y.mean()
        sst = float(np.dot(centrado, centrado))
        salida[objetivo] = {"n": int(len(y)), "mae": float(np.abs(error).mean()),
            "rmse": math.sqrt(sse/len(y)), "r2": None if len(y) < 2 or sst <= 1e-20 else 1-sse/sst,
            "unidad": "ratio_0_1" if "loss_ratio" in objetivo else ("ms" if "delay" in objetivo else "Mbps")}
    return salida


def evaluar_grupos(datos, predicho, mediana):
    import numpy as np
    resultado = {}
    grupos = {"global": np.ones(len(datos["y"]), dtype=bool)}
    for campo in ("topologia", "measurement_method", "probe_loss_scope"):
        for v in sorted({m[campo] for m in datos["metadata"]}):
            grupos[campo+":"+v] = np.asarray([m[campo] == v for m in datos["metadata"]], dtype=bool)
    for t in sorted(TOPOLOGIAS):
        for metodo in sorted({m["measurement_method"] for m in datos["metadata"] if m["topologia"] == t}):
            grupos["topologia:"+t+"|measurement_method:"+metodo] = np.asarray([
                m["topologia"] == t and m["measurement_method"] == metodo for m in datos["metadata"]], dtype=bool)
    for nombre, mascara in grupos.items():
        real = datos["y"][mascara]
        resultado[nombre] = {
            "modelo": metricas(real, predicho[mascara]),
            "referencia_mediana_train": metricas(real, np.tile(mediana, (len(real), 1)))}
    return resultado


def guardar_predicciones(ruta, datos, predicho):
    campos = ["topologia", "run_id", "cycle", "link_id", "label_start", "measurement_method",
              "probe_loss_scope", "sample_status"]
    with open(ruta, "x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos+["real_"+k for k in TARGETS]+["pred_"+k for k in TARGETS])
        w.writeheader()
        for i, meta in enumerate(datos["metadata"]):
            r = dict(meta)
            r.update({"real_"+k: float(datos["y"][i, j]) for j, k in enumerate(TARGETS)})
            r.update({"pred_"+k: float(predicho[i, j]) for j, k in enumerate(TARGETS)})
            w.writerow(r)


def entrenar(args):
    ruta, resumen = exigir_final(args.dataset)
    import numpy as np
    import joblib
    import sklearn
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.multioutput import MultiOutputRegressor
    original_hash = sha256(ruta)
    datos = cargar(ruta)
    train = datos["train"]
    pesos = pesos_comunes(train)
    if sha256(ruta) != original_hash:
        raise ValueError("El CSV cambio durante la lectura")
    raiz = os.path.abspath(os.path.expanduser(args.salida)) if args.salida else os.path.join(
        os.path.dirname(ruta), "modelos_comunes")
    os.makedirs(raiz, exist_ok=True)
    carpeta = tempfile.mkdtemp(prefix="modelo_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_"), dir=raiz)
    parametros = {"n_estimators": args.arboles, "max_depth": args.profundidad,
                  "min_samples_leaf": args.min_hoja, "max_features": "sqrt", "n_jobs": 1, "random_state": 42}
    modelo = MultiOutputRegressor(RandomForestRegressor(**parametros), n_jobs=1)
    print("Entrenando con ambas topologias y solo la particion train...", flush=True)
    modelo.fit(train["x"], train["y"], sample_weight=pesos)
    mediana = np.median(train["y"][train["weights"] > 0], axis=0)
    predicho = modelo.predict(datos["validation"]["x"])
    paquete = {"schema_version": 1, "modelo": modelo, "features": FEATURES, "targets": TARGETS,
        "topologias": sorted(TOPOLOGIAS), "dataset_sha256": original_hash,
        "baseline_mediana_train": mediana, "parametros": parametros,
        "python_version": platform.python_version(), "sklearn_version": sklearn.__version__}
    joblib.dump(paquete, os.path.join(carpeta, "modelo_comun.pkl"), compress=3, protocol=4)
    informe = {k: v for k, v in paquete.items() if k not in ("modelo", "baseline_mediana_train")}
    informe.update(dataset=ruta, creado_utc=datetime.now(timezone.utc).isoformat(),
        cobertura_documentada_total_h=resumen["cobertura_documentada_total_h"],
        pesos="training_weight relativo conservado; peso total igual para cada topologia en train",
        particiones={p: dict(Counter(m["topologia"] for m in d["metadata"])) for p, d in datos.items()},
        estados_muestras={p: dict(Counter(m["sample_status"] for m in d["metadata"])) for p, d in datos.items()},
        alcances_perdida={p: dict(Counter(m["probe_loss_scope"] for m in d["metadata"])) for p, d in datos.items()},
        validation=evaluar_grupos(datos["validation"], predicho, mediana),
        test="Reservado: no se ha predicho ni evaluado en este comando")
    guardar_json(os.path.join(carpeta, "entrenamiento_validacion.json"), informe)
    guardar_predicciones(os.path.join(carpeta, "predicciones_validation.csv"), datos["validation"], predicho)
    print("Modelo y validacion:", carpeta)
    print("El test queda reservado para el comando evaluar del modelo ya guardado.")


def evaluar(args):
    ruta, _ = exigir_final(args.dataset)
    import joblib
    paquete = joblib.load(args.modelo)
    if paquete.get("features") != FEATURES or paquete.get("targets") != TARGETS:
        raise ValueError("El modelo no corresponde al esquema de 60 entradas y seis salidas")
    if paquete["dataset_sha256"] != sha256(ruta):
        raise ValueError("El dataset es distinto del usado para entrenar este modelo")
    carpeta = os.path.dirname(os.path.abspath(args.modelo))
    informe = os.path.join(carpeta, "evaluacion_test.json")
    if os.path.exists(informe) or os.path.exists(os.path.join(carpeta, "predicciones_test.csv")):
        raise ValueError("El test de este modelo ya se evaluo o quedo un intento previo; conserva y revisa sus archivos")
    datos = cargar(ruta)["test"]
    predicho = paquete["modelo"].predict(datos["x"])
    metricas_test = evaluar_grupos(datos, predicho, paquete["baseline_mediana_train"])
    guardar_predicciones(os.path.join(carpeta, "predicciones_test.csv"), datos, predicho)
    guardar_json(informe, {"dataset": ruta, "dataset_sha256": paquete["dataset_sha256"],
        "modelo": os.path.abspath(args.modelo), "test": metricas_test,
        "nota": "Evaluacion del modelo guardado; sin reajuste ni seleccion usando el test"})
    print("Evaluacion final:", informe)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    modos = p.add_subparsers(dest="modo")
    a = modos.add_parser("entrenar")
    a.add_argument("--dataset", required=True)
    a.add_argument("--salida")
    a.add_argument("--arboles", type=int, default=120)
    a.add_argument("--profundidad", type=int, default=12)
    a.add_argument("--min-hoja", type=int, default=6)
    b = modos.add_parser("evaluar")
    b.add_argument("--dataset", required=True)
    b.add_argument("--modelo", required=True)
    args = p.parse_args()
    if args.modo == "entrenar":
        if min(args.arboles, args.profundidad, args.min_hoja) <= 0:
            p.error("Los parametros numericos deben ser positivos")
        entrenar(args)
    elif args.modo == "evaluar":
        evaluar(args)
    else:
        p.print_help()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, ImportError) as error:
        raise SystemExit("ERROR: "+str(error))
