export type EstadoAlmacenamiento = "correcto" | "necesita_atencion" | "critico";

export interface AlmacenamientoCategoria {
  clave: string;
  nombre: string;
  bytes_usados: number;
  bytes_recuperables: number;
  items: number;
  estado: EstadoAlmacenamiento;
  descripcion: string;
}

export interface AlmacenamientoEmisor {
  empresa_id: number;
  etiqueta: string;
  lotes: number;
  filas_persistidas: number;
  filas_compactables: number;
  comprobantes: number;
  bytes_estimados: number;
  bytes_recuperables: number;
}

export interface AlmacenamientoResumen {
  generated_at: string;
  estado: EstadoAlmacenamiento;
  total_bytes_usados: number;
  total_bytes_recuperables: number;
  storage_limit_bytes: number | null;
  disk_total_bytes: number | null;
  disk_used_bytes: number | null;
  disk_free_bytes: number | null;
  categorias: AlmacenamientoCategoria[];
  emisores: AlmacenamientoEmisor[];
}

export interface AlmacenamientoItem {
  id: string;
  nombre: string;
  categoria: string;
  bytes_usados: number;
  bytes_recuperables: number;
  descripcion: string;
  created_at: string | null;
}

export interface LoteCompactable {
  id: number;
  empresa_id: number;
  etiqueta_emisor: string;
  estado: string;
  total_filas: number;
  total_grupos: number;
  filas_persistidas: number;
  bytes_recuperables: number;
  created_at: string;
  finished_at: string | null;
}

export interface CrearExportacionAlmacenamiento {
  lote_ids: number[];
  log_ids: string[];
  temporal_ids: string[];
}

export interface ExportacionAlmacenamiento {
  token: string;
  estado: string;
  archivo_nombre: string;
  checksum_sha256: string;
  size_bytes: number;
  created_at: string;
  downloaded_at: string | null;
  released_at: string | null;
  manifest: Record<string, unknown>;
}

export interface AccionAlmacenamiento {
  mensaje: string;
  bytes_afectados: number;
  items_afectados: number;
}
