# Revisión actualizada de cumplimiento e importancia — SDN/KDN

> Revision anterior a implementar las consolas, hosts/controlador e inspectores ampliados. Se conserva como antecedente; consultar ESTADO_ACTUAL.md para el estado de esta publicacion.

Fecha de referencia del usuario: 9 de noviembre de 2026. Se contrastaron la imagen del requerimiento inicial del 50 %, los cuatro Markdown de `docs.rar`, el código local actual y las salidas/capturas compartidas por el usuario. No se modificaron las VMs ni el funcionamiento del proyecto durante esta revisión.

## Alcance y evidencia

El archivo `docs.rar` tiene SHA256 `741d7acf4263a93195b7b715f2d02709d628df72332e43c45a1f0b69742b959e`. Sus cuatro documentos coinciden byte a byte con la revisión anterior. Lo que cambió desde entonces es la implementación: ya se entrenaron/evaluaron cuatro modelos, se preparó el cálculo de cinco rutas por modelo y se añadió conservación de resultados para la sustentación.

La imagen contiene el alcance inicial más breve: Dijkstra no-ML y ML, dataset, modelo evaluado con MSE/RMSE/MAE, GUI JavaScript, switches/controlador/hosts, cambio de enrutamiento en tiempo real, GEANT o NSF, RYU, OFCTL REST y separación de planos. Los Markdown amplían ese alcance con modelos específicos, paneles técnicos y métricas detalladas. No todas esas ampliaciones aparecen literalmente en la imagen.

Se respetan dos cambios de alcance que el usuario confirmó como aceptados por el profesor: usar Windows como servidor de la interfaz/backend y permitir ambas topologías simultáneas. No se cuentan como faltantes la tercera VM de escritorio ni el apagado de una topología al visualizar la otra. La arquitectura real incluye aplicación web/API en Windows, plano de datos en Mininet y RYU junto con servicios de inferencia en la otra VM; no debe describirse como tres VMs físicamente separadas.

“Implementado” indica evidencia de código o ejecución aportada. “Parcial” indica que una parte del criterio falta. “Por demostrar” no implica que la función no exista: falta una evidencia concreta en la versión final.

## Estado frente a la imagen inicial

| Requisito | Estado | Importancia de lo pendiente |
|---|---|---|
| Dijkstra con pesos no-ML | Cálculo implementado: saltos, retardo e inverso de capacidad. La comparación principal usa el convencional por inverso de capacidad. | **Crítica**: demostrar que el camino convencional elegido se instala y conduce tráfico, no solo que se calcula. |
| Dijkstra con pesos obtenidos mediante ML | Implementado el cálculo de pesos dirigidos y no negativos y un camino por modelo; servicio de cuatro modelos cargado según salida RYU aportada. | **Crítica**: aplicar el camino elegido a flujos reales y verificarlo. La visualización completa de las cinco rutas con mediciones nuevas aún debe quedar documentada después del ajuste de relojes. |
| Dataset construido | Completado según el estado aportado: un CSV consolidado de unas 20,0155 horas totales para ambas topologías, con campo de topología y procedencia. | **Alta para entrega**: acompañarlo con esquema y método reales, sin describir todas sus filas como una única campaña homogénea. No es necesario repetirlo solo porque el documento de planificación esté desactualizado. |
| Modelo entrenado y evaluación MSE/RMSE/MAE | Cumplido con evidencia aportada: Polinomial, Decision Tree, Random Forest y XGBoost, validation y test descriptivo, métricas visibles en GUI. | **Alta para explicar**, sin nuevo entrenamiento obligatorio por este punto. El test ya fue examinado; no presentarlo como nueva evaluación independiente. |
| GUI basada en framework JavaScript | Cumplido: React, HTML/CSS/JS, Cytoscape, API y servidor Windows. | Mantener instrucciones y evidencias de la versión final. |
| Mostrar topología, switches, controlador y hosts | Parcial: se dibujan switches de núcleo y sus enlaces. Hosts figuran en detalles; controlador y hosts no se dibujan como elementos independientes. | **Alta y explícita en la imagen**: añadir hosts, controlador y conexiones de datos/control. No es solamente decoración. |
| Cambio de algoritmo de enrutamiento en tiempo real | Pendiente en el plano de datos. Cambiar criterios o comparar modelos modifica el cálculo, no los flujos de OVS. | **Crítica y explícita en la imagen**: cambiar el modo desde la GUI, confirmar aplicación y mostrar comunicación por el camino elegido sin recrear la red. Ambos modos siguen usando Dijkstra; cambian los pesos. |
| Red GEANT o NSF | Cumplido y ampliado: NSFNET y GEANT2 instrumentadas. | Mostrar la variante académica exacta y sus perfiles. Las ciudades son referencias visuales, no correspondencias históricas verificadas. |
| RYU | Implementado y mostrado en la arquitectura/servicios. | Guardar evidencia del controlador y sus switches en la demostración. |
| OFCTL REST | Implementado: consultas e instalación inicial de reglas en los scripts de red. | **Alta**: reutilizarlo para la aplicación solicitada desde la GUI y mostrar las reglas resultantes. |
| Planos en diferentes VMs | Cambio de despliegue aceptado por el profesor según confirmación del usuario. | Documentar Windows + dos VMs y la ubicación real de ML. No rehacer la arquitectura sin una nueva exigencia. |

