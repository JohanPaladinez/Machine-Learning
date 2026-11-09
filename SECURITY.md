# Seguridad

## Alcance

La aplicación está destinada a una red de laboratorio. FastAPI y Vite escuchan en loopback en la VM de interfaz. La selección de topología es global al proceso; no se ha implementado aislamiento entre usuarios ni autenticación para un despliegue público de la aplicación.

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
