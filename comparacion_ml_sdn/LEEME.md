# Comparación de cuatro modelos — RYU

Código preparado para Python 3.6.9 / sklearn 0.24.2, con XGBoost 1.5.2. No sustituye el modelo en servicio, no cambia flujos, relojes ni datasets. El instalador crea un entorno nuevo por ejecución, fuera de `entorno_ml`; no requiere sudo.

## Método fijado antes de ejecutar

- Mismas 60 entradas, seis objetivos y particiones `train`, `validation`, `test` del CSV consolidado de 20 horas. Se reutilizan las validaciones de fechas, duplicados y ausencia de cruces de run/scenario/seed del cargador original.
- Regresión polinomial completa de grado 2: 1890 términos, interacciones incluidas; estandarización ajustada solo con train y Ridge alfa 10, solver LSQR, tolerancia 0,001 y máximo 300 iteraciones. Es una regresión polinomial regularizada, no OLS sin penalización.
- Decision Tree: profundidad 12, hoja mínima 6. Random Forest: 120 árboles por salida, profundidad 12, hoja mínima 6, max_features sqrt. XGBoost: 120 árboles por salida, profundidad 4, learning_rate 0,05, método hist. Semilla 42 y ejecución secuencial con un hilo por estimador.
- Igual ponderación total de ambas topologías en entrenamiento, conservando los pesos relativos del CSV. Las métricas se calculan sin ponderar sobre exactamente las mismas filas de evaluación.
- MSE, RMSE, MAE y R² por salida, topología y procedencia de medición. No se recortan las predicciones para mejorar resultados; se informa cuántas violan los límites físicos.
- Selección solo por validation, entre los tres candidatos de árboles. Se minimiza la media, con igual peso para las dos topologías y seis salidas, de RMSE dividido por la desviación de cada objetivo/topología en train (mínimo 1e-12). No se suman errores en ms y Mbps sin normalizar. La polinomial sirve como baseline.
- Se conserva el alcance de las pérdidas de cada fuente. Los grupos de métodos históricos no se presentan como mediciones homogéneas con la captura adicional.
- El test ya fue observado en el proyecto. Su comparación posterior será descriptiva sobre esa partición, no una nueva prueba independiente. No se utiliza para retocar parámetros ni elegir ganador. El servicio sigue usando el Random Forest anterior hasta una decisión de integración separada.

## 1. Copiar desde Windows

En PowerShell, copiar esta carpeta a la VM RYU mediante scp. No pegar su contenido en Mininet ni en la consola `mininet>`.

## 2. Instalar e iniciar, en la terminal SSH de RYU

```bash
bash ~/proyecto_nsfnet/comparacion_ml_sdn/iniciar_comparacion_ryu.sh
```

Se instala un entorno aislado con versiones fijadas y se imprime la carpeta del trabajo y el registro. Cada ejecución crea una carpeta diferente; no se borra ni reemplaza una anterior. No repetir este comando si el primer entrenamiento continúa. La instalación necesita Internet en RYU y espacio para bibliotecas y modelos; si falla, conservar el mensaje y la carpeta para diagnosticar.

## 3. Ver el progreso, en RYU

```bash
trabajo_ml=$(cat ~/proyecto_nsfnet/comparacion_ml_sdn/ultima_comparacion.txt)
tail -n 25 "$trabajo_ml/entrenamiento.log"
```

La duración real depende de la VM. El baseline verifica memoria disponible; no se degrada silenciosamente a un polinomio diferente. El script reduce su prioridad en Linux. El modelo en servicio y la telemetría pueden seguir funcionando; el entrenamiento comparte los recursos de RYU.

Al completar, se generan cuatro `.pkl`, predicciones de validation, `protocolo.json`, `comparacion_validation.json` y `metricas_validation.csv`. El modelo recomendado se fija con validation, no se despliega automáticamente. Si una etapa falla no se presenta una comparación completa.

## 4. Comparación descriptiva del test, después de revisar validation

La carpeta de resultados aparece en el registro como `CARPETA_COMPARACION=...`. Usar exactamente esa carpeta:

```bash
"$trabajo_ml/entorno/bin/python" ~/proyecto_nsfnet/comparacion_ml_sdn/comparar_modelos_sdn.py evaluar \
  --dataset "$HOME/proyecto_nsfnet/datos/nocturna_c064e9fb0ad2_win4e5zw/dataset_consolidado_20h.csv" \
  --carpeta "RUTA_CARPETA_COMPARACION_DEL_REGISTRO" --test-ya-examinado
```

El comando comprueba hashes de CSV, modelos y particiones. Solo permite un intento por carpeta. Si un intento falla conserva los archivos y requiere diagnóstico, sin borrar el bloqueo para repetirlo silenciosamente. Genera `comparacion_test.json`, `metricas_test.csv`, resultados por modelo y predicciones. El test del modelo antiguo no se modifica.

## Fuentes de compatibilidad

- [XGBoost 1.5.2: Python >= 3.6](https://pypi.org/project/xgboost/1.5.2/).
- [PolynomialFeatures de sklearn 0.24](https://scikit-learn.org/0.24/modules/generated/sklearn.preprocessing.PolynomialFeatures.html).
- [Ridge y solver LSQR en sklearn 0.24](https://scikit-learn.org/0.24/modules/generated/sklearn.linear_model.Ridge.html).

La verificación local con datos sintéticos usa bibliotecas de Windows. La instalación y ejecución efectiva en la VM de Python 3.6 se comprueban por sus salidas; preparar estos archivos no significa haber entrenado ya con el dataset real.