## Matriz del documento ampliado

| ID | Estado actual | Cierre necesario |
|---|---|---|
| RF-SP-01 | Parcial | Cálculo 1/capacidad correcto; falta demostrar instalación y tráfico de la ruta convencional solicitada. |
| RF-SP-02 | Parcial | Inferencia y cálculo ML implementados; falta instalación y prueba de hosts sobre la ruta elegida. |
| RF-SP-03 | Construcción acreditada por salidas del usuario; documentación/entrega parcial | Entregar CSV, esquema y procedencia del consolidado real. Corregir las referencias a otra campaña del RAR. |
| RF-SP-04 | Entrenamiento y comparación completados según las salidas y GUI aportadas | Conservar los cuatro artefactos, protocolo, particiones y reportes. Declarar test descriptivo ya conocido. La polinomial es de grado 2 regularizada con Ridge; esa elección debe explicitarse. |
| RF-SP-05 | Cumplido | Aplicación web con React y servidor integrada. |
| RF-SP-06 | Parcial | Añadir hosts y controlador, distinguir conexiones de control y datos, conservar selección de switches. |
| RF-SP-07 | Pendiente | Solicitar y aplicar el cambio convencional/ML, confirmar modo activo o error, sin reiniciar las redes. |
| RF-SP-08 | Parcial | Existe identificación del switch, pero falta panel operativo por puerto: estado, contadores, tasas, descartes, errores y fecha. |
| RF-SP-09 | Cumplido conforme al alcance modificado | Selector de sesiones existentes y ambas topologías activas permitido. Registrar la aprobación del profesor. |
| RF-SP-10 | Parcial | Mostrar fabricante, software/hardware, total de puertos y estados reportados por OVS/RYU. DPID y asociación de host ya aparecen. |
| RF-SP-11 | Parcial | Se muestran configuración, RX Mbps, delay medio, pérdida ofrecida y rechazos TX. Faltan bits TX/RX, conteos de pérdidas, tasas TX, mínimos/máximos y estimación residual rotulada como estimación. |
| RF-SP-12 | Parcial | Se elige origen/destino y se resalta camino calculado. Falta camino verificado como instalado y distinción visible del modo realmente activo. |
| RF-SP-13 | No acreditado completamente | Hay promedio de delay, pérdida y throughput. Mínimo/máximo no aparecen en la exportación adicional revisada; verificar fuentes originales antes de concluir que sea necesaria otra captura. |
| RF-NP-01 | Cumplido | Ambas topologías implementadas; documentar variantes y perfiles de laboratorio. |
| RF-NP-02 | Infraestructura implementada; demostración final pendiente | Hosts y tráfico instrumentado existen. Falta demostrar comunicación y camino efectivo bajo cada modo aplicado desde la GUI. |
| RT-01 | Implementado | RYU controla los switches. Conservar prueba de ejecución final. |
| RT-02 | Implementado | OFCTL REST se utiliza. Falta prueba del nuevo circuito GUI → reglas para el modo seleccionado. |
| RT-03 | Excepción aceptada | No exigir tercera VM; documentar ubicación real de procesos. |
| RT-04 | Cumplido | Servidor web/API en Windows. |
| RT-05 | Configurado; negociación real por demostrar | Fuentes de creación declaran OpenFlow13. Guardar evidencia del protocolo negociado en los switches actuales; no confundir configuración con captura de una negociación. |

