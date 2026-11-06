'use client';

import { useEffect, useState } from 'react';
import { api, channelName, nf, percent } from '@/lib/api';
import type { Config, Row, Run } from '@/lib/types';

const valueOne = new Intl.NumberFormat('es-CO', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const percentWhole = new Intl.NumberFormat('es-CO', { style: 'percent', maximumFractionDigits: 0 });
const witnessIds = ['CL000018', 'CL000020', 'CL000039', 'CL000089', 'CL000741'];
const auditGroups = [
  ['A quién ofrecer', ['R01', 'R07', 'R08', 'R06', 'R02', 'R03', 'R04', 'R05']],
  ['Por qué canal', ['R09', 'R10', 'R11', 'R12']],
  ['Cuánto contactar', ['R13', 'R14', 'R15', 'R16']],
] as const;

type Witnesses = { runId: string; rows: Row[]; error: string };

function Gauge({ channel, used, capacity }: { channel: string; used: number; capacity: number }) {
  const ratio = capacity > 0 ? Math.min(1, Math.max(0, used / capacity)) : 0;
  const circumference = Math.PI * 2 * 51;
  const name = channelName(channel);
  return <div className="cl-gauge">
    <svg width="150" height="170" viewBox="0 0 150 170" role="img" aria-label={`${name}: ${nf.format(used)} asignados de ${nf.format(capacity)} cupos`}>
      <title>{name}: {nf.format(used)} asignados de {nf.format(capacity)} cupos</title>
      <circle cx="75" cy="75" r="51" fill="none" stroke="#EEEFF1" strokeWidth="14" />
      {ratio > 0 && <circle cx="75" cy="75" r="51" fill="none" stroke={capacity > 0 && used >= capacity ? '#E12F20' : '#1D1D1F'} strokeWidth="14" strokeLinecap="round" strokeDasharray={`${ratio * circumference} ${circumference}`} transform="rotate(-90 75 75)" />}
      <text x="75" y="77" textAnchor="middle" fontSize="24" fontWeight="700" fill="#1D1D1F">{capacity > 0 ? percentWhole.format(used / capacity) : '—'}</text>
      <text x="75" y="95" textAnchor="middle" fontSize="9.5" fill="#5E6166">{nf.format(used)} / {nf.format(capacity)}</text>
      <text x="75" y="164" textAnchor="middle" fontSize="13" fontWeight="700" fill="#1D1D1F">{name}</text>
    </svg>
  </div>;
}

export default function Campaigns({ run, config, pending, changes }: { run: Run | null; config: Config | null; pending: boolean; changes: string[] }) {
  const [witnesses, setWitnesses] = useState<Witnesses | null>(null);
  const [retry, setRetry] = useState(0);
  const runId = run?.id;

  useEffect(() => {
    if (!runId) return;
    const controller = new AbortController();
    void Promise.allSettled(witnessIds.map(id => {
      const params = new URLSearchParams({ q: id, por_pagina: '1' });
      return api<{ filas: Row[] }>(`/api/parrilla/${runId}?${params}`, undefined, controller.signal)
        .then(data => data.filas.find(row => row.id_cliente === id));
    })).then(outcomes => {
      if (controller.signal.aborted) return;
      const rows = outcomes.flatMap(outcome => outcome.status === 'fulfilled' && outcome.value ? [outcome.value] : []);
      const missing = witnessIds.length - rows.length;
      setWitnesses({ runId, rows, error: missing ? `No se pudieron recuperar ${missing} de los cinco casos del kit.` : '' });
    });
    return () => controller.abort();
  }, [runId, retry]);

  if (!run || !config) return <section className="cl-card"><h2>Campañas del escenario</h2><p className="cl-q">Envía los parámetros desde Inicio para consultar las campañas y los resultados de la simulación.</p></section>;

  const result = run.metodos.optimo;
  const campaignCounts = new Map(result.campanas.map(campaign => [campaign.id, campaign.ofertas]));
  const totalOffers = result.campanas.reduce((sum, campaign) => sum + campaign.ofertas, 0);
  const order = [...config.parametros.priorizacion.jerarquia, ...config.campanas.map(campaign => campaign.id).filter(id => !config.parametros.priorizacion.jerarquia.includes(id))];
  const controls = new Map(result.controles_reto.map(control => [control.control, control]));
  const witnessData = witnesses?.runId === run.id ? witnesses : null;
  const witnessLoading = !witnessData;

  return <>
    <div className="cl-kpis">
      <div className="cl-kpi"><span className="k">Valor esperado</span><span className="v">{valueOne.format(result.valor_esperado)}</span><span className="d">{percent.format(result.valor_esperado / 10241.5 - 1)} frente a la cifra a superar</span></div>
      <div className="cl-kpi"><span className="k">Clientes contactados</span><span className="v">{nf.format(result.clientes)}</span><span className="d">de {nf.format(result.total_clientes)} en la base</span></div>
      <div className="cl-kpi"><span className="k">Productos ofrecidos</span><span className="v">{nf.format(result.productos)}</span><span className="d">según los límites del escenario</span></div>
      <div className="cl-kpi"><span className="k">Reglas del reto</span><span className="v" style={{ color: result.violaciones_reto ? '#B3241A' : '#1E7F45' }}>{result.violaciones_reto ? nf.format(result.violaciones_reto) : 'Cumple'}</span><span className="d">incumplimientos medidos por el auditor</span></div>
    </div>

    <section className="cl-card"><span className="cl-eyebrow">Escenario</span><p className="cl-q">Esta página describe la última simulación enviada desde Inicio, con fecha {run.fecha}. Cambios frente al reto: <b>{changes.length ? changes.join(' · ') : 'ninguno, configuración original del reto'}</b>.</p>{pending && <p className="cl-q" role="status">Hay cambios pendientes en Inicio. Esta vista corresponde a la última simulación completada.</p>}</section>

    <h2 style={{ margin: 0, fontSize: 18 }}>Campañas</h2>
    <div className="cl-grid3">{config.campanas.map(campaign => {
      const offers = campaignCounts.get(campaign.id) ?? 0;
      return <article className={`cl-card cl-camp${campaign.activa ? '' : ' paused'}`} key={campaign.id}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'baseline' }}><h3>{campaign.nombre}</h3><span className={`cl-badge ${campaign.activa ? 'ok' : 'bad'}`}>{campaign.activa ? 'Activa' : 'Pausada'}</span></div>
        <div style={{ fontSize: 30, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{nf.format(offers)}</div>
        <p className="cl-q">ofertas · {totalOffers ? percent.format(offers / totalOffers) : '—'} del total</p>
        <div className="cl-chips">{campaign.canales_permitidos.map(channel => <span className="cl-chip" key={channel}>{channelName(channel)}</span>)}</div>
        <dl className="cl-dl"><dt>Producto</dt><dd>{campaign.producto}</dd><dt>Objetivo</dt><dd>{campaign.objetivo}</dd><dt>Valor de negocio</dt><dd>{valueOne.format(campaign.valor_negocio)}</dd><dt>Prioridad</dt><dd>{order.indexOf(campaign.id) + 1}</dd><dt>Vigencia</dt><dd>{campaign.vigencia_inicio} a {campaign.vigencia_fin}</dd></dl>
      </article>;
    })}</div>

    <section className="cl-card"><h2>Uso de los cupos</h2><p className="cl-q">Clientes asignados a cada canal frente a su cupo. Un canal lleno en rojo es el que limita el valor.</p><div className="cl-grid4">{result.canales.map(channel => <Gauge key={channel.canal} channel={channel.canal} used={channel.uso} capacity={channel.cupo} />)}</div></section>

    <section className="cl-card"><h2>Verificación de las 16 restricciones del reto</h2><p className="cl-q">El auditor del modelo revisa cada cliente de la parrilla contra todas las restricciones del reto.</p><div className="cl-checks">{auditGroups.map(([label, ids]) => <div className="cl-card" key={label} style={{ padding: 16 }}><h3>{label}</h3><div className="cl-check-list">{ids.map(id => {
      const control = controls.get(id);
      const state = control ? control.violaciones ? 'bad' : 'ok' : '';
      return <div className="cl-check" key={id}><span className={`cl-ico ${state}`}>{control ? control.violaciones ? '✕' : '✓' : '—'}</span><span>{id} · {control?.nombre || 'Control no disponible'}</span><span style={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums', color: control ? control.violaciones ? '#B3241A' : '#1E7F45' : '#5E6166' }}>{control ? nf.format(control.violaciones) : '—'}</span></div>;
    })}</div></div>)}</div>{Object.entries(result.exceso_cupos_reto).map(([channel, excess]) => <p className="cl-q" key={channel}>{channelName(channel)}: {nf.format(excess)} contactos por encima del cupo original.</p>)}</section>

    <section className="cl-card"><h2>Clientes de ejemplo del kit</h2><p className="cl-q">Los cinco casos que publicó el reto, con la decisión que toma el modelo en este escenario.</p>{witnessData?.error && <div className="cl-error" role="alert">{witnessData.error} <button className="cl-step" type="button" onClick={() => { setWitnesses(null); setRetry(attempt => attempt + 1); }}>Reintentar</button></div>}<div className="cl-table-wrap" aria-busy={witnessLoading}><table><thead><tr>{['Cliente', 'Estado', 'Canal', 'Campaña 1', 'Campaña 2', 'Razón'].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>{witnessLoading ? <tr><td colSpan={6} role="status">Consultando los casos de esta simulación…</td></tr> : witnessData.rows.map(row => <tr key={row.id_cliente}><td>{row.id_cliente}</td><td><span className={`cl-pill ${row.estado}`}>{row.estado === 'asignado' ? 'Con acción' : 'Sin acción'}</span></td><td>{row.canal ? <span className={`cl-pill ${row.canal}`}>{channelName(row.canal)}</span> : '—'}</td><td>{row.campana_1 || '—'}</td><td>{row.campana_2 || '—'}</td><td className="razon">{row.razon}</td></tr>)}</tbody></table></div></section>
  </>;
}
