#!/bin/sh
set -eu
cd "$HOME/proyecto_nsfnet"
fuentes="$HOME/proyecto_nsfnet/comparacion_ml_sdn"
dataset="$HOME/proyecto_nsfnet/datos/nocturna_c064e9fb0ad2_win4e5zw/dataset_consolidado_20h.csv"
test -f "$dataset" || { echo 'Falta el dataset final esperado.'; exit 1; }
test -x ./entorno_ml/bin/python || { echo 'Falta el Python del proyecto.'; exit 1; }
test -f "$fuentes/comparar_modelos_sdn.py"
trabajo=$(mktemp -d "$HOME/proyecto_nsfnet/comparacion_cuatro_ml_XXXXXX")
echo "Carpeta nueva: $trabajo"
echo 'Preparando un entorno separado. No se cambia entorno_ml ni el modelo en servicio.'
./entorno_ml/bin/python -m venv "$trabajo/entorno"
"$trabajo/entorno/bin/python" -m pip install --disable-pip-version-check 'pip==21.3.1'
"$trabajo/entorno/bin/python" -m pip install --disable-pip-version-check --only-binary=:all: -r "$fuentes/requirements-ryu-py36.txt"
nohup "$trabajo/entorno/bin/python" -u "$fuentes/comparar_modelos_sdn.py" entrenar \
  --dataset "$dataset" --salida "$trabajo/resultados" > "$trabajo/entrenamiento.log" 2>&1 < /dev/null &
pid=$!
printf '%s\n' "$pid" > "$trabajo/pid_entrenamiento.txt"
printf '%s\n' "$trabajo" > "$fuentes/ultima_comparacion.txt"
echo "ENTRENAMIENTO INICIADO. PID: $pid"
echo "Registro: tail -n 25 $trabajo/entrenamiento.log"
echo 'El trabajo continua en segundo plano al cerrar SSH. Manten RYU encendida.'
echo 'Primero se entrenan los cuatro modelos y se compara validation. El test no se ejecuta en este paso.'