## Prioridad e importancia práctica

| Orden | Trabajo | Prioridad | Esfuerzo relativo | Por qué hacerlo |
|---|---|---|---|---|
| 1 | Aplicación de rutas y cambio de modo desde la GUI | **Crítica** | Alto | Cierra el objetivo de enrutamiento SDN. Sin ello, se demuestra un comparador y predictor, pero no el cambio efectivo del tráfico solicitado en la imagen. |
| 2 | Representar hosts y controlador y diferenciar planos | **Alta** | Bajo–medio | Es una exigencia gráfica explícita y permite explicar de dónde sale el tráfico y quién controla los switches. |
| 3 | Información de switches y puertos, y métricas faltantes de enlaces | **Alta en los requisitos ampliados y notas del usuario** | Medio | Hace verificables el estado y el tráfico. Parte de los contadores ya se recolecta, pero aún no se presenta. Que existan como entradas ML no equivale a que aparezcan en el inspector. |
| 4 | Evidencia de OpenFlow 1.3, reglas y comunicación | **Alta** | Bajo para protocolo; medio para prueba completa | Es una comprobación del sistema funcionando y una evidencia de entrega; no requiere inventar otro algoritmo. |
| 5 | Resolver mínimo/máximo del delay en el dataset y GUI | **Alta si se evalúa el documento ampliado** | Variable | No es el mismo requisito que mostrar delay medio. La imagen inicial no detalla esos extremos, pero los Markdown sí los exigen. |
| 6 | Actualizar documentación, paquete de entrega y repositorio | **Alta antes de entregar** | Bajo–medio | Lo que se entrega debe coincidir con lo que se demuestra. La copia Git preparada sigue en el commit 84312a5 y no contiene el endpoint nuevo de cinco rutas; los cambios posteriores están en la aplicación local. |
| 7 | Video y presentación de la arquitectura/resultados | **Alta para la entrega documental** | Medio | El RAR los exige. No se aportaron en esta revisión: no se afirma que no existan, pero falta confirmar su cobertura de la versión final. |

Los esfuerzos son relativos, no estimaciones de horas. No hay una ponderación de calificación que permita convertir estos estados en un porcentaje fiable de cumplimiento.

## Aplicar una ruta: qué debería demostrar el cierre crítico

1. Seleccionar origen y destino de una topología verificada.
2. Calcular convencional o una de las alternativas ML con una ventana válida y mostrar el camino propuesto.
3. Solicitar explícitamente su aplicación, identificando qué flujo/hosts se van a afectar.
4. Instalar reglas mediante RYU/OFCTL REST, conservando sondas, reglas de medición y tráfico ajeno a la demostración.
5. Leer las reglas y comprobar puertos de salida. Informar aplicado, error o recuperación, en lugar de cambiar solo una etiqueta de la GUI.
6. Mostrar comunicación entre hosts y evidencia de que el flujo usa el camino elegido. Probar también el sentido de retorno que corresponda al flujo.
7. Cambiar al otro modo desde la GUI y repetir la verificación sin recrear las redes.

