"""Public display layers: Claro coverage tiles and CRC's published WMS map.

Uses only unauthenticated map images. Does not query the protected WFS or copy
Google Maps credentials. Images are embedded so file:// needs no CORS bypass.
"""

import base64
import concurrent.futures
import io
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache" / "capas-red.json"
CLARO = "https://minisitiosclaro.claro.com.co"
CRC = "https://gis.postdata.gov.co/geoserver/infraestructura_movil/wms"


def download(url):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "BogotaEstratos/1.0"})
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def uri(raw):
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def tile_xy(lng, lat, zoom):
    scale = 2 ** zoom
    return int((lng + 180) / 360 * scale), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * scale)


def tile_corner(x, y, zoom):
    scale = 2 ** zoom
    return [x / scale * 360 - 180, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / scale))))]


def crc_url(bbox, width, height):
    radius = 6378137
    def project(lng, lat):
        return [radius * math.radians(lng), radius * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))]
    mercator = project(bbox[0], bbox[1]) + project(bbox[2], bbox[3])
    return CRC + "?" + urllib.parse.urlencode({
        "service": "WMS", "version": "1.1.1", "request": "GetMap",
        "layers": "infraestructura_movil:sitios", "styles": "", "format": "image/png",
        "transparent": "true", "srs": "EPSG:3857", "bbox": ",".join(map(str, mercator)),
        "width": width, "height": height,
        "CQL_FILTER": "ID_OPERADOR=800153993",
    })


def load_layers(refresh=False):
    if CACHE.exists() and not refresh:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    from PIL import Image

    # Urban study area; includes the official blocks shown by this application.
    bbox = [-74.26, 4.44, -73.97, 4.89]
    zoom = 13
    x0, y0 = tile_xy(bbox[0], bbox[3], zoom)
    x1, y1 = tile_xy(bbox[2], bbox[1], zoom)
    positions = [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]
    corners = [tile_corner(x0, y0, zoom), tile_corner(x1 + 1, y0, zoom), tile_corner(x1 + 1, y1 + 1, zoom), tile_corner(x0, y1 + 1, zoom)]
    coverage = {}
    for technology, directory, legend in [
        ("4g", "cob271026lte", "lte.png"),
        ("5g", "5G4Q2026", "5G.png"),
    ]:
        coverage_cache = ROOT / ".cache" / f"cobertura-{technology}.json"
        if coverage_cache.exists() and not refresh:
            coverage[technology] = json.loads(coverage_cache.read_text(encoding="utf-8"))
            continue
        canvas = Image.new("RGBA", ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))
        def tile(position):
            x, y = position
            url = f"{CLARO}/AdminCobertura/mapImages/{directory}/Z{zoom}/{y}/{x}.png"
            raw = download(url)
            image = Image.open(io.BytesIO(raw)).convert("RGBA")
            if image.size != (256, 256):
                raise ValueError("El servicio de cobertura devolvio una tesela de tamano inesperado.")
            return position, image
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            for (x, y), image in pool.map(tile, positions):
                canvas.paste(image, ((x - x0) * 256, (y - y0) * 256))
        if not canvas.getchannel("A").getbbox():
            raise ValueError(f"La cobertura {technology} esta vacia.")
        out = io.BytesIO()
        canvas.save(out, format="PNG", optimize=True)
        coverage[technology] = {
            "image": uri(out.getvalue()), "coordinates": corners, "zoom": zoom,
            "legend": uri(download(f"{CLARO}/MapasDeCobertura/Content/Images/Cobertura/{legend}")),
            "source": "https://www.claro.com.co/personas/servicios/servicios-moviles/cobertura/",
            "sourceDirectory": f"{CLARO}/AdminCobertura/mapImages/{directory}/",
            "sourceDate": "2026-10-27", "tiles": len(positions),
        }
        coverage_cache.parent.mkdir(parents=True, exist_ok=True)
        coverage_cache.write_text(json.dumps(coverage[technology], separators=(",", ":")), encoding="utf-8")
        print(f"Cobertura {technology.upper()}: {len(positions)} teselas oficiales", flush=True)

    # Use the public map's operator-only filter. The service returns HTTP 500
    # for combined filters, and its bulk WFS requires authentication. Neither
    # restriction is bypassed; this is explicitly labelled a historical map.
    now = datetime.now(timezone.utc)
    antenna_url = crc_url(bbox, 1800, 2800)
    antenna_image = download(antenna_url)
    check = Image.open(io.BytesIO(antenna_image)).convert("RGBA")
    if not check.getchannel("A").getbbox():
        raise ValueError("La capa de sitios moviles CRC esta vacia.")
    result = {
        "downloadedAt": now.isoformat(), "coverage": coverage,
        "antennas": {
            "image": uri(antenna_image), "coordinates": [[bbox[0], bbox[3]], [bbox[2], bbox[3]], [bbox[2], bbox[1]], [bbox[0], bbox[1]]],
            "period": "Histórico reportado", "operator": "Claro / COMCEL", "operatorId": 800153993,
            "source": "https://www.postdata.gov.co/mapa/sitios-de-infraestructura-movil",
            "request": antenna_url,
            "scope": "Recorte cartografico del WMS publico CRC: sitios de Claro reportados en Bogota y alrededores en varios periodos, no inventario certificado de antenas activas ni corte unico actual.",
        },
    }
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("Sitios moviles Claro: recorte historico del mapa publico CRC", flush=True)
    return result
