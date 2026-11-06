import { channelName, nf } from './api';
import type { Config } from './types';

export function scenarioChanges(config: Config, official: Config, date: string): string[] {
  const out: string[] = [];
  const p = config.parametros; const r = official.parametros;
  if (date !== '2026-11-05') out.push(`Fecha: ${date}`);
  for (const [id, n] of Object.entries(p.canal.capacidad_por_corrida)) {
    if (r.canal.capacidad_por_corrida[id] !== n) out.push(`${channelName(id)}: ${nf.format(n)} cupos`);
    if (p.politica_contacto.max_productos_por_canal[id] !== r.politica_contacto.max_productos_por_canal[id]) out.push(`${channelName(id)}: ${p.politica_contacto.max_productos_por_canal[id]} productos por contacto`);
    if (p.canal.columnas_score[id] !== r.canal.columnas_score[id]) out.push(`Score ${channelName(id)}: ${p.canal.columnas_score[id]}`);
  }
  if (p.priorizacion.umbral_score_producto !== r.priorizacion.umbral_score_producto) out.push(`Score de producto: ${p.priorizacion.umbral_score_producto}`);
  if (p.canal.umbral_score_canal !== r.canal.umbral_score_canal) out.push(`Score de canal: ${p.canal.umbral_score_canal}`);
  if (p.politica_contacto.max_contactos_semana !== r.politica_contacto.max_contactos_semana) out.push(`Contactos por semana: ${p.politica_contacto.max_contactos_semana}`);
  if (p.priorizacion.jerarquia.join() !== r.priorizacion.jerarquia.join()) out.push(`Prioridad: ${p.priorizacion.jerarquia.map(id => config.campanas.find(c => c.id === id)?.producto || id).join(' › ')}`);
  if (p.priorizacion.modo !== r.priorizacion.modo) out.push(`Prioridad estricta: ${p.priorizacion.modo === 'jerarquia_estricta' ? 'sí' : 'no'}`);
  if (p.optimizacion.objetivo !== r.optimizacion.objetivo) out.push('Objetivo: puntaje ponderado');
  if (JSON.stringify(p.priorizacion.pesos) !== JSON.stringify(r.priorizacion.pesos)) out.push('Pesos de prioridad modificados');
  for (const c of config.campanas) {
    const original = official.campanas.find(x => x.id === c.id);
    if (!original) out.push(`Campaña nueva: ${c.nombre}`);
    else {
      if (c.activa !== original.activa) out.push(`${c.nombre}: ${c.activa ? 'activa' : 'pausada'}`);
      if (JSON.stringify({ ...c, activa: original.activa }) !== JSON.stringify(original)) out.push(`Configuración modificada: ${c.nombre}`);
    }
  }
  for (const rule of config.reglas) {
    const original = official.reglas.find(x => x.id === rule.id);
    if (!original) out.push(`Regla nueva: ${rule.nombre}`);
    else if (JSON.stringify(rule) !== JSON.stringify(original)) out.push(`${rule.nombre}: ${!rule.activa ? 'apagada' : !original.activa ? 'activa' : 'modificada'}`);
  }
  return out;
}