Esto no exige convertir una de las cinco rutas calculadas en cinco reglas simultáneas para el mismo flujo. Se comparan alternativas y se aplica la que se seleccione. Tampoco exige que todos los modelos elijan caminos diferentes. La instalación debe evitar conflictos con las reglas existentes por destino MAC y con los procesos de medición.

## Importancia de los detalles de métricas

- Los bits son 8 × bytes. Para una ventana se usan deltas de contadores y su duración real; no se sustituye un total de bits por una tasa Mbps.
- Fabricante y versiones corresponden al switch virtual que informa OVS/RYU. No hay evidencia para atribuir fabricantes físicos históricos a cada nodo de NSFNET/GEANT2.
- Descartes OpenFlow, descartes de colas y pérdida de sondas son magnitudes diferentes. Una resta de contadores de tráfico agregado no acredita automáticamente paquetes perdidos de una aplicación concreta.
- El ancho de banda residual, si se añade como capacidad menos tasa observada, debe rotularse como estimación y no como una prueba de ancho de banda disponible.
- El delay mínimo/máximo no se puede obtener a partir del promedio. Si existen tiempos individuales originales puede calcularse desde ellos; si no, se necesita medición nueva y documentar su cobertura real. Una captura suplementaria no convierte las filas viejas en mediciones de extremos que no conservaron.
- Las cinco tarjetas usan agregaciones de enlaces. Eso no demuestra que la ruta ya se haya instalado ni reemplaza una medición extremo a extremo después de aplicarla.

## Qué ya no conviene tratar como pendiente

Los cuatro modelos ya fueron entrenados y evaluados; XGBoost quedó seleccionado por validation con un score global normalizado menor entre los candidatos. Eso no implica ganar cada métrica o cada subconjunto del test. No se requiere otro entrenamiento para resolver la instalación de reglas o los paneles.

Comparar cinco alternativas es una ampliación solicitada por el usuario. El mínimo del documento exige convencional frente a ML seleccionado; no exige desplegar todos los modelos ni que sus caminos difieran. La polinomial se incluye como alternativa experimental, pero su referencia de entrenamiento sigue siendo baseline.

Los mapas geográficos y conservar una comparación para sustentación son ayudas ya implementadas. No sustituyen requisitos operativos. Los resultados guardados se identifican con su ventana original y no prueban que la red siga en ese estado; una demostración de cambio en tiempo real debe usar estado actual y confirmar la aplicación.

## Evidencia y limitaciones de esta revisión

El backend local declara `rules_installed=False` en los endpoints de cálculo. El código de recuperación de las redes contiene programación inicial mediante `/stats/flowentry/add`, con caminos calculados por retardo configurado, pero ese mecanismo no está conectado a las cinco tarjetas ni al cambio de modo solicitado en la GUI.

Las capturas del usuario acreditan entrenamiento, evaluación, importación de informes y servicio RYU con los cuatro modelos cargados. Después se confirmó alineación manual de relojes y se preparó persistencia de la comparación. No se aportó después una captura completa de las cinco rutas con inferencia disponible; no se da esa comprobación de extremo a extremo por realizada.

El código actual del gráfico construye elementos únicamente desde switches y enlaces de núcleo. El inspector muestra DPID, host asociado y configuración, pero no descripciones del fabricante ni la tabla operativa de todos los puertos. Las mediciones de enlace muestran RX, delay medio, pérdida ofrecida y rechazos locales.

Esta revisión es de alcance y evidencia; no ejecutó pruebas repetitivas, no accedió administrativamente a las VMs y no implementó los pendientes. El informe anterior se conserva como antecedente y debe leerse con esta actualización: su pendiente de comparación de modelos ya quedó resuelto.
