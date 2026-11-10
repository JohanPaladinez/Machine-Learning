# Cinco rutas: convencional + cuatro modelos

Este paquete inicia un servicio adicional de inferencia en RYU, puerto 8011, con los cuatro modelos que ya terminaron train/validation/test. No entrena, no sustituye el servicio individual 8010, no instala reglas y no altera datasets o modelos.

Copiar esta carpeta desde Windows a `/home/ryu/proyecto_nsfnet/`. En la terminal SSH de RYU:

```bash
bash ~/proyecto_nsfnet/rutas_cinco_modelos_ryu/iniciar_servicio_modelos.sh
```

El arranque obtiene la carpeta de la última comparación del archivo `comparacion_ml_sdn/ultima_comparacion.txt` y del registro `entrenamiento.log`. Reutiliza el entorno aislado de ese entrenamiento. Exige los informes de validation/test y verifica los hashes de los cuatro PKL antes de cargarlos. Imprime el registro y confirma el PID y contrato del servicio. Si el puerto está ocupado por otro proceso, no lo detiene.

Después, reiniciar únicamente la aplicacion Windows de la raiz del repositorio, con `Detener_interfaz.cmd` y `Abrir_interfaz.cmd`. Recargar Ctrl+F5. En Enrutamiento, elegir origen/destino y pulsar **Comparar las 5 rutas**.

## Qué se calcula

- Convencional: Dijkstra con suma de 1/capacidad nominal.
- Polinomial, Decision Tree, Random Forest y XGBoost: cada modelo pronostica seis magnitudes por enlace sobre exactamente la misma ventana. Una fórmula QoS común produce pesos dirigidos y no negativos; Dijkstra calcula un camino por modelo.
- Los cinco caminos muestran los mismos siete indicadores: saltos, retardo configurado, inverso de capacidad, QoS observado, suma de delay medido, pérdida medida compuesta y capacidad mínima nominal. Los tres indicadores observados usan las mismas mediciones de enlaces, no el pronóstico propio de cada modelo.
- Cada ruta ML añade sus previsiones y su costo de selección, identificados como predicciones de ese modelo. Un QoS propio menor entre modelos no prueba una mejor ruta real.
- La pérdida compuesta y suma de delay son aproximaciones de enlaces, no mediciones extremo a extremo. Throughput RX no representa ancho de banda disponible. No se instala forwarding desde este botón.
- Las rutas coincidentes se indican; los tramos compartidos se marcan en dorado. Todas pueden coincidir sin que eso sea un error.

## Predicciones fuera de rango

Se aplica la misma proyección física a los cuatro modelos, incluida la polinomial: throughput y delay negativos pasan a cero; loss se limita a [0,1]. Se conservan las salidas crudas y cada ajuste. La GUI los muestra por ruta. La polinomial se presenta como alternativa experimental; ajustar sus valores no la convierte en una medición válida del tráfico.

No se recortan los CSV de predicciones de evaluación ni se recalculan sus MSE/RMSE/MAE. Esto es postprocesamiento operativo de nuevas inferencias, no una modificación del entrenamiento o de sus resultados publicados.

## Integración Windows y estado

- Servicio configurado en `SDN_MODELOS_URL` de `configuracion_windows.json`.
- Endpoint nuevo: POST `/api/sdn/rutas/comparar-modelos`.
- Se comprueban sesión, instancia, grafo, revisión de selección, capacidades, esquema y ventana común, con máximo de 120 segundos. Un cambio de red invalida la respuesta. Si la inferencia no está disponible, se conserva únicamente el cálculo convencional y se explican las causas.
- La evaluación de modelos queda en un detalle desplegable de Enrutamiento. Se conservan los informes importados en el navegador.
- El inspector de enlaces y la ruta ML individual conservan el servicio original. El botón de cinco rutas utiliza el nuevo servicio de los cuatro modelos.
- El codigo del panel y la API se incluyen en este repositorio; los modelos permanecen en RYU.

Pruebas locales: 23 regresiones anteriores, 10 casos nuevos de cálculo/servicio/contrato, cuatro casos de presentación y compilación/ESLint. La conexión real a RYU y la revisión de las cinco tarjetas en el navegador quedan por confirmar después del arranque manual. No se tiene acceso administrativo directo a las VMs.
