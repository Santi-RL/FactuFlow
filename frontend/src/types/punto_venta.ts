export interface PuntoVenta {
  id: number
  numero: number
  nombre: string | null
  activo: boolean
  empresa_id: number
  created_at: string
}

export interface PuntoVentaCreate {
  numero: number
  nombre?: string | null
}

export interface PuntoVentaUpdate {
  numero?: number
  nombre?: string | null
  activo?: boolean
}

export interface PuntoVentaArca {
  numero: number
  emision_tipo: string
  bloqueado: string
  fecha_baja?: string | null
}
