# API NBA

La consola Next.js de `web/` usa esta API FastAPI. El único optimizador es el motor compartido de `modelo/`, con OR-Tools y certificado entero. La referencia sencilla se lee de `referencia.json`, extraída de la evaluación histórica del commit `2d12528`; no se ejecuta una baseline en cada solicitud.

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

Cada corrida conserva configuración, fecha, huellas de datos/motor, métricas, CSV comprimido y certificado completo. El manifiesto se escribe después de los artefactos. La caché de manifiestos tiene tres entradas y 15 minutos de vigencia; la caché de parrillas admite una entrada y dos minutos. Las corridas permanecen en el almacenamiento persistente aunque se vacíe la caché. Un bloqueo por proceso limita la optimización a una corrida simultánea por instancia.

Las versiones usan fecha UTC y UUID, tienen endpoints para listar, recuperar y activar, y conservan la corrida a la que pertenecen. Activar define la configuración inicial de nuevas sesiones; no envía campañas ni mensajes a clientes. Las versiones anteriores permanecen como instantáneas con sus huellas y resultados originales. La CLI científica conserva su configuración explícita para reproducir el reto.

## Vercel

`vercel.json` usa Vercel Services (beta): Next.js y FastAPI se construyen por separado y se publican juntos. `/api/*` se dirige al servicio Python y el resto al frontend. Python usa 3.12 y el panel Node.js 24. El comando `compilar.py` incluye el motor y el CSV compartidos en el servicio Python sin mantener copias duplicadas en Git.

El CSV de más de 4,5 MB se entrega mediante una respuesta en streaming. El certificado se descarga comprimido. El servidor no depende de la memoria de una instancia para recuperar una parrilla o versión.

## Rutas

| Ruta | Uso |
| --- | --- |
| `GET /api/config` | Configuración activa, columnas, tipos y referencia original |
| `POST /api/simular` | Optimizar una configuración y fecha |
| `GET /api/parrilla/{id}` | Paginar, buscar y filtrar |
| `GET /api/parrilla/{id}/csv` | Descargar el CSV completo en streaming |
| `GET /api/parrilla/{id}/certificado` | Descargar el certificado entero |
| `GET/POST /api/versiones` | Listar o guardar versiones |
| `GET /api/versiones/{id}` | Recuperar la configuración guardada |
| `POST /api/versiones/{id}/activar` | Elegir la configuración inicial |

La validación comprueba la estructura y los tipos de las reglas antes de optimizar. Las métricas separan el valor esperado comercial del objetivo ponderado y muestran los excesos de cupo originales en número de contactos.
