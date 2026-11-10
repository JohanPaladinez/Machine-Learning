# Machine Learning — SDN/KDN

Laboratorio de visualizacion, telemetria y comparacion de rutas sobre **NSFNET y GEANT2**. El panel y FastAPI funcionan en Windows; Mininet y RYU permanecen en sus VMs. Se admiten ambas topologias simultaneas.

## Estado actual — 10 de noviembre de 2026

- **Cinco alternativas de ruta:** Dijkstra convencional (suma de 1/capacidad nominal) y Dijkstra con pesos derivados de cada modelo: polinomial, Decision Tree, Random Forest y XGBoost.
- Las cinco rutas presentan los mismos siete indicadores: saltos, retardo configurado, costo inverso de capacidad, QoS observado, suma de delay medido, perdida medida compuesta y capacidad minima nominal. Las previsiones de cada modelo se muestran por separado.
- Comparacion de modelos con MSE, RMSE, MAE, R² y conteo de predicciones fuera de rango. XGBoost fue seleccionado usando validacion; el test posterior se presenta como descriptivo porque ya se habia examinado.
- Resultados completos guardados en el navegador para la sustentacion, conservando fecha, ventana e identidad. Un resultado guardado no se presenta como una medicion actual. Las solicitudes de inferencia nuevas siguen exigiendo entradas recientes.
- Mapas geograficos y esquemas con switches, hosts, enlaces de acceso y controlador RYU. Las conexiones de control se distinguen de los enlaces de datos y no participan en Dijkstra.
- Inspector operativo: fabricante, plataforma y version reportados por RYU; puertos, estado, bits y paquetes TX/RX, descartes, errores y tasas. Los datos ausentes se indican, nunca se reemplazan por cero.
- Ventanas nuevas de enlace con delay promedio/minimo/maximo de sondas, throughput TX/RX, bits, paquetes y sondas no recibidas. Perdida ofrecida, rechazos locales y descartes de puerto/cola se identifican por separado.
- **Dos consolas Mininet reales**, una por red, con `nodes`, `links`, `ports`, `pingall` y `telemetria`. Los recolectores miden esas mismas redes mientras se usan las consolas.

**Enrutamiento real implementado:** la seccion **Aplicar y demostrar la ruta** prepara una alternativa convencional o ML, instala sus reglas ICMP mediante RYU y verifica los contadores de todos los saltos de ida y regreso. Permite cambiar de alternativa y retirar exclusivamente las reglas propias. El usuario aporto capturas y confirmo funcionamiento y retiro en NSFNET y GEANT2. La comparacion por si sola sigue sin instalar reglas. Esta evidencia demuestra el recorrido ICMP; no demuestra una mejora de rendimiento extremo a extremo. Consultar [la guia de demostracion](documentacion/GUIA_ENRUTAMIENTO_REAL_ICMP.md).

Las ciudades son referencias visuales reales del laboratorio; la correspondencia historica de cada ciudad con s1…sN no ha sido verificada. Se conservan IDs y conexiones.

## Ejecutar la interfaz en Windows

Requisitos: Python 3.10 o posterior y Node.js compatible con Vite 8. El instalador comprueba las versiones. Desde PowerShell en la raiz del clon:

```powershell
python instalar_windows.py
.\Abrir_interfaz.cmd
```

