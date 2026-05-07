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
  warnings: string[];
}
