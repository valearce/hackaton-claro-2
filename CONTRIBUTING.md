# Desarrollo local

Ejecuta los comandos desde la raíz. Mantén los datos en `datos/`, las fuentes del reto en `docs/reto/` y las imágenes compartidas en `recursos/imagenes/`. `modelo/rutas.py` centraliza las ubicaciones usadas por los comandos del modelo.

## Comprobaciones

```powershell
python -m modelo.probar
python scripts/verificar_repositorio.py
node --test herramientas/android/tests/android.test.mjs
git diff --check
```

Los tests Android utilizan ADB simulado: no requieren teléfono ni publican notificaciones. Las pruebas del modelo se ejecutan mediante el kernel GPU registrado, validan versiones y CUDA y guardan el informe en `modelo/resultados/pruebas-gpu/`. Incluyen optimización frente a búsqueda exhaustiva, auditoría de asignaciones, preprocesamiento sin fuga de datos, perfiles entrenados en CUDA y portabilidad CPU/GPU. Consulta [el entorno estándar](modelo/docs/entorno.md).

Después de modificar rutas del mapa:

```powershell
python mapa/generar_mapa.py
```

Se reutiliza `mapa/.cache/` cuando existe; un clon nuevo descarga las fuentes públicas. `--actualizar` y `--actualizar-red` solicitan expresamente nuevas descargas. Comprueba los totales del CSV y la apertura del HTML.

No es necesario volver a entrenar modelos para cambiar documentación o rutas. Las huellas SHA-256 de la evaluación deben seguir coincidiendo con el CSV. `python -m modelo.exportar_evaluacion` verifica los datos y la configuración antes de actualizar los informes versionados.

## Archivos locales

- `.local/`: dispositivos, configuración privada, ejecutables y grabaciones.
- `tmp/`: diagnósticos y trabajo temporal.
- `modelo/resultados/`: parrillas, pesos y perfiles por cliente.
- `mapa/.cache/`: descargas y capas geográficas.
- `investigacion/estudios/`: copias locales de lectura; `fuentes.json` conserva referencias públicas.
- Entornos Python, cachés y notebooks: excluidos mediante `.gitignore`.

Conserva los datos originales; trabaja con una copia o indica `--datos` al experimentar. No publiques credenciales ni configuración real de dispositivos.

En Windows, ejecuta comandos y pruebas en la sesión de ejecución existente, sin abrir ventanas de terminal adicionales. Los procesos Node deben usar `windowsHide: true`; los procesos Python de consola, `subprocess.CREATE_NO_WINDOW`; los lanzamientos PowerShell en segundo plano, `Start-Process -WindowStyle Hidden`.
