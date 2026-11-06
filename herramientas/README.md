# Herramientas de demostración

[`android/`](android/README.md) contiene los comandos de ADB para inspeccionar el teléfono, grabar la pantalla, compartirla mediante scrcpy y mostrar avisos locales con texto e imagen.

```powershell
node herramientas/android/android.mjs help
node herramientas/android/android.mjs doctor
node --test herramientas/android/tests/android.test.mjs
```

La configuración real y las grabaciones se guardan en `.local/android/`, excluido de Git. `android/config.example.json` sirve como plantilla. El logo compartido está en [`../recursos/imagenes/claro-logo.jpg`](../recursos/imagenes/claro-logo.jpg).

El [PDF de la conversación sobre grabación y SMS](docs/adb-grabacion-sms.pdf) conserva el material proporcionado como referencia. [`android/referencias-qnexus/`](android/referencias-qnexus/) mantiene la copia de los scripts de origen; los comandos adaptados para este repositorio están directamente en `android/`.
