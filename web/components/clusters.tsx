'use client';
import { useEffect, useState } from 'react';
import { nf, percent } from '@/lib/api';
import type { Run } from '@/lib/types';

type Cluster = { id: string; nombre: string; clientes: number; estratos: Record<string, number> };
type Info = {
  meta: { clientes: number; clusters: number };
  clusters: Cluster[];
  rendimiento: { politicas: Record<string, { mejora_pct: number }>; curvas: Record<string, number[]> };
};
const one = new Intl.NumberFormat('es-CO', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const sg = (n: number) => `${n >= 0 ? '+' : '−'}${one.format(Math.abs(n))} %`;
const POL: [string, string, string][] = [['oraculo', 'Techo teórico', '#197c45'], ['bandido_sector', 'Mensajes por perfil', '#da291c'], ['ganador_global', 'Mensaje único (A/B)', '#202124'], ['bandido_global', 'Aprendizaje global', '#8a8d93']];

function Curve({ curvas }: { curvas: Record<string, number[]> }) {
  const W = 760, H = 270, l = 44, r = 20, t = 14, b = 36, n = curvas.bandido_sector.length;
  const max = Math.max(...curvas.oraculo, 1) * 1.05, step = max > 12 ? 5 : max > 5 ? 2 : 1;
  const X = (i: number) => l + (W - l - r) * i / (n - 1), Y = (v: number) => H - b - (H - t - b) * v / max;
  const ticks: number[] = []; for (let v = 0; v <= max; v += step) ticks.push(v);
  return <figure className="cluster-curve"><svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Mejora acumulada del valor esperado por oleada de contactos">
    {ticks.map(v => <g key={v}><line x1={l} x2={W - r} y1={Y(v)} y2={Y(v)} stroke="#e3e5e9" /><text x={l - 6} y={Y(v) + 4} textAnchor="end" fontSize="11" fill="#69707b">{v} %</text></g>)}
    {POL.map(([k, , color]) => <g key={k}>
      <polyline fill="none" stroke={color} strokeWidth={k === 'bandido_sector' ? 3 : 1.8} points={curvas[k].map((v, i) => `${X(i)},${Y(v)}`).join(' ')} />
    </g>)}
    <text x={(l + W - r) / 2} y={H - 8} textAnchor="middle" fontSize="11" fill="#69707b">Oleada de contactos</text>
  </svg><figcaption className="cluster-chart-legend">{POL.map(([id, name, color]) => <span key={id}><i style={{ backgroundColor: color }} />{name}</span>)}</figcaption></figure>;
}

export default function Clusters({ run }: { run: Run | null }) {
  const [info, setInfo] = useState<Info | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    fetch('/datos/clusters.json', { cache: 'no-store', signal: controller.signal })
      .then(r => { if (!r.ok) throw new Error('No se pudo cargar el análisis de referencia de los clusters.'); return r.json() as Promise<Info>; })
      .then(data => { if (!controller.signal.aborted) setInfo(data); })
      .catch((e: Error) => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, []);
  if (!info) return <section className="card"><h2>{error ? 'No se pudieron cargar los clusters' : 'Cargando clusters…'}</h2>{error && <p className="error" role="alert">{error}</p>}</section>;

  const result = run?.metodos.optimo;
  return <div className="clusters cluster-report">
    <section className="cluster-report-header">
      <h2>{info.meta.clusters} perfiles de clientes</h2>
      <dl className="cluster-overview">
        <div><dt>Clientes</dt><dd>{nf.format(info.meta.clientes)}</dd></div>
        <div><dt>Con acción</dt><dd>{result ? nf.format(result.clientes) : '…'}</dd></div>
        <div><dt>Valor esperado</dt><dd>{result ? one.format(result.valor_esperado) : '…'}</dd></div>
      </dl>
    </section>
    <section className="cluster-distribution">
      <h2>Perfiles por estrato</h2>
      <div className="cluster-grid">{info.clusters.map(c => {
        const max = Math.max(1, ...Object.values(c.estratos));
        return <article className="cluster-profile" key={c.id}>
          <header><span className="cluster-code">{c.id}</span><span>{percent.format(info.meta.clientes ? c.clientes / info.meta.clientes : 0)} de la base</span></header>
          <h3>{c.nombre}</h3>
          <div className="cl-estratos" role="img" aria-label={[1, 2, 3, 4, 5, 6].map(n => `Estrato ${n}: ${nf.format(c.estratos[n] ?? 0)} clientes`).join('; ')}>
            {[1, 2, 3, 4, 5, 6].map(n => <div className="cl-estrato" key={n} title={`Estrato ${n}: ${nf.format(c.estratos[n] ?? 0)} clientes`}><i style={{ height: `${100 * (c.estratos[n] ?? 0) / max}%` }} /><span>E{n}</span></div>)}
          </div>
        </article>;
      })}</div>
    </section>
    <section className="cluster-chart">
      <div className="cl-row"><h2>Experimentación de mensajes</h2><b className="cluster-lift">{sg(info.rendimiento.politicas.bandido_sector.mejora_pct)}</b></div>
      <Curve curvas={info.rendimiento.curvas} />
      <p className="muted">Mejora simulada del valor esperado (%)</p>
    </section>
  </div>;
}
