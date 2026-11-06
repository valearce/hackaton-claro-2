# Android: grabaciones y avisos de prueba

Herramientas del proyecto para grabar la pantalla de un Android y publicar una
notificación local durante la grabación. También permiten inspeccionar Chrome
por CDP. Requieren Node.js 22 o superior y Android Platform Tools (ADB), sin
dependencias npm adicionales. Los procesos auxiliares usan `windowsHide: true`.

## Preparación

1. Activa Opciones de desarrollador y Depuración USB en el teléfono, conéctalo
   con un cable de datos y acepta la autorización de este computador.
2. Configura ADB mediante `--adb RUTA`, la variable `ADB_PATH`, o una copia de
   `config.example.json` en `.local/android/config.json`, desde la raíz del repo.
   También se busca en `.local/android/platform-tools`, el SDK Android y `PATH`.
3. Comprueba la conexión:

```powershell
node herramientas/android/android.mjs doctor
node herramientas/android/android.mjs devices
```

`doctor` consulta ADB y enumera dispositivos; no cambia el teléfono. Un estado
`unauthorized` requiere aceptar el permiso en el celular. Una lista vacía no
confirma si la depuración está activa: revisar conexión, cable y controlador.
Si hay varios dispositivos, indica `--serial SERIAL`. Todos los comandos que
actúan sobre el teléfono quedan asociados a ese número de serie.

La instalación local puede reutilizar el ADB existente mediante la configuración
privada en `.local`; el ejecutable y sus DLL no se incluyeron en Git.

## Demo: aviso visible durante una grabación

```powershell
node herramientas/android/android.mjs demo --seconds 20 --delay 3 --title "Claro - Demo" --text "DEMOSTRACION: tenemos una oferta de prueba para ti." --popup
```

El comando confirma el inicio de `screenrecord`, espera el retraso indicado,
publica el aviso flotante con `--popup` y mantiene cerrada la bandeja.
Después descarga el MP4 en `.local/android/grabaciones`. La duración admite de
1 a 180 segundos; el retraso debe ser menor que la duración. Se puede indicar
`--output .local/android/mi-demo.mp4`; no se sobrescriben archivos existentes.
El video no tiene audio. Conviene mantener la misma orientación durante la toma.

El aviso aparece como una notificación local de Android Shell. No crea una
conversación en Mensajes ni envía SMS por la red. `--popup` usa un canal propio
de importancia alta. La opción alternativa `--show` abre el panel y utiliza el
canal estándar de `cmd notification post`; ambas opciones son excluyentes.
Los comandos no cambian Wi-Fi, datos móviles, modo avión ni el rol de SMS.

Comandos individuales:

```powershell
node herramientas/android/android.mjs notify --text "DEMO: mensaje de prueba" --popup
node herramientas/android/android.mjs record --seconds 15
```

Para adjuntar una imagen a la notificación nativa:

```powershell
node herramientas/android/android.mjs notify --popup --title "Claro - Demo" --text "DEMO: mensaje con imagen" --image recursos/imagenes/claro-logo.jpg
```

Se admiten PNG y JPEG locales de hasta 5 MB. La imagen se reduce durante la
decodificación a un máximo aproximado de 1024 píxeles por lado. Se añade como
miniatura y como imagen grande de la notificación expandida. El tamaño de la
vista flotante nativa depende de Android y del fabricante.

### Aviso tipo SMS con imagen para la demo

```powershell
node herramientas/android/android.mjs sms-demo --sender "Claro" --text "DEMO: Hola, tenemos una oferta de prueba para ti." --image recursos/imagenes/claro-logo.jpg
```

Publica una notificación nativa con remitente, texto e imagen adjunta, marcada
como Mensaje de prueba. El aviso flotante usa el espacio que permite Android;
al desplegar la notificación se ve la imagen grande. Se publica mediante Android
Shell y permanece en su bandeja. Es una simulación local, no envía SMS/MMS/RCS
ni escribe conversaciones en la aplicación Mensajes. No abre el banner grande
de demostración ni cambia los permisos de superposición.

### Banner grande de demostración

```powershell
node herramientas/android/android.mjs banner --title "Una oferta pensada para ti" --text "DEMO: una propuesta que se adapta a tu consumo de datos." --image recursos/imagenes/claro-logo.jpg --seconds 15
```

Este comando dibuja una tarjeta flotante con imagen grande, título y varias
líneas de texto sobre la pantalla. Incluye la etiqueta DEMOSTRACIÓN y el botón
Cerrar; desaparece al pulsarlo o al cumplirse la duración de 3 a 60 segundos.
La vista no toma el foco del teclado y utiliza un contexto de ventana propio.
Es un banner de demostración: no crea una entrada en la bandeja de notificaciones.

Se ejecuta con la autorización ADB existente, sin instalar un APK. Comprueba el
permiso de superposición de Android Shell, conserva su ajuste y rechaza un
bloqueo explícito. Se probó su ciclo de apertura y cierre en el ZTE 8050 / Android
13. El auxiliar y la imagen temporal se retiran del teléfono al finalizar.
También es visible en la ventana de scrcpy para presentar la demo por Meet.

Estado del banner experimental: su apertura y cierre automático aprobaron,
pero se detectó un fallo de contexto al interactuar con la tarjeta en el ZTE.
Para la demostración acordada se utiliza `sms-demo` y la notificación nativa.

### Preparar el canal flotante

