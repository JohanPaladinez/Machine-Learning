# Seguridad

## Alcance

La aplicación está destinada a una red de laboratorio. FastAPI sirve la API y el panel compilado en loopback de Windows, puerto 8003. La selección de topología es global al proceso; no se ha implementado aislamiento entre usuarios ni autenticación para un despliegue público de la aplicación.

El repositorio público contiene código y documentación. Publicar el repositorio no publica los servicios de las VMs.

## Reportar un problema

Para problemas que no requieran información sensible, abrir un issue con la versión afectada, pasos de reproducción y comportamiento observado. No adjuntar contraseñas, tokens, claves SSH, datasets privados ni detalles que permitan acceso a una VM.

Si el problema requiere información confidencial, contactar al propietario mediante un canal privado ya acordado antes de compartirla. No se publica una dirección de contacto privada en este repositorio.

## Configuración y datos

- Las fuentes de observación se configuran en el servidor, no mediante URLs arbitrarias del navegador.
- Mantener separados los entornos de CI y del laboratorio.
- Guardar credenciales fuera del repositorio; `.env.example` contiene únicamente valores de configuración del laboratorio.
- No publicar modelos, datasets, logs de ejecución ni copias de respaldo.
- Aplicar cambios al plano de datos solo con autorización y un procedimiento de reversión.

## Escrituras OpenFlow de la funcion de enrutamiento

El comparador calcula sin instalar. La accion explicita Aplicar instala reglas ICMP entre IP de hosts concretos en el controlador de la fuente configurada. El navegador no puede elegir una URL arbitraria de controlador. Se verifican identidad de red, puertos, reglas y contadores; el retiro se limita a cookies/matches propios mediante delete_strict. Se preservan las reglas de arranque, ARP, UDP y sondas.

El journal `.ejecucion_windows/enrutamiento_icmp.json` puede contener identificadores de operaciones y se excluye de Git. No exponer OFCTL REST ni esta API sin autenticacion en Internet. Los servicios del laboratorio deben permanecer en su red privada.
