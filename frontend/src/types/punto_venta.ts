export type AmbienteArca = "homologacion" | "produccion";

export type EstadoElegibilidadRece =
  "verificado_rece" | "no_rece" | "no_verificado";

export interface ElegibilidadRece {
  ambiente: AmbienteArca;
  estado: EstadoElegibilidadRece;
  estado_efectivo: EstadoElegibilidadRece;
  fuente: string | null;
  revision_id: number | null;
  revision: number | null;
  punto_revision_fiscal: number | null;
  verificado_en: string | null;
  vigente_hasta: string | null;
  motivo: string | null;
}

export interface PuntoVenta {
  id: number;
  numero: number;
  nombre: string | null;
  sistema: string | null;
  domicilio: string | null;
  nombre_fantasia: string | null;
  es_webservice: boolean;
  bloqueado: boolean;
  fecha_baja: string | null;
  fuente: string | null;
  activo: boolean;
  usable_factuflow: boolean;
  puede_intentar_emision: boolean;
  ultima_comprobacion_arca_en: string | null;
  comprobacion_arca_desactualizada: boolean;
  revision_fiscal: number;
  elegibilidad_rece: ElegibilidadRece;
  empresa_id: number;
  created_at: string;
}

export interface PuntoVentaCreate {
  numero: number;
  nombre?: string | null;
  sistema?: string | null;
  domicilio?: string | null;
  nombre_fantasia?: string | null;
  es_webservice?: boolean;
  bloqueado?: boolean;
  fecha_baja?: string | null;
  fuente?: string | null;
}

export interface PuntoVentaUpdate {
  numero?: number;
  nombre?: string | null;
  sistema?: string | null;
  domicilio?: string | null;
  nombre_fantasia?: string | null;
  es_webservice?: boolean;
  bloqueado?: boolean;
  fecha_baja?: string | null;
  fuente?: string | null;
  activo?: boolean;
}

export interface PuntoVentaArca {
  numero: number;
  emision_tipo: string;
  bloqueado: string;
  fecha_baja?: string | null;
}

export interface ImportarPuntosVentaResponse {
  total_constancia: number;
  creados: number;
  actualizados: number;
  omitidos: number;
  desactivados_ausentes: number;
  verificados_rece: number;
  pendientes_comprobacion: number;
  no_verificados_rece: number;
  documento_emitido_en: string | null;
  vigente_hasta: string | null;
  warnings: string[];
}

export interface SincronizarPuntosVentaResponse {
  total_arca: number;
  nuevos: number;
  existentes: number;
  actualizados: number;
  desactivados_ausentes: number;
  comprobado_en: string;
}
