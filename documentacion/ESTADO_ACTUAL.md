# Estado de la entrega — 10 de noviembre de 2026

La arquitectura vigente es Windows (React, Cytoscape y FastAPI), VM Mininet (datos y telemetria) y VM RYU (controladores e inferencia). El profesor acepto Windows y las dos topologias simultaneas. Los documentos sobre tres VMs se mantienen como historial.

## Evidencias y limites

El usuario aporto resultados de entrenamiento y evaluacion de cuatro modelos con el dataset consolidado existente. Los scores de validacion global normalizada fueron aproximadamente 0,45061 (polinomial), 0,43551 (Decision Tree), 0,38810 (Random Forest) y 0,34116 (XGBoost). Menor es mejor en ese criterio. XGBoost fue elegido con validacion, combinando las seis salidas y ambas topologias; puede no ser el mejor para cada variable individual. La polinomial es baseline de grado 2 con Ridge, no una regresion OLS sin regularizacion.

El test ya habia sido examinado con el modelo anterior. La comparacion posterior de los cuatro regresores es descriptiva sobre esa particion; no es una nueva prueba independiente ni se usa para retocar parametros o elegir ganador. Las metricas de evaluacion mantienen predicciones crudas. La inferencia operativa usa una proyeccion fisica comun y declara los ajustes, sin alterar los informes.

La captura final reporto 78.561 filas y 20,0155267489 horas documentadas totales entre NSFNET y GEANT2. Conserva datos historicos de metodo no recuperado y dos metodos adicionales de sondas. No se deben presentar como una unica procedencia homogenea ni confundir filas por enlace con horas sumables. Los nuevos minimos/maximos de delay de la telemetria no rellenan retroactivamente el dataset de entrenamiento.

Se observo el mapa de GEANT2 con hosts y controlador en el navegador; la imagen se conserva en `evidencias/Mapa_hosts_controlador.png`. El usuario confirmo que ambas consolas funcionaron tras corregir el fallo de bind de la primera version. Esto no sustituye guardar los resultados de pingall ni una demostracion de forwarding elegido desde la GUI.

## Que hace cada funcion

- La comparacion ML estatica muestra los errores de los cuatro regresores sobre las mismas muestras por grupo. Importar un informe no cambia el modelo del servicio.
- La comparacion de cinco rutas consulta el servicio 8011 con una misma ventana y esquema. Cada modelo produce pesos para Dijkstra; se muestran rutas y previsiones independientes.
- Los siete indicadores comunes de ruta usan configuracion y medidas del mismo snapshot. Sumar delays y componer perdidas por enlace son aproximaciones; no son pruebas extremo a extremo despues de instalar una ruta.
- El inspector individual conserva el servicio del modelo previo en 8010.
- Las comparaciones completas guardadas conservan su fecha, ventana e identidad. Pueden mostrarse en la sustentacion sin borrar el resultado; nuevas inferencias siguen comprobando frescura. Un resultado de otra sesion no se dibuja sobre la red actual.
- Las consolas son la CLI real de Mininet sobre los mismos objetos que generan la telemetria. No se inicia otra red de demostracion desconectada del panel. exit/EOF termina solo la sesion correspondiente.
- El inspector operativo solo consulta GET de OFCTL REST. Los contadores se verifican por interfaz y se separan acumulados, tasas, sondas no recibidas, rechazos, errores y descartes. No se inventan versiones, fabricantes ni metricas ausentes.

## Pendiente para la siguiente fase

Aplicar explicitamente una ruta elegida desde la GUI al trafico de los hosts, comprobar reglas y puertos, demostrar el recorrido y permitir el cambio entre convencional/ML. Los endpoints actuales informan `rules_installed=False`. El forwarding inicial de las redes sirve para la conectividad del laboratorio, pero no se presenta como aplicacion de la ruta propuesta por la GUI.

No hace falta reentrenar ni repetir las 20 horas para publicar esta version. La comprobacion real de OpenFlow negociado, pingall y rutas debe conservarse como evidencia separada. La informacion geografica es una referencia de laboratorio, no una correspondencia historica demostrada.

## Copia de fuentes y artefactos

El repositorio incluye el codigo preparado en Windows y los paquetes de consolas/ML. Las fuentes historicas de `laboratorio/` no son una nueva extraccion de los archivos de las VMs. El lanzador interactivo copia y reutiliza las fuentes instrumentadas que ya funcionan alli, incluidos sus ajustes de reloj/ENOBUFS. Los CSV, PKL, informes privados y registros no se extraen ni publican automaticamente. Consultar README.md para ubicaciones y servicios.
