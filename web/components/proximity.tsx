'use client';

import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent, type MouseEvent } from 'react';
import { api, channelName, nf } from '@/lib/api';
import type { Config } from '@/lib/types';
import AntennaSimulationMap from './antenna-simulation-map';

type Point = { lat: number; lon: number };
type Zone = Point & { id: string; nombre: string; radio_m: number; activo: boolean };
type ProximityCampaign = { id: string; nombre: string; canales_permitidos: string[]; activa: boolean; vigencia_inicio: string; vigencia_fin: string };
type ProximityConfig = {
  demo: boolean; antenas: Zone[]; vallas: Zone[]; campanas: ProximityCampaign[];
  cliente_demo: Point & { id: string; consentimiento: boolean };
  politica: { cooldown_segundos: number; canales: string[] }; momento_demo: string; aviso: string;
};
type ZoneDistance = Zone & { tipo: 'antena' | 'valla'; distancia_m: number; dentro_radio: boolean };
type ProximityResult = {
  demo: boolean; elegible: boolean; decision: string; motivos: string[]; zonas_cercanas: ZoneDistance[]; distancias: ZoneDistance[];
  accion?: { campana_id: string; campana_nombre: string; canal: string; texto: string } | null;
  cooldown_restante_segundos: number; advertencia: string;
};
type Event = { id: string; momento: string; campana_id: string; canal: string; resultado: ProximityResult };

const DEFAULT_POINT: Point = { lat: 4.653, lon: -74.062 };
const meters = (a: Point, b: Point) => {
  const radians = Math.PI / 180;
  const dlat = (b.lat - a.lat) * radians; const dlon = (b.lon - a.lon) * radians;
  const h = Math.sin(dlat / 2) ** 2 + Math.cos(a.lat * radians) * Math.cos(b.lat * radians) * Math.sin(dlon / 2) ** 2;
  return 6371000 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
};

