# Evidencias de validación

Pruebas realizadas el 9 de noviembre de 2026 con los servicios reales existentes. Resultados históricos de validación: no son predicciones actuales para uso en el panel.

## Comprobaciones

- 23 pruebas automáticas aprobadas: 15 originales y 8 nuevas. Casos nuevos sintéticos explícitos, sin presentarlos como resultados del laboratorio.
- Verificación real de identidad OpenFlow y comparación en ambas redes, manteniendo el algoritmo convencional original.
- Activación autorizada en 8002/5181 completada. Las comparaciones reales y las 23 pruebas pasaron otra vez tras activar. Se comprobaron el bundle apuntando a 8002, CORS, rechazo de fuentes arbitrarias y predicciones existentes por enlace. RYU, el modelo y recolectores conservaron sus procesos originales.
- Selector directo NSFNET/GEANT2 y Auto estable entre consultas; observadores mixtos filtrados por topología.
- Compilación Vite aprobada; ESLint de los tres archivos modificados/aportados aprobado. Vite advierte que el bundle supera 500 kB; no impide la compilación.
- Revisión visual de navegador pendiente: Computer Use se detuvo al no poder verificar la URL con confianza.
- No se ejecutaron campañas de tráfico, reglas OpenFlow, reinicios de controladores ni limpieza de redes.

## Comparaciones reales

### NSFNET

- Observación UTC: `2026-11-09T17:31:53.675907+00:00`.
- Sesión: `en_vivo_nsf_reinicio_trjris6r`.
- Modelo: `modelo_20261107T205202Z_n4vncu_0`; 21 enlaces con predicciones validadas.
- Antigüedad de entrada al responder: 24.64 s.

| Indicador | Convencional | ML |
|---|---|---|
| Trayecto | s1 → s3 → s6 → s14 | s1 → s3 → s6 → s14 |
| Saltos | 3 | 3 |
| Costo referencia Σ 1/Mbps | 0.666667 | 0.666667 |
| Costo QoS común | 0.436187 | 0.436187 |
| Delay previsto ms | 50.980317 | 50.980317 |
| Loss compuesto (razón) | 0.0 | 0.0 |
| Capacidad mínima nominal Mbps | 3.0 | 3.0 |

Ambas rutas coinciden bajo este criterio.

### GEANT2

- Observación UTC: `2026-11-09T17:31:58.197710+00:00`.
- Sesión: `en_vivo_geant_v1_t7yjsib7`.
- Modelo: `modelo_20261107T205202Z_n4vncu_0`; 37 enlaces con predicciones validadas.
- Antigüedad de entrada al responder: 4.46 s.

| Indicador | Convencional | ML |
|---|---|---|
| Trayecto | s1 → s2 → s10 → s13 → s22 → s23 → s24 | s1 → s2 → s10 → s13 → s20 → s24 |
| Saltos | 6 | 5 |
| Costo referencia Σ 1/Mbps | 1.333333 | 1.666667 |
| Costo QoS común | 0.822511 | 0.695871 |
| Delay previsto ms | 93.362288 | 73.190439 |
| Loss compuesto (razón) | 0.0 | 0.0 |
| Capacidad mínima nominal Mbps | 3.0 | 1.5 |

La ruta inteligente minimiza el costo QoS previsto de esta ventana; no garantiza mejoras medidas.

## Conservación

Los SHA-256 de los 44 CSV originales bajo `datos/` de RYU y del archivo del modelo común coinciden antes y después. Los manifiestos adjuntos permiten verificarlo. No se modificaron los datasets ni el modelo entrenado.

La recuperación de Mininet se preparó con copias exactas de los workers y dependencias inspeccionadas. Su nuevo wrapper pasó análisis de sintaxis; no se probó un ciclo de apagado y arranque real para conservar las redes activas.
