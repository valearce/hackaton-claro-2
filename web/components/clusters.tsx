'use client';
import { useEffect, useState } from 'react';
import { api, nf, percent, value } from '@/lib/api';
import type { Run } from '@/lib/types';

type Ad = {
  cluster: string; campana: string; contactos: number; principal: string; principal_nombre: string; reparto: Record<string, number>; texto: string; canal_tipico: string;
  por_estrato: { estrato: number; variante: string; nombre: string; p_mejor: number; texto: string }[];
};
type Cluster = {
  id: string; nombre: string; clientes: number; estratos: Record<string, number>;
  rasgos: { hogar: number; netflix: number; banca: number; compras: number; redes: number };
  mejora_publicidad: { sector: number; p5: number; p95: number };
};
type Perf = { mejora_pct: number; p5: number; p95: number };
type Info = {
  advertencia: string; meta: { clientes: number; clusters: number; segmentos: number };
  campanas: Record<string, string>; variantes: Record<string, string>;
  clusters: Cluster[]; publicidad: Ad[];
  rendimiento: { politicas: Record<string, Perf>; curvas: Record<string, number[]>; sensibilidad: { nombre: string; sector: number; global: number }[] };
};
type Part = { id: string; clientes: number; con_accion: number; valor: number; ofertas: Record<string, number> };
type Live = { metodos: Record<'optimo' | 'baseline', { clusters: Part[]; total: { valor: number; con_accion: number } }> };

