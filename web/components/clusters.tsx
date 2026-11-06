'use client';
import { useEffect, useState } from 'react';
import { api, nf, percent, value } from '@/lib/api';
import type { Run } from '@/lib/types';

type Cluster = { id: string; nombre: string; clientes: number; consumo_datos_pct: number; mejora_publicidad: { sector: number; p5: number; p95: number } };
type Ad = { cluster: string; campana: string; contactos: number; principal_nombre: string; texto: string; canal_tipico: string };
type Perf = { mejora_pct: number; p5: number; p95: number };
type Info = {
  advertencia: string; meta: { clientes: number; clusters: number; variables: string[] }; campanas: Record<string, string>;
  clusters: Cluster[]; publicidad: Ad[]; rendimiento: { politicas: Record<string, Perf>; repeticiones: number; oleadas: number };
};
type Live = { clusters: { id: string; clientes: number; con_accion: number; valor: number; ofertas: Record<string, number> }[]; total: { valor: number; con_accion: number } };

const channelLabel: Record<string, string> = { asesor: 'Asesor', whatsapp: 'WhatsApp', correo: 'Correo', sms: 'SMS' };
const signed = (n: number) => `${n >= 0 ? '+' : '−'}${Math.abs(n).toFixed(1).replace('.', ',')} %`;

export default function Clusters({ run }: { run: Run | null }) {
  const [info, setInfo] = useState<Info | null>(null);
  const [live, setLive] = useState<Live | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let alive = true;
    fetch('/datos/clusters.json', { cache: 'no-store' })
      .then(r => { if (!r.ok) throw new Error('Falta web/public/datos/clusters.json (python -m modelo.experimentos.exportar_app --web .)'); return r.json() as Promise<Info>; })
      .then(data => { if (alive) setInfo(data); })
      .catch((e: Error) => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, []);
  useEffect(() => {
    if (!run) { setLive(null); return; }
    let alive = true;
    api<Live>(`/api/clusters/${run.id}`)
      .then(data => { if (alive) setLive(data); })
      .catch((e: Error) => { if (alive) { setLive(null); setError(e.message); } });
    return () => { alive = false; };
  }, [run]);
  if (!info) return <section className="card"><h2>{error ? 'No se pudieron cargar los clusters' : 'Cargando clusters…'}</h2>{error && <p className="error" role="alert">{error}</p>}</section>;
  const campaigns = Object.keys(info.campanas);
  const liveOf = (id: string) => live?.clusters.find(c => c.id === id);
  const gain = info.rendimiento.politicas.bandido_sector;
  const best = info.rendimiento.politicas.ganador_global;
  return <div className="clusters">
    <section className="card">
      <span className="eyebrow">Plus del proyecto</span>
      <h2>{info.meta.clusters} clusters por comportamiento</h2>
      <p className="hint">Se agrupan {nf.format(info.meta.clientes)} clientes por lo que hacen (consumo y plan de datos, streaming, Hogar, redes, banca digital y compras en línea), no por estrato ni ARPU. Los clusters no cambian la asignación oficial del optimizador: explican a quién llega y con qué mensaje.</p>
      <div className="kpis">
        <div><span>Clusters</span><b>{nf.format(info.meta.clusters)}</b></div>
        <div><span>Valor del escenario actual</span><b>{live ? value.format(live.total.valor) : '—'}</b></div>
        <div><span>Mejora simulada del mensaje por cluster</span><b>{signed(gain.mejora_pct)}</b></div>
        <div><span>Mejor mensaje único (simulado)</span><b>{signed(best.mejora_pct)}</b></div>
      </div>
      <p className="warning">{info.advertencia}</p>
      <p className="muted">La mejora simulada es otra comparación que la del optimizador frente a la línea base: no se suman.</p>
    </section>
    <section className="card">
      <h2>Qué publicidad recibe cada cluster</h2>
      <div className="cluster-grid">
        {info.clusters.map(c => {
          const ads = info.publicidad.filter(a => a.cluster === c.id);
          const l = liveOf(c.id);
          return <article className="cluster-card" key={c.id}>
            <header><span className="eyebrow">{c.id}</span><b>{nf.format(c.clientes)} clientes</b></header>
            <h3>{c.nombre}</h3>
            {l && <p className="muted">{nf.format(l.con_accion)} con acción · valor {value.format(l.valor)}</p>}
            <ul>
              {campaigns.map(id => {
                const ad = ads.find(a => a.campana === id);
                return ad ? <li key={id}><b>{id}</b> · {ad.principal_nombre} <span className="muted">({channelLabel[ad.canal_tipico] || ad.canal_tipico}, {nf.format(ad.contactos)} contactos)</span><br /><span className="muted">“{ad.texto}”</span></li> : null;
              })}
            </ul>
            <p className="muted">Mejora simulada: {signed(c.mejora_publicidad.sector)} (rango {c.mejora_publicidad.p5.toFixed(1).replace('.', ',')} a {c.mejora_publicidad.p95.toFixed(1).replace('.', ',')})</p>
          </article>;
        })}
      </div>
    </section>
    <section className="card">
      <h2>Rendimiento por cluster</h2>
      <p className="hint">Valor esperado del escenario actual (score de producto × score de canal × valor de negocio), repartido por cluster. La suma coincide con el valor certificado de la simulación.</p>
      {!live && <p className="notice">{run ? 'Calculando el desglose…' : 'Ejecuta una simulación para ver el desglose.'}</p>}
      {live && <div className="table-wrap"><table>
        <thead><tr><th>Cluster</th><th>Clientes</th><th>Con acción</th><th>Valor esperado</th><th>% del valor</th>{campaigns.map(id => <th key={id}>{id}</th>)}</tr></thead>
        <tbody>
          {live.clusters.map(c => <tr key={c.id}><td>{c.id} · {info.clusters.find(x => x.id === c.id)?.nombre}</td><td>{nf.format(c.clientes)}</td><td>{nf.format(c.con_accion)}</td><td>{value.format(c.valor)}</td><td>{percent.format(c.valor / (live.total.valor || 1))}</td>{campaigns.map(id => <td key={id}>{nf.format(c.ofertas[id] ?? 0)}</td>)}</tr>)}
          <tr><td><b>Total</b></td><td>{nf.format(live.clusters.reduce((s, c) => s + c.clientes, 0))}</td><td>{nf.format(live.total.con_accion)}</td><td><b>{value.format(live.total.valor)}</b></td><td>100 %</td>{campaigns.map(id => <td key={id}>{nf.format(live.clusters.reduce((s, c) => s + (c.ofertas[id] ?? 0), 0))}</td>)}</tr>
        </tbody>
      </table></div>}
    </section>
  </div>;
}
