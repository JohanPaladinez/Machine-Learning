# Mapas de referencia y comparación de cuatro rutas

Actualización local del 9 de noviembre de 2026 en `Interfaz_SDN_Windows_Rutas_ML`. Panel de producción: http://127.0.0.1:8003/sdn-selector.html.

## Resultado

La comparación presenta menos saltos, retardo configurado, inverso de capacidad nominal y ML. Muestra cuatro tarjetas, una tabla común, colores por criterio y controles para aislar o combinar trazados. Señala caminos coincidentes y enlaces compartidos. No fuerza caminos diferentes ni instala reglas en RYU.

Los cuatro caminos se evalúan con las mismas predicciones direccionales por enlace y la misma ventana. Cada criterio mantiene su costo propio y sus unidades. Si ML falta o caduca, quedan los tres caminos de configuración y se retiran las cifras previstas. Si falta un retardo configurado, ese criterio se declara no disponible.

NSFNET y GEANT2 incorporan ciudades reales de Estados Unidos y Europa, respectivamente, con mapa geográfico y esquema de red. Los detalles de nodo muestran el país y las coordenadas aproximadas. Las ciudades son referencias visuales del laboratorio: la asociación de una ciudad a s1…sN no está históricamente verificada. Los perfiles BNN numerados consultados no contienen nombres ni coordenadas geográficas útiles.

Los IDs usados por las API, los enlaces, las capacidades, los retardos y los puertos se conservan. La geografía se aplica solo al grafo esperado. No determina costos de ruta ni mediciones de latencia.

## Archivos principales

Dentro de la carpeta Windows:

- `backend/servicios/comparacion_rutas.py`: cálculo de los cuatro criterios, resumen común y coincidencias. Conserva la fórmula QoS y la compatibilidad del cálculo anterior.
- `backend/api/sdn_comparacion.py`: respuesta de cuatro criterios, comprobaciones de identidad, ventana y disponibilidad; conserva los alias anteriores.
- `frontend/app/src/sdn-selector-v2/ComparacionRutas.jsx` y `comparisonView.js`: tarjetas, tabla, trazados y retirada de predicciones caducadas.
- `frontend/app/src/sdn-selector-v2/PanelSdn.jsx` y `presentation.css`: mapas, controles, detalles de lugares y resaltado de rutas.
- `frontend/app/src/geografia/`: ciudades, proyección, fondo cartográfico incluido localmente y comprobación del grafo.
- `frontend/app/src/sdn-vivo-v1/graph.js`: enriquecimiento visual conservando los IDs.
- `frontend/app/dist-sdn-selector-v2/`: compilación actual para la API de producción del puerto 8003.

No se editaron las VMs ni sus archivos, el dataset consolidado ni los modelos. No se publicaron cambios en GitHub.

## Validación

- Pasaron las 23 pruebas originales de Python, seis pruebas nuevas de cuatro rutas y seis de geografía/presentación en Node.
- Las comprobaciones HTTP con datos sintéticos verificaron cuatro resultados, alias anteriores, ausencia/caducidad de ML, rechazo de alias de ciudad como ID y rechazo de un cambio de selección durante el cálculo.
- ESLint de los archivos de interfaz modificados y compilación de producción completados.
- Revisión de navegador en un servidor separado, con aviso permanente de datos sintéticos: NSFNET y GEANT2, mapas geográfico/esquema, cuatro tarjetas y tabla, y trazado individual ML. Ese servidor de prueba se detuvo al finalizar.
- La comparación actualizada con las VMs reales queda por comprobar al reiniciar únicamente la aplicación Windows. La prueba visual no constituye una evaluación de rendimiento del tráfico real.

## Uso y respaldo

Ejecutar `Detener_interfaz.cmd` y después `Abrir_interfaz.cmd` en Windows. Mantener los servicios y las redes existentes de RYU y Mininet. Abrir el panel y pulsar **Comparar las 4 rutas** en Enrutamiento; recargar con Ctrl+F5 si el navegador conserva archivos anteriores.

Respaldo de los archivos previos y de la compilación anterior: `respaldos/geografia_cuatro_rutas_a6a25345`, con manifiesto de hashes `respaldo.json`.

## Corrección de la carga del backend (1.1.1)

La respuesta del servicio Windows que seguía abierto solo contenía los campos anteriores `convencional` e `inteligente`; no contenía `rutas`. Esto provocaba que la interfaz nueva mostrara las tarjetas de saltos y retardo sin resultados y las atribuyera incorrectamente a configuración insuficiente.

El estado de salud actual anuncia los cuatro criterios y el lanzador comprueba esa capacidad antes de reutilizar un proceso propio. La interfaz rechaza explícitamente respuestas del contrato anterior y explica que hay que cargar el backend actualizado. Se conserva la comprobación de identidad de cada proceso y no se detienen servicios ajenos.

Pasaron cuatro pruebas del contrato de arranque, tres pruebas de detección de respuestas antiguas, ESLint de los dos archivos modificados y la compilación para 8003. Además, se leyó un estado real de GEANT2 desde la API Windows y se calcularon los tres criterios clásicos con el código actualizado: saltos, 5; retardo configurado mínimo, 75 ms; inverso de capacidad, 1,3333333333333333 sobre 6 saltos. Saltos y retardo eligieron el mismo camino, lo cual es válido.

El proceso que seguía abierto no pudo identificarse/cerrarse desde el entorno de ejecución del agente. La carga en el proceso real queda pendiente de ejecutar el lanzador en la sesión normal de Windows. La conexión directa a las VMs desde el entorno de prueba fue rechazada; no se afirma una prueba completa de cuatro rutas en producción. El respaldo previo a esta corrección está en `respaldos/criterios_api_20261109T230312Z`.

## Fuentes

- [Natural Earth: términos de uso y dominio público](https://www.naturalearthdata.com/about/terms-of-use/). Cartografía simplificada incluida localmente; no requiere claves ni servicios de mapas.
- [BNN-UPC: topologías numeradas](https://github.com/BNN-UPC/DRL-ES-OTN/tree/main/dataset_Topologies). Referencia de los grafos, no de la asignación de ciudades.
- [NSF: historia de NSFNET](https://www.nsf.gov/impacts/internet).
- [GÉANT2/DANTE, presentación de 2005](https://indico.cern.ch/event/408143/contributions/980571/attachments/816363/1118606/GEANT2_EGEE_18_4_05_ppt.pdf).
