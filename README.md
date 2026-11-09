# Machine Learning — SDN/KDN

Proyecto de visualización y comparación de rutas sobre NSFNET y GEANT2, con RYU y Mininet en máquinas virtuales y la interfaz ejecutándose directamente en Windows.

## Versión actual

- Selección de NSFNET o GEANT2 y verificación de la red observada en Mininet/Ryu.
- Mapas geográficos y esquemas de red, con ciudades de referencia e inspección de nodos y enlaces.
- Cuatro criterios: menor número de saltos, menor retardo configurado, inverso de capacidad nominal y ruta con métricas previstas por ML.
- Las cuatro tarjetas y la tabla presentan los mismos siete indicadores: saltos, retardo configurado, inverso de capacidad, QoS previsto, delay previsto, pérdida prevista y capacidad mínima nominal.
- Colores por criterio, enlaces compartidos, caminos coincidentes y controles para aislar trazados.
- Predicciones por enlace de la siguiente ventana, con comprobación de identidad, entradas completas y antigüedad máxima de 120 segundos.

La comparación calcula caminos; no instala reglas ni demuestra una mejora de rendimiento del tráfico real. Las métricas previstas se distinguen de las medidas y de los valores configurados. Las ciudades son ubicaciones reales asignadas como referencias visuales del laboratorio: su asociación con s1…sN no es una identificación histórica verificada. Los IDs y conexiones originales se conservan.

## Ejecutar en Windows

Requisitos: Python 3.10 o posterior y Node.js compatible con Vite 8 (22.12 o posterior; también se admite la rama 20 desde 20.19). Git es necesario para clonar.

Después de clonar, abre PowerShell en esta carpeta y ejecuta:

```powershell
python instalar_windows.py
.\Abrir_interfaz.cmd
```

El instalador crea un entorno Python propio, instala las dependencias y compila la interfaz. El panel y FastAPI comparten [http://127.0.0.1:8003/sdn-selector.html](http://127.0.0.1:8003/sdn-selector.html). No es necesario arrancar Vite por separado ni usar una tercera VM de interfaz.

Para detener solo esta aplicación:

```powershell
.\Detener_interfaz.cmd
```

Los archivos `.cmd` se ejecutan: no hay que copiar su contenido dentro de PowerShell. Las VMs y sus servicios se mantienen por separado. La guía ampliada está en [LEEME_WINDOWS.md](LEEME_WINDOWS.md).

## Conexiones del laboratorio

Edita `configuracion_windows.json` si las direcciones de tus VMs son diferentes y reinicia la aplicación Windows.

| Servicio | Configuración del laboratorio |
|---|---|
| Observador NSFNET / Mininet | http://192.168.56.107:8769 |
| Observador GEANT2 / Mininet | http://192.168.56.107:8768 |
| RYU REST NSFNET | http://192.168.56.108:18081 |
| RYU REST GEANT2 | http://192.168.56.108:18080 |
| Inferencia del modelo común / RYU | http://192.168.56.108:8010 |

Puertos OpenFlow: NSFNET 16654; GEANT2 16653. Encender las VMs no garantiza que sus controladores, observadores y servicio de inferencia estén en ejecución. La interfaz necesita acceso HTTP a esos servicios.

## Dataset y modelo

Se completó un dataset consolidado de **20 horas totales entre ambas topologías**, con procedencia diferenciada y campo `topologia`. El modelo común utiliza 60 entradas y seis salidas direccionales: throughput RX, delay y pérdida en ambos sentidos. El entrenamiento y la evaluación final ya se realizaron en RYU.

Los archivos originales permanecen en RYU y **no están incluidos en este repositorio**:

- Dataset: `/home/ryu/proyecto_nsfnet/datos/nocturna_c064e9fb0ad2_win4e5zw/dataset_consolidado_20h.csv`.
- Modelo: `/home/ryu/proyecto_nsfnet/resultados_comun_20261107T205101/modelo_20261107T205202Z_n4vncu_0/modelo_comun.pkl`.
- Evaluación guardada: `evaluacion_test.json` junto al modelo.

Clonar este código no reconstruye por sí solo esos artefactos ni el contenido completo de las VMs. El panel consume el servicio de inferencia existente; no reentrena ni necesita copiar el modelo a Windows. La pérdida de las sesiones instrumentadas incluye rechazos locales de sondas y el throughput RX no equivale a ancho de banda disponible.

## Organización

- `frontend/app/`: React, Cytoscape, mapas y comparación.
- `backend/`: FastAPI, cálculo de rutas, verificación de fuentes e integración ML.
- Lanzadores y `requirements-windows.txt`: ejecución nativa en Windows.
- `laboratorio/`: copias de recuperación de scripts y perfiles RYU/Mininet procedentes de la entrega anterior. No constituyen una copia recién extraída de las VMs actuales.
- `tests/`: pruebas sintéticas y comprobaciones explícitas del laboratorio.
- `documentacion/` y `evidencias/`: arquitectura, cambios e historial. Las guías de puertos 5181/5182 y de la tercera VM describen versiones anteriores; para esta versión utiliza esta guía y LEEME_WINDOWS.

Los entornos, dependencias instaladas, registros de ejecución, respaldos, CSV, modelos y credenciales se excluyen mediante `.gitignore`.

## Comprobaciones

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ci.txt
.\.venv\Scripts\python.exe -m pytest tests -q
node --test tests/test_geografia_cuatro.mjs tests/test_contrato_cuatro_frontend.mjs
```

Estas pruebas sintéticas no necesitan las VMs. La compilación se realiza con `python instalar_windows.py`. El script `tests/validar_en_vivo.py` es una comprobación separada que consulta redes reales y puede cambiar la selección del backend probado; no forma parte del arranque habitual.

## Procedencia

Basado en [Sergio777gg/sdn-kdn-rutas-ml](https://github.com/Sergio777gg/sdn-kdn-rutas-ml), commit `aeab8d50f7de505672b3940c9905ed9ee5929194`, con adaptación Windows, cuatro criterios, métricas comunes y mapas añadidos en esta entrega.

Cartografía incluida localmente: [Natural Earth, dominio público](https://www.naturalearthdata.com/about/terms-of-use/). Referencia de grafos numerados: [BNN-UPC](https://github.com/BNN-UPC/DRL-ES-OTN/tree/main/dataset_Topologies). Se conserva la documentación de procedencia; no se añade una licencia general al código sin decisión de sus autores.
