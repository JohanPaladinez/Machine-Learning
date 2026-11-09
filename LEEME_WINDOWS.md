# SDN/KDN con comparacion de rutas en Windows

La aplicacion se ejecuta directamente en Windows. Solo necesitas las VMs de RYU y Mininet; la VM Ubuntu de la interfaz puede permanecer apagada.

## Abrir

Abre esta carpeta en el Explorador de archivos y haz doble clic en **Abrir_interfaz.cmd**. El lanzador inicia el backend y abre el panel en:

**http://127.0.0.1:8003/sdn-selector.html**

Esta es la version nueva con comparacion de rutas. La version Windows anterior utiliza el puerto 8002. El nuevo lanzador no detiene esa version ni otros servicios para liberar puertos.

El panel y FastAPI comparten el puerto 8003. Node se utiliza para compilar; no tienes que iniciar Vite por separado para usar el panel. Puedes cerrar la ventana del lanzador cuando termine. El servicio sigue en segundo plano hasta que lo detengas o apagues Windows.

Para cerrar esta version, haz doble clic en **Detener_interfaz.cmd**. Despues de reiniciar Windows, vuelve a abrir **Abrir_interfaz.cmd**.

Desde la version 1.1.1, el lanzador comprueba que el backend devuelva los cuatro criterios. Si encuentra una ejecucion anterior propia, la reinicia en lugar de reutilizarla. La identidad del proceso se verifica antes de cerrarlo; los servicios de RYU y Mininet no se detienen.

## Usar las funciones nuevas

1. Enciende RYU y Mininet y deja ejecutandose sus servicios y redes instrumentadas. Encender las VMs no confirma que los servicios hayan arrancado.
2. En la cabecera, selecciona NSFNET o GEANT2. El backend elige el observador configurado para esa topologia. Auto conserva la seleccion mientras este disponible.
3. Espera el estado de red verificada. El estado del modelo y las mediciones se comprueban por separado.
4. En **Enrutamiento**, selecciona origen y destino distintos. Puedes calcular una ruta individual o pulsar **Comparar las 4 rutas**.
5. Se muestran cuatro criterios: menos saltos (azul), retardo configurado (naranja), inverso de capacidad nominal (verde) y prediccion ML (violeta). Cada tarjeta conserva su costo y unidad. La tabla evalua los cuatro caminos con las mismas predicciones por enlace y la misma ventana.
6. Las casillas permiten ocultar trazados. **Ver solo este trazado** aisla uno; **Mostrar todos** restaura los cuatro. El dorado identifica enlaces compartidos por varios criterios visibles. Se indica cuando varios criterios eligen el mismo camino, sin forzar diferencias.

ML predice las metricas por enlace; Dijkstra elige el camino usando un costo QoS. La comparacion no aplica esas rutas al trafico. Los resultados caducan al superar 120 segundos desde el fin de la ventana usada. Si faltan entradas completas y recientes, se informa la indisponibilidad de ML.

Sin ML disponible, se conservan los tres calculos clasicos. Si falta retardo configurado, solo ese criterio se marca como no disponible. Los datos ausentes no se reemplazan por cero. Al caducar ML, se retiran sus predicciones y se conservan los caminos clasicos como referencia de configuracion.

## Mapas y nombres de lugares

El mapa incluye las vistas **Mapa geografico** y **Esquema de red**. NSFNET usa ciudades de Estados Unidos; GEANT2 usa ciudades europeas. Puedes desplazar y acercar el mapa y consultar la ciudad, el pais y las coordenadas aproximadas en los detalles de cada nodo. Los nombres tambien aparecen en origen/destino, caminos e inventario de enlaces.

Las ciudades son ubicaciones reales asignadas como **referencias del laboratorio**. La correspondencia entre s1...sN y esas ciudades no es una identificacion historica verificada: los perfiles numerados originales no aportan esa correspondencia. Se conservan los IDs, enlaces, capacidades y retardos; las coordenadas no cambian los pesos de las rutas. La asignacion solo se aplica cuando coincide exactamente el grafo esperado.

La cartografia de Natural Earth se incluye localmente y no necesita conexion a un servicio de mapas ni claves. Fuente: https://www.naturalearthdata.com/about/terms-of-use/ (dominio publico).

## Aplicar esta actualizacion

Con RYU y Mininet funcionando, ejecuta **Detener_interfaz.cmd** y despues **Abrir_interfaz.cmd**, ambos en esta carpeta de Windows. Recarga el navegador con Ctrl+F5 si conserva la vista anterior. Solo se reinicia esta aplicacion Windows; no hace falta recrear las redes ni volver a entrenar el modelo.

Si aparecen capacidad y ML pero las tarjetas de saltos y retardo no tienen resultados, comprueba que no siga abierto el backend anterior. Ese backend devuelve dos rutas y no permite concluir que falte configuracion en la red. La interfaz actual detecta esa respuesta incompatible y muestra instrucciones de reinicio, en lugar de atribuirla a datos ausentes.

## Direcciones de tus VMs

La configuracion esta en **configuracion_windows.json**. Se preparo con las ultimas direcciones que usamos en este chat:

| Servicio | Direccion |
|---|---|
| NSFNET en Mininet | http://192.168.56.107:8769 |
| GEANT2 en Mininet | http://192.168.56.107:8768 |
| REST RYU para NSFNET | http://192.168.56.108:18081 |
| REST RYU para GEANT2 | http://192.168.56.108:18080 |
| Modelo guardado en RYU | http://192.168.56.108:8010 |

Puertos OpenFlow: NSFNET 16654 y GEANT2 16653. El repositorio de tu companero usa Mininet en .103; esta copia Windows usa .107. Si ahora tu Mininet tiene otra IP, cambia las dos URL del observador en el JSON y reinicia solo esta aplicacion. No necesitas recompilar para cambiar esas direcciones.

Windows debe poder alcanzar esos servicios. Un fallo de conexion puede indicar una direccion distinta, un servicio detenido o un problema de red; no confirma por si solo que la VM este apagada. SSH sirve para operar las VMs, pero el panel consulta sus API HTTP directamente.

El modelo y su evaluacion permanecen en RYU. El dataset consolidado de 20 horas tambien permanece alli. No se entrena ni se copia el modelo a Windows. Esta instalacion no cambia relojes ni configura NTP. Si las ventanas aparecen antiguas o futuras, hay que comprobar los tiempos antes de modificar nada.

## Origen y alcance

Codigo adaptado de **Sergio777gg/sdn-kdn-rutas-ml**, commit **aeab8d50f7de505672b3940c9905ed9ee5929194**. Se conserva la formula QoS. La comparacion local se amplio a los cuatro criterios; tambien se agregaron geografia, arranque nativo, configuracion de servicios y servidor del panel en Windows. No se ejecutan los scripts Linux de activacion ni de recuperacion de redes. Estos cambios no se publicaron en GitHub.

La seleccion sigue siendo compartida por los navegadores que se conecten a esta instancia local. Los pesos iniciales son decisiones de diseno, no coeficientes aprendidos. Un costo QoS menor no demuestra una mejora de rendimiento medida en trafico real.

Los registros estan en **.ejecucion_windows/sesion_.../api.log** y la identidad de la ejecucion actual, en **.ejecucion_windows/estado.json**. El entorno Python es privado, en **.venv**. Conserva esta carpeta completa en su ubicacion actual.

Para reinstalar dependencias o recompilar despues de editar, ejecuta **python instalar_windows.py** desde esta carpeta. El instalador compila el panel para la API local del puerto 8003.
