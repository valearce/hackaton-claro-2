'use client';

import { useState, type ReactNode } from 'react';
import { channelName, nf, percent, value } from '@/lib/api';
import type { Change, Config, Metadata, Run } from '@/lib/types';

const capacities: Record<string, number[]> = {
  asesor: [0, 1250, 2500, 5000, 7500], whatsapp: [5000, 10000, 15000, 20000, 30000],
  correo: [10000, 20000, 30000, 40000], sms: [10000, 20000, 40000, 60000],
};
const decimal = new Intl.NumberFormat('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const oneDecimal = new Intl.NumberFormat('es-CO', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

function Choices({ label, values, current, official, change, format = nf.format, min = 0, max = 1000000, step = 1 }: {
  label: string; values: number[]; current: number; official: number; change: (n: number) => void;
  format?: (n: number) => string; min?: number; max?: number; step?: number;
}) {
  const [other, setOther] = useState(false);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState('');
  const options = [...new Set([...values, current])].sort((a, b) => a - b);
  return <div className="cl-choice">
    <div className="cl-steps" role="group" aria-label={label}>
      {options.map(n => <button className="cl-step" type="button" key={n} aria-pressed={n === current} onClick={() => { change(n); setOther(false); }}>{format(n)}{n === official && <span className="reto">reto</span>}</button>)}
      <button className="cl-step" type="button" aria-expanded={other} onClick={() => { setOther(!other); setDraft(String(current)); setError(''); }}>Seleccionar otro</button>
    </div>
    {other && <form className="cl-custom" onSubmit={e => {
      e.preventDefault(); const n = Number(draft);
      if (!draft.trim() || !Number.isFinite(n) || n < min || n > max || (step === 1 && !Number.isInteger(n))) { setError(`Escribe un valor válido entre ${min} y ${max}.`); return; }
      change(n); setOther(false); setError('');
    }}><label>{label}<input className="cl-input num" type="number" value={draft} min={min} max={max} step={step} onChange={e => setDraft(e.target.value)} autoFocus required /></label><button className="cl-step" type="submit">Usar este valor</button><button className="cl-step" type="button" onClick={() => setOther(false)}>Cancelar</button>{error && <p className="cl-error" role="alert">{error}</p>}</form>}
  </div>;
}

function Row({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return <div className="cl-rowctl"><div className="lab">{title}{description && <span>{description}</span>}</div><div>{children}</div></div>;
}

function Toggle({ on, label, change }: { on: boolean; label: string; change: () => void }) {
  return <button type="button" className="cl-toggle" role="switch" aria-checked={on} aria-label={label} onClick={change} />;
}

export default function Settings({ config, metadata, change, run, initialRun }: { config: Config; metadata: Metadata; change: Change; run: Run | null; initialRun: Run | null }) {
  const [otherOrder, setOtherOrder] = useState(false);
  const p = config.parametros; const official = metadata.config_reto.parametros;
  const channels = Object.keys(p.canal.capacidad_por_corrida);
  const order = p.priorizacion.jerarquia;
  const suggested = [official.priorizacion.jerarquia, ['C-OTT', 'C-TER', 'C-VCH'], ['C-TER', 'C-VCH', 'C-OTT'], order]
    .map(ids => [...ids.filter(id => config.campanas.some(c => c.id === id)), ...order.filter(id => !ids.includes(id))]);
  const orders = [...new Map(suggested.map(ids => [ids.join('>'), ids])).values()];
  const short = (id: string) => config.campanas.find(c => c.id === id)?.producto || id;
  const digital = channels.filter(c => c !== 'asesor');
  const digitalLimit = digital.length ? p.politica_contacto.max_productos_por_canal[digital[0]] : 2;
  const result = run?.metodos.optimo;
  const initialValue = initialRun?.metodos.optimo.valor_esperado;
  const improvement = initialValue !== undefined && metadata.meta > 0 ? initialValue / metadata.meta - 1 : null;
  return <>
    <section className="cl-card"><span className="cl-eyebrow">Paso 1</span><h2>¿Cómo decidimos a quién contactar?</h2>
      <div className="cl-opts" style={{ gridTemplateColumns: '1fr' }}><button type="button" className="cl-opt" aria-pressed="true"><span className="t">Optimizador del equipo</span><span className="d">Reparte los cupos entre todos los clientes para sacar el mayor valor posible.</span></button></div>
      <p className="cl-q">Con la configuración inicial, la referencia del reto es <strong>{oneDecimal.format(metadata.meta)}</strong>{initialValue !== undefined ? <> y nuestro optimizador obtiene <strong>{oneDecimal.format(initialValue)}</strong> de valor esperado{improvement !== null && improvement !== 0 ? <>: <strong>{percent.format(Math.abs(improvement))} {improvement > 0 ? 'más' : 'menos'}</strong></> : null}.</> : <>. Calculando el resultado de nuestro optimizador…</>}</p>
    </section>

    <section className="cl-card"><span className="cl-eyebrow">Paso 2</span><h2>¿Cuántos clientes puede atender cada canal?</h2><p className="cl-q">Selecciona el cupo por corrida. Puedes combinar los cambios de todos los canales antes de enviarlos.</p>
      <div className="cl-chan">{channels.map(c => { const limit = p.politica_contacto.max_productos_por_canal[c]; const used = result?.canales.find(x => x.canal === c); return <div className="cl-chan-card" key={c}><div className="n">{channelName(c)}<span className="u">{limit === 1 ? '1 producto por contacto' : `hasta ${limit} productos`}</span></div><div className="v">{nf.format(p.canal.capacidad_por_corrida[c])}</div><div className="u">{used ? `${nf.format(used.uso)} asignados · ${used.cupo ? percent.format(used.uso / used.cupo) : '—'} del cupo en la última corrida` : 'Pendiente de enviar parámetros'}</div>
        <Choices label={`Cupo ${channelName(c)}`} values={capacities[c] || [0, 1000, 5000, 10000]} current={p.canal.capacidad_por_corrida[c]} official={official.canal.capacidad_por_corrida[c] ?? 0} change={n => change(d => { d.parametros.canal.capacidad_por_corrida[c] = n; })} />
      </div>; })}</div>
    </section>

    <section className="cl-card"><span className="cl-eyebrow">Paso 3</span><h2>¿A quién le ofrecemos y cuánto lo contactamos?</h2><div>
      <Row title="Probabilidad mínima de compra" description="Score de producto desde el que una campaña compite"><Choices label="Probabilidad mínima de compra" values={[.25, .30, .35, .40, .45, .50]} current={p.priorizacion.umbral_score_producto} official={official.priorizacion.umbral_score_producto} max={1} step={.01} format={decimal.format} change={n => change(d => { d.parametros.priorizacion.umbral_score_producto = n; })} /></Row>
      <Row title="Probabilidad mínima de respuesta" description="Score de canal desde el que un canal es opción"><Choices label="Probabilidad mínima de respuesta" values={[.15, .20, .25, .30, .35]} current={p.canal.umbral_score_canal} official={official.canal.umbral_score_canal} max={1} step={.01} format={decimal.format} change={n => change(d => { d.parametros.canal.umbral_score_canal = n; })} /></Row>
      <Row title="Contactos por semana" description="Máximo por cliente, contando los ya recibidos"><Choices label="Contactos por semana" values={[1, 2, 3, 4]} current={p.politica_contacto.max_contactos_semana} official={official.politica_contacto.max_contactos_semana} max={100} change={n => change(d => { d.parametros.politica_contacto.max_contactos_semana = n; })} /></Row>
      {digital.length > 0 && <Row title="Productos por mensaje digital" description={digital.map(channelName).join(', ')}><Choices label="Productos por mensaje digital" values={[1, 2]} current={digitalLimit} official={2} max={2} format={n => `${n} ${n === 1 ? 'producto' : 'productos'}`} change={n => change(d => { for (const c of digital) d.parametros.politica_contacto.max_productos_por_canal[c] = n; })} />{digital.some(c => p.politica_contacto.max_productos_por_canal[c] !== digitalLimit) && <p className="cl-q">Hay límites distintos por canal en opciones avanzadas.</p>}</Row>}
      {channels.includes('asesor') && <Row title="Productos por llamada de asesor"><Choices label="Productos por llamada de asesor" values={[1, 2]} current={p.politica_contacto.max_productos_por_canal.asesor} official={official.politica_contacto.max_productos_por_canal.asesor} max={2} format={n => `${n} ${n === 1 ? 'producto' : 'productos'}`} change={n => change(d => { d.parametros.politica_contacto.max_productos_por_canal.asesor = n; })} /></Row>}
    </div></section>

    <section className="cl-card"><span className="cl-eyebrow">Paso 4</span><h2>Campañas y prioridad</h2><p className="cl-q">Pausa una campaña o cambia qué producto va primero cuando un cliente califica para varios.</p>
      <div className="cl-switches">{config.campanas.map((c, i) => <div className="cl-sw" key={c.id}><div className="meta"><b>{c.nombre}</b><small>{c.producto} · valor de negocio {value.format(c.valor_negocio)}</small></div><Toggle on={c.activa} label={`${c.activa ? 'Pausar' : 'Activar'} ${c.nombre}`} change={() => change(d => { d.campanas[i].activa = !c.activa; })} /></div>)}</div>
      <Row title="Orden de prioridad" description="Jerarquía entre productos"><div className="cl-steps" role="group" aria-label="Orden de prioridad">{orders.map(ids => <button type="button" className="cl-step" key={ids.join('>')} aria-pressed={ids.join('>') === order.join('>')} onClick={() => change(d => { d.parametros.priorizacion.jerarquia = ids; })}>{ids.map(short).join(' › ')}</button>)}<button type="button" className="cl-step" aria-expanded={otherOrder} onClick={() => setOtherOrder(!otherOrder)}>Seleccionar otro</button></div>{otherOrder && <div className="cl-orden">{order.map((id, i) => <div className="cl-orden-item" key={id}><span className="pos">{i + 1}</span><span className="nom">{config.campanas.find(c => c.id === id)?.nombre}</span>{[-1, 1].map(direction => <button className="cl-mini" type="button" key={direction} disabled={i + direction < 0 || i + direction >= order.length} aria-label={`${direction < 0 ? 'Subir' : 'Bajar'} ${short(id)}`} onClick={() => change(d => { const list = d.parametros.priorizacion.jerarquia; [list[i], list[i + direction]] = [list[i + direction], list[i]]; })}>{direction < 0 ? '↑' : '↓'}</button>)}</div>)}</div>}</Row>
      <Row title="Exigir el orden de prioridad" description="El producto elegible preferido siempre va en la oferta"><div className="cl-steps">{([['ponderado', 'No'], ['jerarquia_estricta', 'Sí']] as const).map(([mode, title]) => <button type="button" className="cl-step" key={mode} aria-pressed={p.priorizacion.modo === mode} onClick={() => change(d => { d.parametros.priorizacion.modo = mode; })}>{title}</button>)}</div></Row>
      <Row title="Qué maximiza el optimizador"><div className="cl-steps">{([['valor_esperado', 'Valor esperado'], ['prioridad', 'Puntaje ponderado']] as const).map(([objective, title]) => <button type="button" className="cl-step" key={objective} aria-pressed={p.optimizacion.objetivo === objective} onClick={() => change(d => { d.parametros.optimizacion.objetivo = objective; })}>{title}</button>)}</div></Row>
    </section>

    <section className="cl-card"><span className="cl-eyebrow">Paso 5</span><h2>Reglas del negocio</h2><p className="cl-q">Activa o apaga las reglas del escenario. El resultado se audita también contra las restricciones originales del reto.</p><div className="cl-switches">{config.reglas.map((r, i) => <div className="cl-sw" key={r.id}><div className="meta"><b>{r.nombre}</b><small>{r.id} · control {r.control}</small></div>{!r.activa && metadata.config_reto.reglas.some(x => x.id === r.id && x.activa) && <span className="cl-badge bad">Regla del reto apagada</span>}<Toggle on={r.activa} label={`${r.activa ? 'Apagar' : 'Activar'} ${r.nombre}`} change={() => change(d => { d.reglas[i].activa = !r.activa; })} /></div>)}</div></section>
  </>;
}
