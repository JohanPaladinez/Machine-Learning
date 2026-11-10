# Comprobacion local del cambio

Actualizacion de publicacion: el usuario confirmo que ambas consolas funcionaron despues de instalar la correccion 1.1. Los pendientes de arranque mencionados mas abajo reflejan la comprobacion local previa; no se sustituyen los resultados aun no aportados de pingall ni de aplicacion real de rutas.

- Ocho pruebas nuevas Python: contadores, tasas, reinicios, valores no soportados, descripcion ausente, identidad de interfaces, rechazo de sesiones antiguas, consultas solo lectura, seleccion de fuentes y enriquecimiento de ventanas conservando las entradas ML.
- Dos pruebas JavaScript: agregar hosts/controlador mantiene intacto el grafo de enrutamiento; no se crean elementos sin datos de origen.
- Diez pruebas de la comparacion de cinco rutas y seis de los criterios convencionales existentes: correctas, usando sus entornos de dependencias correspondientes.
- ESLint sobre los cuatro archivos JavaScript/JSX modificados: correcto. La comprobacion global del proyecto tambien alcanza compilaciones anteriores y archivos heredados con errores preexistentes; no se presenta como superada.
- Compilacion Vite del panel: correcta; conserva una advertencia de tamano del bundle (~800 kB), no un fallo.
- Sintaxis de los dos lanzadores comprobada; se verifico compatibilidad sintactica con Python 3.6. No se ejecuto Mininet real en este equipo Windows.
- Se observo en navegador GEANT2 activa mediante el servidor existente, con hosts y controlador dibujados. La captura esta en `outputs/Mapa_hosts_controlador.png`. Esto no certifica la ejecucion del lanzador nuevo ni la carga de los endpoints nuevos en el proceso ya abierto.
- El intento de reinicio local fue bloqueado por las restricciones de conexiones del entorno. El gestor no detuvo procesos que no pudo identificar. El reinicio debe ejecutarse desde Windows con los lanzadores existentes.
- No se ejecutaron SSH, cambios de reloj, recreaciones de redes ni entrenamiento desde esta revision. La transicion en las VMs se realiza al abrir Instalar_consolas_Mininet.cmd y autenticar las dos sesiones.

Pendiente de confirmacion con el usuario: ambos prompts reales, salidas de nodes/links/pingall, telemetria activa, nuevos datos de puertos y enlace en la interfaz despues del reinicio. La aplicacion dinamica de rutas sigue fuera de este cambio, por indicacion del usuario.

## Correccion 1.1 tras el primer intento en las VMs

Las capturas del usuario muestran que ambos lanzadores cerraron su sesion anterior y fallaron con Errno 98 antes de entrar en la consola nueva. Se identifico la prueba preliminar de bind sin reutilizacion como el punto del error. TIME_WAIT puede provocar ese rechazo sin un listener activo; las capturas por si solas no excluyen la existencia de otro listener.

Se retiro ese socket de prueba. Se abre el servidor HTTP definitivo con SO_REUSEADDR y sin SO_REUSEPORT antes de crear Mininet. Un conflicto real ahora informa el puerto y consulta ss, conservando al otro proceso. Tambien se corrigio el cierre del servidor reservado que aun no ejecuto serve_forever, para evitar un bloqueo en shutdown.

Cuatro pruebas nuevas verifican el contrato de reutilizacion con un socket simulado, el rechazo de un listener activo y ambas rutas de cierre; pasaron junto con las ocho pruebas Python anteriores. No se presenta esta simulacion como una prueba de sockets Linux reales ni como confirmacion del nuevo arranque remoto. El usuario debe ejecutar nuevamente el instalador actualizado para copiar la version 1.1.