El canal estándar de Shell tiene importancia normal y el ZTE bloquea su aumento.
El modo `--popup` crea el canal propio `claro_demo_popup_v1` con importancia alta
mediante un auxiliar temporal ejecutado con la autorización ADB existente.
No instala una aplicación ni necesita permisos de acceso a SMS. Usa interfaces
internas de Android; se probó en el ZTE 8050 con Android 13 y puede requerir
adaptación en otras versiones. No evita el modo No molestar ni un bloqueo de
notificaciones impuesto por el usuario.

Para reconstruirlo se necesita Java 8 o superior y el ensamblador oficial
[Smali 2.5.2](https://github.com/JesusFreke/smali):

1. Descarga `https://bitbucket.org/JesusFreke/smali/downloads/smali-2.5.2.jar`
   en `.local/android/smali-2.5.2.jar`.
2. Ejecuta `node herramientas/android/build-popup.mjs`.

El constructor valida el SHA-256 de la descarga. Los fuentes de la notificación
y del banner están en `popup/`; el DEX compilado queda en `.local/android/popup`.
El modo flotante transfiere un auxiliar con nombre único a `/data/local/tmp`,
publica el aviso y retira ese archivo al finalizar. No abre la bandeja.

## Compartir el celular desde el PC en Meet

La instalación portable oficial de scrcpy 5.0.1 está en
`.local/android/scrcpy/scrcpy-win64-v5.0.1`. Para volver a abrirla:

```powershell
node herramientas/android/mirror.mjs
```

La ventana se llama **Celular - Claro Demo**. En Meet del PC, selecciona
**Presentar ahora > Una ventana** y elige esa ventana. El lanzador evita duplicar
su sesión, reutiliza el ADB configurado y guarda los logs en `.local/android`.
No abre una consola adicional. El audio del celular está desactivado en este
lanzador. Para finalizar, cierra la ventana del celular.

Para preparar scrcpy en otro equipo, descarga y extrae la
[versión oficial para Windows](https://github.com/Genymobile/scrcpy/blob/master/doc/windows.md)
en la misma ruta o configura `scrcpyPath` en `.local/android/config.json`.
La descarga win64 5.0.1 usada se verificó con SHA-256
`b12a2c4ee8be317422451fc7dcf8ee20a71b5ea7ef9ad73ddd825a25316227a5`.

Si falla el aviso, se intenta descargar la grabación de todas formas y se informa
el error. El archivo remoto generado por esta herramienta sólo se elimina tras
verificar que la descarga local existe y tiene contenido. Si falla la grabación
o transferencia, el archivo remoto se conserva para su recuperación. Un cierre
abrupto del proceso también puede dejar el archivo en el teléfono; `screenrecord`
conserva su límite de tiempo.

## Chrome Android por CDP

Abre el sitio en Chrome en el teléfono y crea el túnel:

```powershell
node herramientas/android/android.mjs connect --port 9223
node herramientas/android/phone.mjs tabs
node herramientas/android/phone.mjs inspect --origin https://tu-sitio.example
node herramientas/android/phone.mjs screenshot --target ID --output .local/android/pantalla.png
node herramientas/android/phone.mjs observe --target ID --seconds 15
node herramientas/android/phone.mjs evaluate --target ID --script fragmento.js
```

`--origin` compara el origen exacto. Si hay varias pestañas del mismo sitio,
elige `--target ID` del resultado de `tabs`. Para evaluar en un service worker,
añade `--worker`. `evaluate` ejecuta el archivo con los permisos y la sesión del
navegador: revisar su contenido antes de usarlo. La observación de red guarda
método, ruta sin parámetros y estado de peticiones del mismo origen; no exporta
cabeceras, cookies ni cuerpos. El túnel no reemplaza uno que ya esté ocupado.

Para ADB directo: `node herramientas/android/run-adb.mjs devices -l`.
Las rutas de archivos pasadas por el usuario se resuelven desde su directorio
actual. Los comandos de ejemplo se ejecutan desde la raíz del repositorio.

## Referencias originales y verificación

`referencias-qnexus/` conserva los 20 archivos copiados del proyecto QNexus,
incluido su README original, sin cambios de contenido. Sus rutas y comandos
pertenecen a aquel proyecto. No son los puntos de entrada de esta adaptación:
hay selectores, dominios y eventos propios de QNexus; `qnx-reproduce.mjs` cambia
la conectividad y `qnx-attendance-correction.js` modifica una asistencia concreta
en producción. Se conservan para consulta y no se ejecutan automáticamente.

```powershell
node --test herramientas/android/tests/android.test.mjs
```

Las pruebas usan ADB y CDP simulados: selección del teléfono, escapado de texto,
secuencia de grabación y aviso, conservación del video ante fallos y desconexión
de CDP. Una prueba con teléfono real es necesaria para verificar la visualización
del aviso y la codificación de video de ese dispositivo.

Validación física del 2026-11-05: ZTE 8050 reconocido y autorizado en ADB.
El comando `demo` de 8 segundos terminó correctamente, publicó el aviso local,
abrió el panel y descargó un MP4 de 936.008 bytes en `.local/android/grabaciones`.
Se añadió después el canal de importancia alta, confirmado por Android con
importancia 4, y se abrió la ventana de scrcpy para presentar desde el PC.
El video, las herramientas descargadas y la configuración local quedan
excluidos de Git mediante `.gitignore`.

Fuentes consultadas al adaptar la conversación guardada en el PDF:

- [ADB: grabación de pantalla](https://developer.android.com/tools/adb#screenrecord)
- [AOSP: NotificationShellCmd](https://android.googlesource.com/platform/frameworks/base/+/android16-qpr2-release/services/core/java/com/android/server/notification/NotificationShellCmd.java)
- [Android: SMS en emulador](https://developer.android.com/studio/run/emulator-console#sms)
