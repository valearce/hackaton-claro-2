'use client';
import { channelName, nf, percent, value } from '@/lib/api';
import type { Run } from '@/lib/types';

const oneDecimal = new Intl.NumberFormat('es-CO', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
function Trend({ history, meta }: { history: Run[]; meta: number }) {
  const rows = [...history].reverse();
  const values = rows.map(r => r.metodos.optimo.valor_esperado);
  const low = Math.min(meta, ...values) * .98;
  const high = Math.max(meta, ...values) * 1.02;
  const y = (n: number) => 175 - (n - low) / Math.max(high - low, 1) * 145;
  const x = (i: number) => rows.length === 1 ? 170 : 45 + i / Math.max(rows.length - 1, 1) * 250;
  return <section className="cl-card"><h3>Valor según el cambio</h3><p className="cl-q">Cada punto es un escenario enviado. La línea punteada es la cifra a superar.</p><div className="cl-chart">
    {rows.length === 0 ? <p className="cl-q" style={{ paddingTop: 65, textAlign: 'center' }}>Envía tus parámetros para ver el primer resultado.</p> : <svg className="cl-trend" viewBox="0 0 330 220" role="img" aria-label="Valor esperado de los escenarios enviados">
      <line x1="45" x2="305" y1={y(meta)} y2={y(meta)} stroke="#8A8D93" strokeDasharray="5 4" /><text x="45" y={y(meta) - 6} fontSize="10" fill="#5E6166">Meta {oneDecimal.format(meta)}</text>
      <line x1="45" x2="305" y1="185" y2="185" stroke="#E4E5E7" />
      {rows.length > 1 && <polyline points={values.map((n, i) => `${x(i)},${y(n)}`).join(' ')} fill="none" stroke="#E12F20" strokeWidth="2" />}
      {rows.map((r, i) => <g key={r.id}><circle cx={x(i)} cy={y(r.metodos.optimo.valor_esperado)} r="5" fill="#E12F20"><title>{`Escenario ${i + 1}: ${value.format(r.metodos.optimo.valor_esperado)} · ${r.metodos.optimo.violaciones_reto ? 'con incumplimientos del reto' : 'cumple el reto'}`}</title></circle><text x={x(i)} y="202" textAnchor="middle" fontSize="10" fill="#5E6166">{i + 1}</text></g>)}
    </svg>}
  </div></section>;
}

export default function Results({ run, busy, dirty, error, meta, changes, history, reset, restoreCapacity, submit }: {
  run: Run | null; busy: boolean; dirty: boolean; error: string; meta: number; changes: string[]; history: Run[]; reset: () => void; restoreCapacity: (c: string) => void; submit: () => void;
}) {
  const r = run?.metodos.optimo;
  const reference = run?.referencia;
  const scale = Math.max(meta * 1.2, (r?.valor_esperado || 0) * 1.05);
  const sign = (n: number) => `${n >= 0 ? '+' : '−'}${nf.format(Math.abs(n))}`;
  return <>
    <section className="cl-card cl-res" aria-label="Resultado de la simulación" aria-busy={busy}>
      <div className="cl-result-total"><span className="cl-eyebrow">Resultado</span><p className="cl-q">Valor esperado del escenario</p><div className="cl-big">{r ? oneDecimal.format(r.valor_esperado) : '—'}</div></div>
      <div className="cl-meta-bar" aria-hidden="true"><div className="cl-meta-fill" style={{ width: `${(r?.valor_esperado || 0) / scale * 100}%` }} /><div className="cl-meta-tick" style={{ left: `${meta / scale * 100}%` }} /></div>
      <p className="cl-q">{r ? r.violaciones_reto ? `Comparación informativa: ${percent.format(r.valor_esperado / meta - 1)} frente a ${oneDecimal.format(meta)}. Este escenario cambia restricciones del reto.` : `${percent.format(r.valor_esperado / meta - 1)} frente a la cifra a superar de ${oneDecimal.format(meta)}` : `Cifra a superar: ${oneDecimal.format(meta)}`}</p>
      <div className="cl-res-grid">
        <div><div className="k">Clientes con acción</div><div className="v">{r ? nf.format(r.clientes) : '—'}</div><div className="d cl-flat">{r && reference ? `${sign(r.clientes - reference.clientes_con_accion)} vs. referencia` : '—'}</div></div>
        <div><div className="k">Productos ofrecidos</div><div className="v">{r ? nf.format(r.productos) : '—'}</div><div className="d cl-flat">{r && reference ? `${sign(r.productos - reference.productos_asignados)} vs. referencia` : '—'}</div></div>
        <div className="cl-baseline-metric"><div className="k">Frente a la línea base</div><div className="v">{r && reference && reference.valor_esperado > 0 ? percent.format(r.valor_esperado / reference.valor_esperado - 1) : '—'}</div><div className="d cl-flat">referencia histórica del reto</div></div>
        <div><div className="k">Respeto a la prioridad</div><div className="v">{r?.jerarquia == null ? '—' : percent.format(r.jerarquia)}</div><div className="d cl-flat">del escenario enviado</div></div>
      </div>
      {r && <>
        <div className={`cl-status ${r.violaciones ? 'bad' : 'ok'}`}>{r.violaciones ? 'Revisar parámetros enviados' : '✓ Cumple los parámetros enviados'} · {nf.format(r.violaciones)} violaciones</div>
        <div className={`cl-status ${r.violaciones_reto ? 'bad' : 'ok'}`}>{r.violaciones_reto ? `No cumple el reto original: ${nf.format(r.violaciones_reto)} ${r.violaciones_reto === 1 ? 'control incumplido' : 'controles incumplidos'}` : '✓ Cumple las 16 restricciones del reto original'}</div>
        {Object.entries(r.exceso_cupos_reto).map(([c, n]) => <div key={c}><p className="cl-down">{channelName(c)}: {nf.format(n)} contactos por encima del cupo original.</p><button className="cl-btn" type="button" disabled={busy} onClick={() => restoreCapacity(c)}>Restaurar cupo de {channelName(c)}</button></div>)}
        <div className="cl-acciones"><a className="cl-btn" href={`/api/parrilla/${run.id}/csv`}>Descargar CSV</a></div>
      </>}
      {busy && <p className="cl-pend" role="status"><span className="cl-spinner" />Procesando la solicitud enviada…</p>}
      {!busy && dirty && <p className="cl-pend" role="status">{r ? 'Hay cambios pendientes de enviar. El resultado visible corresponde a la última corrida completada.' : 'Prepara tus opciones y pulsa Enviar parámetros.'}</p>}
      {error && <p className="cl-error" role="alert">{error}</p>}
      <div className="cl-change"><small>Cambios frente al reto</small>{changes.length ? <ul className="cl-cambios">{changes.map((c, i) => <li key={i}>{c}</li>)}</ul> : <span>Configuración original del reto</span>}</div>
      <button type="button" className="cl-cta cl-submit" disabled={busy || (!!run && !dirty)} onClick={submit}>{busy ? 'Procesando parámetros…' : 'Enviar parámetros'}</button>
      <button type="button" className="cl-btn" disabled={busy} onClick={reset}>Volver a la configuración del reto</button>
    </section>
    <Trend history={history} meta={meta} />
  </>;
}
