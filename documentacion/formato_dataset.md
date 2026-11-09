# Formato del dataset NSFNET

## 1. Objetivo

Almacenar las metricas de calidad de servicio
de cada enlace de la topologia de red.

## 2. Nombre del archivo

metricas_enlaces.csv

## 3. Columnas requeridas

| Columna | Descripcion | Unidad |
|---|---|---|
| timestamp | Inicio de la ventana | Fecha y hora |
| window_seconds | Duracion de ventana | Segundos |
| origen | Switch de origen | Identificador |
| destino | Switch de destino | Identificador |
| perdida_paquetes_pct | Perdida de paquetes | Porcentaje |
| retardo_ms | Retardo del enlace | Milisegundos |
| throughput_mbps | Rendimiento del enlace | Mbps |
| qs_metrics | Indice de calidad del enlace | Indice normalizado |

## 4. Reglas de construccion

- Cada registro representa un enlace durante una ventana.
- La ventana de sensado sera de 60 segundos.
- El periodo minimo de sensado sera de 48 horas.
- Se conservaran las mediciones originales.
- Se identificaran los enlaces mediante origen y destino.
- Se documentara la formula utilizada para QS_metrics.

## 5. Machine Learning

El modelo utilizara las metricas de una
ventana para predecir QS_metrics de la
siguiente ventana.

Entrada:
- Perdida de paquetes.
- Retardo.
- Throughput.

Objetivo:
- QS_metrics en t+60 segundos.

## 6. Evaluacion

Los modelos se compararan mediante:

- MSE
- RMSE
- MAE

La separacion entre entrenamiento y prueba
respetara el orden temporal para evitar
fuga de informacion.

