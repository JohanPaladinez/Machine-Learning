# Usar SDN/KDN en Windows — version actual

El panel React y FastAPI se ejecutan en Windows, puerto 8003. Mininet y RYU siguen en sus VMs. Esta guia sustituye las instrucciones de la antigua tercera VM y de las cuatro tarjetas por criterio.

## Instalar y abrir

En un clon nuevo, ejecutar `python instalar_windows.py` desde la raiz. Despues hacer doble clic en `Abrir_interfaz.cmd`. Abrir http://127.0.0.1:8003/sdn-selector.html. Node solo se utiliza para compilar; no hace falta iniciar Vite por separado.

Para cargar cambios de backend, ejecutar `Detener_interfaz.cmd` y luego `Abrir_interfaz.cmd`. Recargar Ctrl+F5. Los archivos cmd se ejecutan; su contenido no se pega en PowerShell. El gestor comprueba el contrato del servidor y la identidad de los procesos propios. No detiene servicios ajenos para liberar puertos.

## Redes y consolas

Mantener RYU, sus controladores y los servicios de modelos disponibles. Ejecutar `Instalar_consolas_Mininet.cmd` para abrir las dos consolas SSH y autenticar Mininet/sudo. El lanzador requiere las fuentes instrumentadas existentes en la VM y conserva sus archivos anteriores. La correccion 1.1 de la reserva TCP ya fue confirmada por el usuario.

Se esperan `mininet-geant2>` y `mininet-nsfnet>`. En cada una se admiten `nodes`, `links`, `net`, `ports`, `pingall` y `telemetria`. La medicion continua en un hilo sobre esa misma red; `exit` o cerrar SSH termina solo esa topologia. Mantener ambas ventanas abiertas. No usar limpieza global para resolver un fallo de una sola sesion.

En el panel seleccionar NSFNET o GEANT2 y esperar identidad de red verificada y telemetria reciente. Despues de recrear una red, seleccionar su sesion nueva. El estado de FastAPI, de RYU y del modelo se comprueba por separado.

## Comparar las cinco rutas

1. Elegir origen y destino distintos en Enrutamiento.
2. Pulsar **Comparar las 5 rutas**.
3. Revisar convencional (1/capacidad), polinomial, Decision Tree, Random Forest y XGBoost. Cada modelo produce pesos para Dijkstra; no se instala una ruta al pulsar este boton.
4. Las cinco alternativas se evalúan con los mismos siete indicadores y la misma ventana medida de enlaces. Las previsiones propias de cada modelo aparecen aparte. Las rutas pueden coincidir sin que exista un error.
5. Las casillas y **Ver solo este trazado** controlan el mapa. El dorado identifica tramos compartidos. **Mostrar todos** restaura los trazados visibles.

La comparacion completa se conserva en el navegador con su fecha, ventana e identidad para la sustentacion. **Actualizar comparacion** pide inferencias nuevas; **Recuperar ultima comparacion guardada** recupera la ultima completa; **Limpiar comparacion** elimina esa copia local. Una respuesta parcial no sustituye la ultima completa. Las peticiones nuevas mantienen el limite de 120 segundos y las comprobaciones de sesion/entradas; un resultado archivado no se anuncia como actual ni se dibuja sobre otra sesion.

## Evaluacion de modelos e inspector

La evaluacion de los cuatro modelos esta en un desplegable dentro de Enrutamiento. **Cargar informe de RYU** importa los JSON de validacion y test descriptivo, sin cargar PKL en Windows. Muestra MSE, RMSE, MAE, R², muestras, tiempos y predicciones fuera de rango, por variable/topologia/procedencia. Importar informes no cambia el modelo conectado y no verifica por si solo que ambos archivos provengan de la misma ejecucion.

El servicio 8011 atiende las cinco rutas. El inspector de predicciones de enlaces y la ruta ML individual conservan 8010. XGBoost se selecciono con validacion; el test posterior es descriptivo porque ya se habia examinado. Los errores se calculan con predicciones crudas; los ajustes fisicos de las nuevas inferencias se muestran aparte.

Seleccionar un switch muestra su configuracion e informacion operativa de OFCTL REST: fabricante, plataforma, versiones, puertos y contadores. Seleccionar un enlace muestra ambos puertos y la ventana de sondas. Los campos ausentes aparecen como no disponibles. Drops, errores, rechazos locales y sondas no recibidas son magnitudes diferentes.

El mapa muestra hosts, acceso y controlador, con casillas para ocultarlos si dificultan ver las rutas. Las conexiones de control son logicas; las posiciones del controlador/hosts son esquematicas. Las ciudades no certifican una correspondencia historica de los IDs.

## Diagnostico y alcance

Editar `configuracion_windows.json` si cambian las IP y reiniciar el servidor. Los registros estan en `.ejecucion_windows/sesion_.../api.log`. Encender una VM no confirma que los servicios esten iniciados. Si faltan datos recientes, comprobar servicio, identidad y tiempos; no rellenar entradas ML con ceros.

`Alinear_relojes_VMs.cmd` es una herramienta manual opcional que cambia la hora de las VMs usando Windows como referencia. No se ejecuta automaticamente y no configura NTP. Solo usarla cuando se haya decidido ese ajuste; las ventanas que cruzan un salto temporal se descartan.

Aplicar y demostrar el recorrido real elegido desde la GUI sigue pendiente. Las medidas de enlace y el costo QoS no acreditan una mejora extremo a extremo. El dataset, los modelos y los resultados originales permanecen en RYU y no se reentrenan para abrir esta version. Consultar README.md y documentacion/ESTADO_ACTUAL.md.