export interface FormatoImportacionVersion {
  id: number;
  version: number;
  estado: string;
  configuracion_json: Record<string, unknown>;
  headers_firma_json: Record<string, unknown> | null;
  created_at: string;
}

export interface FormatoImportacion {
  id: number;
  nombre: string;
  descripcion: string | null;
  alcance: string;
  activo: boolean;
  empresa_id: number | null;
  created_at: string;
  updated_at: string;
  version_vigente: FormatoImportacionVersion | null;
}

export interface FormatoImportacionPayload {
  nombre: string;
  descripcion?: string | null;
  alcance: "global" | "emisor";
  configuracion_json: Record<string, unknown>;
}

export interface FormatoImportacionCampoCatalogo {
  codigo: string;
  etiqueta: string;
  grupo: string;
  descripcion: string;
  requerido_base: boolean;
  transformaciones: string[];
  origenes: string[];
}

export interface FormatoImportacionExcelColumna {
  indice: number;
  letra: string;
  encabezado: string;
}

export interface FormatoImportacionExcelAnalisis {
  hoja: string;
  fila_encabezado: number;
  columnas: FormatoImportacionExcelColumna[];
}

export interface FormatoImportacionCompatibilidadMensaje {
  codigo: string;
  campo: string | null;
  severidad: "info" | "warning" | "error" | string;
  mensaje: string;
}

export interface FormatoImportacionCompatibilidad {
  estado: "compatible" | "advertencia" | "incompatible" | string;
  faltantes: FormatoImportacionCompatibilidadMensaje[];
  omitibles: FormatoImportacionCompatibilidadMensaje[];
  advertencias: FormatoImportacionCompatibilidadMensaje[];
  conflictos: FormatoImportacionCompatibilidadMensaje[];
}

export interface FormatoImportacionCandidato {
  formato_id: number | null;
  formato_version_id: number | null;
  nombre: string;
  alcance: string;
  version: number | null;
  score: number;
  confianza: string;
  columnas_detectadas: string[];
  columnas_faltantes: string[];
  mensajes: string[];
}

export interface FormatoImportacionDeteccion {
  headers_detectados: string[];
  candidatos: FormatoImportacionCandidato[];
  formato_sugerido_version_id: number | null;
  requiere_confirmacion: boolean;
}
