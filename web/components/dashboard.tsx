'use client';
import Image from 'next/image';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, value } from '@/lib/api';
import type { Change, Config, Metadata, Run, Version } from '@/lib/types';
import Settings from './settings';
import Results from './results';
import Grid from './grid';
import Versions from './versions';

type Job = { config: Config; fecha: string; signature: string };
export default function Dashboard() {
  const [meta, setMeta] = useState<Metadata | null>(null); const [config, setConfig] = useState<Config | null>(null); const [date, setDate] = useState('2026-11-05');
  const [run, setRun] = useState<Run | null>(null); const [runConfig, setRunConfig] = useState<Config | null>(null); const [runSignature, setRunSignature] = useState('');
  const [page, setPage] = useState<'simulacion' | 'parrilla' | 'versiones'>('simulacion'); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const [versions, setVersions] = useState<Version[]>([]); const [active, setActive] = useState<string | null>(null); const [history, setHistory] = useState<Run[]>([]);
  const alive = useRef(true); const running = useRef(false); const pending = useRef<Job | null>(null); const latest = useRef('');
  const signature = config ? JSON.stringify({ config, fecha: date }) : '';
  const reloadVersions = useCallback(async () => { const r = await api<{ versiones: Version[]; activa: string | null }>('/api/versiones'); setVersions(r.versiones); setActive(r.activa); }, []);
  const init = useCallback(async (signal?: AbortSignal) => {
    setError('');
    try { const m = await api<Metadata>('/api/config', undefined, signal); setMeta(m); setConfig(m.config); setDate(m.fecha); setActive(m.version_activa); await reloadVersions(); }
    catch (e) { if ((e as Error).name !== 'AbortError') setError((e as Error).message); }
  }, [reloadVersions]);
  useEffect(() => { alive.current = true; const c = new AbortController(); void init(c.signal); return () => { alive.current = false; c.abort(); }; }, [init]);
  const drain = useCallback(async () => {
    if (running.current) return; running.current = true;
    while (pending.current && alive.current) {
      const job: Job = pending.current; pending.current = null; setBusy(true); setError('');
      try {
        const result = await api<Run>('/api/simular', { config: job.config, fecha: job.fecha });
        if (alive.current && latest.current === job.signature) { setRun(result); setRunConfig(job.config); setRunSignature(job.signature); setHistory(h => [result, ...h.filter(r => r.id !== result.id)].slice(0, 8)); }
      } catch (e) { if (alive.current && latest.current === job.signature) setError((e as Error).message); }
    }
    running.current = false; if (alive.current) setBusy(false);
  }, []);
  useEffect(() => {
    latest.current = signature;
    if (!config || !signature) return;
    const job = { config, fecha: date, signature };
    const timer = setTimeout(() => { pending.current = job; void drain(); }, 650);
    return () => clearTimeout(timer);
  }, [signature, config, date, drain]);
  const change: Change = useCallback(fn => { setConfig(previous => { if (!previous) return previous; const draft = structuredClone(previous); fn(draft); return draft; }); }, []);
  const load = useCallback((c: Config, d: string) => { setConfig(structuredClone(c)); setDate(d); setPage('simulacion'); }, []);
  const incomplete = busy || !!(signature && runSignature !== signature);
  return <main className="shell"><header className="header"><div><span className="eyebrow">Claro · Grupo 5</span><h1>Orquestador NBA</h1><p>La siguiente mejor acción, con las reglas de tu negocio.</p></div><Image src="/claro.png" width={110} height={52} alt="Claro" priority style={{ objectFit: 'contain' }} /></header><nav className="tabs" aria-label="Secciones de la consola">{([['simulacion', 'Simulación'], ['parrilla', 'Parrilla'], ['versiones', 'Versiones']] as const).map(([key, label]) => <button key={key} aria-current={page === key ? 'page' : undefined} onClick={() => setPage(key)}>{label}</button>)}</nav>
    {!meta || !config ? <section className="card"><h2>{error ? 'No se pudo cargar la consola' : 'Cargando configuración…'}</h2>{error && <><p className="error" role="alert">{error}</p><button className="button" onClick={() => void init()}>Reintentar</button></>}</section> : <>
      <div className="page-heading"><div><span className="eyebrow">Configurable sin código</span><h2>{page === 'simulacion' ? 'Configura, simula y decide' : page === 'parrilla' ? 'Revisa las ofertas asignadas' : 'Configuraciones de negocio'}</h2></div><button className="button secondary" onClick={() => load(meta.config_reto, '2026-11-05')}>Volver a la configuración del reto</button></div>
      {page === 'simulacion' && <div className="workspace"><Settings config={config} metadata={meta} change={change} date={date} setDate={setDate} /><Results run={run} pending={incomplete && !error} error={error} meta={meta.meta} /></div>}
      {page === 'parrilla' && <>{incomplete && <p className="notice">La parrilla corresponde a la última simulación completada. Hay cambios pendientes.</p>}<Grid run={run} config={runConfig} /></>}
      {page === 'versiones' && <Versions versions={versions} active={active} run={run} pending={incomplete} config={runConfig} reload={reloadVersions} load={load} />}
      {page === 'simulacion' && history.length > 0 && <section className="card history"><h2>Escenarios calculados en esta sesión</h2><p className="hint">Cada fila corresponde a una configuración completa. Los resultados con restricciones modificadas se identifican frente al reto original.</p><div className="table-wrap"><table><thead><tr><th>Fecha</th><th>Valor esperado</th><th>Objetivo</th><th>Controles del reto</th><th>Parrilla</th></tr></thead><tbody>{history.map(r => <tr key={r.id}><td>{r.fecha}</td><td>{value.format(r.metodos.optimo.valor_esperado)}</td><td>{r.metodos.optimo.objetivo === 'prioridad' ? 'Prioridad ponderada' : 'Valor esperado'}</td><td>{r.metodos.optimo.violaciones_reto ? `${r.metodos.optimo.violaciones_reto} incumplimientos` : 'Cumple'}</td><td><a href={`/api/parrilla/${r.id}/csv`}>CSV</a></td></tr>)}</tbody></table></div></section>}
      <footer>100.000 clientes sintéticos del reto · una asignación global por escenario · certificado de optimalidad y auditoría de reglas.</footer>
    </>}
  </main>;
}
