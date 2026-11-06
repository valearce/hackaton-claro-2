export type Condition = { atributo?: string; operador?: string; valor?: unknown; todas?: Condition[]; alguna?: Condition[] };
export type Campaign = { id: string; nombre: string; producto: string; objetivo: string; columna_score: string; valor_negocio: number; canales_permitidos: string[]; vigencia_inicio: string; vigencia_fin: string; activa: boolean };
export type Rule = { id: string; control: string; nombre: string; tipo: 'elegibilidad' | 'canal'; alcance: { nivel: string; valores: string[] }; condicion: Condition; accion: 'excluir'; activa: boolean };
export type Config = {
  campanas: Campaign[]; reglas: Rule[];
  parametros: {
    priorizacion: { modo: 'ponderado' | 'jerarquia_estricta'; modos_disponibles: string[]; jerarquia: string[]; pesos: { score_producto: number; valor_negocio: number; jerarquia: number }; umbral_score_producto: number; desempate: string[] };
    canal: { criterio: string; criterios_disponibles: string[]; orden_preferencia: string[]; umbral_score_canal: number; capacidad_por_corrida: Record<string, number>; columnas_score: Record<string, string> };
    politica_contacto: { canales_por_cliente: 1; max_contactos_semana: number; max_productos_por_canal: Record<string, number>; columna_contactos_semana?: string };
    optimizacion: { backend: 'flujo_ortools'; objetivo: 'valor_esperado' | 'prioridad' };
  };
};
export type Proof = { brecha_exacta: string; valor_objetivo_exacto: string; valor_esperado_exacto: string; objetivo: string; optimo_exacto: boolean };
export type Result = { valor_esperado: number; clientes: number; total_clientes: number; productos: number; jerarquia: number | null; violaciones: number; violaciones_reto: number; exceso_cupos_reto: Record<string, number>; controles_reto: { control: string; nombre: string; violaciones: number }[]; canales: { canal: string; cupo: number; uso: number }[]; campanas: { id: string; ofertas: number }[]; segundos: number; segundos_motor: number; certificado: Proof; objetivo: string };
export type Reference = { valor_esperado: number; clientes_con_accion: number; productos_asignados: number };
export type Run = { id: string; creado: string; fecha: string; metodos: { optimo: Result }; referencia: Reference; datos_sha256: string; motor_sha256: string };
export type Version = { version: string; nombre: string; creado: string; fecha: string; corrida: string; resultado: Result; config?: Config };
export type Metadata = { config: Config; config_reto: Config; fecha: string; version_activa: string | null; meta: number; columnas: string[]; tipos_columnas: Record<string, 'numero' | 'texto'>; clientes: number; referencia: Reference };
export type Row = { id_cliente: string; estado: string; canal: string; campana_1: string; campana_2: string; razon: string };
export type Change = (fn: (draft: Config) => void) => void;
