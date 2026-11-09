# Respaldo y reversión

## Ubicación e integridad

Respaldo en la VM de interfaz: `/home/vboxuser/proyecto_nsfnet/backups/work_rutas_ml_20261109_170550`.

Contiene las versiones originales de los tres archivos modificados, con sus rutas relativas y `originales.sha256.json`. Los módulos de Dijkstra, pesos, inferencia por enlace y runtime original no se sobrescribieron. Los demás archivos de esta ampliación se añadieron con nombres nuevos.

`evidencias/inventario_cambios.json` registra SHA-256 originales y finales. Los manifiestos `conservacion-antes.sha256` y `conservacion-despues.sha256` son idénticos para los 44 CSV bajo `datos/` de RYU y el modelo común. No se modificaron esos archivos. Las nuevas consultas pueden añadir logs operativos de inferencia; no se confunden con el dataset de entrenamiento.

## Revertir sin activar los puertos habituales

La activación en 8002/5181 se realizó con autorización del usuario. Antes de restaurar fuentes y reiniciar la interfaz, consultar también la sección «Revertir después de activar». Copiar desde el respaldo únicamente:

```bash
cd /home/vboxuser/proyecto_nsfnet
BACKUP="/home/vboxuser/proyecto_nsfnet/backups/work_rutas_ml_20261109_170550"
cp -- "$BACKUP/backend/api/sdn_selector_v2.py" backend/api/sdn_selector_v2.py
cp -- "$BACKUP/frontend/app/src/sdn-selector-v2/SelectorRoot.jsx" frontend/app/src/sdn-selector-v2/SelectorRoot.jsx
cp -- "$BACKUP/frontend/app/src/sdn-selector-v2/PanelSdn.jsx" frontend/app/src/sdn-selector-v2/PanelSdn.jsx
```

Verificar los hashes contra `originales.sha256.json`. Los archivos nuevos pueden conservarse sin uso para auditoría; no es necesario eliminarlos. El `dist-sdn-selector-v2` original se conserva porque las compilaciones nuevas usan directorios diferentes. Los modelos, datos y observadores no necesitan restauración.

## Activar la versión revisada

Preparar primero, sin detener nada:

```bash
cd ~/proyecto_nsfnet
bash scripts/compilar_interfaz.sh
.venv/bin/python scripts/activar_interfaz.py
```

La segunda orden solo identifica los procesos esperados. Únicamente tras la autorización del usuario:

```bash
.venv/bin/python scripts/activar_interfaz.py --activar
```

La activación comprueba la identidad de los procesos FastAPI/selector y Vite/preview en 8002/5181, registra sus argumentos y directorios, les envía SIGTERM e inicia la versión nueva. No toca 8003/5182, RYU ni Mininet. Los registros quedan en `interfaz_rutas_ml_ejecucion/`. No se incorporan contraseñas al paquete ni a los scripts.

## Revertir después de activar

Con autorización para detener únicamente la interfaz, identificar los procesos actuales por puerto y argumentos, detenerlos de forma ordenada y restaurar los tres fuentes como arriba. Reiniciar la API original con `.venv/bin/python -m uvicorn backend.api.sdn_selector_v2:app --host 127.0.0.1 --port 8002`. Para el frontend original usar, desde `frontend/app`, `node node_modules/.bin/vite preview --config vite.sdn-selector.config.js --host 127.0.0.1 --port 5181 --strictPort`, sin `--outDir`: sirve la compilación original conservada. Cargar antes el entorno Node existente si no está en PATH.

La configuración antigua del observador se puede recuperar del campo `previous_selection` del registro de activación o mediante su formulario original. No reutilizar PID históricos. Este rollback no requiere reiniciar ninguna VM ni modificar el plano de datos.

## Ajuste posterior: tarjeta individual de ruta ML

Se añadió la opción **Ruta inteligente (ML)** al formulario original. Respaldo previo de `PanelSdn.jsx`: `/home/vboxuser/proyecto_nsfnet/backups/work_ruta_ml_panel_20261109_173738`. El JSON `evidencias/ajuste_tarjeta_ml.json` conserva los hashes anterior y posterior. Para revertir únicamente este ajuste, copiar ese `PanelSdn.jsx` a su ruta original y ejecutar `bash scripts/compilar_interfaz.sh`; Vite preview sirve la compilación nueva sin reiniciar los controladores ni el backend.
