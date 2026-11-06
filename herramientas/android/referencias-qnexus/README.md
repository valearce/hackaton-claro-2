# Diagnóstico Android

Diecinueve auxiliares recuperados de `tmp/android` y conservados en esta carpeta.
Las herramientas ADB siguen en `.local/android/platform-tools`.

Ejecutar desde la raíz del repositorio:

```powershell
node utilidades/android/run-adb.mjs devices
node utilidades/android/run-adb.mjs forward tcp:9223 localabstract:chrome_devtools_remote
node utilidades/android/qnx-phone.mjs utilidades/android/qnx-inspect.js
```

`run-adb.mjs` ejecuta ADB sin abrir una consola adicional. `qnx-phone.mjs`
conecta al puerto CDP 9223 y selecciona la pestaña de QNexus del teléfono.
Puede evaluar un fragmento `.js`, inspeccionar el service worker con `--worker`,
observar metadatos de red con `--observe` o guardar una captura con
`--screenshot .local/android/diagnostico.png`.

Los `.js` son fragmentos para el navegador; se envían mediante `qnx-phone.mjs`.
Incluyen inspección de estado/caché, lectura y apertura/cierre de menús, selección
de vistas y acciones de diagnóstico. `qnx-reproduce.mjs` automatiza una reproducción
del incidente de conectividad y puede cambiar el estado del teléfono; se utiliza
para una sesión de diagnóstico autorizada, no como comprobación rutinaria.

Se conservaron los fragmentos originales, se ajustaron rutas de los lanzadores
y se adaptaron los tres ejecutables al formato ESM del proyecto. No se ha ejecutado
ninguna acción sobre el teléfono al trasladarlos. La captura de la sesión anterior
permanece en el ZIP privado, fuera de esta carpeta de scripts.
