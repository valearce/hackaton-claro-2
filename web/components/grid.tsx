'use client';
import { useEffect, useState } from 'react';
import { api, channelName, nf } from '@/lib/api';
import type { Config, Row, Run } from '@/lib/types';

export default function Grid({ run, config }: { run: Run | null; config: Config | null }) {
  const [query, setQuery] = useState(''); const [filter, setFilter] = useState('todos'); const [page, setPage] = useState(1);
  const [data, setData] = useState<{ total: number; pagina: number; paginas: number; filas: Row[] } | null>(null);
  const [loading, setLoading] = useState(false); const [error, setError] = useState('');
  useEffect(() => { setPage(1); }, [run?.id, query, filter]);
  useEffect(() => {
    if (!run) return;
    const controller = new AbortController(); const timer = setTimeout(() => {
      setLoading(true); setError('');
      const params = new URLSearchParams({ pagina: String(page), por_pagina: '30', q: query, filtro: filter });
      api<NonNullable<typeof data>>(`/api/parrilla/${run.id}?${params}`, undefined, controller.signal)
        .then(setData).catch(e => { if (e.name !== 'AbortError') setError(e.message); })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [run, page, query, filter]);
  if (!run) return <section className="card">Completa una simulación para consultar la parrilla.</section>;
  return <section className="card"><span className="eyebrow">Parrilla</span><h2>Una decisión por cliente</h2><p className="hint">Escenario del {run.fecha}. La descarga contiene todos los clientes de esta simulación.</p><div className="toolbar"><label className="field">Buscar cliente<input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="CL000039" /></label><label className="field">Filtrar<select value={filter} onChange={e => setFilter(e.target.value)}><option value="todos">Todos</option><option value="asignado">Con acción</option><option value="sin_accion">Sin acción</option>{Object.keys(config?.parametros.canal.capacidad_por_corrida || {}).map(c => <option key={c} value={c}>{channelName(c)}</option>)}{config?.campanas.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select></label><a className="button secondary" href={`/api/parrilla/${run.id}/csv`}>Descargar CSV</a></div>{error && <p className="error" role="alert">{error}</p>}<p className="hint" role="status">{loading ? 'Cargando parrilla…' : data ? `${nf.format(data.total)} clientes coinciden · página ${data.pagina} de ${nf.format(data.paginas)}` : ''}</p><div className="table-wrap" aria-busy={loading}><table><thead><tr>{['Cliente', 'Estado', 'Canal', 'Campaña 1', 'Campaña 2', 'Motivo'].map(x => <th key={x}>{x}</th>)}</tr></thead><tbody>{data?.filas.map(row => <tr key={row.id_cliente}><td>{row.id_cliente}</td><td><span className={`pill ${row.estado === 'asignado' ? 'green' : ''}`}>{row.estado === 'asignado' ? 'Con acción' : 'Sin acción'}</span></td><td>{channelName(row.canal)}</td><td>{row.campana_1 || '—'}</td><td>{row.campana_2 || '—'}</td><td>{row.razon}</td></tr>)}</tbody></table></div><div className="pager"><button className="button secondary" disabled={loading || page <= 1} onClick={() => setPage(p => p - 1)}>← Anterior</button><span>{data ? `${data.pagina} / ${nf.format(data.paginas)}` : '—'}</span><button className="button secondary" disabled={loading || !data || page >= data.paginas} onClick={() => setPage(p => p + 1)}>Siguiente →</button></div></section>;
}
