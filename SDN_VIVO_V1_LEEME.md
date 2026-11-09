# Mininet, RYU y la interfaz conectados

Esta ampliación conserva el código anterior y prepara un panel que consulta la sesión real de Mininet y verifica sus interfaces contra los puertos OpenFlow de RYU. Los archivos están preparados aquí; la instalación y la comprobación entre tus VMs se hacen ejecutando los dos instaladores.

## Instalación

1. **VM Mininet:** abre `instalar_observador_mininet_v1.sh`, copia su contenido completo y pégalo en su terminal. Solicita sudo para leer las carpetas de sesión que Mininet crea como administrador. Añade un observador de solo lectura en el puerto 8766 y muestra `URL PARA EL PANEL: http://IP:8766`. Déjalo funcionando. No inicia otra topología ni modifica la captura.
2. **VM de la interfaz (`vboxuser@ubuntu-vm`):** abre `instalar_integracion_interfaz_v1.sh`, copia su contenido y pégalo. Añade una entrada a tu API, comprueba la compilación y arranca el backend nuevo en 8001 y el panel nuevo en 5180. Reutiliza las dependencias que ya están instaladas. No necesita detener la API ni la interfaz anteriores.
3. Abre Firefox **en la VM de la interfaz**, entra en `http://127.0.0.1:5180/sdn-vivo.html`, copia en el campo Mininet la URL del primer paso y pulsa **Conectar a Mininet**.

No ejecutes repetidamente los instaladores. Si un destino o puerto ya existe, se conserva y el instalador se detiene; pega el mensaje para continuar desde lo que ya esté instalado. No se instala ningún paquete ni se modifica `package.json`.

El observador y los dos servidores se inician como procesos independientes de la terminal, pero se detienen al apagar sus VMs. Los instaladores imprimen los PID y las ubicaciones de sus registros. La dirección de Mininet se conserva en memoria del backend: al reiniciar ese backend hay que conectarla otra vez, o configurar `SDN_MININET_URL` al arrancarlo.

## Qué se reconoce automáticamente

- La captura `sdn_noche_capturar.py` ya iniciada: lee `estado.json` y `config.json`, comprueba su proceso y verifica los pares veth reales `nc*-eth*`. Identifica NSFNET o GEANT2 por la fase registrada, no por su cantidad de nodos. Usa el REST dedicado registrado por esa captura.
- Las sesiones del lanzador `topologia_dual_sdn.py` situado en la carpeta de preparación: lee su `topologia_activa.json`, comprueba su proceso y que no exista `sesion_cerrada.json`, y observa las interfaces que registró. Cuando uses este lanzador después de la captura, indica el REST real de su controlador en la opción correspondiente del panel si la sesión no lo publica. El puerto OpenFlow y el puerto REST son distintos.
- Si hay varias sesiones registradas activas, muestra la ambigüedad y no elige una arbitrariamente. Si detecta interfaces sin una sesión registrada, lo indica; un script antiguo que no publica su sesión todavía necesita esa adaptación. No se promete descubrir automáticamente cualquier script de Mininet desconocido.

La consulta del panel se realiza cada 5 segundos. Se comprueba `/stats/switches` y se comparan los números y nombres de los puertos de RYU con las interfaces del lanzamiento de Mininet. Las descripciones de puertos se reutilizan hasta 30 segundos para limitar consultas; al calcular una ruta se fuerzan lecturas nuevas. Con los mismos DPID, pero nombres de interfaz de otra red, se rechaza la asociación.

## Qué información muestra

El grafo, los DPID, nombres físicos de switches, hosts, IP y puertos pertenecen al lanzamiento seleccionado. Los enlaces muestran su estado observado, capacidad nominal, retardo configurado y cola configurada. Las rutas se calculan en FastAPI sobre el grafo verificado, reutilizando tus funciones `calcular_ruta` y `calcular_costo_capacidad`. El navegador envía origen, destino, criterio y versión de la sesión; no manda un grafo de demostración. Los enlaces conocidos como caídos se excluyen. Cambiar de sesión o de estado invalida una ruta anterior.

