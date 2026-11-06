'use client';

import Script from 'next/script';
import { useEffect, useRef, useState, type ReactNode } from 'react';

type Point = { lat: number; lon: number };
type Zone = Point & { id: string; nombre: string; radio_m: number; activo: boolean };
type Feature = { type: 'Feature'; properties: Record<string, string | number | boolean>; geometry: { type: string; coordinates: unknown } };
type GeoData = { type: 'FeatureCollection'; features: Feature[] };
type GeoSource = { setData(data: GeoData): void };
type Marker = { setLngLat(point: number[]): Marker; addTo(map: MapInstance): Marker; remove(): void; getElement(): HTMLElement };
type MapInstance = {
  on(name: string, handler: (event: { lngLat?: { lat: number; lng: number } }) => void): void;
  addControl(control: unknown, position?: string): void;
  addSource(id: string, source: Record<string, unknown>): void;
  addLayer(layer: Record<string, unknown>): void;
  getSource(id: string): GeoSource | undefined;
  flyTo(options: Record<string, unknown>): void;
  easeTo(options: Record<string, unknown>): void;
  fitBounds(bounds: number[][], options: Record<string, unknown>): void;
  remove(): void;
  resize(): void;
};
type MapLibrary = {
  Map: new (options: Record<string, unknown>) => MapInstance;
  Marker: new (options: Record<string, unknown>) => Marker;
  NavigationControl: new (options: Record<string, unknown>) => unknown;
  ScaleControl: new (options: Record<string, unknown>) => unknown;
  AttributionControl: new (options: Record<string, unknown>) => unknown;
};
declare global { interface Window { maplibregl?: MapLibrary } }

const empty: GeoData = { type: 'FeatureCollection', features: [] };
const motionDuration = (duration: number) => window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : duration;
function circle(zone: Zone): number[][] {
  const lat = zone.lat * Math.PI / 180, lon = zone.lon * Math.PI / 180, angular = zone.radio_m / 6371000;
  return Array.from({ length: 73 }, (_, i) => {
    const bearing = i / 72 * 2 * Math.PI;
    const y = Math.asin(Math.sin(lat) * Math.cos(angular) + Math.cos(lat) * Math.sin(angular) * Math.cos(bearing));
    const x = lon + Math.atan2(Math.sin(bearing) * Math.sin(angular) * Math.cos(lat), Math.cos(angular) - Math.sin(lat) * Math.sin(y));
    return [x * 180 / Math.PI, y * 180 / Math.PI];
  });
}