const COLOR: Record<string, string> = { ahorro: '#da291c', novedad: '#202124', familia: '#8a8d93', entretenimiento: '#2b7a9b' };
const LETRA: Record<string, string> = { ahorro: 'A', novedad: 'N', familia: 'F', entretenimiento: 'E' };
const channelLabel: Record<string, string> = { asesor: 'Asesor', whatsapp: 'WhatsApp', correo: 'Correo', sms: 'SMS' };
const one = new Intl.NumberFormat('es-CO', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const sg = (n: number) => `${n >= 0 ? '+' : '−'}${one.format(Math.abs(n))} %`;
const POL: [string, string, string][] = [['oraculo', 'Techo (conoce la verdad)', '#197c45'], ['bandido_sector', 'Mensajes por cluster', '#da291c'], ['ganador_global', 'Un solo mensaje ganador (A/B)', '#202124'], ['bandido_global', 'Aprende sin separar clusters', '#8a8d93']];

function Curve({ curvas }: { curvas: Record<string, number[]> }) {
  const W = 760, H = 270, l = 44, r = 190, t = 14, b = 36, n = curvas.bandido_sector.length;
  const max = Math.max(...curvas.oraculo, 1) * 1.05, step = max > 12 ? 5 : max > 5 ? 2 : 1;
  const X = (i: number) => l + (W - l - r) * i / (n - 1), Y = (v: number) => H - b - (H - t - b) * v / max;
  const ticks: number[] = []; for (let v = 0; v <= max; v += step) ticks.push(v);
  return <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Mejora acumulada del valor esperado por oleada de contactos" style={{ maxWidth: W }}>
    {ticks.map(v => <g key={v}><line x1={l} x2={W - r} y1={Y(v)} y2={Y(v)} stroke="#e3e5e9" /><text x={l - 6} y={Y(v) + 4} textAnchor="end" fontSize="11" fill="#69707b">{v} %</text></g>)}
    {POL.map(([k, name, color]) => <g key={k}>
      <polyline fill="none" stroke={color} strokeWidth={k === 'bandido_sector' ? 3 : 1.8} points={curvas[k].map((v, i) => `${X(i)},${Y(v)}`).join(' ')} />
      <text x={W - r + 8} y={Y(curvas[k][n - 1]) + 4} fontSize="11" fontWeight="600" fill={color}>{name}</text>
    </g>)}
    <text x={(l + W - r) / 2} y={H - 8} textAnchor="middle" fontSize="11" fill="#69707b">Oleada de contactos</text>
  </svg>;
}

function Ads({ ad, info }: { ad: Ad; info: Info }) {
  const parts = Object.entries(ad.reparto).filter(([, v]) => v > 0.005);
  return <div className="cl-pub">
    <div className="cl-row"><b>{info.campanas[ad.campana] || ad.campana}</b><span className="muted">{nf.format(ad.contactos)} contactos · {channelLabel[ad.canal_tipico] || ad.canal_tipico}</span></div>
    <div className="cl-row"><span className="cl-var" style={{ background: COLOR[ad.principal] }}>{ad.principal_nombre}</span><span className="muted">{nf.format(100 * ad.reparto[ad.principal])} % de los envíos</span></div>
    <div className="cl-reparto" title="Reparto esperado de las propuestas en este cluster">{parts.map(([k, v]) => <span key={k} style={{ width: `${100 * v}%`, background: COLOR[k] }} title={`${info.variantes[k]}: ${nf.format(100 * v)} %`} />)}</div>
    <blockquote className="cl-texto">«{ad.texto}»</blockquote>
    <details><summary>Qué mensaje va en cada estrato</summary>
      <p className="muted">Cada chip es estrato + propuesta (A ahorro, N novedad, F familia, E entretenimiento).</p>
      <div className="cl-letras">{ad.por_estrato.map(x => <span key={x.estrato} className="cl-letra" style={{ background: COLOR[x.variante] }} title={`Estrato ${x.estrato}: ${x.nombre} (${nf.format(100 * x.p_mejor)} % de probabilidad de ser la mejor)`}>{x.estrato}{LETRA[x.variante]}</span>)}</div>
      {ad.por_estrato.map(x => <p key={x.estrato} className="muted"><b>Estrato {x.estrato} · {x.nombre}:</b> «{x.texto}»</p>)}
    </details>
  </div>;
}

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
      .then(data => { if (alive) { setLive(data); setError(''); } })
      .catch((e: Error) => { if (alive) { setLive(null); setError(e.message); } });
    return () => { alive = false; };
  }, [run]);
  if (!info) return <section className="card"><h2>{error ? 'No se pudieron cargar los clusters' : 'Cargando clusters…'}</h2>{error && <p className="error" role="alert">{error}</p>}</section>;

  const opt = live?.metodos.optimo, base = live?.metodos.baseline;
  const part = (m: typeof opt, id: string) => m?.clusters.find(c => c.id === id);
  const pol = info.rendimiento.politicas;
  return <div className="clusters">
    <section className="card">
      <span className="eyebrow">Plus del proyecto</span>
      <h2>{info.meta.clusters} clusters por comportamiento</h2>
      <div className="kpis">
        <div><span>Clusters formados</span><b>{nf.format(info.meta.clusters)}</b></div>
        <div><span>Segmentos (cluster × estrato)</span><b>{nf.format(info.meta.segmentos)}</b></div>
        <div><span>Valor del optimizador</span><b>{opt ? value.format(opt.total.valor) : '…'}</b></div>
        <div><span>Mejora de la publicidad por cluster (simulada)</span><b>{sg(pol.bandido_sector.mejora_pct)}</b></div>
      </div>
      <p className="hint">Se agrupó a los {nf.format(info.meta.clientes)} clientes por lo que hacen y consumen: consumo y tamaño del plan de datos, Netflix, Amazon Prime, Win, redes sociales, banca digital, compras en línea y servicio Hogar. No se usó tipo de línea, ARPU, gama del equipo ni estrato. Cada cluster se cruza luego con el estrato ({info.meta.segmentos} segmentos) porque el mensaje que mejor funciona puede cambiar de un estrato a otro.</p>
      <p className="warning">{info.advertencia}</p>
      <p className="muted">La mejora simulada de la publicidad no se suma a la del optimizador: son dos comparaciones distintas.</p>
    </section>

    <section className="card">
      <h2>Qué tiene en común cada cluster</h2>
      <p className="hint">Las barras muestran cuánto pesa cada cluster en cada estrato y los chips, el porcentaje de clientes del cluster con cada hábito.</p>
      <div className="cluster-grid">
        {info.clusters.map(c => {
          const maxE = Math.max(...Object.values(c.estratos)), o = part(opt, c.id), b = part(base, c.id);
          const trait = (name: string, v: number) => <span className="cl-pill" key={name}>{name} {nf.format(100 * v)} %</span>;
          return <article className="cluster-card" key={c.id}>
            <header><span className="eyebrow">{c.id}</span><b>{nf.format(c.clientes)} clientes</b></header>
            <h3>{c.nombre}</h3>
            <p className="muted">{percent.format(c.clientes / info.meta.clientes)} de la base</p>
            <div className="cl-estratos" title="Clientes del cluster por estrato">
              {[1, 2, 3, 4, 5, 6].map(n => <div className="cl-estrato" key={n} title={`Estrato ${n}: ${nf.format(c.estratos[n] ?? 0)} clientes`}><i style={{ height: `${Math.max(4, 100 * (c.estratos[n] ?? 0) / maxE)}%` }} /><span>E{n}</span></div>)}
            </div>
            <div className="cl-pills">{trait('Hogar', c.rasgos.hogar)}{trait('Netflix', c.rasgos.netflix)}{trait('Redes', c.rasgos.redes)}{trait('Banca digital', c.rasgos.banca)}{trait('Compra en línea', c.rasgos.compras)}</div>
            <h4>El modelo en este cluster</h4>
            {o && b ? <div className="cl-modelo">
              <div><span>Optimizador</span><b>{value.format(o.valor)}</b></div>
              <div><span>Regla simple</span><b>{value.format(b.valor)}</b></div>
              <div><span>Mejora</span><b className={o.valor >= b.valor ? 'cl-up' : 'cl-down'}>{sg(100 * (o.valor / b.valor - 1))}</b></div>
              <div><span>Contactados</span><b>{percent.format(o.con_accion / o.clientes)}</b></div>
            </div> : <p className="muted">Calculando el modelo en este cluster…</p>}
            <h4>Publicidad que recibe</h4>
            {info.publicidad.filter(a => a.cluster === c.id).map(a => <Ads key={a.campana} ad={a} info={info} />)}
          </article>;
        })}
      </div>
    </section>

    <section className="card">
      <h2>Rendimiento por cluster</h2>
      <p className="hint">Valor esperado (score de producto × score de canal × valor de negocio) del escenario actual, repartido por cluster. La mejora de la publicidad es simulada.</p>
      {!live && <p className="notice">{error || (run ? 'Calculando el desglose…' : 'Ejecuta una simulación para ver el desglose.')}</p>}
      <div className="table-wrap"><table>
        <thead><tr><th>Cluster</th><th>Clientes</th><th>Contactados</th><th>Regla simple</th><th>Optimizador</th><th>Mejora del optimizador</th><th>Mejora de la publicidad (simulada)</th></tr></thead>
        <tbody>
          {info.clusters.map(c => {
            const o = part(opt, c.id), b = part(base, c.id), m = c.mejora_publicidad;
            return <tr key={c.id}><td><b>{c.id}</b> {c.nombre}</td><td>{nf.format(c.clientes)}</td><td>{o ? percent.format(o.con_accion / o.clientes) : '…'}</td><td>{b ? value.format(b.valor) : '…'}</td><td>{o ? value.format(o.valor) : '…'}</td>
              <td className={o && b ? (o.valor >= b.valor ? 'cl-up' : 'cl-down') : ''}>{o && b ? sg(100 * (o.valor / b.valor - 1)) : '…'}</td>
              <td>{sg(m.sector)} ({one.format(m.p5)} a {one.format(m.p95)})</td></tr>;
          })}
          <tr className="cl-total"><td>Todos los clusters</td><td>{nf.format(info.meta.clientes)}</td><td>{opt ? percent.format(opt.total.con_accion / info.meta.clientes) : '…'}</td><td>{base ? value.format(base.total.valor) : '…'}</td><td>{opt ? value.format(opt.total.valor) : '…'}</td>
            <td>{opt && base ? sg(100 * (opt.total.valor / base.total.valor - 1)) : '…'}</td><td>{sg(pol.bandido_sector.mejora_pct)}</td></tr>
        </tbody>
      </table></div>
    </section>

    <section className="card">
      <h2>Cómo aprende la publicidad por cluster</h2>
      <p className="hint">Mejora acumulada del valor esperado, oleada tras oleada, frente a mandar los mensajes por igual (simulado).</p>
      <Curve curvas={info.rendimiento.curvas} />
      <div className="table-wrap"><table>
        <thead><tr><th>Estrategia</th><th>Mejora media</th><th>Rango (p5 a p95)</th></tr></thead>
        <tbody>{([['bandido_sector', 'Mensajes por cluster'], ['ganador_global', 'Un solo mensaje ganador (A/B)'], ['bandido_global', 'Aprende sin separar clusters'], ['oraculo', 'Techo (no alcanzable)']] as const).map(([k, name]) =>
          <tr key={k}><td>{name}</td><td>{sg(pol[k].mejora_pct)}</td><td>{one.format(pol[k].p5)} a {one.format(pol[k].p95)}</td></tr>)}</tbody>
      </table></div>
    </section>

    <section className="card">
      <h2>Qué pasa si los clusters casi no se diferencian</h2>
      <p className="hint">Prueba de sensibilidad: separar por cluster solo rinde cuando los perfiles responden distinto.</p>
      <div className="table-wrap"><table>
        <thead><tr><th>Escenario simulado</th><th>Mensajes por cluster</th><th>Un solo mensaje ganador</th></tr></thead>
        <tbody>{info.rendimiento.sensibilidad.map(s => <tr key={s.nombre}><td>{s.nombre.replace('entre sectores', 'entre clusters')}</td><td className={s.sector > s.global ? 'cl-up' : ''}>{sg(s.sector)}</td><td className={s.global > s.sector ? 'cl-up' : ''}>{sg(s.global)}</td></tr>)}</tbody>
      </table></div>
    </section>
  </div>;
}
