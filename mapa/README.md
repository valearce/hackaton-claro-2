# Mapa de estratos de Bogotá

La consola Next.js sirve el mapa en `/mapa`. También puedes abrir `mapa-estratos-bogota.html` dentro del repositorio: las geometrías oficiales, los agregados del CSV y las imágenes de cobertura están incluidas en el HTML. MapLibre y sus estilos se sirven desde `web/public/mapa-assets/`, con su licencia e integridad del paquete npm oficial en `manifest.json`. Conserva esa carpeta al copiar el mapa.

El fondo geométrico local muestra las manzanas y las capas incluidas sin esperar a servicios cartográficos externos. «Calles y etiquetas en línea» añade el fondo OpenFreeMap de forma opcional. Si ese proveedor falla, el mapa local, sus filtros y las coberturas permanecen disponibles. Las fuentes de texto adicionales usan un espejo del repositorio original con revisión fijada; no se desactiva la verificación TLS.

- MapLibre y estilo de referencia de GrouPay, sobre OpenFreeMap/OpenMapTiles. Se usa la distribución 5.6.0 con worker clásico para que el HTML funcione al abrirlo con doble clic; los workers de módulo de la versión 6 fallan en Chrome con origen `file://`.
- Filtros por estrato, búsqueda local de códigos de manzana, selección y detalle.
- Capas activables: estratos, sitios móviles de Claro reportados en el WMS público de la CRC y cobertura móvil Claro 4G/5G con leyenda y opacidad.
- Los clientes proceden de [`../datos/clientes.csv`](../datos/clientes.csv), exclusivamente de la región Bogotá. Se muestran agregados por estrato. No se inventan coordenadas ni se distribuyen clientes entre manzanas.
- El visor mantiene una sola vista **Mapa**, con filtros, búsqueda por código, capas y agregados del CSV. Seleccionar una manzana abre su información en una ventana sobre el mapa.
- Los perfiles y las propuestas de Vale están en la pestaña **Clusters** de la consola. Su desglose usa la parrilla del último escenario enviado, sin ejecutar otro motor; las propuestas publicitarias siguen siendo una referencia precalculada.

La copia histórica del análisis territorial se conserva en [analisis-clusters.json](analisis-clusters.json), extraída de `origin/main-clusters`, revisión `9e652e3b1f0a993733d3f5814e74d9ae60bad03f`. Su procedencia y la huella del CSV figuran en `origen`; el visor ya no incluye los bloques analíticos.
- La ubicación se solicita únicamente al pulsar «Mi ubicación» y se usa para centrar el mapa. No se registra presencia ni se envía al visor de Claro.
- El visor completo de Claro se abre con un enlace externo porque restringe la incrustación. Sus imágenes de cobertura publicadas se recortan para Bogotá y se incluyen en el HTML con su leyenda y fecha de corte (27 de octubre de 2026). La cobertura móvil no certifica disponibilidad de Hogar.
- La capa de antenas es un recorte cartográfico histórico del WMS público CRC, filtrado por Claro/COMCEL (800153993), en Bogotá y alrededores. Incluye varios periodos: no certifica sitios activos hoy, no es un conteo de antenas únicas y no tiene consulta individual por antena. El servicio de descarga WFS exige autenticación y no se utiliza. No se eluden sus restricciones ni las de incrustación.

## Fuentes

- Manzanas: Secretaría Distrital de Planeación, `https://sinu.sdp.gov.co/serverp/rest/services/ESTRATO/Estratificacion/FeatureServer/2`.
- Ficha pública de referencia: `https://www.ideca.gov.co/recursos/mapas/manzana-estratificacion-bogota-dc`.
- Clientes sintéticos: CSV del reto. La fecha de descarga de geometrías y la huella SHA-256 del CSV están incluidas en el HTML.
- Cartografía base: OpenFreeMap, OpenMapTiles y OpenStreetMap. Se conservan sus atribuciones.
- Cobertura: `https://www.claro.com.co/personas/servicios/servicios-moviles/cobertura/`.
- Sitios móviles: `https://www.postdata.gov.co/mapa/sitios-de-infraestructura-movil`, WMS `https://gis.postdata.gov.co/geoserver/infraestructura_movil/wms`.

Las geometrías se convierten a EPSG:4326 y se simplifican aproximadamente a escala submétrica para visualización. La fecha de descarga no constituye una certificación de vigencia del estrato de un inmueble.

## Regeneración

Python 3. La primera descarga de capas de red requiere Pillow; las regeneraciones desde caché utilizan la biblioteca estándar:

```powershell
python -m pip install Pillow
python mapa/generar_mapa.py
python mapa/generar_mapa.py --actualizar
python mapa/generar_mapa.py --actualizar-red
python mapa/generar_mapa.py --reutilizar-html mapa/mapa-estratos-bogota.html
```

`--reutilizar-html` reconstruye el HTML con la plantilla y el CSV actuales reutilizando las manzanas y las capas de red incluidas, sin descargar nada. El generador lee `modelo/evaluacion/experimentos.json` si se aporta; en su ausencia conserva el análisis de referencia de `analisis-clusters.json`.

`mapa.template.html` contiene la interfaz editable. `estilo-base.json` conserva el estilo cartográfico de la referencia y su atribución. El logo compartido está en [`../recursos/imagenes/claro-logo.jpg`](../recursos/imagenes/claro-logo.jpg). `.cache/` guarda la última descarga y está excluida de Git.

`capas_red.py` prepara los recortes georreferenciados a partir de imágenes públicas. Las teselas de cobertura no permiten CORS desde un archivo local; la copia incluida evita depender de esas peticiones al visualizar el HTML, sin desactivar la seguridad del navegador. Los recortes son estáticos y no sustituyen los visores oficiales. Las atribuciones se mantienen visibles.

El HTML admite PMTiles editando `SETTINGS.pmtilesUrl` en la plantilla y regenerándolo. Esa URL debe ser pública, compatible con el esquema Protomaps v4 y soportar Range/CORS. Con un valor vacío utiliza la misma fuente OpenFreeMap que la referencia actual de GrouPay.

## Comprobaciones realizadas

Se verificaron las 44.260 geometrías, sus 415.923 coordenadas, los 100.000 registros del CSV y los agregados de los 28.190 clientes de Bogotá. El logo está incluido sin modificar el archivo proporcionado.

Se comprobó en Chrome la carga del mapa, sus filtros, búsqueda, ventanas de detalle, controles de las tres capas de red, leyendas, opacidad y preservación de las cifras del CSV. El visor requiere WebGL y muestra una opción de reintento si falla la cartografía.

