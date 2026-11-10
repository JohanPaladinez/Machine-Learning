> Documento de una version anterior. Para el estado actual (Windows, cinco rutas y consolas interactivas), consultar README.md y documentacion/ESTADO_ACTUAL.md. Se conserva como historial.

# Arranque y recuperación de las tres VMs

## 1. Consultar antes de iniciar

En cada VM: `hostname -I` e `ip -br a`. Direcciones verificadas el 9 de noviembre de 2026: RYU `.108`, Mininet `.103`, interfaz `.120`, en la red `192.168.56.0/24`. Si cambian, revisar la configuración específica del servicio; no reemplazar direcciones históricas masivamente.

En RYU:

```bash
ss -lntp | grep -E ':(16653|16654|18080|18081|8010)\b'
```

En Mininet:

```bash
sudo ovs-vsctl list-br
ss -lnt | grep -E ':(8768|8769)\b'
```

En interfaz:

```bash
ss -lntp | grep -E ':(8002|8003|5181|5182)\b'
python3 -c "import urllib.request; print(urllib.request.urlopen('http://192.168.56.108:8010/health', timeout=5).read().decode())"
python3 -c "import urllib.request; print(urllib.request.urlopen('http://192.168.56.103:8769/snapshot', timeout=5).status)"
python3 -c "import urllib.request; print(urllib.request.urlopen('http://192.168.56.103:8768/snapshot', timeout=5).status)"
```

Si ya están activos, continuar con ellos. No iniciar duplicados ni liberar puertos matando procesos.

## 2. Iniciar RYU después de apagar las VMs

Solo si los puertos correspondientes están libres, en terminales separadas:

```bash
ryu-manager --ofp-tcp-listen-port 16653 --wsapi-host 0.0.0.0 --wsapi-port 18080 ryu.app.ofctl_rest
```

```bash
ryu-manager --ofp-tcp-listen-port 16654 --wsapi-host 0.0.0.0 --wsapi-port 18081 ryu.app.ofctl_rest
```

Para ML, copiar una vez `laboratorio/ryu/servidor.py` de este paquete a una ubicación estable de RYU, por ejemplo `~/proyecto_nsfnet/laboratorio/ryu/servidor.py`. Es una copia exacta del servidor inspeccionado, no un modelo nuevo. Usar el entorno ML existente:

```bash
cd ~/proyecto_nsfnet
./entorno_ml/bin/python -u laboratorio/ryu/servidor.py \
  resultados_comun_20261107T205101/modelo_20261107T205202Z_n4vncu_0/modelo_comun.pkl
```

El modelo debe conservar `evaluacion_test.json` en su carpeta actual. El servidor verifica la coincidencia de su dataset con el paquete del modelo. No mover, regenerar ni reentrenar esos artefactos.

## 3. Iniciar Mininet después del apagado

Se incluyen copias de los dos workers, sus tres dependencias locales, perfiles originales embebidos y el observador base bajo `laboratorio/mininet/`. El wrapper `iniciar.py` evita depender de la última carpeta temporal o de PID anteriores. Copiar esa carpeta completa una vez a `~/proyecto_nsfnet/laboratorio/mininet/` en Mininet.

Primero consultar, sin crear redes:

```bash
python3 ~/proyecto_nsfnet/laboratorio/mininet/iniciar.py geant2
python3 ~/proyecto_nsfnet/laboratorio/mininet/iniciar.py nsfnet
```

**Arranque explícito, únicamente con las redes anteriores apagadas y autorización del operador:** estos comandos crean interfaces, instalan el forwarding convencional del experimento existente e inician sus sondas y tráfico de baja carga. No aplicar en la sesión activa de esta entrega.

En dos terminales de Mininet, primero GEANT2 y después NSFNET:

```bash
sudo python3 ~/proyecto_nsfnet/laboratorio/mininet/iniciar.py geant2 --arrancar-red
```

```bash
sudo python3 ~/proyecto_nsfnet/laboratorio/mininet/iniciar.py nsfnet --arrancar-red
```

El wrapper comprueba que el observador no esté respondiendo, que Mininet conserve su IP, que el REST dedicado no tenga switches y que el puerto local esté libre. Los workers originales también rechazan bridges existentes. No se ejecuta `mn -c`. Los errores no autorizan limpiar redes ajenas.

Las sesiones nuevas quedan en una carpeta persistente `laboratorio/mininet/sesiones/vivo_<topologia>_<fecha>_<id>/`. `ultima_nsfnet.txt` y `ultima_geant2.txt` apuntan a sus estados. El código fuente está en carpetas estables y no depende de sesiones anteriores. Esperar el estado `telemetria_nsfnet` o `telemetria_geant2` y una ventana reciente con 60 entradas por enlace. Una primera predicción guardada no demuestra actualización continua: comprobar que `window_end` avanza en `/snapshot`.

**Límite de validación:** las fuentes se copiaron sin cambios y el wrapper pasó comprobación de sintaxis; el arranque completo después de apagar VMs no se ejecutó para preservar las dos redes activas. Los workers conservan sus direcciones fijas del laboratorio. Si la IP cambia, el wrapper se detiene y se requiere adaptar esas copias conscientemente antes del próximo arranque.

## 4. Iniciar la interfaz

Se reutilizan `.venv` y `frontend/app/node_modules`. En el proyecto de interfaz:

```bash
cd ~/proyecto_nsfnet
bash scripts/compilar_interfaz.sh
```

En terminales separadas, cuando los puertos habituales estén libres:

```bash
bash scripts/iniciar_backend.sh
```

```bash
bash scripts/iniciar_frontend.sh
```

Abrir `http://127.0.0.1:5181/sdn-selector.html` **en la VM de interfaz**. Elegir NSFNET o GEANT2; no configurar manualmente el puerto del observador. Los scripts se niegan a ocupar puertos ya utilizados a través de Uvicorn/Vite; no detienen procesos para liberarlos.

Para una validación paralela, usar `SDN_API_PORT=8003`, compilar con `VITE_SDN_SELECTOR_API_URL=http://127.0.0.1:8003 SDN_DIST_DIR=dist-rutas-ml-validacion`, e iniciar frontend con `SDN_FRONTEND_PORT=5182 SDN_DIST_DIR=dist-rutas-ml-validacion`. Esa variante está disponible en esta entrega; no iniciar otra si esos puertos ya están ocupados.

## 5. Detener, recuperar y revertir

- **Consultar:** los comandos de la sección 1 no cambian la red.
- **Iniciar:** secciones 2–4 solo cuando no existen los servicios y redes correspondientes.
- **Detener:** Ctrl+C en la terminal propietaria de un servicio de interfaz. Para detener una red Mininet se requiere autorización: Ctrl+C en su worker cierra sus hosts, interfaces y sondas. No reutilizar PID del informe; consultar el estado y el proceso actual.
- **Recuperar:** si un puerto está ocupado o quedan bridges, inspeccionar identidad y estado. No borrar ni detener automáticamente nada. Resolver con el operador antes de repetir el arranque.
- **Revertir código:** seguir `RESPALDO_Y_ROLLBACK.md`. No restaurar modelos, datasets ni carpetas de telemetría para revertir esta ampliación.

Los logs nuevos se separan de los históricos. Los instaladores y launchers antiguos con PID fijos no deben reutilizarse como guía del próximo arranque.
