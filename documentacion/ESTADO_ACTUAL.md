# Estado de la entrega — 10 de noviembre de 2026

La arquitectura vigente es Windows (React, Cytoscape y FastAPI), VM Mininet (datos y telemetria) y VM RYU (controladores e inferencia). El profesor acepto Windows y las dos topologias simultaneas. Los documentos sobre tres VMs se mantienen como historial.

## Evidencias y limites

El usuario aporto resultados de entrenamiento y evaluacion de cuatro modelos con el dataset consolidado existente. Los scores de validacion global normalizada fueron aproximadamente 0,45061 (polinomial), 0,43551 (Decision Tree), 0,38810 (Random Forest) y 0,34116 (XGBoost). Menor es mejor en ese criterio. XGBoost fue elegido con validacion, combinando las seis salidas y ambas topologias; puede no ser el mejor para cada variable individual. La polinomial es baseline de grado 2 con Ridge, no una regresion OLS sin regularizacion.

El test ya habia sido examinado con el modelo anterior. La comparacion posterior de los cuatro regresores es descriptiva sobre esa particion; no es una nueva prueba independiente ni se usa para retocar parametros o elegir ganador. Las metricas de evaluacion mantienen predicciones crudas. La inferencia operativa usa una proyeccion fisica comun y declara los ajustes, sin alterar los informes.

La captura final reporto 78.561 filas y 20,0155267489 horas documentadas totales entre NSFNET y GEANT2. Conserva datos historicos de metodo no recuperado y dos metodos adicionales de sondas. No se deben presentar como una unica procedencia homogenea ni confundir filas por enlace con horas sumables. Los nuevos minimos/maximos de delay de la telemetria no rellenan retroactivamente el dataset de entrenamiento.

Se observo el mapa de GEANT2 con hosts y controlador en el navegador; la imagen se conserva en `evidencias/Mapa_hosts_controlador.png`. El usuario confirmo que ambas consolas funcionaron tras corregir el fallo de bind de la primera version. Despues aporto capturas de reglas y contadores de forwarding elegido desde la GUI y confirmo resultados equivalentes y retiro en ambas topologias. No se afirma una mejora de rendimiento ni que esto sustituya una evidencia de pingall.

## Que hace cada funcion

- La comparacion ML estatica muestra los errores de los cuatro regresores sobre las mismas muestras por grupo. Importar un informe no cambia el modelo del servicio.
- La comparacion de cinco rutas consulta el servicio 8011 con una misma ventana y esquema. Cada modelo produce pesos para Dijkstra; se muestran rutas y previsiones independientes.
- Los siete indicadores comunes de ruta usan configuracion y medidas del mismo snapshot. Sumar delays y componer perdidas por enlace son aproximaciones; no son pruebas extremo a extremo despues de instalar una ruta.
- El inspector individual conserva el servicio del modelo previo en 8010.
- Las comparaciones completas guardadas conservan su fecha, ventana e identidad. Pueden mostrarse en la sustentacion sin borrar el resultado; nuevas inferencias siguen comprobando frescura. Un resultado de otra sesion no se dibuja sobre la red actual.
- Las consolas son la CLI real de Mininet sobre los mismos objetos que generan la telemetria. No se inicia otra red de demostracion desconectada del panel. exit/EOF termina solo la sesion correspondiente.
- El inspector operativo solo consulta GET de OFCTL REST. Los contadores se verifican por interfaz y se separan acumulados, tasas, sondas no recibidas, rechazos, errores y descartes. No se inventan versiones, fabricantes ni metricas ausentes.

## Aplicacion y evidencia de enrutamiento real

La API 1.3 permite preparar y aplicar una de las cinco alternativas al flujo ICMP IPv4 entre los hosts correspondientes. Instala reglas por switch y sentido a traves de OFCTL REST, con prioridad superior al forwarding de arranque y cookie propia. El regreso usa el mismo recorrido fisico invertido; no es una optimizacion ML independiente.

Antes de instalar se recalculan la ruta y la identidad de sesion/grafo/modelo. La API confirma reglas y puertos mediante lectura posterior. La evidencia compara contadores antes/despues de un ping en todos los saltos y ambos sentidos. Cambiar una ruta instala y verifica la nueva antes de retirar la anterior. El retiro usa delete_strict para reglas propias; no hay borrado global ni cambios a ARP/UDP/sondas. Un rollback no confirmado se mantiene como limpieza pendiente.

El usuario mostro NSFNET S1 → S3 → S6 → S14 con incrementos de tres paquetes por regla en ambos sentidos. Confirmo la prueba con XGBoost, el retiro y funcionamiento equivalente en GEANT2. Esta evidencia es aportada por el usuario; no se accedio remotamente a las VMs para auditarla. No implica una comparacion de rendimiento entre modelos.

Los endpoints de calculo siguen informando `rules_installed=False`: calcular no modifica el plano de datos. Solo la accion explicita de aplicar instala reglas. Las reglas aplicadas no tienen expiracion automatica; el plan sin aplicar y las nuevas entradas ML conservan sus comprobaciones de frescura.

No hace falta reentrenar ni repetir las 20 horas. La informacion geografica es una referencia de laboratorio, no una correspondencia historica demostrada. El nuevo arranque diario reutiliza fuentes/modelos existentes y fue comprobado localmente; el proximo encendido completo en las VMs es una comprobacion pendiente. Ver [demostracion](GUIA_ENRUTAMIENTO_REAL_ICMP.md) y [arranque diario](GUIA_APAGADO_Y_ARRANQUE_SDN.md).

## Copia de fuentes y artefactos

El repositorio incluye el codigo preparado en Windows y los paquetes de consolas/ML. Las fuentes historicas de `laboratorio/` no son una nueva extraccion de los archivos de las VMs. El lanzador interactivo copia y reutiliza las fuentes instrumentadas que ya funcionan alli, incluidos sus ajustes de reloj/ENOBUFS. Los CSV, PKL, informes privados y registros no se extraen ni publican automaticamente. Consultar README.md para ubicaciones y servicios.
