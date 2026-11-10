#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comparacion reproducible de cuatro regresores. Python 3.6/sklearn 0.24.

No despliega modelos ni modifica el CSV. Entrenar solo evalua validation.
Evaluar produce una comparacion descriptiva del test previamente examinado.
"""
import os
for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[variable] = '1'
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
import platform
import sys
import tempfile
import time

import entrenar_modelo_comun_sdn as datos_base

MODELOS = ('polinomial', 'decision_tree', 'random_forest', 'xgboost')
NOTA_TEST = ('El test de este dataset ya fue examinado anteriormente. Esta es una '
             'comparacion descriptiva sobre la particion existente, no una nueva '
             'evaluacion independiente. No se usa para elegir parametros ni modelos.')


def guardar(path, obj):
    datos_base.guardar_json(str(path), obj)


def protocolo():
    return {
        'polinomial': {'degree': 2, 'include_bias': False, 'ridge_alpha': 10.0,
                      'solver': 'lsqr', 'max_iter': 300, 'tol': 0.001},
        'decision_tree': {'max_depth': 12, 'min_samples_leaf': 6, 'random_state': 42},
        'random_forest': {'n_estimators': 120, 'max_depth': 12, 'min_samples_leaf': 6,
                          'max_features': 'sqrt', 'n_jobs': 1, 'random_state': 42},
        'xgboost': {'n_estimators': 120, 'max_depth': 4, 'learning_rate': 0.05,
                    'subsample': 1.0, 'colsample_bytree': 1.0, 'objective': 'reg:squarederror',
                    'tree_method': 'hist', 'n_jobs': 1, 'random_state': 42, 'verbosity': 0}}


def construir(nombre, parametros):
    from sklearn.multioutput import MultiOutputRegressor
    from sklearn.tree import DecisionTreeRegressor
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler, PolynomialFeatures
    from sklearn.linear_model import Ridge
    if nombre == 'polinomial':
        return Pipeline([
            ('escala', StandardScaler()),
            ('polinomio', PolynomialFeatures(degree=parametros['degree'], include_bias=False)),
            ('regresor', Ridge(alpha=parametros['ridge_alpha'], solver=parametros['solver'],
                               max_iter=parametros['max_iter'], tol=parametros['tol']))])
    if nombre == 'decision_tree':
        return MultiOutputRegressor(DecisionTreeRegressor(**parametros), n_jobs=1)
    if nombre == 'random_forest':
        return MultiOutputRegressor(RandomForestRegressor(**parametros), n_jobs=1)
    if nombre == 'xgboost':
        from xgboost import XGBRegressor
        return MultiOutputRegressor(XGBRegressor(**parametros), n_jobs=1)
    raise ValueError('Modelo desconocido')


def comprobar_memoria(x):
    # El polinomio completo de 60 variables tiene 1890 columnas, no solo cuadrados.
    n, d = x.shape
    columnas = d + d * (d + 1) // 2
    estimado = 3 * n * columnas * 8 + 700 * 1024**2
    disponible = None
    if Path('/proc/meminfo').is_file():
        for linea in Path('/proc/meminfo').read_text().splitlines():
            if linea.startswith('MemAvailable:'):
                disponible = int(linea.split()[1]) * 1024
    print('Memoria estimada para baseline completo: {:.0f} MiB'.format(estimado / 1024**2), flush=True)
    if disponible is not None and estimado > disponible:
        raise ValueError('Memoria disponible insuficiente para el polinomio completo. '
                         'No se cambia silenciosamente el baseline ni se modifican las redes.')
    return {'columnas_polinomiales': columnas, 'estimacion_bytes': estimado,
            'disponible_bytes_al_inicio': disponible}


def predecir(modelo, x, bloque=256):
    import numpy as np
    partes = [modelo.predict(x[i:i+bloque]) for i in range(0, len(x), bloque)]
    p = np.concatenate(partes, axis=0)
    if p.shape != (len(x), len(datos_base.TARGETS)) or not np.isfinite(p).all():
        raise ValueError('Predicciones incompletas o no finitas')
    return p


def grupos(datos, predicho):
    import numpy as np
    meta = datos['metadata']
    masks = {'global': np.ones(len(meta), dtype=bool)}
    for campo in ('topologia', 'measurement_method', 'probe_loss_scope'):
        for valor in sorted({m[campo] for m in meta}):
            masks[campo+':'+valor] = np.array([m[campo] == valor for m in meta])
    for t in sorted(datos_base.TOPOLOGIAS):
        for metodo in sorted({m['measurement_method'] for m in meta if m['topologia'] == t}):
            masks['topologia:'+t+'|measurement_method:'+metodo] = np.array([
                m['topologia'] == t and m['measurement_method'] == metodo for m in meta])
    result = {}
    for nombre, mask in masks.items():
        y, p = datos['y'][mask], predicho[mask]
        metricas = datos_base.metricas(y, p)
        for j, target in enumerate(datos_base.TARGETS):
            metricas[target]['mse'] = float(np.mean((p[:, j]-y[:, j])**2))
            metricas[target]['unidad_mse'] = metricas[target]['unidad'] + '^2'
            invalidas = (p[:, j] < 0) | ((p[:, j] > 1) if 'loss_ratio' in target else False)
            metricas[target]['predicciones_fuera_rango'] = int(invalidas.sum())
        result[nombre] = metricas
    return result


def escala_train(train):
    import numpy as np
    # Escala por salida y topologia, calculada solo con entrenamiento.
    return {t: np.maximum(np.std(train['y'][np.array([m['topologia'] == t for m in train['metadata']])], axis=0),
                          1e-12).tolist() for t in sorted(datos_base.TOPOLOGIAS)}


def puntuacion(metricas, escalas):
    # Igual peso para ambas topologias y las seis salidas; no sumar ms con Mbps.
    valores = [metricas['topologia:'+t][target]['rmse']/escalas[t][j]
               for t in sorted(escalas) for j, target in enumerate(datos_base.TARGETS)]
    return sum(valores)/len(valores)


def tabla(path, informes):
    columnas = ['modelo', 'grupo', 'objetivo', 'n', 'mse', 'rmse', 'mae', 'r2',
                'unidad', 'unidad_mse', 'predicciones_fuera_rango']
    with path.open('x', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columnas)
        writer.writeheader()
        for modelo, informe in informes.items():
            for grupo, objetivos in informe['metricas'].items():
                for target, metricas in objetivos.items():
                    writer.writerow(dict(metricas, modelo=modelo, grupo=grupo, objetivo=target))


def identidad(datos):
    return {p: hashlib.sha256(json.dumps(d['metadata'], sort_keys=True).encode()).hexdigest()
            for p, d in datos.items()}


def versiones():
    import numpy, scipy, sklearn, xgboost, joblib
    return {m.__name__: m.__version__ for m in (numpy, scipy, sklearn, xgboost, joblib)}


def entrenar(args):
    import joblib
    ruta, resumen = datos_base.exigir_final(args.dataset)
    digest = datos_base.sha256(ruta)
    versiones_instaladas = versiones()  # Falla antes de entrenar si falta XGBoost.
    datos = datos_base.cargar(ruta)
    if datos_base.sha256(ruta) != digest:
        raise ValueError('El CSV cambio durante la lectura')
    memoria = comprobar_memoria(datos['train']['x'])
    salida = Path(args.salida).expanduser().resolve()
    salida.mkdir(parents=True, exist_ok=True)
    carpeta = Path(tempfile.mkdtemp(prefix='comparacion_', dir=str(salida)))
    params, escalas = protocolo(), escala_train(datos['train'])
    manifiesto = {'schema_version': 1, 'dataset': ruta, 'dataset_sha256': digest,
        'features': datos_base.FEATURES, 'targets': datos_base.TARGETS,
        'parametros': params, 'escala_score_train': escalas,
        'pesos_train': 'training_weight conservado; suma equilibrada entre topologias',
        'metricas': 'sin ponderar y sin recortar predicciones; por salida, topologia y procedencia',
        'seleccion': 'Menor media de RMSE/std_train por salida y topologia en validation; '
                     'polinomial es baseline, no candidato de despliegue. Sin busqueda de hiperparametros.',
        'huellas_particiones': identidad(datos),
        'filas': {p: dict(Counter(m['topologia'] for m in d['metadata'])) for p, d in datos.items()},
        'cobertura_horas': resumen['cobertura_documentada_total_h'], 'memoria': memoria,
        'versiones': versiones_instaladas, 'python': platform.python_version(),
        'creado_utc': datetime.now(timezone.utc).isoformat(), 'nota_test': NOTA_TEST}
    guardar(carpeta/'protocolo.json', manifiesto)
    pesos = datos_base.pesos_comunes(datos['train'])
    informes = {}
    print('CARPETA_COMPARACION='+str(carpeta), flush=True)
    for nombre in MODELOS:
        print('Entrenando '+nombre+' exclusivamente con train...', flush=True)
        modelo = construir(nombre, params[nombre])
        inicio = time.monotonic()
        fit_params = {'regresor__sample_weight': pesos} if nombre == 'polinomial' else {'sample_weight': pesos}
        modelo.fit(datos['train']['x'], datos['train']['y'], **fit_params)
        duracion = time.monotonic()-inicio
        inicio = time.monotonic()
        pred = predecir(modelo, datos['validation']['x'])
        tiempo_prediccion = time.monotonic()-inicio
        metricas = grupos(datos['validation'], pred)
        paquete = {'modelo': modelo, 'features': datos_base.FEATURES, 'targets': datos_base.TARGETS,
                   'dataset_sha256': digest, 'nombre': nombre, 'parametros': params[nombre]}
        joblib.dump(paquete, str(carpeta/(nombre+'.pkl')), compress=3, protocol=4)
        datos_base.guardar_predicciones(str(carpeta/('predicciones_validation_'+nombre+'.csv')), datos['validation'], pred)
        informes[nombre] = {'metricas': metricas, 'score_validation': puntuacion(metricas, escalas),
                            'entrenamiento_s': duracion, 'prediccion_s': tiempo_prediccion}
        guardar(carpeta/('validacion_'+nombre+'.json'), informes[nombre])
        print(nombre+': score validation='+str(informes[nombre]['score_validation']), flush=True)
        del modelo, paquete, pred
        gc.collect()
    elegido = min(MODELOS[1:], key=lambda k: informes[k]['score_validation'])
    huellas = {n: datos_base.sha256(str(carpeta/(n+'.pkl'))) for n in MODELOS}
    if datos_base.sha256(ruta) != digest:
        raise ValueError('El CSV cambio durante el entrenamiento')
    tabla(carpeta/'metricas_validation.csv', informes)
    guardar(carpeta/'comparacion_validation.json', {'modelos': informes, 'seleccion_validation': elegido,
            'huellas_modelos': huellas, 'nota_test': NOTA_TEST, 'modelo_en_servicio_modificado': False})
    print('VALIDACION COMPLETADA. Seleccion por validation: '+elegido, flush=True)
    print('No se ha predicho test. El modelo en servicio se conserva.', flush=True)


def evaluar(args):
    import joblib
    carpeta = Path(args.carpeta).expanduser().resolve()
    manifiesto = json.loads((carpeta/'protocolo.json').read_text(encoding='utf-8'))
    validacion = json.loads((carpeta/'comparacion_validation.json').read_text(encoding='utf-8'))
    if not args.test_ya_examinado:
        raise ValueError('Usa --test-ya-examinado para registrar el alcance descriptivo de esta evaluacion')
    lock = carpeta/'evaluacion_test_iniciada.json'
    if lock.exists() or (carpeta/'comparacion_test.json').exists():
        raise ValueError('Ya hubo una evaluacion o intento. Se conservan sus archivos; no se repite el test.')
    ruta, _ = datos_base.exigir_final(args.dataset)
    if datos_base.sha256(ruta) != manifiesto['dataset_sha256']:
        raise ValueError('El CSV no es el mismo del entrenamiento')
    for nombre in MODELOS:
        if datos_base.sha256(str(carpeta/(nombre+'.pkl'))) != validacion['huellas_modelos'][nombre]:
            raise ValueError('Un modelo cambio desde la validacion: '+nombre)
    datos = datos_base.cargar(ruta)
    if identidad(datos) != manifiesto['huellas_particiones']:
        raise ValueError('Las particiones cambiaron')
    guardar(lock, {'inicio_utc': datetime.now(timezone.utc).isoformat(), 'nota': NOTA_TEST})
    informes = {}
    for nombre in MODELOS:
        paquete = joblib.load(str(carpeta/(nombre+'.pkl')))
        if paquete['features'] != datos_base.FEATURES or paquete['targets'] != datos_base.TARGETS:
            raise ValueError('Esquema incompatible')
        inicio = time.monotonic()
        pred = predecir(paquete['modelo'], datos['test']['x'])
        informes[nombre] = {'metricas': grupos(datos['test'], pred), 'prediccion_s': time.monotonic()-inicio}
        datos_base.guardar_predicciones(str(carpeta/('predicciones_test_'+nombre+'.csv')), datos['test'], pred)
        guardar(carpeta/('test_'+nombre+'.json'), informes[nombre])
        del paquete, pred
        gc.collect()
    tabla(carpeta/'metricas_test.csv', informes)
    guardar(carpeta/'comparacion_test.json', {'modelos': informes,
        'seleccion_previa_validation': validacion['seleccion_validation'], 'nota': NOTA_TEST,
        'dataset_sha256': manifiesto['dataset_sha256'], 'modelo_en_servicio_modificado': False})
    print('COMPARACION DESCRIPTIVA COMPLETADA: '+str(carpeta/'metricas_test.csv'), flush=True)
    print('Seleccion fijada previamente en validation: '+validacion['seleccion_validation'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='modo')
    a = sub.add_parser('entrenar')
    a.add_argument('--dataset', required=True)
    a.add_argument('--salida', required=True)
    b = sub.add_parser('evaluar')
    b.add_argument('--dataset', required=True)
    b.add_argument('--carpeta', required=True)
    b.add_argument('--test-ya-examinado', action='store_true')
    args = parser.parse_args()
    if hasattr(os, 'nice'):
        os.nice(10)
    if args.modo == 'entrenar':
        entrenar(args)
    elif args.modo == 'evaluar':
        evaluar(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, ImportError, KeyError) as error:
        raise SystemExit('ERROR: '+str(error))
