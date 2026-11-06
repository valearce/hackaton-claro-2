'use client';
import Image from 'next/image';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, value } from '@/lib/api';
import { scenarioChanges } from '@/lib/scenario';
import type { Change, Config, Metadata, Run, Version } from '@/lib/types';
import Settings from './settings';
import AdvancedSettings from './advanced-settings';
import Results from './results';
import Campaigns from './campaigns';
import Grid from './grid';
import Versions from './versions';
import MapPanel from './map-panel';
import Proximity from './proximity';
import Clusters from './clusters';
import HomeIntro from './home-intro';

type Page = 'inicio' | 'campanas' | 'parrilla' | 'mapa' | 'clusters' | 'cercania';
export default function Dashboard() {
  const [meta, setMeta] = useState<Metadata | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [date, setDate] = useState('2026-11-05');
  const [run, setRun] = useState<Run | null>(null);
  const [initialRun, setInitialRun] = useState<Run | null>(null);
  const [runConfig, setRunConfig] = useState<Config | null>(null);
  const [runSignature, setRunSignature] = useState('');
  const [page, setPage] = useState<Page>('inicio');
  const [scrollRequested, setScrollRequested] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [versions, setVersions] = useState<Version[]>([]);
  const [history, setHistory] = useState<Run[]>([]);
  const alive = useRef(true);
  const running = useRef(false);
  const defaultRun = useRef<Run | null>(null);
  const defaultConfig = useRef<Config | null>(null);
  const defaultSignature = useRef('');
  const signature = config ? JSON.stringify({ config, fecha: date }) : '';
  const dirty = signature !== runSignature;
  const reloadVersions = useCallback(async () => {
    const r = await api<{ versiones: Version[]; activa: string | null }>('/api/versiones');
    setVersions(r.versiones);
  }, []);
  const init = useCallback(async (signal?: AbortSignal) => {
    setError('');
    let ownsRun = false;
    try {
      const [m, v] = await Promise.all([
        api<Metadata>('/api/config', undefined, signal),
        api<{ versiones: Version[]; activa: string | null }>('/api/versiones', undefined, signal),
      ]);
      if (signal?.aborted) return;
      const initial = structuredClone(m.config_reto);
      const initialSignature = JSON.stringify({ config: initial, fecha: '2026-11-05' });
      setMeta(m); setConfig(initial); setDate('2026-11-05'); setVersions(v.versiones);
      defaultConfig.current = initial; defaultSignature.current = initialSignature;
      if (running.current) return;
      running.current = true; ownsRun = true; setBusy(true);
      const result = await api<Run>('/api/simular', { config: initial, fecha: '2026-11-05' }, signal);
      if (signal?.aborted) return;
      defaultRun.current = result;
      setInitialRun(result);
      setRun(result); setRunConfig(initial); setRunSignature(initialSignature); setHistory([result]);
    } catch (e) { if ((e as Error).name !== 'AbortError') setError((e as Error).message); }
    finally { if (ownsRun) { running.current = false; if (!signal?.aborted) setBusy(false); } }
  }, []);
  useEffect(() => {
    alive.current = true;
    const controller = new AbortController(); void init(controller.signal);
    return () => { alive.current = false; controller.abort(); };
  }, [init]);
  useEffect(() => {
    const sync = () => { const p = location.hash.slice(1); if (['inicio', 'campanas', 'parrilla', 'mapa', 'clusters', 'cercania'].includes(p)) setPage(p as Page); };
    sync(); window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);
  function navigate(next: Page) { setPage(next); historyReplace(next); window.scrollTo({ top: 0, behavior: 'instant' }); }
  function historyReplace(next: Page) { window.history.replaceState(null, '', `#${next}`); }
  function openSimulator() { setPage('inicio'); historyReplace('inicio'); setScrollRequested(true); }
  useEffect(() => {
    if (!scrollRequested || page !== 'inicio' || !meta) return;
    const frame = requestAnimationFrame(() => {
      const target = document.getElementById('simulador');
      if (target) {
        target.focus({ preventScroll: true });
        target.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' });
        setScrollRequested(false);
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [scrollRequested, page, meta]);
  const change: Change = useCallback(fn => {
    setConfig(previous => { if (!previous) return previous; const draft = structuredClone(previous); fn(draft); return draft; });
    setError('');
  }, []);
  const load = useCallback((c: Config, d: string) => {
    setConfig(structuredClone(c)); setDate(d); setPage('inicio'); setError('');
    if (defaultRun.current && JSON.stringify({ config: c, fecha: d }) === defaultSignature.current) {
      setRun(defaultRun.current); setRunConfig(defaultConfig.current); setRunSignature(defaultSignature.current);
    }
    window.history.replaceState(null, '', '#inicio');
  }, []);
  async function submit() {
    if (!config || running.current || (!!run && !dirty)) return;
    running.current = true; setBusy(true); setError('');
    const snapshot = structuredClone(config);
    const sent = JSON.stringify({ config: snapshot, fecha: date });
    try {
      const result = await api<Run>('/api/simular', { config: snapshot, fecha: date });
      if (alive.current) {
        setRun(result); setRunConfig(snapshot); setRunSignature(sent);
        setHistory(previous => [result, ...previous.filter(r => r.id !== result.id)].slice(0, 8));
      }
    } catch (e) { if (alive.current) setError((e as Error).message); }
    finally { running.current = false; if (alive.current) setBusy(false); }
  }
  const changes = config && meta ? scenarioChanges(config, meta.config_reto, date) : [];
  const completedChanges = runConfig && run && meta ? scenarioChanges(runConfig, meta.config_reto, run.fecha) : [];
  const submitButton = <button type="button" className="cl-cta cl-submit" disabled={busy || (!!run && !dirty)} onClick={() => void submit()}>{busy ? 'Procesando parámetros…' : 'Enviar parámetros'}</button>;
  return <main className="cl">
    <header className="cl-top"><div className="cl-top-in">
      <div className="cl-brand"><button className="cl-brand-home" type="button" onClick={() => navigate('inicio')} aria-label="Volver al inicio"><Image className="cl-logo" src="/claro.png" width={110} height={40} alt="Claro" unoptimized priority /></button><div className="cl-titulo"><h1>Orquestador NBA</h1><p className="sub">Grupo 5 · Claro + Universidad del Rosario</p></div></div>
      <nav className="cl-tabs" aria-label="Páginas">{([['inicio', 'Inicio'], ['campanas', 'Campañas'], ['parrilla', 'Parrilla'], ['mapa', 'Mapa'], ['clusters', 'Clusters'], ['cercania', 'Cercanía']] as const).map(([id, title]) => <button type="button" className="cl-tab" key={id} aria-current={page === id ? 'page' : undefined} aria-selected={page === id} onClick={() => navigate(id)}>{title}</button>)}</nav>
      <button className="cl-header-cta" type="button" onClick={openSimulator}>Ir al simulador</button>
    </div></header>
    <section className={`cl-page${page === 'inicio' ? ' cl-page-home' : ''}`} aria-label={page === 'inicio' ? 'Inicio' : page === 'campanas' ? 'Campañas' : page === 'mapa' ? 'Mapa' : page === 'clusters' ? 'Clusters' : page === 'cercania' ? 'Cercanía' : 'Parrilla'}>
      {page === 'mapa' ? <MapPanel /> : page === 'cercania' ? <Proximity config={config} /> : !meta || !config ? <section className="cl-card"><h2>{error ? 'No se pudo cargar la consola' : 'Cargando configuración…'}</h2>{error && <><p className="cl-error" role="alert">{error}</p><button type="button" className="cl-step" onClick={() => void init()}>Reintentar</button></>}</section> : <>
        {page === 'inicio' && <>
          <HomeIntro clients={meta.clientes} campaigns={meta.config_reto.campanas.length} channelCount={Object.keys(meta.config_reto.parametros.canal.capacidad_por_corrida).length} onExplore={openSimulator} />
          <section id="simulador" className="cl-simulator" aria-label="Simulador de campañas" tabIndex={-1}>
          <header className="cl-simulator-title"><p>Simulador de campañas</p><h2>Prueba tu siguiente escenario.</h2></header>
          <div className="cl-home"><div className="cl-controls">
            <Settings config={config} metadata={meta} change={change} run={run} initialRun={initialRun} />
            <section className="cl-card"><span className="cl-eyebrow">Confirmar escenario</span><h2>Envía la configuración completa</h2><p className="cl-q">Los botones preparan tus parámetros. Al enviarlos se ejecuta únicamente el optimizador seleccionado, una sola vez.</p>{submitButton}</section>
            <details className="cl-card"><summary style={{ cursor: 'pointer' }}><span className="cl-eyebrow">Opciones avanzadas</span><h2 style={{ display: 'inline', marginLeft: 8 }}>Más cambios de negocio</h2></summary><p className="cl-q">Ajusta fechas, valores, canales, reglas y pesos. Los cambios se aplican al pulsar Enviar parámetros.</p><div className="advanced-editor">
              <AdvancedSettings config={config} metadata={meta} change={change} date={date} setDate={setDate} />
              <Versions versions={versions} run={run} pending={busy || dirty} config={runConfig} reload={reloadVersions} load={load} />
              {history.length > 0 && <section className="card"><h2>Historial de escenarios enviados</h2><div className="cl-table-wrap"><table className="cl-hist"><thead><tr><th>Fecha</th><th>Valor esperado</th><th>Objetivo</th><th>Reglas del reto</th><th>Parrilla</th></tr></thead><tbody>{history.map(r => <tr key={r.id}><td>{r.fecha}</td><td>{value.format(r.metodos.optimo.valor_esperado)}</td><td>{r.metodos.optimo.objetivo === 'prioridad' ? 'Prioridad ponderada' : 'Valor esperado'}</td><td>{r.metodos.optimo.violaciones_reto ? `${r.metodos.optimo.violaciones_reto} incumplimientos` : 'Cumple'}</td><td><a href={`/api/parrilla/${r.id}/csv`}>CSV</a></td></tr>)}</tbody></table></div></section>}
            </div></details>
          </div><aside className="cl-side"><Results run={run} busy={busy} dirty={dirty} error={error} meta={meta.meta} changes={changes} history={history} reset={() => load(meta.config_reto, '2026-11-05')} restoreCapacity={c => change(d => { d.parametros.canal.capacidad_por_corrida[c] = meta.config_reto.parametros.canal.capacidad_por_corrida[c]; })} submit={() => void submit()} /></aside></div>
          <p className="cl-foot">Cada envío calcula un escenario completo sobre {meta.clientes.toLocaleString('es-CO')} clientes. El resultado incluye auditoría de las reglas del escenario y del reto original. La curva muestra solamente escenarios enviados en esta sesión.</p>
          </section>
        </>}
        {page === 'campanas' && <Campaigns run={run} config={runConfig} pending={busy || (!!run && dirty)} changes={completedChanges} />}
        {page === 'clusters' && <div className="advanced-editor cl-clusters">{(busy || (!!run && dirty)) && <p className="cl-q" role="status">Los resultados corresponden al último escenario enviado.</p>}<Clusters run={run} /></div>}
        {page === 'parrilla' && <>{(busy || (!!run && dirty)) && <p className="cl-q" role="status">La parrilla corresponde a la última solicitud completada. Hay parámetros pendientes de enviar.</p>}<Grid run={run} config={runConfig} /></>}
      </>}
    </section>
  </main>;
}
