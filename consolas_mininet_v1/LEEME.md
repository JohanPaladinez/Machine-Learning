# Consolas reales de Mininet y datos operativos

Version 1.1: se elimino la prueba temporal de bind sin SO_REUSEADDR, que podia fallar al cerrar un observador con conexiones en TIME_WAIT. Ahora se reserva el servidor HTTP definitivo con reutilizacion de direccion, sin SO_REUSEPORT, antes de crear la red. Si hay un listener realmente activo, se conserva y se muestra el puerto y la consulta de ss. El cierre de un servidor reservado pero aun no iniciado tampoco llama a shutdown, evitando una espera indefinida si falla la creacion de Mininet.

La aplicacion sigue en Windows. Las dos redes y sus hosts siguen en la VM Mininet; los controladores y modelos permanecen en RYU. No se instala una tercera VM ni se cambia el modelo.

## Preparar

Mantener encendidas Mininet (192.168.56.107) y RYU (192.168.56.108), con el servicio original de modelo en 8010 y ambos controladores disponibles en 18080/16653 y 18081/16654. El servicio de cuatro modelos 8011 sigue siendo necesario para comparar cinco rutas, pero no es sustituido por este paquete.

Hacer doble clic en **Instalar_consolas_Mininet.cmd**, situado en la raiz del repositorio. No pegar su contenido en PowerShell. Copia exclusivamente iniciar.py y consola_sdn.py y abre dos ventanas SSH interactivas, con sus propias solicitudes de contrasena y sudo. Si Windows pregunta por una clave SSH nueva, comprobar que corresponde a la VM propia.

Cada lanzador reconoce la sesion instrumentada activa por su archivo de configuracion, PID, argumentos y momento de inicio. Prepara una copia nueva de sus scripts en una carpeta `consola_geant2_*` o `consola_nsfnet_*`, cierra limpiamente solo su proceso anterior y recrea esa red en primer plano. La transicion interrumpe brevemente esa topologia; la otra se gestiona independientemente. No se usa `mn -c`, no se borran bridges huerfanos ni se reinician controladores. Si hay procesos o bridges que no puede atribuir con seguridad, se detiene con un mensaje para revisar.

Los scripts de medicion reutilizados son los de la VM, incluyendo sus correcciones de relojes y ENOBUFS. La primera ventana completa puede tardar unos 20–40 segundos despues de crear la red. Las 60 entradas ML y las seis salidas se conservan. No se escriben filas en el dataset final ni se reentrena nada.

## Usar

En la ventana GEANT2 debe aparecer `mininet-geant2>`. En la otra, `mininet-nsfnet>`. Son dos CLI reales sobre los mismos objetos Mininet que publican la telemetria. Ejecutar, por ejemplo:

```
nodes
links
net
ports
pingall
telemetria
```

Los nombres se conservan para no colisionar entre redes: GEANT2 usa switches `nc1…nc24` y hosts `nh1…nh24`; NSFNET usa `ns1…ns14` y `nsh1…nsh14`. Ejemplos: `nh1 ping -c 3 nh2` en GEANT2 y `nsh1 ping -c 3 nsh2` en NSFNET. `pingall` comprueba los hosts de la consola correspondiente, no las dos redes a la vez.

La telemetria se ejecuta en un hilo del mismo proceso y no imprime continuamente sobre el prompt. El comando `telemetria` muestra su estado y la ruta al registro. `pingall` y los comandos de trafico pueden influir en las mediciones: la ventana incluye una anotacion de actividad de consola. Ese trafico no se presenta como una prueba de aplicacion de las rutas propuestas por la GUI.

**Mantener ambas ventanas abiertas. `exit`/EOF cierra solo esa red y su recolector.** Cerrar una ventana SSH tambien termina la sesion; no se pretende dejarla desatendida en segundo plano. Si se desea mantener terminales al desconectar SSH, usar un multiplexor como una decision posterior; este cambio no lo instala.

Los comandos pertenecen a la [CLI oficial de Mininet](https://github.com/mininet/mininet/blob/master/mininet/cli.py); se reutiliza esa CLI, no una imitacion del prompt.

## Panel de Windows

Reiniciar solamente el servidor de la interfaz mediante `Detener_interfaz.cmd` y despues `Abrir_interfaz.cmd` en la raiz del repositorio. Abrir http://127.0.0.1:8003/sdn-selector.html y actualizar con Ctrl+F5. Pulsar NSFNET/GEANT2 para escoger las nuevas sesiones: las identidades anteriores quedan obsoletas.

El mapa incluye hosts, enlaces de acceso y un controlador RYU con conexiones logicas de control. Casillas permiten ocultarlos si dificultan ver las rutas. Las posiciones de hosts/controlador son esquematicas; el servidor RYU no se ubica en una ciudad historica ficticia. El conteo principal sigue contando switches y enlaces de nucleo.

Al seleccionar un switch, se consultan descripcion, fabricante, plataforma, software, serie y puertos mediante GET a OFCTL REST. Se muestra numero de puertos de datos (LOCAL aparte), vecinos, estado, bits/paquetes acumulados, errores, descartes y tasas calculadas con dos consultas de la misma instancia. Si RYU no publica un campo o no responde, aparece no disponible. El protocolo configurado es OpenFlow 1.3; el endpoint de descripcion no certifica la version negociada y no se inventa esa evidencia.

Al seleccionar un enlace se muestran los contadores de sus dos puertos y la ultima ventana medida. Las ventanas nuevas incluyen bits TX/RX, paquetes de puerto, minimo/maximo/promedio de delay de sondas, sondas ofrecidas/aceptadas/recibidas/no recibidas, rechazos locales, descartes y una capacidad residual estimada. Son metricas de enlace con intervalos de lectura por puerto, no mediciones de una ruta extremo a extremo. Los nuevos extremos de delay no modifican ni completan retroactivamente el dataset historico.

El acceso de un host se confirma con el estado de su interfaz del lado del switch. No se declara conectividad IP del host solo por tener el enlace levantado; `pingall` proporciona esa prueba adicional.

## Alcance

El calculo de rutas sigue sin instalar reglas desde la GUI. La red arranca con el mismo enrutamiento de destino de su recolector anterior para permitir la comunicacion. La aplicacion dinamica de rutas elegidas se deja para la siguiente fase.

La preparacion y las pruebas locales no equivalen a una ejecucion confirmada en las VMs. Despues de lanzar, conservar las salidas de `nodes`, `links`, `pingall`, `telemetria` y una captura del panel con datos reales. Si falla, pegar el mensaje de esa consola; no ejecutar limpiezas globales.