export default function AntennaSimulationMap({ antennas, billboards, position, route, progress, sector, playing, onMove, onSelect, children }: {
  antennas: Zone[]; billboards: Zone[]; position: Point; route: Point[]; progress: number;
  sector: { antennaId: string; billboardId: string; zoom: 'sector' | 'bogota' }; playing: boolean;
  onMove: (point: Point) => void; onSelect: (kind: 'antena' | 'valla', id: string) => void; children: ReactNode;
}) {
  const container = useRef<HTMLDivElement>(null), map = useRef<MapInstance | null>(null);
  const markers = useRef<Marker[]>([]), client = useRef<Marker | null>(null);
  const latest = useRef({ onMove, onSelect, position });
  const lastCamera = useRef(0), previousSector = useRef('');
  const [scriptReady, setScriptReady] = useState(false), [ready, setReady] = useState(false), [failed, setFailed] = useState(false), [follow, setFollow] = useState(false);
  useEffect(() => { latest.current = { onMove, onSelect, position }; }, [onMove, onSelect, position]);

  useEffect(() => {
    if (!scriptReady || !container.current || !window.maplibregl) return;
    const library = window.maplibregl;
    let instance: MapInstance;
    try {
      instance = new library.Map({ container: container.current, center: [-74.064, 4.651], zoom: 15.4,
        minZoom: 10, maxZoom: 19, pitch: 0, dragRotate: false, keyboard: false, attributionControl: false,
        style: { version: 8, sources: {}, layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#F2F3EF' } }] } });
    } catch { setFailed(true); return; }
    map.current = instance;
    instance.addControl(new library.NavigationControl({ showCompass: false }), 'top-right');
    instance.addControl(new library.ScaleControl({ unit: 'metric', maxWidth: 100 }), 'bottom-left');
    instance.addControl(new library.AttributionControl({ compact: true, customAttribution: 'Manzanas: SDP Bogotá · Antenas y vallas simuladas' }));
    instance.on('click', event => { if (event.lngLat) latest.current.onMove({ lat: event.lngLat.lat, lon: event.lngLat.lng }); });
    instance.on('load', () => {
      instance.addSource('city', { type: 'geojson', data: '/mapa/geometria?v=2' });
      instance.addLayer({ id: 'blocks', type: 'fill', source: 'city', paint: { 'fill-color': '#DBDFDC', 'fill-opacity': .7 } });
      instance.addLayer({ id: 'blocks-outline', type: 'line', source: 'city', paint: { 'line-color': '#FFFFFF', 'line-width': .6 } });
      for (const id of ['coverage', 'route', 'travelled']) instance.addSource(id, { type: 'geojson', data: empty });
      instance.addLayer({ id: 'coverage-fill', type: 'fill', source: 'coverage', paint: {
        'fill-color': ['match', ['get', 'kind'], 'antena', '#1D1D1F', '#E12F20'],
        'fill-opacity': ['case', ['get', 'active'], .1, .025],
      } });
      instance.addLayer({ id: 'coverage-line', type: 'line', source: 'coverage', paint: {
        'line-color': ['match', ['get', 'kind'], 'antena', '#1D1D1F', '#E12F20'],
        'line-opacity': ['case', ['get', 'active'], .7, .2], 'line-width': ['case', ['get', 'selected'], 2.5, 1.2],
      } });
      instance.addLayer({ id: 'route-line', type: 'line', source: 'route', paint: { 'line-color': '#7A8480', 'line-width': 3, 'line-dasharray': [2, 2] } });
      instance.addLayer({ id: 'travelled-line', type: 'line', source: 'travelled', paint: { 'line-color': '#1E7F45', 'line-width': 4 } });
      const marker = document.createElement('div'); marker.className = 'sim-client-marker'; marker.setAttribute('aria-label', 'Cliente simulado');
      marker.innerHTML = '<span class="sim-client-halo"></span><span class="sim-client-dot"></span>';
      client.current = new library.Marker({ element: marker }).setLngLat([latest.current.position.lon, latest.current.position.lat]).addTo(instance);
      setReady(true);
    });
    const observer = new ResizeObserver(() => instance.resize()); observer.observe(container.current);
    return () => { observer.disconnect(); markers.current.forEach(marker => marker.remove()); markers.current = []; client.current = null; instance.remove(); map.current = null; setReady(false); };
  }, [scriptReady]);

  useEffect(() => {
    const instance = map.current, library = window.maplibregl;
    if (!ready || !instance || !library) return;
    const zones = [...antennas.map(zone => ({ ...zone, kind: 'antena' as const })), ...billboards.map(zone => ({ ...zone, kind: 'valla' as const }))];
    instance.getSource('coverage')?.setData({ type: 'FeatureCollection', features: zones.map(zone => ({
      type: 'Feature', geometry: { type: 'Polygon', coordinates: [circle(zone)] },
      properties: { id: zone.id, kind: zone.kind, active: zone.activo, selected: zone.id === sector.antennaId || zone.id === sector.billboardId },
    })) });
    markers.current.forEach(marker => marker.remove());
    markers.current = zones.map((zone, index) => {
      const button = document.createElement('button'); button.type = 'button'; button.className = `sim-zone-marker ${zone.kind}`;
      button.setAttribute('aria-label', `Seleccionar ${zone.nombre}`); button.title = `${zone.nombre} · ${zone.radio_m} m`;
      button.dataset.selected = String(zone.id === sector.antennaId || zone.id === sector.billboardId);
      button.dataset.muted = String(!zone.activo);
      const art = document.createElement('span'); art.className = 'sim-zone-art'; art.textContent = zone.kind === 'antena' ? 'A' : 'V'; art.style.animationDelay = `${Math.min(index, 8) * 55}ms`;
      button.append(art);
      button.addEventListener('click', event => { event.stopPropagation(); latest.current.onSelect(zone.kind, zone.id); });
      return new library.Marker({ element: button, offset: zone.kind === 'antena' ? [0, -22] : [0, 22] }).setLngLat([zone.lon, zone.lat]).addTo(instance);
    });
    const key = `${sector.antennaId}:${sector.billboardId}:${sector.zoom}`;
    if (key !== previousSector.current) {
      previousSector.current = key;
      const shown = sector.zoom === 'sector' ? zones.filter(zone => zone.id === sector.antennaId || zone.id === sector.billboardId) : zones;
      const coordinates = shown.flatMap(circle);
      if (sector.zoom === 'sector') coordinates.push(...route.map(point => [point.lon, point.lat]));
      if (coordinates.length) instance.fitBounds([[Math.min(...coordinates.map(p => p[0])), Math.min(...coordinates.map(p => p[1]))], [Math.max(...coordinates.map(p => p[0])), Math.max(...coordinates.map(p => p[1]))]],
        { padding: { top: 70, bottom: 65, left: 55, right: 55 }, maxZoom: 16, duration: motionDuration(750) });
    }
  }, [ready, antennas, billboards, sector.antennaId, sector.billboardId, sector.zoom, route]);

  useEffect(() => {
    const instance = map.current;
    if (!ready || !instance) return;
    client.current?.setLngLat([position.lon, position.lat]);
    client.current?.getElement().setAttribute('data-playing', String(playing));
    const routeLine = route.map(point => [point.lon, point.lat]);
    const count = Math.min(route.length - 1, Math.floor(progress * (route.length - 1)));
    const travelled = [...routeLine.slice(0, count + 1), [position.lon, position.lat]];
    const line = (coordinates: number[][]): GeoData => ({ type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates } }] });
    instance.getSource('route')?.setData(line(routeLine));
    instance.getSource('travelled')?.setData(line(travelled));
    if (follow && (!playing || performance.now() - lastCamera.current > 600)) {
      lastCamera.current = performance.now();
      instance.easeTo({ center: [position.lon, position.lat], duration: motionDuration(playing ? 650 : 750) });
    }
  }, [ready, position, route, progress, playing, follow]);

  return <div className="sim-map-shell">
    <link rel="stylesheet" href="/mapa-assets/maplibre-gl.css" />
    <Script src="/mapa-assets/maplibre-gl.js" strategy="afterInteractive" onReady={() => setScriptReady(true)} onError={() => setFailed(true)} />
    {failed ? <>{children}<p className="cl-q">Vista esquemática disponible. Puedes seguir usando el recorrido y los controles.</p></> : <div ref={container} className="sim-map-canvas" role="group" aria-label="Mapa interactivo de la simulación de antenas y vallas" tabIndex={0} onKeyDown={event => {
      if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      event.preventDefault(); onMove({ lat: position.lat + (event.key === 'ArrowUp' ? .0003 : event.key === 'ArrowDown' ? -.0003 : 0), lon: position.lon + (event.key === 'ArrowRight' ? .0003 : event.key === 'ArrowLeft' ? -.0003 : 0) });
    }} />}
    {!ready && !failed && <p className="sim-map-loading" role="status">Preparando el mapa…</p>}
    {!failed && <label className="sim-map-follow"><input type="checkbox" checked={follow} onChange={event => setFollow(event.target.checked)} />Seguir al cliente</label>}
  </div>;
}
