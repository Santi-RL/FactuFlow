export type ConceptoPerfilCargaMasiva =
  | "productos"
  | "servicios"
  | "archivo"
  | "";
export type DescripcionPerfilCargaMasiva = "archivo" | "fija" | "";
export type PuntoVentaPerfilModo = "archivo" | "fijo" | "";

export type FechaEmisionPerfilModo = "archivo" | "manual" | "personalizada";

export type PeriodoServicioPerfilModo =
  | "archivo"
  | "manual"
  | "mes_anterior_completo"
  | "mes_actual_completo"
  | "personalizado";

export type VencimientoPerfilModo =
  | "archivo"
  | "manual"
  | "mismo_dia_emision"
  | "emision_mas_dias"
  | "personalizada";

export interface PerfilFechaEmisionRegla {
  modo: FechaEmisionPerfilModo;
  fecha?: string;
}

export interface PerfilPeriodoServicioRegla {
  modo: PeriodoServicioPerfilModo;
  desde?: string;
  hasta?: string;
}

export interface PerfilVencimientoRegla {
  modo: VencimientoPerfilModo;
  fecha?: string;
  dias?: number;
}

export interface PerfilPuntoVentaRegla {
  modo: PuntoVentaPerfilModo;
  numero?: number | null;
}

export interface PerfilCargaMasivaConfiguracion {
  version: number;
  formato_importacion_version_id?: number | null;
  punto_venta: PerfilPuntoVentaRegla;
  concepto_modo: ConceptoPerfilCargaMasiva;
  descripcion_item_modo: DescripcionPerfilCargaMasiva;
  descripcion_item_fija?: string;
  fecha_emision: PerfilFechaEmisionRegla;
  periodo_servicio: PerfilPeriodoServicioRegla;
  fecha_vto_pago: PerfilVencimientoRegla;
}

export interface PerfilCargaMasiva {
  id: number;
  empresa_id: number;
  nombre: string;
  descripcion: string | null;
  configuracion_json: PerfilCargaMasivaConfiguracion;
  es_predeterminado: boolean;
  activo: boolean;
  created_at: string;
  updated_at: string;
}

export interface PerfilCargaMasivaPayload {
  nombre: string;
  descripcion?: string | null;
  configuracion_json: PerfilCargaMasivaConfiguracion;
  es_predeterminado?: boolean;
  activo?: boolean;
}
