'use client';
import { useState } from 'react';
import { api, value } from '@/lib/api';
import type { Config, Run, Version } from '@/lib/types';

export default function Versions({ versions, run, pending, config, reload, load }: { versions: Version[]; run: Run | null; pending: boolean; config: Config | null; reload: () => Promise<void>; load: (c: Config, d: string) => void }) {
  const [name, setName] = useState(''); const [busy, setBusy] = useState(false); const [message, setMessage] = useState(''); const [error, setError] = useState('');
  async function save() {
    if (!run || !config) return; setBusy(true); setError(''); setMessage('');
    try { const r = await api<Version>('/api/versiones', { config, fecha: run.fecha, nombre: name.trim() || 'Escenario de negocio' }); setName(''); await reload(); setMessage(`Versión guardada: ${r.nombre}`); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function restore(id: string) { setBusy(true); setError(''); try { const r = await api<Version>(`/api/versiones/${id}`); if (r.config) load(r.config, r.fecha); setMessage('Configuración recuperada. Pulsa Enviar parámetros para calcularla.'); } catch (e) { setError((e as Error).message); } finally { setBusy(false); } }
  return <section className="card"><span className="eyebrow">Versiones</span><h2>Conserva y recupera las decisiones de negocio</h2><p className="hint">Cada versión guarda su configuración, fecha, resultado y vínculo con la parrilla. Al abrir la consola siempre se carga la configuración oficial del reto. Recuperar una versión prepara sus parámetros para enviarlos.</p><div className="toolbar"><label className="field">Nombre de la versión<input value={name} maxLength={100} onChange={e => setName(e.target.value)} placeholder="Ej.: Campaña de noviembre" /></label><button className="button" onClick={save} disabled={busy || pending || !run}>Guardar escenario calculado</button></div>{message && <p className="success" role="status">{message}</p>}{error && <p className="error" role="alert">{error}</p>}<div className="version-list">{versions.length === 0 && <p className="hint">Todavía no hay versiones guardadas.</p>}{versions.map(v => <article className="version" key={v.version}><div><h3>{v.nombre}</h3><p className="hint">{v.fecha} · valor esperado {value.format(v.resultado.valor_esperado)} · {v.resultado.violaciones_reto ? `${v.resultado.violaciones_reto} incumplimientos del reto original` : 'Cumple el reto original'}</p><code>{v.version}</code></div><div className="inline-buttons"><button className="button secondary" disabled={busy} onClick={() => restore(v.version)}>Recuperar</button><a className="button secondary" href={`/api/parrilla/${v.corrida}/csv`}>CSV</a></div></article>)}</div></section>;
}