El instalador crea `.venv`, instala dependencias y compila React. El panel y FastAPI comparten [http://127.0.0.1:8003/sdn-selector.html](http://127.0.0.1:8003/sdn-selector.html). No hace falta una tercera VM ni ejecutar Vite por separado.

Para cargar cambios del backend, ejecutar `Reiniciar_interfaz.cmd` (Detener y despues Abrir); recargar el navegador con Ctrl+F5. Los `.cmd` se ejecutan con doble clic o como archivos: no se pega su contenido en PowerShell. La guia ampliada esta en [LEEME_WINDOWS.md](LEEME_WINDOWS.md).

## Arranque diario y apagado

Con las dos VMs encendidas: ejecutar `Arrancar_RYU.cmd`, esperar **RYU LISTO**, ejecutar `Abrir_consolas_Mininet.cmd`, esperar ambas consolas y abrir `Abrir_interfaz.cmd`. Mantener abiertas las dos consolas de red.

Los lanzadores diarios reutilizan las fuentes instrumentadas y los modelos que ya existen en las VMs del laboratorio; no crean un laboratorio completo a partir de un clon vacio. No entrenan, cambian relojes ni detienen procesos desconocidos. El nuevo lanzador RYU se reviso localmente; su primer arranque completo despues de apagar las VMs queda por comprobar. Consultar [todos los comandos y el orden de apagado](documentacion/GUIA_APAGADO_Y_ARRANQUE_SDN.md).

## Consolas interactivas de Mininet

Mantener RYU y sus servicios disponibles. Desde Windows, ejecutar **Instalar_consolas_Mininet.cmd**. Copia los dos lanzadores y abre dos ventanas SSH; cada una pide las credenciales de Mininet y sudo. Se esperan los prompts:

```text
mininet-geant2>
mininet-nsfnet>
```

En cada consola se pueden ejecutar `nodes`, `links`, `net`, `ports`, `pingall` y `telemetria`. GEANT2 usa switches nc/hosts nh; NSFNET usa ns/nsh para evitar colisiones. `exit` o cerrar SSH detiene solo la red de esa terminal. Mantener las dos abiertas.

La version 1.1 reserva el observador con reutilizacion de direccion TCP, sin compartir un listener activo, antes de crear Mininet. El usuario confirmo el funcionamiento de ambas consolas tras esta correccion. El usuario confirmo tambien el trafico por las rutas aplicadas y su retiro en ambas topologias. Los resultados de `pingall` y las mediciones de rendimiento son comprobaciones diferentes.

El lanzador **requiere las carpetas instrumentadas y configuraciones existentes en la VM**. Identifica su propietario, conserva una copia de sus fuentes y reemplaza limpiamente solo esa sesion. No ejecuta una limpieza global ni borra modelos o datasets. Consultar [la guia de consolas](consolas_mininet_v1/LEEME.md).

## Servicios del laboratorio

Editar `configuracion_windows.json` si cambian las direcciones. Son direcciones privadas de ejemplo del laboratorio, no credenciales.

| Servicio | Direccion / puerto |
|---|---|
| Observador NSFNET / Mininet | http://192.168.56.107:8769 |
| Observador GEANT2 / Mininet | http://192.168.56.107:8768 |
| RYU REST NSFNET / OpenFlow | http://192.168.56.108:18081 / 16654 |
| RYU REST GEANT2 / OpenFlow | http://192.168.56.108:18080 / 16653 |
| Modelo individual del inspector | http://192.168.56.108:8010 |
| Servicio de cuatro modelos | http://192.168.56.108:8011 |

El inspector y la ruta ML individual conservan el servicio 8010. **Comparar las 5 rutas** usa 8011. OpenFlow 1.3 esta configurado al crear los switches; el inspector no inventa la version negociada si REST no la publica. Encender las VMs no implica iniciar automaticamente sus servicios.

## Dataset, entrenamiento y modelos

Un unico dataset consolidado contiene **20,0155 horas documentadas totales entre las dos topologias**, con campo `topologia` y procedencia diferenciada. El esquema usa 60 entradas y seis objetivos: throughput RX, delay y perdida en ambos sentidos.

- [Comparacion y entrenamiento de cuatro modelos](comparacion_ml_sdn/LEEME.md): entorno RYU aislado, protocolo y validacion. No repetir el entrenamiento ya completado para abrir el panel.
- [Servicio de inferencia de cuatro modelos](rutas_cinco_modelos_ryu/LEEME.md): verifica hashes y conserva el servicio anterior.
- [Estado, metodologia y limites](documentacion/ESTADO_ACTUAL.md).

Los datos y pesos entrenados permanecen en RYU y **no se publican como parte del codigo**:

- Dataset: `/home/ryu/proyecto_nsfnet/datos/nocturna_c064e9fb0ad2_win4e5zw/dataset_consolidado_20h.csv`.
- Modelo individual: `/home/ryu/proyecto_nsfnet/resultados_comun_20261107T205101/modelo_20261107T205202Z_n4vncu_0/modelo_comun.pkl`, junto a su `evaluacion_test.json`.
- Comparacion de cuatro modelos: el archivo `~/proyecto_nsfnet/comparacion_ml_sdn/ultima_comparacion.txt` apunta al trabajo; su registro identifica `CARPETA_COMPARACION`.

Clonar no reconstruye esos artefactos ni equivale a copiar las VMs. Los informes reales de evaluacion pueden cargarse desde RYU en la GUI; los archivos de pruebas del repositorio son sinteticos. La perdida ofrecida incluye rechazos locales. El throughput RX y la capacidad residual estimada no demuestran ancho de banda disponible.

El ajuste manual de relojes se conserva en `Alinear_relojes_VMs.cmd`, como herramienta opcional bajo accion expresa del usuario. No se ejecuta al iniciar el panel o las redes y no configura NTP. Las comparaciones guardadas no necesitan repetir ese ajuste para seguir visibles.

## Organizacion

- `backend/`, `frontend/app/`: API, calculos, inspectores y panel actual.
- `consolas_mininet_v1/`, `Instalar_consolas_Mininet.cmd`: consolas reales y telemetria.
- `arranque_diario_sdn/`, `Arrancar_RYU.cmd`, `Abrir_consolas_Mininet.cmd`: arranque diario sobre las VMs existentes.
- `comparacion_ml_sdn/`: scripts del experimento de cuatro regresores y dependencias RYU Python 3.6.
- `rutas_cinco_modelos_ryu/`: inferencia adicional del puerto 8011.
- `laboratorio/`: fuentes de recuperacion de la entrega anterior; no son una extraccion nueva de las VMs actuales. Su documentacion se conserva como historial.
- `tests/`: pruebas sinteticas; `tests/ml/` contiene el circuito de entrenamiento de prueba.
- `documentacion/`, `evidencias/`: estado actual, limitaciones, historial y captura del mapa.

## Comprobar el codigo sin contactar las VMs

En un entorno de pruebas aislado, distinto de `entorno_ml` de RYU:

```powershell
python -m pip install -r requirements-ci.txt
python -m pytest tests -q --ignore=tests/ml
node --test tests/*.mjs
```

El circuito sintetico de entrenamiento usa otro entorno de Python 3.12 o posterior con `requirements-ci-ml.txt` y se ejecuta con `python -m pytest tests/ml -q`. Las versiones modernas de CI no sustituyen las versiones fijadas en `comparacion_ml_sdn/requirements-ryu-py36.txt` para la VM antigua. Las comprobaciones reales de trafico se realizan separadamente; no se entrenan modelos ni se contactan las VMs durante las pruebas sinteticas.

## Procedencia

Basado en [Sergio777gg/sdn-kdn-rutas-ml](https://github.com/Sergio777gg/sdn-kdn-rutas-ml), commit `aeab8d50f7de505672b3940c9905ed9ee5929194`, con los cambios de este laboratorio. Cartografia de [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/) y referencia de grafos numerados de [BNN-UPC](https://github.com/BNN-UPC/DRL-ES-OTN/tree/main/dataset_Topologies). Se mantiene la atribucion y no se añade una licencia general sin decision de los autores.

Entornos, dependencias instaladas, datos, pesos entrenados, respaldos, sesiones y credenciales quedan excluidos mediante `.gitignore`.