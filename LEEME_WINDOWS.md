# SDN/KDN 1.3 — interfaz en Windows

Windows ejecuta React/Cytoscape y FastAPI en el puerto 8003. Solo se necesitan las VMs Mininet y RYU; la antigua VM Ubuntu de interfaz puede permanecer apagada. Ambas topologias pueden funcionar simultaneamente.

## Instalar y abrir

Con Python 3.10 o posterior y Node compatible con Vite 8, ejecutar en PowerShell desde la raiz del clon:

```powershell
python instalar_windows.py
.\Abrir_interfaz.cmd
```

El instalador prepara el entorno y compila el panel. No copia ni entrena modelos: las fuentes instrumentadas, datos y modelos deben existir en las VMs. Clonar no reconstruye las VMs.

Los CMD se ejecutan con doble clic o como archivos; no se pega su contenido en PowerShell. `Abrir_interfaz.cmd` abre http://127.0.0.1:8003/sdn-selector.html; `Detener_interfaz.cmd` cierra solo esta aplicacion. Tras actualizar codigo, recompilar con `python instalar_windows.py`, usar `Reiniciar_interfaz.cmd` y Ctrl+F5. El contrato de salud identifica version 1.3.0 y las funciones de cinco rutas y enrutamiento ICMP; no se reutiliza un backend anterior como si incluyera los cambios.

## Arranque diario

1. Encender RYU y Mininet y esperar que arranquen.
2. Ejecutar `Arrancar_RYU.cmd` y esperar **RYU LISTO**.
3. Ejecutar `Abrir_consolas_Mininet.cmd`, introducir SSH/sudo y esperar `mininet-geant2>` y `mininet-nsfnet>`. Mantener ambas ventanas abiertas.
4. Ejecutar `Abrir_interfaz.cmd`, seleccionar topologia y esperar red verificada y una ventana completa de medicion.

Los lanzadores diarios reutilizan fuentes/modelos existentes, sin entrenar ni cambiar relojes. El nuevo arranque RYU se reviso localmente; su primera comprobacion completa tras apagar las VMs queda pendiente. Ver [comandos y apagado](documentacion/GUIA_APAGADO_Y_ARRANQUE_SDN.md).

## Comparar cinco rutas

En Enrutamiento, elegir origen y destino y pulsar **Comparar las 5 rutas**: Dijkstra convencional por suma de 1/capacidad y cuatro rutas con pesos derivados de Polinomial, Decision Tree, Random Forest y XGBoost. Los caminos pueden coincidir; no se fuerzan diferencias.

Tarjetas y tabla presentan los mismos siete indicadores sobre la misma informacion de red: saltos, retardo configurado, costo inverso de capacidad, QoS observado, delay medido agregado, perdida medida compuesta y capacidad minima nominal. Las previsiones de cada modelo se muestran aparte. Las agregaciones por enlace son aproximaciones, no medidas extremo a extremo. Las casillas y Ver solo este trazado/Mostrar todos controlan el mapa; el dorado identifica enlaces compartidos. Comparar calcula y dibuja, sin instalar reglas.

## Aplicar y demostrar la ruta

**Preparar** recalcula la alternativa elegida y valida camino, sesion, grafo, modelo y puertos. **Aplicar ruta ICMP** instala reglas mediante RYU y confirma su lectura. Se afecta ICMP IPv4 entre los hosts elegidos; el regreso usa el mismo recorrido invertido. ARP, UDP del recolector y sondas mantienen su forwarding.

**Iniciar evidencia** toma contadores; ejecutar el ping mostrado en la consola Mininet y pulsar **Verificar trafico**. Se exigen incrementos en todos los saltos y ambos sentidos, y se permite descargar evidencia JSON. **Retirar reglas aplicadas** elimina estrictamente solo las reglas propias. El usuario aporto capturas y confirmo funcionamiento con convencional/XGBoost, retiro y ambas topologias. Esta evidencia demuestra recorrido ICMP, no una mejora de rendimiento. Ver [guia de demostracion](documentacion/GUIA_ENRUTAMIENTO_REAL_ICMP.md).

Las reglas aplicadas no expiran automaticamente; permanecen hasta retirarlas o detener la red. El plan sin aplicar dura 90 segundos y las nuevas solicitudes ML siguen exigiendo entradas recientes/completas. Aplicar fija la seleccion, sin reoptimizarla automaticamente.

## Comparaciones guardadas y evaluacion ML

Las comparaciones se conservan con ventana, pesos e identidad para la sustentacion. Actualizar comparacion calcula de nuevo; Recuperar ultima comparacion guardada restaura la copia de este navegador. Una respuesta parcial no reemplaza el ultimo resultado completo. Un resultado de otra sesion puede verse como historial, pero no se dibuja ni aplica como si perteneciera a la red actual. Se mantienen las validaciones al pedir nuevas predicciones.

El detalle de evaluacion importa comparacion_validation.json y comparacion_test.json de RYU, sin cargar PKL en Windows. Presenta MSE, RMSE, MAE, R2, muestras, predicciones fuera de rango y tiempos por variable, sentido, topologia y procedencia. XGBoost se selecciono por validacion global normalizada de seis salidas y ambas topologias; puede no ganar cada metrica. La polinomial es baseline grado 2 con Ridge. El test posterior es descriptivo porque ya se habia examinado. Las metricas conservan predicciones crudas y la inferencia declara su proyeccion a rangos fisicos. Importar informes no cambia el modelo conectado ni instala rutas.

## Mapas e inspectores

Mapa geografico y Esquema muestran switches, hosts y controlador; los enlaces de control no participan en Dijkstra. Las ciudades son referencias reales del laboratorio, sin correspondencia historica verificada con los IDs; no cambian enlaces ni pesos. La cartografia local de Natural Earth no requiere claves externas.

Los inspectores muestran fabricante/version/plataforma reportados, puertos y estado, bits/paquetes TX/RX, errores, descartes, tasas y medidas dirigidas. La perdida ofrecida incluye rechazos locales de sondas y se distingue de descartes y perdida en transito. Los datos ausentes no se sustituyen por cero.

## Servicios

Editar configuracion_windows.json si cambian las direcciones y reiniciar el panel; no requiere recompilar ese cambio.

| Servicio | Direccion |
|---|---|
| Observador NSFNET | http://192.168.56.107:8769 |
| Observador GEANT2 | http://192.168.56.107:8768 |
| REST RYU NSFNET / OpenFlow | http://192.168.56.108:18081 / 16654 |
| REST RYU GEANT2 / OpenFlow | http://192.168.56.108:18080 / 16653 |
| Modelo individual del inspector | http://192.168.56.108:8010 |
| Cuatro modelos | http://192.168.56.108:8011 |

Windows consulta estas API directamente; SSH opera las VMs. Los servicios son de laboratorio, sin autenticacion multiusuario para Internet. La seleccion es compartida por navegadores de la misma instancia. Los registros y journal de reglas estan en .ejecucion_windows/ y el entorno en .venv/; no se publican. Dataset/modelos siguen en RYU. El arranque no cambia la hora ni configura NTP. Un rechazo por ventana antigua exige comprobar tiempos/recolector, no desactivar validaciones.

Basado en [Sergio777gg/sdn-kdn-rutas-ml](https://github.com/Sergio777gg/sdn-kdn-rutas-ml), commit aeab8d50f7de505672b3940c9905ed9ee5929194, ampliado para este laboratorio. Ver [README](README.md) y [estado actual](documentacion/ESTADO_ACTUAL.md).
