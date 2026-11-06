'use client';

import { useEffect, useRef, useState } from 'react';
import { api, channelName, nf, value } from '@/lib/api';
import type { Change, Config, Metadata, Run } from '@/lib/types';
import AdvancedSettings from './advanced-settings';
import Grid from './grid';

type Column = { nombre: string; tipo: 'numero' | 'texto'; vacios: number; unicos: number; clave: boolean; score: boolean };
type Table = { id: string; nombre: string; archivo: string; filas: number; columnas: Column[] };
type Join = { tabla: string; izquierda: string; derecha: string };
type Base = { id: string; nombre: string; clientes: number; columnas: Column[]; datos_sha256: string; config: Config; avisos: string[]; fuentes: { nombre: string; filas: number }[] };
const idNames = ['id_cliente', 'cliente_id', 'customer_id', 'id_customer', 'documento', 'cedula', 'identificacion', 'id'];
const storageKey = 'claro-nba:base:v1';
const slug = (text: string) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 48);

function preferredKey(table: Table) {
  return table.columnas.find(column => column.clave && idNames.includes(column.nombre))?.nombre || table.columnas.find(column => column.clave)?.nombre || '';
}

function suggestJoins(tables: Table[], main: Table): Join[] {
  return tables.filter(table => table.id !== main.id).map(table => {
    const exact = table.columnas.find(column => column.clave && idNames.includes(column.nombre) && main.columnas.some(left => left.nombre === column.nombre));
    const right = exact?.nombre || preferredKey(table);
    const left = exact?.nombre || preferredKey(main);
    return { tabla: table.id, izquierda: left, derecha: right };
  });
}

