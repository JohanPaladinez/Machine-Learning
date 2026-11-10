# Cambios

## Actualizacion — 2026-11-10

- Comparacion de cinco rutas: convencional y una por cada modelo polinomial, Decision Tree, Random Forest y XGBoost.
- Entrenamiento, evaluacion y servicio aislado de los cuatro regresores en RYU; inferencia adicional en 8011 y conservacion de 8010.
- Informes de validacion/test descriptivo, proyeccion fisica declarada de las nuevas inferencias y comparaciones guardadas para la sustentacion.
- Hosts, enlaces de acceso y controlador visibles en el mapa; inspectores de switches, puertos y metricas de enlace ampliados.
- Consolas Mininet interactivas simultaneas; correccion v1.1 de reserva TCP y cierre de observador no iniciado. El usuario confirmo el arranque de ambas consolas.
- Documentacion actualizada, pruebas portables y comprobaciones sinteticas de CI. Datos y pesos entrenados permanecen fuera de Git.
- La aplicacion de rutas de la GUI al trafico real se deja pendiente expresamente; no se presenta como implementada.

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
