# Desarrollo local

Ejecuta los comandos desde la raíz. Mantén los datos en `datos/`, las fuentes del reto en `docs/reto/` y las imágenes compartidas en `recursos/imagenes/`. `modelo/rutas.py` centraliza las ubicaciones usadas por los comandos del modelo.

## Comprobaciones

Para cambios en la consola, ejecuta `npm ci` y `npm run build`, inicia `npm start` y verifica la simulación, la descarga completa del CSV y la recuperación de versiones. La [guía de la API](backend/README.md) describe su entorno y almacenamiento. Next.js valida TypeScript durante la compilación.

```powershell
python -m modelo.ejecutar --fecha 2026-11-05
python scripts/verificar_repositorio.py
node --test herramientas/android/tests/android.test.mjs
git diff --check
```

Los tests Android utilizan ADB simulado: no requieren teléfono ni publican notificaciones. El modelo ya no tiene suite de pruebas ni comparadores ejecutables. La ejecución NBA usa exclusivamente OR-Tools y exige certificado exacto y auditoría de negocio antes de exportar. Consulta [el entorno de ejecución](modelo/docs/entorno.md).

Después de modificar rutas del mapa:

```powershell
python mapa/generar_mapa.py
```

Se reutiliza `mapa/.cache/` cuando existe; un clon nuevo descarga las fuentes públicas. `--actualizar` y `--actualizar-red` solicitan expresamente nuevas descargas. Comprueba los totales del CSV y la apertura del HTML.

No es necesario volver a entrenar modelos para cambiar documentación o rutas. Las huellas SHA-256 de la evaluación deben seguir coincidiendo con el CSV. `python -m modelo.exportar_evaluacion` verifica los datos, configuración, código y certificado del motor antes de actualizar los informes versionados.

## Archivos locales

- `.local/`: dispositivos, configuración privada, ejecutables y grabaciones.
- `tmp/`: diagnósticos y trabajo temporal.
- `modelo/resultados/`: parrillas, pesos y perfiles por cliente.
- `mapa/.cache/`: descargas y capas geográficas.
- `investigacion/estudios/`: copias locales de lectura; `fuentes.json` conserva referencias públicas.
- Entornos Python, cachés y notebooks: excluidos mediante `.gitignore`.

Conserva los datos originales; trabaja con una copia o indica `--datos` al experimentar. No publiques credenciales ni configuración real de dispositivos.

En Windows, ejecuta comandos y pruebas en la sesión de ejecución existente, sin abrir ventanas de terminal adicionales. Los procesos Node deben usar `windowsHide: true`; los procesos Python de consola, `subprocess.CREATE_NO_WINDOW`; los lanzamientos PowerShell en segundo plano, `Start-Process -WindowStyle Hidden`.
