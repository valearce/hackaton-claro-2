import { channelName, nf, percent, value } from '@/lib/api';
import type { Run } from '@/lib/types';

export default function Results({ run, pending, error, meta }: { run: Run | null; pending: boolean; error: string; meta: number }) {
  const result = run?.metodos.optimo;
  return <aside className="results">
    <section className="result-card" aria-busy={pending} aria-label="Resultado de la simulación">
      <span className="eyebrow">Resultado</span>
      <p>Valor esperado del escenario</p>
      <strong className="big-value">{result ? value.format(result.valor_esperado) : '—'}</strong>
      <p className="muted">{result ? `${percent.format(result.valor_esperado / meta - 1)} frente a la referencia de ${value.format(meta)}` : 'Preparando el escenario…'}</p>
      {run && <p className="muted">Fecha del escenario: {run.fecha}</p>}
      <div className="kpis"><div><span>Clientes con acción</span><b>{result ? nf.format(result.clientes) : '—'}</b></div><div><span>Productos ofrecidos</span><b>{result ? nf.format(result.productos) : '—'}</b></div><div><span>Respeto a la jerarquía</span><b>{result?.jerarquia == null ? '—' : percent.format(result.jerarquia)}</b></div><div><span>Controles del escenario</span><b>{result ? result.violaciones === 0 ? 'Cumple' : nf.format(result.violaciones) : '—'}</b></div></div>
      {pending && <div className="notice" role="status">Calculando tus cambios. El resultado visible corresponde a la última simulación completada.</div>}
      {error && <div className="error" role="alert">{error}</div>}
      {result && <>
        <div className={result.violaciones_reto ? 'status bad' : 'status ok'}>{result.violaciones_reto ? `${nf.format(result.violaciones_reto)} incumplimientos respecto del reto original` : 'Cumple las 16 restricciones del reto original'}</div>
        {Object.entries(result.exceso_cupos_reto).map(([key, count]) => <p className="warning" key={key}>{channelName(key)}: {nf.format(count)} contactos por encima del cupo original.</p>)}
        <p className="muted">Certificado: brecha exacta {result.certificado.brecha_exacta}. Objetivo: {result.objetivo === 'prioridad' ? 'prioridad ponderada' : 'valor esperado'}.</p>
        {result.objetivo === 'prioridad' && <p className="muted">Valor del objetivo de prioridad: {result.certificado.valor_objetivo_exacto}. El valor esperado comercial se informa por separado.</p>}
        <p className="muted">Proceso completo: {value.format(result.segundos)} s · motor: {value.format(result.segundos_motor)} s.</p>
        <div className="downloads"><a href={`/api/parrilla/${run!.id}/csv`}>Descargar CSV</a><a href={`/api/parrilla/${run!.id}/certificado`}>Descargar certificado</a></div>
      </>}
    </section>
    {result && <section className="card"><h2>Uso de los canales</h2>{result.canales.map(c => <div className="channel-use" key={c.canal}><div><b>{channelName(c.canal)}</b><span>{nf.format(c.uso)} / {nf.format(c.cupo)}</span></div><progress max={Math.max(c.cupo, 1)} value={c.uso} aria-label={`Uso de ${channelName(c.canal)}`} /></div>)}</section>}
    {result && <section className="card"><h2>Auditoría del reto</h2><div className="checks">{result.controles_reto.map(c => <div key={c.control}><span className={c.violaciones ? 'red' : 'green'}>{c.violaciones ? '✕' : '✓'}</span><span>{c.control} · {c.nombre}</span><b>{nf.format(c.violaciones)}</b></div>)}</div></section>}
  </aside>;
}
