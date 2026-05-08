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
  punto_venta_numero: number | null;
  cliente_documento: string | null;
  cliente_razon_social: string | null;
  total_estimado: number;
  mensajes_json: string[];
  cae: string | null;
  numero_asignado: number | null;
  comprobante_id: number | null;
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
  mensaje_resumen: string | null;
  metadata_json: Record<string, string | number | null> | null;
  mapeo_usado_json: Record<string, unknown> | null;
  headers_detectados_json: string[] | null;
  started_at: string | null;
  finished_at: string | null;
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

export const ESTADOS_LOTE_NOMBRES: Record<string, string> = {
  cargado: "Cargado",
  validado: "Validado",
  en_cola: "En cola",
  con_errores: "Con errores",
  procesando: "Procesando",
  autorizado_parcial: "Autorizado parcial",
  completado: "Completado",
  fallido: "Fallido",
};

export const ESTADOS_LOTE_COLOR: Record<string, string> = {
  cargado: "bg-gray-100 text-gray-800",
  validado: "bg-blue-100 text-blue-800",
  en_cola: "bg-sky-100 text-sky-800",
  con_errores: "bg-amber-100 text-amber-800",
  procesando: "bg-indigo-100 text-indigo-800",
  autorizado_parcial: "bg-yellow-100 text-yellow-800",
  completado: "bg-green-100 text-green-800",
  fallido: "bg-red-100 text-red-800",
};

export const ESTADOS_GRUPO_COLOR: Record<string, string> = {
  validado: "bg-blue-50 text-blue-700",
  autorizado: "bg-green-50 text-green-700",
  con_error: "bg-amber-50 text-amber-700",
  fallido: "bg-red-50 text-red-700",
  cargado: "bg-gray-50 text-gray-700",
};
