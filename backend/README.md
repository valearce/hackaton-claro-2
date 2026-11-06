# API NBA

La consola Next.js de `web/` usa esta API FastAPI. El único optimizador es el motor compartido de `modelo/`, con OR-Tools. La referencia sencilla se lee de `referencia.json`, extraída de la evaluación histórica del commit `2d12528`; no se ejecuta una baseline en cada solicitud.

## Desarrollo

Desde la raíz del repositorio:

```powershell
python -m venv .local/consola-web
.local/consola-web/Scripts/python.exe -m pip install -r backend/requirements.txt
npm ci
npm run dev
```

El lanzador inicia Python en el puerto 8001 y Next.js en el 3000, reutiliza servicios que ya responden y oculta las ventanas auxiliares en Windows. `NBA_PYTHON` permite indicar otro intérprete. Los registros quedan en `.local/consola/logs/`.

Para compilar y servir la versión de producción:

```powershell
npm run build
npm start
```

## Estado y artefactos

En local, configuraciones y resultados se guardan en `.local/consola/`. `NBA_STORAGE_DIR` permite cambiar ese destino. En Vercel se exige un almacén Blob privado conectado al proyecto; `BLOB_READ_WRITE_TOKEN` permanece exclusivamente en el servidor. Producción y previews usan prefijos distintos.

Cada corrida conserva configuración, fecha, huellas de datos/motor, métricas y CSV comprimido. El manifiesto se escribe después de los artefactos. La caché de manifiestos tiene tres entradas y 15 minutos de vigencia; la caché de parrillas admite una entrada y dos minutos. Las corridas permanecen en el almacenamiento persistente aunque se vacíe la caché. Un bloqueo por proceso limita la optimización a una corrida simultánea por instancia.

La consola siempre inicia con `config_reto` y la fecha oficial `2026-11-05`, aunque la API tenga otra versión activa. Calcula ese escenario una vez al abrir. Los botones y «Seleccionar otro» preparan cambios locales; «Enviar parámetros» se habilita si la configuración o fecha cambian y envía una sola solicitud con la configuración completa. Restablecer el reto recupera el resultado inicial de la sesión. Durante un cálculo, los cambios posteriores quedan pendientes de un nuevo envío explícito.

Las versiones usan fecha UTC y UUID y conservan la corrida a la que pertenecen. Recuperar una versión prepara sus parámetros sin ejecutar el motor. La API mantiene el endpoint de activación para otros consumidores; la consola conserva siempre el inicio oficial. Las versiones anteriores permanecen como instantáneas con sus huellas y resultados originales. La CLI científica conserva su configuración explícita para reproducir el reto.

La pestaña Mapa muestra `mapa/mapa-estratos-bogota.html` mediante la ruta Next.js `/mapa`, incluida en el empaquetado del frontend, con una única vista cartográfica. La geometría y las coberturas están incluidas; solo el fondo opcional de calles requiere Internet. La pestaña Clusters contiene los perfiles y gráficos de Vale. `GET /api/clusters/{id}` desglosa la parrilla del escenario enviado sin ejecutar otro optimizador ni una línea base. Las propuestas de publicidad son una referencia precalculada de la configuración oficial.

## Vercel

`vercel.json` usa Vercel Services (beta): Next.js y FastAPI se construyen por separado y se publican juntos. `/api/*` se dirige al servicio Python y el resto al frontend. Python usa 3.12 y el panel Node.js 24. El comando `compilar.py` incluye el motor y el CSV compartidos en el servicio Python sin mantener copias duplicadas en Git.

El CSV de más de 4,5 MB se entrega mediante una respuesta en streaming. El servidor no depende de la memoria de una instancia para recuperar una parrilla o versión.

## Rutas

| Ruta | Uso |
| --- | --- |
| `GET /api/config` | Configuración activa, columnas, tipos y referencia original |
| `POST /api/simular` | Optimizar una configuración y fecha |
| `GET /api/parrilla/{id}` | Paginar de diez en diez, buscar y filtrar |
| `GET /api/parrilla/{id}/csv` | Descargar el CSV completo en streaming |
| `GET/POST /api/versiones` | Listar o guardar versiones |
| `GET /api/versiones/{id}` | Recuperar la configuración guardada |
| `POST /api/versiones/{id}/activar` | Marcar una versión activa en la API; no cambia el inicio oficial de la consola |

La validación comprueba la estructura y los tipos de las reglas antes de optimizar. Las métricas separan el valor esperado comercial del objetivo ponderado y muestran los excesos de cupo originales en número de contactos.

## Cercanía y vallas

La pestaña Cercanía simula el recorrido de un cliente entre antenas y vallas con posiciones de demostración. Se puede mover el marcador con el mapa, las flechas del teclado o los pasos del recorrido. Los radios y la disponibilidad de cada zona son configurables.

El mapa usa MapLibre y las manzanas de Bogotá incluidas en el repositorio, servidas como GeoJSON por `/mapa/geometria`. No necesita un mapa base externo. La reproducción completa dura ocho segundos a 1×; admite pausa, avance manual, seguimiento del cliente y velocidades de 0,5× a 4×. El reloj avanza doce minutos simulados durante el recorrido. Reproducirlo no ejecuta evaluaciones en el backend.

`POST /api/cercania/evaluar` recibe la posición, las zonas, la campaña y todas las reglas de la prueba en una solicitud explícita. Calcula las distancias Haversine y comprueba cobertura de antena, cercanía a una valla activa, vigencia de campaña, canal, consentimiento e intervalo entre oportunidades. El reloj del escenario permite repetir la prueba. Mover el marcador o editar un radio prepara el escenario; se evalúa al pulsar el botón.

El resultado genera una vista previa de la oportunidad de contacto. El historial de la sesión registra evaluaciones y bloqueos por frecuencia; no representa mensajes entregados ni conversiones reales.

| Ruta | Uso |
| --- | --- |
| `GET /api/cercania/config` | Zonas ficticias y valores iniciales de la prueba |
| `POST /api/cercania/evaluar` | Evaluar campaña y cercanía con el escenario completo |
