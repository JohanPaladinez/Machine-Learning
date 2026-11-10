# Apagado y arranque diario del proyecto

El proyecto utiliza Windows para la interfaz y las VMs RYU (192.168.56.108) y Mininet (192.168.56.107). La tercera VM Ubuntu no hace falta. El dataset, los modelos entrenados y el codigo estan guardados en disco; no necesitan quedar ejecutandose durante la noche.

## Esta noche

1. Ya confirmaste que retiraste las reglas aplicadas y que las pruebas funcionaron tambien en GEANT2. Si deseas conservar la demostracion, descarga la evidencia JSON del panel antes de apagar.
2. En **cada una de las dos consolas Mininet**, escribe `exit` y pulsa Enter. Espera a que cierre su red y termine SSH; puede tardar mientras acaba la ventana de medicion. No basta con cerrar la pestana del navegador.
3. En Windows, ejecuta con doble clic `Detener_interfaz.cmd`.
4. Apaga primero la VM Mininet y despues RYU desde Ubuntu, usando **Apagar**. Si prefieres hacerlo por SSH, pega estas lineas **una por una en PowerShell de Windows**:

```powershell
ssh -t mininet@192.168.56.107 "sudo shutdown -h now"
ssh -t ryu@192.168.56.108 "sudo shutdown -h now"
```

Es normal que SSH indique que se cerro la conexion. Espera a que VirtualBox muestre ambas VMs apagadas; entonces puedes apagar Windows. No hace falta detener manualmente cada controlador o servicio de modelos: Ubuntu lo hace al apagarse. Evita usar el apagado forzado de VirtualBox.

**Atencion:** al terminar una consola Mininet abierta mediante SSH, puedes quedar en el indicador `C:\...>` de Windows. En ese indicador no ejecutes `sudo` directamente; utiliza las lineas SSH anteriores o el apagado de Ubuntu.

## Manana: orden de arranque

### 1. Encender las dos VMs

En VirtualBox inicia RYU y Mininet, y espera a que ambas terminen de arrancar. No necesitas iniciar un escritorio grafico en ellas. Conserva las IP anteriores.

### 2. Preparar RYU

En la raiz del repositorio, haz doble clic en **Arrancar_RYU.cmd**. Introduce la contrasena SSH de RYU cuando la solicite. Copia un pequeno lanzador a RYU y lo ejecuta como usuario `ryu`, sin sudo.

El lanzador reutiliza los scripts y modelos existentes. Arranca los servicios que faltan y reutiliza los que ya responden con el contrato esperado. No detiene procesos desconocidos ni selecciona otros puertos silenciosamente.

| Servicio | Puerto |
|---|---:|
| Controlador GEANT2, OpenFlow | 16653 |
| Controlador GEANT2, REST | 18080 |
| Controlador NSFNET, OpenFlow | 16654 |
| Controlador NSFNET, REST | 18081 |
| Modelo individual del inspector | 8010 |
| Cuatro modelos para comparar rutas | 8011 |

Espera el mensaje **RYU LISTO: controladores y modelos comprobados**. Los servicios quedan independientes de esa ventana SSH. Sus registros se conservan en una carpeta nueva `~/proyecto_nsfnet/arranque_diario_ryu_*`.

Si ya copiaste el lanzador y estas en una terminal SSH de RYU, el comando equivalente es:

```bash
env PYTHONIOENCODING=utf-8 python3 -B /home/ryu/proyecto_nsfnet/arranque_diario_sdn/arrancar_ryu.py
```

### 3. Abrir las dos redes con consolas interactivas

Haz doble clic en **Abrir_consolas_Mininet.cmd**. Se abren dos ventanas: una por topologia. Cada una puede pedir la contrasena SSH y la de sudo de Mininet.

Espera a que aparezcan `mininet-geant2>` y `mininet-nsfnet>`. Manten abiertas ambas ventanas mientras utilices el proyecto. Son las consolas reales de las redes que observa la interfaz; permiten `nodes`, `links` y `pingall`.

Los comandos equivalentes, **cada uno en una ventana distinta de PowerShell de Windows**, son:

```powershell
ssh -t mininet@192.168.56.107 "sudo env PYTHONIOENCODING=utf-8 python3 -B /home/mininet/proyecto_nsfnet/consolas_mininet_v1/iniciar.py geant2 --proyecto /home/mininet/proyecto_nsfnet"
```

```powershell
ssh -t mininet@192.168.56.107 "sudo env PYTHONIOENCODING=utf-8 python3 -B /home/mininet/proyecto_nsfnet/consolas_mininet_v1/iniciar.py nsfnet --proyecto /home/mininet/proyecto_nsfnet"
```

Estos archivos ya estaban instalados y funcionando. Si aparece especificamente que falta `consolas_mininet_v1/iniciar.py`, usa **Instalar_consolas_Mininet.cmd** en lugar de Abrir: copia los lanzadores y tambien abre ambas consolas. No ejecutes los dos archivos a la vez.

### 4. Abrir la interfaz en Windows

Haz doble clic en **Abrir_interfaz.cmd**. Abre:

http://127.0.0.1:8003/sdn-selector.html

Recarga con **Ctrl+F5**. Selecciona NSFNET o GEANT2 y espera la red verificada. Si pide observador, usa:

- NSFNET: `http://192.168.56.107:8769`
- GEANT2: `http://192.168.56.107:8768`

El arranque crea sesiones nuevas. Si el panel conserva una seleccion anterior, vuelve a seleccionar la topologia/sesion actual. Espera al menos una ventana completa de medicion (normalmente unos 20-40 segundos; el arranque puede necesitar mas). Una comparacion guardada puede seguir visible como historial; pulsa **Comparar las 5 rutas** para un calculo nuevo.

## Reglas y demostracion

No se vuelve a capturar el dataset, entrenar ni evaluar el test. Los modelos se cargan desde sus archivos guardados.

Las reglas ICMP aplicadas desde el panel no se reinstalan automaticamente despues de apagar las redes. Para una demostracion futura, calcula las rutas y usa **Preparar / Aplicar / Iniciar evidencia / Verificar trafico** con la alternativa que quieras mostrar. Esto no exige repetir hoy las pruebas que ya confirmaste.

## Si algo falla

Conserva el mensaje exacto y el registro que indique el lanzador. Si RYU no confirma el arranque, resuelvelo antes de abrir redes adicionales. No ejecutes los antiguos lanzadores de topologias en segundo plano ni `mn -c` para intentar arreglarlo: podrias interferir con la otra red.

Este arranque no cambia la hora ni configura NTP. Si aparece otra vez un rechazo por relojes desajustados, conserva esa salida para corregir ese problema concreto; no quites la comprobacion de frescura de las entradas ML.

El lanzador se reviso localmente; el proximo encendido sera su primera comprobacion completa en tus VMs. No se ha ejecutado un reinicio remoto desde este chat.
