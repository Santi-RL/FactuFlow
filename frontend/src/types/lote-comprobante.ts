export interface LoteComprobanteFila {
  id: number;
  fila_excel: number;
  comprobante_ref: string;
  estado: string;
  datos_json: Record<string, string | number | null> | null;
  mensajes_json: string[];
}

export interface LoteComprobanteGrupo {
  id: number;
  comprobante_ref: string;
  orden: number;
  estado: string;
  tipo_comprobante: number | null;
  concepto: number | null;
  punto_venta_numero: number | null;
  cliente_documento: string | null;
  cliente_razon_social: string | null;
  fecha_emision: string | null;
  fecha_servicio_desde: string | null;
  fecha_servicio_hasta: string | null;
  fecha_vto_pago: string | null;
  total_estimado: number;
  mensajes_json: string[];
  cae: string | null;
  numero_asignado: number | null;
  comprobante_id: number | null;
}

export interface LoteComprobanteGrupoDetalle extends LoteComprobanteGrupo {
  descripcion_facturada: string | null;
}

export interface LoteComprobante {
  id: number;
  nombre_archivo: string;
  archivo_hash: string;
  estado: string;
  modo_procesamiento: string;
  procesamiento_async: boolean;
  total_filas: number;
  total_grupos: number;
  grupos_validos: number;
  grupos_con_error: number;
  grupos_emitidos: number;
  grupos_fallidos: number;
  grupos_reconciliados_externos: number;
  grupos_descartados: number;
  mensaje_resumen: string | null;
  metadata_json: Record<string, unknown> | null;
  mapeo_usado_json: Record<string, unknown> | null;
  headers_detectados_json: string[] | null;
  started_at: string | null;
  finished_at: string | null;
  compactado_at: string | null;
  created_at: string;
  updated_at: string;
  empresa_id: number;
  usuario_id: number | null;
  formato_importacion_id: number | null;
  formato_importacion_version_id: number | null;
}

export interface LoteComprobanteDetalle extends LoteComprobante {
  grupos: LoteComprobanteGrupo[];
  filas: LoteComprobanteFila[];
}

export interface LoteTotalesListos {
  comprobantes: number;
  neto: number;
  iva21: number;
  iva105: number;
  total: number;
  valores_invalidos: number;
}

export interface LoteComprobanteResumen extends LoteComprobante {
  confirmacion_fecha_fiscal: string;
  mensaje_confirmacion_fecha_fiscal: string;
  confirmacion_reintento_fallidos: string;
  mensaje_confirmacion_reintento_fallidos: string;
  confirmacion_duplicado_logico: string;
  mensaje_confirmacion_duplicado_logico: string;
  cantidad_duplicados_logicos: number;
  fechas_emision_validas: string[];
  puntos_venta_validos: number[];
  totales_listos_para_emitir: LoteTotalesListos;
}

export interface LoteComprobanteGruposPage {
  items: LoteComprobanteGrupoDetalle[];
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
  estado: string | null;
}

export interface LoteValidacionResponse {
  lote: LoteComprobante;
  puede_emitirse: boolean;
  requiere_background: boolean;
  mensaje: string;
}

export interface LoteProcesamientoResponse {
  lote: LoteComprobante;
  mensaje: string;
  en_progreso: boolean;
}

export interface LoteAccionResponse {
  lote: LoteComprobante;
  mensaje: string;
}

export interface ReconciliacionExternaItem {
  grupo_id: number;
  tipo_comprobante: number;
  punto_venta_numero: number;
  numero: number;
  fecha_emision: string;
  total: number;
  cae?: string;
  motivo: string;
}

export interface LoteOpcionesFechas {
  punto_venta_modo: "archivo" | "fijo";
  punto_venta_numero?: number;
  concepto_modo: "productos" | "servicios" | "archivo" | "";
  descripcion_item_modo: "archivo" | "fija" | "";
  descripcion_item_fija?: string;
  fecha_emision_modo: "archivo" | "fija" | "";
  fecha_emision_fija?: string;
  fecha_servicio_desde_modo: "archivo" | "fija" | "";
  fecha_servicio_desde_fija?: string;
  fecha_servicio_hasta_modo: "archivo" | "fija" | "";
  fecha_servicio_hasta_fija?: string;
  fecha_vto_pago_modo: "archivo" | "fija" | "";
  fecha_vto_pago_fija?: string;
}

export const ESTADOS_LOTE_NOMBRES: Record<string, string> = {
  cargado: "Cargado",
  validado: "Validado",
  en_cola: "En cola",
  con_errores: "Con errores",
  procesando: "Procesando",
  autorizado_parcial: "Autorizado parcial",
  requiere_reconciliacion: "Requiere reconciliación",
  completado: "Completado",
  cerrado_reconciliado: "Cerrado reconciliado",
  cerrado_con_descartes: "Cerrado con descartes",
  fallido: "Fallido",
};

export const ESTADOS_LOTE_COLOR: Record<string, string> = {
  cargado: "bg-gray-100 text-gray-800",
  validado: "bg-blue-100 text-blue-800",
  en_cola: "bg-sky-100 text-sky-800",
  con_errores: "bg-amber-100 text-amber-800",
  procesando: "bg-indigo-100 text-indigo-800",
  autorizado_parcial: "bg-yellow-100 text-yellow-800",
  requiere_reconciliacion: "bg-orange-100 text-orange-800",
  completado: "bg-green-100 text-green-800",
  cerrado_reconciliado: "bg-emerald-100 text-emerald-800",
  cerrado_con_descartes: "bg-stone-100 text-stone-800",
  fallido: "bg-red-100 text-red-800",
};

export const ESTADOS_GRUPO_COLOR: Record<string, string> = {
  validado: "bg-blue-50 text-blue-700",
  autorizado: "bg-green-50 text-green-700",
  autorizado_externo: "bg-emerald-50 text-emerald-700",
  con_error: "bg-amber-50 text-amber-700",
  requiere_reconciliacion: "bg-orange-50 text-orange-700",
  reintentando: "bg-orange-50 text-orange-700",
  fallido: "bg-red-50 text-red-700",
  descartado: "bg-stone-50 text-stone-700",
  cargado: "bg-gray-50 text-gray-700",
};

export const ESTADOS_GRUPO_NOMBRES: Record<string, string> = {
  validado: "Validado",
  autorizado: "Autorizado",
  autorizado_externo: "Autorizado externo",
  con_error: "Con observaciones",
  requiere_reconciliacion: "Requiere reconciliación",
  reintentando: "Requiere reconciliación",
  fallido: "Fallido",
  descartado: "Descartado",
  cargado: "Cargado",
};
