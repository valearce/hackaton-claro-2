# Mapa de estratos de Bogotá

Abre `mapa-estratos-bogota.html` en un navegador moderno. Es un único HTML: incluye las geometrías oficiales y los agregados del CSV. La cartografía base y MapLibre requieren Internet; la lista de manzanas y las estadísticas no dependen del servicio geográfico durante su uso.

- MapLibre y estilo de referencia de GrouPay, sobre OpenFreeMap/OpenMapTiles. Se usa la distribución 5.6.0 con worker clásico para que el HTML funcione al abrirlo con doble clic; los workers de módulo de la versión 6 fallan en Chrome con origen `file://`.
- Filtros por estrato, búsqueda local de códigos de manzana, selección y detalle.
- Capas activables: estratos, sitios móviles de Claro reportados en el WMS público de la CRC y cobertura móvil Claro 4G/5G con leyenda y opacidad.
- Los clientes proceden de `../clientes 1.csv`, exclusivamente de la región Bogotá. Se muestran agregados por estrato. No se inventan coordenadas ni se distribuyen clientes entre manzanas.
- La lista permite consultar las mismas manzanas cuando WebGL o la cartografía no están disponibles.
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
python 'producto añadido/generar_mapa.py'
python 'producto añadido/generar_mapa.py' --actualizar
python 'producto añadido/generar_mapa.py' --actualizar-red
```

`mapa.template.html` contiene la interfaz editable. `estilo-base.json` conserva el estilo cartográfico de la referencia y su atribución. `.cache/` guarda la última descarga y está excluida de Git.

`capas_red.py` prepara los recortes georreferenciados a partir de imágenes públicas. Las teselas de cobertura no permiten CORS desde un archivo local; la copia incluida evita depender de esas peticiones al visualizar el HTML, sin desactivar la seguridad del navegador. Los recortes son estáticos y no sustituyen los visores oficiales. Las atribuciones se mantienen visibles.

El HTML admite PMTiles editando `SETTINGS.pmtilesUrl` en la plantilla y regenerándolo. Esa URL debe ser pública, compatible con el esquema Protomaps v4 y soportar Range/CORS. Con un valor vacío utiliza la misma fuente OpenFreeMap que la referencia actual de GrouPay.

## Comprobaciones realizadas

Se verificaron las 44.260 geometrías, sus 415.923 coordenadas, los 100.000 registros del CSV y los agregados de los 28.190 clientes de Bogotá. El logo está incluido sin modificar el archivo proporcionado.

Se comprobó en Chrome abriendo el HTML con `file://`: carga del mapa, filtros, búsqueda, selección, ventanas de detalle, controles de las tres capas de red, leyendas, opacidad y preservación de las cifras del CSV. También se verificaron el diseño a 390 px de ancho y la lista alternativa al simular indisponibilidad de WebGL.

