# Aplicar y demostrar enrutamiento real desde la GUI

La version Windows 1.3 incorpora instalacion explicita de un **flujo ICMP IPv4 entre los hosts asociados al origen y destino**. Se puede elegir la alternativa convencional o cualquiera de los cuatro modelos. Es forwarding real en Open vSwitch, enviado por OFCTL REST de RYU; no es una animacion. El alcance se muestra en la GUI: no se cambia el enrutamiento del UDP controlado del recolector, ARP ni las sondas Ethernet de medicion.

## Activar el codigo nuevo

Las redes y los modelos existentes se mantienen funcionando. Hacer doble clic en `Reiniciar_interfaz.cmd` en la raiz del repositorio (equivale a Detener y despues Abrir). Abrir http://127.0.0.1:8003/sdn-selector.html y recargar Ctrl+F5. El contrato de salud identifica `version=1.3.0` y `enrutamiento_icmp_version=1`; el gestor evita reutilizar un backend anterior como si incluyera este cambio.

## Demostracion NSFNET

1. Mantener abiertas las dos consolas Mininet. En el panel elegir NSFNET y esperar red verificada.
2. En Enrutamiento seleccionar S1 y S14 y pulsar **Comparar las 5 rutas**. Si los modelos no responden, se puede preparar la convencional disponible; preparar convencional no necesita el servicio de los cuatro modelos.
3. En **Aplicar y demostrar la ruta**, elegir **Convencional · 1/capacidad** y pulsar **Preparar ruta seleccionada**. El servidor recalcula con el contexto actual y exige el mismo camino mostrado. Si cambio el camino, modelo, sesion o grafo, pide actualizar la comparacion.
4. Revisar el plan y pulsar **Aplicar ruta ICMP**. El estado solo pasa a aplicada cuando RYU devuelve las reglas con los puertos y match esperados. La pantalla separa preparar/aplicar/verificar trafico.
5. Pulsar **Iniciar evidencia**. En `mininet-nsfnet>` ejecutar `nsh1 ping -c 3 nsh14`. Esperar el resumen del ping.
6. Pulsar **Verificar trafico**. Debe aumentar el contador de cada regla de ida y regreso. La GUI muestra antes/despues/delta por switch y puerto. Se puede descargar evidencia JSON. Conservar tambien la salida del ping: los contadores verifican el flujo ICMP, pero no identifican por si solos quien lo genero ni prueban una mejora de rendimiento.
7. Elegir una alternativa ML disponible, preparar y aplicar. La nueva ruta tiene otra cookie/prioridad; se instala antes de retirar estrictamente la anterior. Repetir la evidencia. Dos criterios pueden elegir el mismo camino sin que exista un error.
8. **Retirar reglas aplicadas** elimina exclusivamente las reglas creadas por esta funcion y confirma su ausencia. El forwarding de arranque queda disponible; no se borran sus reglas.

Para GEANT2 se utiliza su seleccion en el mismo panel y el comando de ping que este muestre (hosts nh). No se introducen manualmente IP de controlador ni puertos en la solicitud del navegador.

## Puertos aportados por el usuario para el primer caso

Camino calculado: S1 → S3 → S6 → S14. Los datos de links confirman:

| Switch | Salida ida | Salida regreso |
|---|---|---|
| ns1 | 3 hacia ns3 | 1 hacia nsh1 |
| ns3 | 4 hacia ns6 | 2 hacia ns1 |
| ns6 | 5 hacia ns14 | 2 hacia ns3 |
| ns14 | 1 hacia nsh14 | 2 hacia ns6 |

La implementacion deriva el plan del perfil vivo verificado; esta tabla no se incrusta como un camino fijo ni se aplica a GEANT2. El regreso usa el recorrido inverso, explicitamente mostrado; no se afirma que sea una optimizacion ML independiente de la direccion contraria.

## Conservacion y comprobaciones

- Se agrega un flujo con eth_type IPv4 e ip_proto ICMP, IP origen/destino exactas, tabla 0 y una unica salida, por switch y sentido. Las cookies tienen prefijo de esta funcion y una parte aleatoria. Prioridad inicial 30000, superior a las reglas de arranque de prioridad 100; un cambio posterior usa una prioridad siguiente.
- Instalacion desde el destino hacia el origen, lectura posterior desde RYU y contexto de red revalidado. Si falla o se pierde una respuesta de instalacion, se intenta retirar las nuevas reglas propias. Un retiro no confirmado se conserva como pendiente y bloquea nuevas instalaciones; no se limpia silenciosamente.
- Retiro mediante `delete_strict` con cookie completa, mascara completa, tabla, prioridad y match. No hay borrado global ni cambios de reglas de sondas/UDP. Se rechazan cookies/matches de un registro que no pertenezca al alcance ICMP de esta funcion.
- El registro local esta en `.ejecucion_windows/enrutamiento_icmp.json`. Permite conocer las reglas aplicadas o pendientes despues de reiniciar FastAPI. La consulta vuelve a leer las reglas; no confirma forwarding solo por tener un registro en disco.
- Las reglas no tienen hard_timeout ni idle_timeout: siguen hasta retirarlas o detener la red. El plan sin aplicar dura 90 s y las entradas ML deben ser recientes al aplicar. Una comparacion guardada sigue visible, pero no se reutiliza como si fuera una prediccion reciente.
- Aplicar fija esa seleccion; no reoptimiza automaticamente al cambiar las metricas. Generar ping puede aparecer en los contadores de la ventana de telemetria, sin modificar sus archivos de entrenamiento.
- El mapa solo enfoca un recorrido aplicado cuando coincide exactamente con la comparacion de esa sesion/grafo. Un calculo nuevo diferente no se dibuja como si fuese el camino ya instalado.

## Alcance de las pruebas

Se comprobaron con switches simulados: puertos de la captura, trafico en todos los saltos, direccion de regreso, cambio de modelo, retiro, preservacion de reglas previas, perdida de respuesta, rollback, limpieza pendiente tras reinicio, identidad de puertos/contexto, modelos y entradas antiguas. Estas pruebas no sustituyen la evidencia de RYU/Mininet del usuario.

El usuario aporto evidencia de ping y aumentos de contadores en todos los saltos de NSFNET, y confirmo el mismo resultado con XGBoost, el retiro de las reglas y el funcionamiento equivalente en GEANT2. Esto cierra la demostracion funcional segun las capturas y confirmaciones del usuario; no constituye una medicion comparativa de rendimiento entre modelos ni una inspeccion remota independiente. La publicacion incluye el codigo y las guias; no incluye datos ni registros de ejecucion de las VMs.

Referencia del contrato REST: https://ryu.readthedocs.io/en/latest/app/ofctl_rest.html (consulta de flujos, flowentry/add y flowentry/delete_strict).