**Calcular una ruta no instala reglas OpenFlow.** Durante la captura se conserva la política del experimento. La aplicación de rutas y la comparación de políticas sobre tráfico real se conectan y prueban después, de forma separada de este cálculo.

Las mediciones de Throughput RX, Delay y Loss se toman de la última ventana completa y válida que el recolector existente ya escribió en `captura_adicional.csv`. Se leen como máximo los últimos 512 KiB del archivo; no se relee el dataset completo. No se generan sondas nuevas, no se estiman pérdidas restando contadores desincronizados y no se usa el retardo configurado como si fuera una medición. En un cambio a GEANT2 no se reutilizan las mediciones anteriores de NSFNET.

Las mediciones incluyen fecha de inicio y fin, antigüedad y método. Pueden renovarse cada decenas de segundos, según las ventanas reales del capturador: consultar la pantalla cada 5 segundos no crea una muestra nueva. Pasados 120 segundos se señalan como antiguas. Los valores ausentes se mantienen ausentes. El Loss de la captura actual incluye rechazos locales de envío; estos se muestran por separado y no se presentan como pérdida exclusivamente en tránsito.

Para una sesión manual sin un recolector compatible registrado, la topología y las rutas pueden estar disponibles y las métricas figuran pendientes. Conectar otro recolector exige conocer su formato y su procedencia; no se inventan muestras.

## Archivos conservados y entradas nuevas

No se reemplazan scripts anteriores de Mininet, archivos originales de FastAPI, `App.jsx`, `App.css`, `index.css`, `main.jsx`, `vite.config.js`, `package.json`, el `dist` original, datasets ni modelos. La entrada original `backend.api.main:app` se importa en un proceso nuevo y se le añade un router en memoria. El backend anterior puede seguir en 8000.

En la tercera VM se añaden `backend/api/sdn_vivo_v1.py`, `backend/servicios/sdn_vivo_runtime_v1.py`, `iniciar_sdn_vivo_v1.py` y el frontend `frontend/app/src/sdn-vivo-v1/`, `sdn-vivo.html`, `vite.sdn-vivo.config.js` y `dist-sdn-vivo-v1`. Los registros nuevos quedan en `sdn_vivo_ejecucion_v1`.

El modelo ML común permanece pendiente de conectar después de finalizar y validar el único dataset consolidado de **20 horas totales entre ambas topologías**, conservando `topologia` y las fuentes anteriores.

## Verificación y límites

Pasaron seis pruebas con archivos y respuestas de protocolo simulados: unión de la sesión Mininet con la identidad de RYU sin escribir las fuentes; cambio de topología incluso con idéntico número de nodos; rechazo de otro controlador con los mismos DPID; puerto caído que invalida rutas; proceso de captura terminado; y lectura de un CSV mientras su última fila todavía está incompleta. También pasó la lectura del documento generado por el observador con el adaptador JavaScript del frontend, incluidos los nombres físicos `nc*` y `nh*`.

Se comprobó la sintaxis de Python y la compatibilidad del observador con la gramática de Python 3.6. El backend nuevo usa el mismo entorno moderno que tu API original. Aquí no están instalados FastAPI, Uvicorn ni las dependencias de React, y el entorno impide la descarga de npm y las conexiones de prueba a sockets locales. Por eso las pruebas usan un transporte simulado: **no acreditan una conexión real entre tus VMs ni una compilación o revisión visual del frontend**. Los instaladores comprueban el arranque y la compilación en tus VMs; el resultado real depende de la salida que compartas.

Referencias: [lecturas de switches y puertos en RYU](https://ryu.readthedocs.io/en/latest/app/ofctl_rest.html), [integración mediante routers de FastAPI](https://fastapi.tiangolo.com/tutorial/bigger-applications/), [entradas HTML y compilación de Vite](https://vite.dev/guide/build.html#multi-page-app).
