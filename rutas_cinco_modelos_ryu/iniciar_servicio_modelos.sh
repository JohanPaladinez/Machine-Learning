#!/bin/sh
set -eu
cd "$HOME/proyecto_nsfnet"
trabajo_ml=$(cat "$HOME/proyecto_nsfnet/comparacion_ml_sdn/ultima_comparacion.txt")
carpeta_ml=$(sed -n 's/^CARPETA_COMPARACION=//p' "$trabajo_ml/entrenamiento.log")
test -n "$carpeta_ml"
test -f "$carpeta_ml/comparacion_test.json" || { echo 'Falta completar el test descriptivo de los cuatro modelos.'; exit 1; }
python_ml="$trabajo_ml/entorno/bin/python"
fuente="$HOME/proyecto_nsfnet/rutas_cinco_modelos_ryu/servidor_cuatro_modelos.py"
test -x "$python_ml"
test -f "$fuente"
carpeta_servicio=$(mktemp -d "$HOME/proyecto_nsfnet/servicio_cuatro_modelos_XXXXXX")
nohup "$python_ml" -u "$fuente" --carpeta "$carpeta_ml" \
  --host 192.168.56.108 --puerto 8011 > "$carpeta_servicio/servicio.log" 2>&1 < /dev/null &
pid=$!
printf '%s\n' "$pid" > "$carpeta_servicio/pid.txt"
echo "Servicio nuevo PID: $pid"
echo "Registro: $carpeta_servicio/servicio.log"
"$python_ml" - "$pid" "$carpeta_servicio/servicio.log" <<'PY'
import json, os, sys, time
from urllib.request import build_opener, ProxyHandler
pid=int(sys.argv[1]); log=sys.argv[2]
client=build_opener(ProxyHandler({}))
for _ in range(40):
    try:
        with client.open('http://192.168.56.108:8011/health',timeout=2) as r:
            health=json.load(r)
        if health.get('pid') != pid:
            raise SystemExit('El puerto 8011 pertenece a otro proceso. No se detuvo. Revisa '+log)
        if health.get('estado') != 'cuatro_modelos_cargados':
            raise ValueError('Contrato incompleto')
        summary={k:health[k] for k in ('estado','modelos','seleccion_validation','pid')}
        summary.update(features=len(health['features']),targets=len(health['targets']),puerto=8011)
        print('CUATRO MODELOS LISTOS: '+json.dumps(summary,ensure_ascii=True),flush=True)
        print('Servicio anterior, redes y modelos guardados conservados.',flush=True)
        break
    except (OSError,ValueError):
        try:
            os.kill(pid,0)
        except OSError:
            raise SystemExit('El servicio termino. Registro:\n'+open(log).read()[-4000:])
        time.sleep(1)
else:
    raise SystemExit('No se confirmo el arranque. Revisa '+log)
PY
