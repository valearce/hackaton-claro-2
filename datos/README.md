# Datos del reto

[`clientes.csv`](clientes.csv) contiene los **100.000 clientes sintéticos y 45 columnas** del archivo originalmente llamado `clientes 1.csv`. Se cambió su ubicación y nombre; los bytes del CSV se conservaron.

El diccionario está en [`../docs/reto/diccionario-datos.pdf`](../docs/reto/diccionario-datos.pdf). La huella SHA-256, tamaño y dimensiones del CSV se conservan en [`manifest.json`](manifest.json). `python scripts/verificar_repositorio.py` contrasta los archivos y las evaluaciones con esa huella.

Las columnas incluyen perfil, consumo, productos actuales, permisos de contacto, historial y scores suministrados por el reto. No contienen compras observadas ni horas de envío, lectura o respuesta. No permiten medir conversión ni predecir emociones directamente.

Los cinco CSV pequeños del kit se conservan en [`../modelo/kit_original/`](../modelo/kit_original/) como referencias de configuración y casos oficiales. Las parrillas y los perfiles generados se guardan en `modelo/resultados/`, excluido de Git.
