'use client';

import { useEffect, useState } from 'react';
import { api, channelName, nf, percent } from '@/lib/api';
import type { Config, Row, Run } from '@/lib/types';

type GridData = { total: number; pagina: number; paginas: number; filas: Row[] };
type ResponseState = { key: string; data: GridData | null; error: string };
const PAGE_SIZE = 10;

export default function Grid({ run, config }: { run: Run | null; config: Config | null }) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('todos');
  const [page, setPage] = useState(1);
  const [response, setResponse] = useState<ResponseState | null>(null);
  const runId = run?.id;
  const filters = [
    { id: 'todos', label: 'Todos' }, { id: 'asignado', label: 'Con acción' }, { id: 'sin_accion', label: 'Sin acción' },
    ...Object.keys(config?.parametros.canal.capacidad_por_corrida || {}).map(id => ({ id, label: channelName(id) })),
    ...(config?.campanas || []).map(campaign => ({ id: campaign.id, label: campaign.nombre })),
  ];
  const activeFilter = filters.some(item => item.id === filter) ? filter : 'todos';
  const requestKey = JSON.stringify([runId, page, query, activeFilter]);
  const data = response?.key === requestKey ? response.data : null;
  const error = response?.key === requestKey ? response.error : '';
  const loading = !!runId && response?.key !== requestKey;

  useEffect(() => { setPage(1); }, [runId]);
  useEffect(() => {
    if (!runId) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ pagina: String(page), por_pagina: String(PAGE_SIZE), q: query, filtro: activeFilter });
      void api<GridData>(`/api/parrilla/${runId}?${params}`, undefined, controller.signal)
        .then(result => { if (!controller.signal.aborted) setResponse({ key: requestKey, data: result, error: '' }); })
        .catch((failure: Error) => { if (!controller.signal.aborted) setResponse({ key: requestKey, data: null, error: failure.message }); });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [runId, page, query, activeFilter, requestKey]);

  if (!run) return <section className="cl-card"><h2>Parrilla de clientes</h2><p className="cl-q">Envía los parámetros desde Inicio para consultar y descargar la parrilla.</p></section>;

  const result = run.metodos.optimo;
  const currentPage = data?.pagina ?? page;
  const lastPage = data?.paginas ?? 1;
  const start = data?.total ? (data.pagina - 1) * PAGE_SIZE + 1 : 0;
  const end = data ? Math.min(data.total, data.pagina * PAGE_SIZE) : 0;
  const kpi = (label: string, count: number, detail: string) => <div className="cl-kpi" key={label}><span className="k">{label}</span><span className="v">{nf.format(count)}</span><span className="d">{detail}</span></div>;

  return <>
    <section className="cl-card"><span className="cl-eyebrow">Entrega del reto</span><h2>Parrilla completa de {nf.format(result.total_clientes)} clientes</h2><p className="cl-q">Una fila por cliente en el formato que pide el reto, de la última simulación completada. Escenario del {run.fecha}.</p><div className="cl-acciones"><a className="cl-cta sec" href={`/api/parrilla/${run.id}/csv`} style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center' }}>Descargar CSV</a></div></section>

    <div className="cl-kpis">
      {kpi('Con acción', result.clientes, result.total_clientes ? `${percent.format(result.clientes / result.total_clientes)} de la base` : '—')}
      {kpi('Sin acción', result.total_clientes - result.clientes, result.total_clientes ? `${percent.format(1 - result.clientes / result.total_clientes)} de la base` : '—')}
      {result.canales.map(channel => kpi(channelName(channel.canal), channel.uso, `de ${nf.format(channel.cupo)} cupos`))}
    </div>

    <section className="cl-card"><div className="cl-filters"><input type="search" className="cl-search" aria-label="Buscar cliente" placeholder="Buscar cliente, por ejemplo CL000039" value={query} onChange={event => { setQuery(event.target.value); setPage(1); }} /><div className="cl-steps" role="group" aria-label="Filtrar la parrilla">{filters.map(item => <button className="cl-step" type="button" key={item.id} aria-pressed={activeFilter === item.id} onClick={() => { setFilter(item.id); setPage(1); }}>{item.label}</button>)}</div></div>
      {error && <p className="cl-error" role="alert">{error}</p>}
      <p className="cl-q" role="status">{loading ? 'Cargando parrilla…' : data ? `${nf.format(data.total)} clientes coinciden · mostrando ${nf.format(start)} a ${nf.format(end)} · optimizador del equipo` : 'La parrilla no está disponible.'}</p>
      <div className="cl-table-wrap cl-paged" aria-busy={loading}><table><thead><tr>{['Cliente', 'Estado', 'Canal', 'Campaña 1', 'Campaña 2', 'Razón'].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>{data?.filas.map(row => <tr key={row.id_cliente}><td>{row.id_cliente}</td><td><span className={`cl-pill ${row.estado}`}>{row.estado === 'asignado' ? 'Con acción' : 'Sin acción'}</span></td><td>{row.canal ? <span className={`cl-pill ${row.canal}`}>{channelName(row.canal)}</span> : '—'}</td><td>{row.campana_1 || '—'}</td><td>{row.campana_2 || '—'}</td><td className="razon">{row.razon}</td></tr>)}{!data?.filas.length && <tr><td colSpan={6}>{loading ? 'Consultando clientes…' : data ? 'No hay clientes que coincidan con la búsqueda y el filtro.' : 'No hay filas disponibles.'}</td></tr>}</tbody></table></div>
      <nav className="cl-pager" aria-label="Páginas de la parrilla"><button className="cl-step cl-pag" type="button" aria-label="Primera página" disabled={loading || !data || currentPage <= 1} onClick={() => setPage(1)}>«</button><button className="cl-step cl-pag" type="button" disabled={loading || !data || currentPage <= 1} onClick={() => setPage(currentPage - 1)}>‹ Anterior</button><span className="cl-pag-txt">{data ? `Página ${nf.format(data.pagina)} de ${nf.format(data.paginas)}` : '—'}</span><button className="cl-step cl-pag" type="button" disabled={loading || !data || currentPage >= lastPage} onClick={() => setPage(currentPage + 1)}>Siguiente ›</button><button className="cl-step cl-pag" type="button" aria-label="Última página" disabled={loading || !data || currentPage >= lastPage} onClick={() => setPage(lastPage)}>»</button></nav>
    </section>
  </>;
}