export default function Proximity({ config = null }: { config?: Config | null }) {
  const [settings, setSettings] = useState<ProximityConfig | null>(null);
  const [antennas, setAntennas] = useState<Zone[]>([]); const [billboards, setBillboards] = useState<Zone[]>([]);
  const [position, setPosition] = useState<Point>(DEFAULT_POINT); const [consent, setConsent] = useState(false);
  const [campaignId, setCampaignId] = useState(''); const [channel, setChannel] = useState('sms');
  const [cooldown, setCooldown] = useState(300); const [moment, setMoment] = useState('2026-11-05T15:00');
  const [antennaId, setAntennaId] = useState(''); const [billboardId, setBillboardId] = useState(''); const [routeStep, setRouteStep] = useState(-1); const [mapZoom, setMapZoom] = useState<'sector' | 'bogota'>('sector');
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const [events, setEvents] = useState<Event[]>([]); const [lastResult, setLastResult] = useState<ProximityResult | null>(null); const [lastSignature, setLastSignature] = useState('');
  const mounted = useRef(true); const busyRef = useRef(false);
  const lastActions = useRef<Record<string, string>>({});
  const [playing, setPlaying] = useState(false), [progress, setProgress] = useState(0), [speed, setSpeed] = useState(4);
  const progressRef = useRef(0);
  const demoView = useRef<HTMLDivElement>(null), audio = useRef<AudioContext | null>(null);
  const soundEnabled = useRef(false), previousAntennas = useRef(new Set<string>());
  const [sound, setSound] = useState(false), [fullscreen, setFullscreen] = useState(false), [mediaError, setMediaError] = useState('');

  useEffect(() => {
    const changed = () => setFullscreen(!!document.fullscreenElement && demoView.current?.contains(document.fullscreenElement) === true);
    document.addEventListener('fullscreenchange', changed);
    return () => {
      document.removeEventListener('fullscreenchange', changed);
      soundEnabled.current = false;
      const context = audio.current; audio.current = null;
      if (context && context.state !== 'closed') void context.close().catch(() => {});
    };
  }, []);

  async function enableSound() {
    try {
      const context = audio.current ?? new AudioContext(); audio.current = context;
      await context.resume();
      if (mounted.current) { soundEnabled.current = true; setSound(true); setMediaError(''); }
    } catch { if (mounted.current) setMediaError('No se pudo activar el sonido. Comprueba el audio del navegador.'); }
  }

  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement && demoView.current?.contains(document.fullscreenElement)) await document.exitFullscreen();
      else {
        void enableSound();
        await demoView.current?.querySelector<HTMLElement>('.sim-map-shell')?.requestFullscreen();
      }
      setMediaError('');
    } catch { setMediaError('El navegador no permitió abrir el mapa en pantalla completa.'); }
  }

  const antennaRangeKey = antennas.filter(zone => zone.activo && meters(position, zone) <= zone.radio_m).map(zone => zone.id).sort().join('|');
  useEffect(() => {
    const current = new Set(antennaRangeKey ? antennaRangeKey.split('|') : []);
    const entered = [...current].some(id => !previousAntennas.current.has(id));
    previousAntennas.current = current;
    const context = audio.current;
    if (!entered || !soundEnabled.current || !context || context.state !== 'running') return;
    for (const [index, frequency] of [880, 1174.66].entries()) {
      const oscillator = context.createOscillator(), gain = context.createGain();
      const start = context.currentTime + index * .19;
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(0, start);
      gain.gain.linearRampToValueAtTime(.18, start + .015);
      gain.gain.exponentialRampToValueAtTime(.001, start + .3);
      oscillator.connect(gain); gain.connect(context.destination);
      oscillator.onended = () => { oscillator.disconnect(); gain.disconnect(); };
      oscillator.start(start); oscillator.stop(start + .32);
    }
  }, [antennaRangeKey]);

  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    void api<ProximityConfig>('/api/cercania/config', undefined, controller.signal).then(s => {
      if (controller.signal.aborted) return;
      setSettings(s); setAntennas(s.antenas); setBillboards(s.vallas);
      setPosition({ lat: s.cliente_demo.lat, lon: s.cliente_demo.lon });
      setConsent(s.cliente_demo.consentimiento); setCooldown(s.politica.cooldown_segundos);
      setMoment(s.momento_demo.slice(0, 16));
      setAntennaId(s.antenas[0]?.id || ''); setBillboardId(s.vallas[0]?.id || '');
    }).catch(e => { if (!controller.signal.aborted) setError((e as Error).message); });
    return () => { mounted.current = false; controller.abort(); };
  }, []);

  const campaigns = useMemo<ProximityCampaign[]>(() => config ? config.campanas.map(c => ({
    id: c.id, nombre: c.nombre, canales_permitidos: c.canales_permitidos, activa: c.activa, vigencia_inicio: c.vigencia_inicio, vigencia_fin: c.vigencia_fin,
  })) : settings?.campanas || [], [config, settings]);
  useEffect(() => { if (campaigns.length && !campaigns.some(c => c.id === campaignId)) setCampaignId(campaigns.find(c => c.activa)?.id || campaigns[0].id); }, [campaigns, campaignId]);
  const campaign = campaigns.find(c => c.id === campaignId);
  const allZones = [...antennas.map(z => ({ ...z, tipo: 'antena' as const })), ...billboards.map(z => ({ ...z, tipo: 'valla' as const }))];
  const simulatedTime = new Date(new Date(`${moment.slice(0, 16)}:00-05:00`).getTime() + Math.round(progress * 720) * 1000).toISOString();
  const signature = JSON.stringify({ antennas, billboards, position, consent, campaign, channel, cooldown, simulatedTime });
  const stale = !!lastResult && lastSignature !== signature;
  const clientId = settings?.cliente_demo.id || 'DEMO-001';
  const channels = settings?.politica.canales || ['sms', 'whatsapp', 'push'];

  async function evaluate(event?: FormEvent) {
    event?.preventDefault(); if (!campaign || busyRef.current) return;
    busyRef.current = true; setBusy(true); setError(''); const submittedSignature = signature;
    const previous = lastActions.current['mapa_demo'];
    const timestamp = simulatedTime;
    try {
      const result = await api<ProximityResult>('/api/cercania/evaluar', {
        modo: 'mapa_demo', cliente: { id: clientId, consentimiento: consent, ...position },
        antenas: antennas, vallas: billboards, campana: campaign, canal: channel, cooldown_segundos: cooldown,
        momento: timestamp, ...(previous ? { ultimo_evento: previous } : {}),
      });
      if (!mounted.current) return;
      if (result.elegible) lastActions.current['mapa_demo'] = timestamp;
      setLastResult(result); setLastSignature(submittedSignature);
      setEvents(list => [{ id: crypto.randomUUID(), momento: timestamp, campana_id: campaign.id, canal: channel, resultado: result }, ...list].slice(0, 20));
    } catch (e) { if (mounted.current) setError((e as Error).message); }
    finally { busyRef.current = false; if (mounted.current) setBusy(false); }
  }

  function updateZone(kind: 'antena' | 'valla', id: string, patch: Partial<Zone>) {
    setPlaying(false);
    const update = (zones: Zone[]) => zones.map(z => z.id === id ? { ...z, ...patch } : z);
    if (kind === 'antena') setAntennas(update); else setBillboards(update);
  }

  const map = useMemo(() => {
    const all = [...antennas, ...billboards];
    const zones = mapZoom === 'sector' ? all.filter(z => z.id === antennaId || z.id === billboardId) : all;
    const center = mapZoom === 'sector' && zones.length ? zones[0] : zones.length ? { lat: zones.reduce((s, z) => s + z.lat, 0) / zones.length, lon: zones.reduce((s, z) => s + z.lon, 0) / zones.length } : DEFAULT_POINT;
    const longitudeMeters = 111320 * Math.cos(center.lat * Math.PI / 180); const latitudeMeters = 111320;
    const bounds = zones.length ? zones : [DEFAULT_POINT];
    const xs = bounds.flatMap(z => [(z.lon - center.lon) * longitudeMeters - ('radio_m' in z ? Number(z.radio_m) : 0), (z.lon - center.lon) * longitudeMeters + ('radio_m' in z ? Number(z.radio_m) : 0)]);
    const ys = bounds.flatMap(z => [(z.lat - center.lat) * latitudeMeters - ('radio_m' in z ? Number(z.radio_m) : 0), (z.lat - center.lat) * latitudeMeters + ('radio_m' in z ? Number(z.radio_m) : 0)]);
    const span = Math.max(1800, Math.max(...xs) - Math.min(...xs), (Math.max(...ys) - Math.min(...ys)) * 1.5) * 1.25;
    const scale = 660 / span;
    return { scale, project: (point: Point) => ({ x: 360 + (point.lon - center.lon) * longitudeMeters * scale, y: 235 - (point.lat - center.lat) * latitudeMeters * scale }),
      invert: (x: number, y: number) => ({ lat: center.lat + (235 - y) / scale / latitudeMeters, lon: center.lon + (x - 360) / scale / longitudeMeters }) };
  }, [antennas, billboards, antennaId, billboardId, mapZoom]);
  const route = useMemo(() => {
    const antenna = antennas.find(z => z.id === antennaId) || antennas[0] || { ...DEFAULT_POINT, radio_m: 600 };
    const billboard = billboards.find(z => z.id === billboardId) || billboards[0] || { ...DEFAULT_POINT, lat: DEFAULT_POINT.lat + .002, radio_m: 180 };
    const offset = (antenna.radio_m + Math.max(billboard.radio_m, 200) + 180) / 111320;
    return [
      { nombre: 'Fuera del sector', lat: antenna.lat - offset, lon: antenna.lon - offset },
      { nombre: 'Cobertura de antena', lat: antenna.lat + .001, lon: antenna.lon },
      { nombre: 'Junto a la valla', lat: billboard.lat, lon: billboard.lon },
      { nombre: 'Salida del sector', lat: antenna.lat + offset, lon: antenna.lon + offset },
    ];
  }, [antennas, billboards, antennaId, billboardId]);
  const routePosition = (value: number) => {
    const segment = Math.min(route.length - 2, Math.floor(value * (route.length - 1)));
    const fraction = Math.min(1, value * (route.length - 1) - segment);
    return { lat: route[segment].lat + (route[segment + 1].lat - route[segment].lat) * fraction,
      lon: route[segment].lon + (route[segment + 1].lon - route[segment].lon) * fraction };
  };
  useEffect(() => {
    if (!playing) return;
    const start = performance.now(), initial = progressRef.current;
    let frame = 0, last = 0;
    const tick = (now: number) => {
      const value = Math.max(0, Math.min(1, initial + (now - start) * speed / 8000));
      if (now - last >= 32 || value === 1) {
        last = now; progressRef.current = value; setProgress(value);
        const segment = Math.min(route.length - 2, Math.floor(value * (route.length - 1)));
        const fraction = Math.min(1, value * (route.length - 1) - segment);
        setPosition({ lat: route[segment].lat + (route[segment + 1].lat - route[segment].lat) * fraction,
          lon: route[segment].lon + (route[segment + 1].lon - route[segment].lon) * fraction });
        setRouteStep(Math.min(route.length - 1, Math.floor(value * (route.length - 1))));
      }
      if (value < 1) frame = requestAnimationFrame(tick); else setPlaying(false);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, speed, route]);
  function seek(value: number) {
    value = Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
    setPlaying(false); progressRef.current = value; setProgress(value);
    setPosition(routePosition(value)); setRouteStep(Math.min(route.length - 1, Math.floor(value * (route.length - 1))));
  }
  function resetSimulation() {
    seek(0); lastActions.current = {}; setEvents([]); setLastResult(null); setError('');
  }
  function selectZone(kind: 'antena' | 'valla', id: string) {
    setPlaying(false); if (kind === 'antena') setAntennaId(id); else setBillboardId(id);
  }
  const nearby = allZones.filter(zone => zone.activo && meters(position, zone) <= zone.radio_m);
  const inAntenna = nearby.some(zone => zone.tipo === 'antena'), inBillboard = nearby.some(zone => zone.tipo === 'valla');
  const stage = !inAntenna ? 'Fuera de cobertura' : !inBillboard ? 'Dentro de cobertura' : 'Cerca de la valla';
  function mapClick(event: MouseEvent<SVGSVGElement>) {
    setPlaying(false);
    const point = event.currentTarget.createSVGPoint(); point.x = event.clientX; point.y = event.clientY;
    const matrix = event.currentTarget.getScreenCTM(); if (!matrix) return;
    const local = point.matrixTransform(matrix.inverse()); setRouteStep(-1); setPosition(map.invert(local.x, local.y));
  }
  function mapKey(event: KeyboardEvent<SVGSVGElement>) {
    if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault(); setPlaying(false); setRouteStep(-1); setPosition(point => ({ lat: point.lat + (event.key === 'ArrowUp' ? .0003 : event.key === 'ArrowDown' ? -.0003 : 0), lon: point.lon + (event.key === 'ArrowRight' ? .0003 : event.key === 'ArrowLeft' ? -.0003 : 0) }));
  }
  function moveRoute(step: number) { seek(step / (route.length - 1)); }
  const marker = map.project(position);
  const eligibleEvents = events.filter(e => e.resultado.elegible).length;

  return <div className="cl-proximity">
    <section className="cl-card">
      <span className="cl-eyebrow">Mercadeo por cercanía</span>
      <h2>Simulación de antenas y vallas</h2>
      <p className="cl-q">Mueve un cliente de prueba por el sector, ajusta los radios de las antenas y las vallas y evalúa cuándo una campaña puede generar una oportunidad de contacto.</p>
      <p className="cl-proximity-demo">Simulación · antenas, vallas y cliente de prueba sobre el mapa de Bogotá</p>
    </section>

    <div className="cl-proximity-layout">
      <section className="cl-card">
        <span className="cl-eyebrow">Paso 1 · Recorrido</span><h2>Antenas y vallas del escenario</h2>
        <p className="cl-q" id="proximity-map-help">Haz clic en el mapa o usa las flechas del teclado para mover el cliente. El recorrido solo cambia su posición; pulsa Evaluar cercanía para consultar la decisión.</p>
        <div className="cl-steps" role="group" aria-label="Escala del esquema"><button className="cl-step" type="button" aria-pressed={mapZoom === 'sector'} onClick={() => setMapZoom('sector')}>Acercar al sector</button><button className="cl-step" type="button" aria-pressed={mapZoom === 'bogota'} onClick={() => setMapZoom('bogota')}>Ver todos los sectores</button></div>
        <div className="sim-demo-view" ref={demoView}>
        <AntennaSimulationMap antennas={antennas} billboards={billboards} position={position} route={route} progress={progress}
          sector={{ antennaId, billboardId, zoom: mapZoom }} playing={playing}
          onMove={point => { setPlaying(false); setRouteStep(-1); setPosition(point); }} onSelect={selectZone}>
          <svg viewBox="0 0 720 470" role="group" aria-label="Mapa esquemático de antenas y vallas de Bogotá" aria-describedby="proximity-map-help" tabIndex={0} onClick={mapClick} onKeyDown={mapKey}>
            <rect width="720" height="470" rx="12" fill="#F4F5F7" />
            <path d="M540 0 720 0 720 470 655 470 606 380 565 295 586 195 549 100Z" fill="#E4EDE3" />
            {[85, 175, 265, 355].map(y => <path key={`h${y}`} d={`M0 ${y} L720 ${y + 45}`} fill="none" stroke="#FFFFFF" strokeWidth="13" />)}
            {[125, 265, 405, 545].map(x => <path key={`v${x}`} d={`M${x} 0 L${x - 85} 470`} fill="none" stroke="#FFFFFF" strokeWidth="9" />)}
            <text x="22" y="29" fill="#8A8D93" fontSize="13" fontWeight="600">BOGOTÁ · ESQUEMA DE DEMOSTRACIÓN</text>
            <text x="625" y="85" fill="#85927F" fontSize="12" transform="rotate(65 625 85)">Cerros orientales</text>
            <path d="M35 410 35 365 M28 375 35 365 42 375" stroke="#69716B" strokeWidth="2" fill="none" /><text x="31" y="356" fill="#69716B" fontSize="11">N</text>
            <polyline points={route.map(point => { const p = map.project(point); return `${p.x},${p.y}`; }).join(' ')} fill="none" stroke="#7A8480" strokeWidth="3" strokeDasharray="8 6" />
            {allZones.map(zone => { const p = map.project(zone); const dy = zone.tipo === 'antena' ? -32 : 32; return <g key={`${zone.tipo}-${zone.id}`} opacity={zone.activo ? 1 : .3}>
              <circle cx={p.x} cy={p.y} r={zone.radio_m * map.scale} fill={zone.tipo === 'antena' ? '#1D1D1F' : '#E12F20'} fillOpacity={.07} stroke={zone.tipo === 'antena' ? '#5E6166' : '#E12F20'} strokeDasharray={zone.tipo === 'antena' ? '6 4' : undefined} strokeOpacity={.5} />
              <line x1={p.x} x2={p.x} y1={p.y} y2={p.y + dy} stroke={zone.tipo === 'antena' ? '#1D1D1F' : '#E12F20'} strokeWidth="2" />
              <circle cx={p.x} cy={p.y + dy} r="15" fill={zone.tipo === 'antena' ? '#1D1D1F' : '#E12F20'} stroke="#FFFFFF" strokeWidth="3" />
              <text x={p.x} y={p.y + dy + 4} textAnchor="middle" fill="#FFFFFF" fontSize="11" fontWeight="700">{zone.tipo === 'antena' ? 'A' : 'V'}</text>
              <title>{zone.nombre} · {nf.format(zone.radio_m)} m · {zone.activo ? 'activo' : 'inactivo'}</title>
            </g>; })}
            <g transform={`translate(${marker.x},${marker.y})`}><circle r="22" fill="#FFFFFF" stroke="#1E7F45" strokeWidth="3" /><rect x="-7" y="-12" width="14" height="23" rx="3" fill="#1E7F45" /><circle cy="7" r="1.3" fill="#FFFFFF" /><title>Cliente de demostración</title></g>
          </svg>
        </AntennaSimulationMap>
        <div className="sim-playback">
          <div className="cl-acciones"><button type="button" className="cl-cta" disabled={!settings} onClick={() => {
            if (playing) setPlaying(false); else { if (!soundEnabled.current) void enableSound(); if (progressRef.current >= 1 || routeStep < 0) seek(0); setPlaying(true); }
          }}>{playing ? 'Pausar simulación' : 'Reproducir recorrido'}</button><button type="button" className="cl-cta sec" onClick={resetSimulation}>Reiniciar simulación</button><button type="button" className="cl-cta sec" onClick={() => void toggleFullscreen()}>{fullscreen ? 'Salir de pantalla completa' : 'Pantalla completa'}</button><button type="button" className="cl-cta sec" aria-pressed={sound} onClick={() => { if (sound) { soundEnabled.current = false; setSound(false); } else void enableSound(); }}>{sound ? 'Silenciar aviso' : 'Activar sonido'}</button>{fullscreen && <button type="button" className="cl-cta" disabled={busy || !campaign} onClick={() => void evaluate()}>{busy ? 'Evaluando…' : 'Evaluar cercanía'}</button>}</div>
          {mediaError && <p className="cl-error" role="alert">{mediaError}</p>}
          <label className="cl-proximity-field">Recorrido del cliente<input aria-label="Progreso del recorrido" type="range" min={0} max={100} step={.1} value={progress * 100} onChange={event => seek(Number(event.target.value) / 100)} /></label>
          <div className="sim-playback-row"><div className="cl-steps" role="group" aria-label="Velocidad de reproducción">{[.5, 1, 2, 4].map(value => <button type="button" className="cl-step" key={value} aria-pressed={speed === value} onClick={() => setSpeed(value)}>{value === .5 ? '0,5' : value}×</button>)}</div><span>Hora simulada: <time dateTime={simulatedTime}>{new Intl.DateTimeFormat('es-CO', { timeZone: 'America/Bogota', hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(simulatedTime))}</time></span></div>
          <div className="sim-coverage-state" data-stage={inAntenna && inBillboard ? 'opportunity' : inAntenna ? 'coverage' : 'outside'} role="status"><span className="sim-state-dot" /><div><b>{stage}</b><span>{inAntenna && inBillboard ? 'Cobertura y cercanía listas. Evalúa la campaña para comprobar autorización y frecuencia.' : inAntenna ? 'El cliente está dentro de una antena activa; todavía no está junto a la valla.' : 'Acerca el cliente a una antena activa para entrar al sector.'}</span></div></div>
          {fullscreen && lastResult && <div className={`cl-status ${lastResult.elegible ? 'ok' : 'bad'}`} role="status">{stale ? 'Posición modificada. Evalúa de nuevo.' : lastResult.elegible ? `Oferta elegible · ${lastResult.accion?.campana_nombre} · ${channelName(lastResult.accion?.canal || channel)}` : lastResult.motivos.join(' ')}</div>}
        </div>
        </div>
        <div className="cl-proximity-legend"><span><i className="antenna" />Antena del escenario</span><span><i className="billboard" />Valla</span><span><i className="customer" />Cliente demo</span><span>Círculos: radio configurado</span></div>
        <><div className="cl-steps" role="group" aria-label="Recorrido de demostración">{route.map((point, i) => <button className="cl-step" type="button" key={point.nombre} aria-pressed={routeStep === i} onClick={() => moveRoute(i)}>{i + 1}. {point.nombre}</button>)}</div><div className="cl-acciones"><button type="button" className="cl-cta sec" onClick={() => moveRoute((routeStep + 1) % route.length)}>Avanzar recorrido</button></div><p className="cl-q">Posición de demo: {position.lat.toFixed(5)}, {position.lon.toFixed(5)}</p></>
        <p className="cl-q">Mapa de manzanas de Bogotá con antenas, vallas y cliente de demostración. Las ubicaciones del escenario son ficticias.</p>
      </section>

      <section className="cl-card">
        <span className="cl-eyebrow">Paso 2 · Reglas de contacto</span><h2>Evaluar una oferta de la valla</h2>
        {!settings && !error && <p className="cl-q">Cargando el escenario…</p>}
        <form className="cl-proximity-form" onSubmit={evaluate}>
          <label className="cl-proximity-field">Campaña anunciada<select className="cl-input" value={campaignId} onChange={e => setCampaignId(e.target.value)} required>{campaigns.map(c => <option key={c.id} value={c.id}>{c.nombre}{c.activa ? '' : ' · pausada'}</option>)}</select></label>
          <label className="cl-proximity-field">Canal de la acción<select className="cl-input" value={channel} onChange={e => setChannel(e.target.value)}>{channels.map(c => <option value={c} key={c}>{channelName(c)}</option>)}</select></label>
          {campaign && <p className="cl-q">Canales habilitados en la campaña: {campaign.canales_permitidos.map(channelName).join(', ') || 'ninguno'}.</p>}
          <><label className="cl-proximity-field">Antena del sector<select className="cl-input" value={antennaId} onChange={e => setAntennaId(e.target.value)} required>{antennas.map(z => <option key={z.id} value={z.id}>{z.nombre}</option>)}</select></label><label className="cl-proximity-field">Valla asociada a esta campaña<select className="cl-input" value={billboardId} onChange={e => setBillboardId(e.target.value)} required>{billboards.map(z => <option key={z.id} value={z.id}>{z.nombre}</option>)}</select></label><p className="cl-q">Elige la antena y la valla para centrar el mapa y preparar el recorrido de prueba.</p></>
          <label className="cl-proximity-consent"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /><span>El cliente de esta demo autorizó el contacto por el canal seleccionado.</span></label>
          <label className="cl-proximity-field">Tiempo mínimo por cliente de prueba entre acciones (segundos)<input className="cl-input" type="number" min={0} max={86400} step={1} value={cooldown} onChange={e => { const n = Number(e.target.value); if (Number.isInteger(n) && n >= 0 && n <= 86400) setCooldown(n); }} /></label>
          <label className="cl-proximity-field">Reloj del escenario · hora de Bogotá<input className="cl-input" type="datetime-local" value={moment} onChange={e => e.target.value && setMoment(e.target.value)} required /></label>
          <button className="cl-cta" type="submit" disabled={busy || !settings || !campaign}>{busy ? 'Evaluando…' : 'Evaluar cercanía'}</button>
          <p className="cl-q">La evaluación usa los parámetros enviados al pulsar el botón. Un resultado elegible muestra un aviso local de demostración.</p>
        </form>
        {error && <p className="cl-error" role="alert">{error}</p>}
        {lastResult && <div className="cl-proximity-result" aria-live="polite"><div className={`cl-status ${lastResult.elegible ? 'ok' : 'bad'}`}>{lastResult.elegible ? '✓ Oferta elegible · aviso demo local' : 'Sin oportunidad de contacto'}</div>{stale && <p className="cl-proximity-pending">Cambiaste los parámetros. Este resultado corresponde a la última evaluación.</p>}<ul>{lastResult.motivos.map((reason, i) => <li key={`${i}-${reason}`}>{reason}</li>)}</ul>{lastResult.accion && <div className="cl-proximity-local-notice" role="status"><small>AVISO LOCAL DE DEMOSTRACIÓN</small><b>{lastResult.accion.campana_nombre}</b><p>{lastResult.accion.texto}</p><span>Canal propuesto: {channelName(lastResult.accion.canal)}</span></div>}{lastResult.cooldown_restante_segundos > 0 && <p className="cl-q">Espera restante: {nf.format(lastResult.cooldown_restante_segundos)} segundos.</p>}{lastResult.distancias?.length > 0 && <div className="cl-proximity-distances">{lastResult.distancias.map(z => <span key={`${z.tipo}-${z.id}`}><b>{z.nombre}</b>{nf.format(z.distancia_m)} m · {z.dentro_radio && z.activo ? 'dentro del radio activo' : 'fuera del radio o inactivo'}</span>)}</div>}<p className="cl-q">{lastResult.advertencia}</p></div>}
      </section>
    </div>

    <section className="cl-card"><span className="cl-eyebrow">Sectores editables</span><h2>Radio y disponibilidad de antenas y vallas</h2><p className="cl-q">Los radios determinan las zonas de cercanía. Cambia su tamaño o disponibilidad y pulsa Evaluar cercanía para comprobar el escenario.</p><div className="cl-proximity-zones">{allZones.map(zone => <article className="cl-proximity-zone" key={`${zone.tipo}-${zone.id}`}><div><span className="cl-eyebrow">{zone.tipo === 'antena' ? 'Antena del escenario' : 'Valla publicitaria'}</span><h3>{zone.nombre}</h3><p className="cl-q">{zone.lat.toFixed(5)}, {zone.lon.toFixed(5)}{` · cliente a ${nf.format(meters(position, zone))} m`}</p></div><label className="cl-proximity-field">Radio (m)<input className="cl-input num" type="number" min={25} max={5000} step={1} value={zone.radio_m} onChange={e => { const n = Number(e.target.value); if (Number.isInteger(n) && n >= 25 && n <= 5000) updateZone(zone.tipo, zone.id, { radio_m: n }); }} /></label><button type="button" className="cl-toggle" role="switch" aria-label={`${zone.nombre} activo`} aria-checked={zone.activo} onClick={() => updateZone(zone.tipo, zone.id, { activo: !zone.activo })} /></article>)}</div></section>

    <section className="cl-card"><span className="cl-eyebrow">Registro de la demo</span><h2>Del acercamiento a la acción elegible</h2><div className="cl-proximity-metrics"><div><b>{events.length}</b><span>Evaluaciones</span></div><div><b>{eligibleEvents}</b><span>Oportunidades elegibles</span></div><div><b>{events.filter(e => e.resultado.cooldown_restante_segundos > 0).length}</b><span>Bloqueos por frecuencia</span></div></div><p className="cl-q">Estos contadores miden evaluaciones y avisos de la demo. No son conversiones ni mensajes entregados a clientes.</p>{events.length === 0 ? <p className="cl-q">El registro comienza al pulsar Evaluar cercanía.</p> : <><ol className="cl-proximity-events">{events.map(event => <li key={event.id}><span className={`cl-badge ${event.resultado.elegible ? 'ok' : 'bad'}`}>{event.resultado.elegible ? 'Elegible' : 'Bloqueado'}</span><div><b>{event.resultado.accion?.campana_nombre || campaigns.find(c => c.id === event.campana_id)?.nombre || event.campana_id}</b><small>{new Intl.DateTimeFormat('es-CO', { timeZone: 'America/Bogota', hour: '2-digit', minute: '2-digit' }).format(new Date(event.momento))} · Simulación · {channelName(event.canal)}</small><span>{event.resultado.motivos.join(' · ')}</span></div></li>)}</ol><div className="cl-acciones"><button type="button" className="cl-cta sec" onClick={() => { lastActions.current = {}; setEvents([]); setLastResult(null); }}>Reiniciar historial de la demo</button></div><p className="cl-q">El historial vive en esta pestaña. Reiniciarlo también reinicia la referencia de frecuencia de esta demostración.</p></>}</section>
  </div>;
}
