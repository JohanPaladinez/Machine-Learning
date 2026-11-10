# Cambios

## 1.3.0 — Enrutamiento real y arranque diario — 2026-11-10

- Aplicacion explicita de una ruta convencional o de cualquiera de los cuatro modelos al flujo ICMP mediante RYU.
- Confirmacion de reglas, puertos, identidad de red y contadores de trafico en todos los saltos de ida/regreso. Retiro estricto de reglas propias y recuperacion de operaciones pendientes.
- Capturas y confirmacion del usuario de funcionamiento con convencional/XGBoost, retiro y ambas topologias; no es una comparacion de rendimiento.
- Nuevos lanzadores de arranque diario RYU y consolas Mininet, guia de apagado/arranque y Reiniciar_interfaz.cmd. El arranque tras un apagado completo sigue pendiente de su primera comprobacion en VMs.
- Pruebas sinteticas de forwarding y presentacion, sin contactar las VMs. Los registros de reglas locales, datos, pesos y entornos quedan excluidos de Git.

## Actualizacion — 2026-11-10

- Comparacion de cinco rutas: convencional y una por cada modelo polinomial, Decision Tree, Random Forest y XGBoost.
- Entrenamiento, evaluacion y servicio aislado de los cuatro regresores en RYU; inferencia adicional en 8011 y conservacion de 8010.
- Informes de validacion/test descriptivo, proyeccion fisica declarada de las nuevas inferencias y comparaciones guardadas para la sustentacion.
- Hosts, enlaces de acceso y controlador visibles en el mapa; inspectores de switches, puertos y metricas de enlace ampliados.
- Consolas Mininet interactivas simultaneas; correccion v1.1 de reserva TCP y cierre de observador no iniciado. El usuario confirmo el arranque de ambas consolas.
- Documentacion actualizada, pruebas portables y comprobaciones sinteticas de CI. Datos y pesos entrenados permanecen fuera de Git.
- En esta entrega anterior la aplicacion real estaba pendiente; se completa en 1.3.0, descrita arriba.

## 1.1.1 — Entrega Windows del 2026-11-09

- Interfaz nativa Windows con FastAPI y panel en el puerto 8003.
- Comparación de cuatro criterios con siete indicadores comunes en cada tarjeta.
- Mapas de ciudades de referencia, conservación de IDs y trazados seleccionables.
- Comprobación del contrato de cuatro rutas al reutilizar un servidor abierto.
- Dataset y modelo originales conservados en RYU; dependencias y ejecución local excluidas.


## 0.1.0 — 2026-11-09

- Selección automática de fuentes NSFNET/GEANT2 con Auto estable y validación del controlador.
- Comparación convencional/ML con costos QoS direccionales, normalizados y configurables.
- Validación de sesión, instancia, grafo, enlace, ventana, esquema, modelo y antigüedad de predicciones.
- Tarjetas, tabla de métricas, trazados diferenciados y consulta de predicciones por enlace en Enrutamiento.
- Respaldo, hashes, reversión y guías de arranque y recuperación.
- Activación autorizada en los puertos habituales, con 23 pruebas y validación real en ambas topologías.
- Preparación del repositorio público con exclusiones, guías de contribución y comprobaciones aisladas en GitHub Actions.

La revisión visual completa y el arranque Mininet tras un apagado real permanecen pendientes; no se interrumpieron las redes para ensayarlos.
