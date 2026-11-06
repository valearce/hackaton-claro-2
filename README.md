# Orquestador NBA · Hackatón Claro

Herramienta para elegir la siguiente mejor acción por cliente: producto, canal y explicación, respetando elegibilidad, permisos y capacidad. El repositorio reúne el motor de asignación, perfiles de consumo, un mapa de Bogotá y herramientas para demostrar la entrega en Android.

En la evaluación guardada de 100.000 clientes, el motor obtiene **10.940,0024511** de valor esperado, frente a la referencia publicada de **10.241,5**: **+6,82 %**, con **cero violaciones**. Son resultados sobre datos sintéticos y scores suministrados, no ventas observadas. [Detalle de la evaluación](modelo/README.md#resultado-nba).

## Estructura

| Carpeta | Contenido |
| --- | --- |
| [`datos/`](datos/README.md) | CSV original de 100.000 clientes y su huella de integridad |
| [`docs/reto/`](docs/reto/README.md) | Enunciado, diccionario, presentación, kit oficial y transcripción |
| [`REGLAS.md`](REGLAS.md) | Las 45 variables, las 16 reglas, parámetros y contrato de salida |
| [`modelo/`](modelo/README.md) | Motor NBA con flujo OR-Tools, configuración, certificados y perfiles |
| [`mapa/`](mapa/README.md) | Mapa de estratos, agregados de clientes y capas de red de Bogotá |
| [`herramientas/`](herramientas/README.md) | ADB, grabación, espejo de pantalla y notificaciones locales de demostración |
| [`investigacion/`](investigacion/README.md) | Evidencia sobre receptividad y horarios; catálogo de fuentes |
| [`recursos/`](recursos/README.md) | Imágenes compartidas por los módulos |
| [`docs/ideas.md`](docs/ideas.md) | Lluvia de ideas original del equipo |

`.local/` guarda configuración privada y ejecutables locales. `tmp/` guarda trabajo temporal. Los resultados completos del modelo y los cachés del mapa se generan localmente; `modelo/evaluacion/` contiene métricas compactas versionadas. Los notebooks no se versionan.

## Modelo

La consola usa **Next.js** para la interfaz y compilación, y FastAPI para el motor Python. Desde la raíz, `npm ci` y `npm run build` generan el panel. `npm start` inicia la consola local en el puerto 3000 con su API en el 8001. La [guía de la consola](backend/README.md) incluye instalación, persistencia y despliegue conjunto en Vercel.

Desde la raíz, con Python 3.11:

```powershell
python -m modelo.ejecutar --tarea nba --fecha 2026-11-05
```

Para entrenar los perfiles de consumo de forma independiente:

```powershell
python -m modelo.ejecutar --tarea perfiles --fecha 2026-11-05
python -m modelo.exportar_evaluacion
```

El motor usa únicamente OR-Tools en el Python WSL del kernel registrado; consulta [modelo/docs/entorno.md](modelo/docs/entorno.md). La configuración editable está en [`modelo/config/`](modelo/config/). El CSV predeterminado es `datos/clientes.csv`; puede sustituirse con `--datos RUTA`. Los comandos no requieren cambiar al directorio `modelo`.

## Mapa y demostración

Abre [`mapa/mapa-estratos-bogota.html`](mapa/mapa-estratos-bogota.html) en un navegador. El HTML incorpora las geometrías y los agregados; la cartografía base requiere Internet. Para regenerarlo, consulta el [README del mapa](mapa/README.md).

Con Node.js 22+, Android Platform Tools y un teléfono autorizado:

```powershell
node herramientas/android/android.mjs doctor
node herramientas/android/android.mjs sms-demo --sender "Claro" --text "DEMO: una oferta para ti" --image recursos/imagenes/claro-logo.jpg
```

El aviso es una demostración local con aspecto de SMS. No envía un SMS por la red. Los pasos de conexión, espejo y grabación están en [herramientas/android](herramientas/android/README.md).

## Desarrollo

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para ejecutar las comprobaciones y mantener la estructura. El material oficial se conserva con su contenido original; los nombres de archivo se simplificaron para usar rutas estables.