export default function DataWorkbench() {
  const [tables, setTables] = useState<Table[]>([]);
  const [principal, setPrincipal] = useState(''), [idColumn, setIdColumn] = useState('');
  const [joins, setJoins] = useState<Join[]>([]);
  const [base, setBase] = useState<Base | null>(null), [config, setConfig] = useState<Config | null>(null);
  const [run, setRun] = useState<Run | null>(null), [runConfig, setRunConfig] = useState<Config | null>(null), [sent, setSent] = useState('');
  const [date, setDate] = useState('2026-11-05');
  const [busy, setBusy] = useState(false), [status, setStatus] = useState(''), [error, setError] = useState('');
  const [accepted, setAccepted] = useState(false);
  const [productScore, setProductScore] = useState(''), [productName, setProductName] = useState('');
  const [channelScore, setChannelScore] = useState(''), [channel, setChannel] = useState('');
  const alive = useRef(true), running = useRef(false);
  const signature = config && base ? JSON.stringify({ base: base.id, config, date }) : '';
  const stale = !!run && sent !== signature;

  function adopt(next: Base) {
    setBase(next); setConfig(next.config); setRun(null); setRunConfig(null); setSent(''); setAccepted(false);
    const first = next.columnas.find(column => column.score)?.nombre || '';
    setProductScore(first); setChannelScore(first);
    try { localStorage.setItem(storageKey, next.id); } catch { /* La base también funciona sin almacenamiento del navegador. */ }
  }

  useEffect(() => {
    alive.current = true;
    const controller = new AbortController();
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved && /^[a-f0-9]{32}$/.test(saved)) {
        void api<Base>(`/api/datos/bases/${saved}`, undefined, controller.signal).then(next => {
          if (!controller.signal.aborted) adopt(next);
        }).catch(failure => { if (!controller.signal.aborted) setError(`No se pudo recuperar la base anterior: ${(failure as Error).message}`); });
      }
    } catch { /* El almacenamiento del navegador es opcional. */ }
    return () => { alive.current = false; controller.abort(); };
  }, []);

  const change: Change = fn => {
    setConfig(previous => { if (!previous) return previous; const draft = structuredClone(previous); fn(draft); return draft; });
    setError('');
  };

  async function upload(files: FileList | null) {
    if (!files?.length || running.current) return;
    if (files.length > 10) { setError('Selecciona hasta diez archivos por carga.'); return; }
    running.current = true; setBusy(true); setError('');
    try {
      const received: Table[] = [];
      for (const file of Array.from(files)) {
        if (!file.size || file.size > 32 * 1024 * 1024) throw new Error('Cada archivo debe pesar entre 1 byte y 32 MB.');
        setStatus(`Leyendo ${file.name}…`);
        const buffer = await file.arrayBuffer();
        const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', buffer)), byte => byte.toString(16).padStart(2, '0')).join('');
        const load = await api<{ id: string; tamano_parte: number }>('/api/datos/archivos', { nombre: file.name, bytes: file.size, sha256: hash });
        for (let offset = 0; offset < buffer.byteLength; offset += load.tamano_parte) {
          if (!alive.current) return;
          setStatus(`Cargando ${file.name} · ${Math.round(offset / buffer.byteLength * 100)} %`);
          const response = await fetch(`/api/datos/archivos/${load.id}/partes/${offset / load.tamano_parte}`, { method: 'PUT', headers: { 'Content-Type': 'application/octet-stream' }, body: buffer.slice(offset, offset + load.tamano_parte) });
          if (!response.ok) { const failure = await response.json().catch(() => null); throw new Error(failure?.detail || 'No se pudo completar la carga.'); }
        }
        setStatus(`Identificando tablas y columnas de ${file.name}…`);
        const result = await api<{ tablas: Table[] }>(`/api/datos/archivos/${load.id}/analizar`, {});
        received.push(...result.tablas);
      }
      if (!alive.current) return;
      if (received.length > 10) throw new Error('Carga hasta diez tablas en total. Divide el Excel o los archivos.');
      const first = received.find(table => table.columnas.some(column => column.clave && idNames.includes(column.nombre))) || received[0];
      setTables(received); setPrincipal(first.id); setIdColumn(preferredKey(first)); setJoins(suggestJoins(received, first));
      setBase(null); setConfig(null); setRun(null); setRunConfig(null); setStatus(`${received.length} ${received.length === 1 ? 'tabla identificada' : 'tablas identificadas'}. Revisa las relaciones.`);
    } catch (failure) { if (alive.current) { setError((failure as Error).message); setStatus(''); } }
    finally { running.current = false; if (alive.current) setBusy(false); }
  }

  async function prepare() {
    if (running.current) return;
    running.current = true; setBusy(true); setError(''); setStatus('Uniendo tablas y reconstruyendo la configuración…');
    try {
      const next = await api<Base>('/api/datos/preparar', { principal, id_columna: idColumn, uniones: joins });
      if (alive.current) { adopt(next); setStatus('Base preparada. Revisa las campañas, los canales y las reglas.'); }
    } catch (failure) { if (alive.current) { setError((failure as Error).message); setStatus(''); } }
    finally { running.current = false; if (alive.current) setBusy(false); }
  }

  async function simulate() {
    if (!base || !config || running.current) return;
    if (!accepted || !config.campanas.length || !Object.keys(config.parametros.canal.columnas_score).length || !config.parametros.politica_contacto.columna_contactos_semana) {
      setError('Completa los datos del modelo y confirma la revisión de reglas antes de ejecutar.'); return;
    }
    running.current = true; setBusy(true); setError(''); setStatus('Reconstruyendo y resolviendo la asignación con la base cargada…');
    const snapshot = structuredClone(config), submitted = signature;
    try {
      const result = await api<Run>(`/api/datos/bases/${base.id}/simular`, { config: snapshot, fecha: date });
      if (alive.current) { setRun(result); setRunConfig(snapshot); setSent(submitted); setStatus('Asignación reconstruida y validada. La nueva parrilla está lista.'); }
    } catch (failure) { if (alive.current) { setError((failure as Error).message); setStatus(''); } }
    finally { running.current = false; if (alive.current) setBusy(false); }
  }

  const main = tables.find(table => table.id === principal);
  const scores = base?.columnas.filter(column => column.score) || [];
  const metadata: Metadata | null = base && config ? {
    config, config_reto: base.config, fecha: date, version_activa: null, meta: 0, clientes: base.clientes,
    columnas: base.columnas.map(column => column.nombre), tipos_columnas: Object.fromEntries(base.columnas.map(column => [column.nombre, column.tipo])),
    referencia: { valor_esperado: 0, clientes_con_accion: 0, productos_asignados: 0 },
  } : null;

  return <div className="cl-data">
    <header className="cl-data-title"><p className="cl-eyebrow">Datos y adaptabilidad</p><h2>Una base nueva. Una nueva asignación.</h2><p className="cl-q">Carga tus tablas, revisa lo que detectamos y vuelve a construir la parrilla con tus datos y reglas.</p></header>
    <section className="cl-card"><span className="cl-eyebrow">Paso 1 · Cargar</span><h2>Identificar las tablas</h2><p className="cl-q">CSV, TSV, Excel XLSX o JSON. Cada hoja de Excel se identifica como una tabla. Hasta diez tablas, 100.000 filas por tabla y 32 MB por archivo.</p>
      <label className="cl-data-upload">Seleccionar archivos<input type="file" accept=".csv,.tsv,.xlsx,.json" multiple disabled={busy} onChange={event => { void upload(event.target.files); event.target.value = ''; }} /></label>
      <p className="cl-q">Los encabezados se normalizan para reconocerlos: «ID Cliente» pasa a «id_cliente». Las columnas nuevas quedan disponibles para crear reglas.</p>
    </section>
    {tables.length > 0 && <section className="cl-card"><span className="cl-eyebrow">Paso 2 · Relacionar</span><h2>Una fila por cliente</h2><div className="cl-data-fields">
      <label>Tabla principal<select value={principal} disabled={busy} onChange={event => { const table = tables.find(item => item.id === event.target.value)!; setPrincipal(table.id); setIdColumn(preferredKey(table)); setJoins(suggestJoins(tables, table)); setBase(null); setConfig(null); setRun(null); }}>
        {tables.map(table => <option value={table.id} key={table.id}>{table.nombre} · {nf.format(table.filas)} filas</option>)}
      </select></label>
      <label>Identificador del cliente<select value={idColumn} disabled={busy} onChange={event => { setIdColumn(event.target.value); setBase(null); setConfig(null); setRun(null); }}><option value="">Selecciona una clave única</option>{main?.columnas.filter(column => column.clave).map(column => <option key={column.nombre}>{column.nombre}</option>)}</select></label>
    </div>
    {tables.filter(table => table.id !== principal).map(table => { const join = joins.find(item => item.tabla === table.id); return <div className="cl-data-join" key={table.id}><label className="cl-data-check"><input type="checkbox" checked={!!join} disabled={busy} onChange={event => { setJoins(previous => event.target.checked ? [...previous, { tabla: table.id, izquierda: idColumn, derecha: preferredKey(table) }] : previous.filter(item => item.tabla !== table.id)); setBase(null); setConfig(null); setRun(null); }} />Incorporar {table.nombre} · {nf.format(table.filas)} filas</label>{join && <div className="cl-data-fields"><label>Columna en la tabla principal<select value={join.izquierda} disabled={busy} onChange={event => { setJoins(previous => previous.map(item => item.tabla === table.id ? { ...item, izquierda: event.target.value } : item)); setBase(null); setConfig(null); setRun(null); }}><option value="">Selecciona una columna</option>{main?.columnas.map(column => <option key={column.nombre}>{column.nombre}</option>)}</select></label><label>Clave en {table.nombre}<select value={join.derecha} disabled={busy} onChange={event => { setJoins(previous => previous.map(item => item.tabla === table.id ? { ...item, derecha: event.target.value } : item)); setBase(null); setConfig(null); setRun(null); }}><option value="">Selecciona una clave única</option>{table.columnas.filter(column => column.clave).map(column => <option key={column.nombre}>{column.nombre}</option>)}</select></label></div>}</div>; })}
    <p className="cl-q">Las relaciones sugeridas se basan en claves comunes. Se comprueba que cada cliente tenga correspondencia y que la unión conserve el número de filas.</p>
    {tables.map(table => <details className="cl-data-schema" key={table.id}><summary>{table.nombre} · {table.columnas.length} columnas detectadas</summary><div className="cl-table-wrap"><table><thead><tr><th>Columna</th><th>Tipo</th><th>Vacíos</th><th>Identificación</th></tr></thead><tbody>{table.columnas.map(column => <tr key={column.nombre}><td>{column.nombre}</td><td>{column.tipo}</td><td>{nf.format(column.vacios)}</td><td>{column.clave ? 'Clave única' : column.score ? 'Probabilidad válida (0–1)' : 'Atributo'}</td></tr>)}</tbody></table></div></details>)}
    <button type="button" className="cl-cta" disabled={busy || !idColumn || joins.some(join => !join.izquierda || !join.derecha)} onClick={() => void prepare()}>Preparar el modelo con estas tablas</button>
    </section>}
    {base && config && metadata && <>
      <section className="cl-card"><span className="cl-eyebrow">Paso 3 · Revisar el modelo</span><h2>{base.nombre} · {nf.format(base.clientes)} clientes</h2><p className="cl-q">{base.fuentes.map(source => source.nombre).join(' + ')} · {base.columnas.length} columnas. Detectamos {config.campanas.length} campañas y {Object.keys(config.parametros.canal.columnas_score).length} canales a partir de los nombres de sus scores.</p>
        {base.avisos.map(warning => <p className="cl-data-notice" key={warning}>{warning}</p>)}
        <div className="cl-data-fields"><label>Columna de contactos semanales<select disabled={busy} value={config.parametros.politica_contacto.columna_contactos_semana || ''} onChange={event => change(draft => { draft.parametros.politica_contacto.columna_contactos_semana = event.target.value; })}><option value="">Selecciona el contador real</option>{base.columnas.filter(column => column.tipo === 'numero').map(column => <option key={column.nombre}>{column.nombre}</option>)}</select></label></div>
        <div className="cl-data-fields">{config.campanas.map((campaign, index) => <label key={campaign.id}>Score de {campaign.nombre}<select disabled={busy} value={campaign.columna_score} onChange={event => change(draft => { draft.campanas[index].columna_score = event.target.value; })}>{scores.map(column => <option key={column.nombre}>{column.nombre}</option>)}</select></label>)}</div>
        <div className="cl-data-fields">{Object.entries(config.parametros.canal.columnas_score).map(([id, score]) => <label key={id}>Score de respuesta por {channelName(id)}<select disabled={busy} value={score} onChange={event => change(draft => { draft.parametros.canal.columnas_score[id] = event.target.value; })}>{scores.map(column => <option key={column.nombre}>{column.nombre}</option>)}</select></label>)}</div>
        <details className="cl-data-schema"><summary>Asignar columnas con otros nombres a campañas y canales</summary>
          <form className="cl-data-fields" onSubmit={event => { event.preventDefault(); if (!productScore || !productName.trim()) return; change(draft => { const id = `C-${crypto.randomUUID().slice(0, 8)}`; draft.campanas.push({ id, nombre: productName.trim(), producto: id, objetivo: 'Oferta de la base cargada', columna_score: productScore, valor_negocio: 1, canales_permitidos: Object.keys(draft.parametros.canal.columnas_score), vigencia_inicio: '2000-01-01', vigencia_fin: '2099-12-31', activa: true }); draft.parametros.priorizacion.jerarquia.push(id); }); setProductName(''); }}>
            <label>Nombre de campaña<input value={productName} onChange={event => setProductName(event.target.value)} maxLength={200} required /></label><label>Probabilidad del producto<select value={productScore} onChange={event => setProductScore(event.target.value)} required><option value="">Selecciona un score</option>{scores.map(column => <option key={column.nombre}>{column.nombre}</option>)}</select></label><button className="cl-step" disabled={busy || config.campanas.length >= 20}>Agregar campaña</button>
          </form>
          <form className="cl-data-fields" onSubmit={event => { event.preventDefault(); const id = slug(channel); if (!id || !channelScore) return; if (id in config.parametros.canal.columnas_score) { setError('Ese canal ya existe. Puedes editar su score más abajo.'); return; } change(draft => { draft.parametros.canal.columnas_score[id] = channelScore; draft.parametros.canal.capacidad_por_corrida[id] = 0; draft.parametros.canal.orden_preferencia.push(id); draft.parametros.politica_contacto.max_productos_por_canal[id] = 1; }); setChannel(''); }}>
            <label>Canal nuevo<input value={channel} onChange={event => setChannel(event.target.value)} placeholder="Ej.: push" maxLength={48} required /></label><label>Probabilidad de respuesta<select value={channelScore} onChange={event => setChannelScore(event.target.value)} required><option value="">Selecciona un score</option>{scores.map(column => <option key={column.nombre}>{column.nombre}</option>)}</select></label><button className="cl-step" disabled={busy || Object.keys(config.parametros.canal.columnas_score).length >= 20}>Agregar canal con cupo cero</button>
          </form>
        </details>
        {!scores.length && <p className="cl-error">No hay columnas completas con valores entre 0 y 1. Incorpora una tabla con scores de producto y canal para construir la asignación.</p>}
      </section>
      <fieldset className="cl-data-config advanced-editor" disabled={busy}><legend className="cl-eyebrow">Campañas, canales y reglas de la nueva base</legend><AdvancedSettings key={base.id} config={config} metadata={metadata} change={change} date={date} setDate={setDate} /></fieldset>
      <section className="cl-card"><span className="cl-eyebrow">Paso 4 · Reconstruir</span><h2>Calcular la nueva asignación</h2><label className="cl-data-check"><input type="checkbox" checked={accepted} disabled={busy} onChange={event => setAccepted(event.target.checked)} />Revisé los scores, los cupos, las autorizaciones y las reglas aplicables a esta base.</label><div className="cl-acciones"><button type="button" className="cl-cta" disabled={busy || !accepted || !config.campanas.length || !Object.keys(config.parametros.canal.columnas_score).length || !config.parametros.politica_contacto.columna_contactos_semana || (!!run && !stale)} onClick={() => void simulate()}>{busy ? 'Procesando…' : 'Reconstruir asignación'}</button></div><p className="cl-q">El resultado corresponde a los datos cargados y a la configuración revisada. La referencia del reto de 100.000 clientes no se compara con esta base.</p></section>
      {run && <section className="cl-card"><span className="cl-eyebrow">Nueva parrilla</span><h2>Asignación reconstruida</h2><div className="cl-data-metrics"><div><span>Valor esperado</span><strong>{value.format(run.metodos.optimo.valor_esperado)}</strong></div><div><span>Clientes con acción</span><strong>{nf.format(run.metodos.optimo.clientes)} / {nf.format(run.metodos.optimo.total_clientes)}</strong></div><div><span>Violaciones</span><strong>{run.metodos.optimo.violaciones}</strong></div><div><span>Productos asignados</span><strong>{nf.format(run.metodos.optimo.productos)}</strong></div></div><p className="cl-q">{run.metodos.optimo.canales.map(item => `${channelName(item.canal)}: ${nf.format(item.uso)} / ${nf.format(item.cupo)}`).join(' · ')}</p>{stale && <p className="cl-data-notice" role="status">Hay cambios pendientes. La parrilla corresponde a la última reconstrucción completada.</p>}<Grid key={run.id} run={run} config={runConfig} /></section>}
    </>}
    {status && <p className="cl-data-progress" role="status" aria-live="polite">{busy && <span className="cl-spinner" />}{status}</p>}
    {error && <p className="cl-error" role="alert">{error}</p>}
  </div>;
}
