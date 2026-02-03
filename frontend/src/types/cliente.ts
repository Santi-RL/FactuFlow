export interface Cliente {
  id: number
  empresa_id: number
  razon_social: string
  tipo_documento: 'CUIT' | 'CUIL' | 'DNI' | 'LE' | 'LC' | 'Pasaporte' | 'CI'
  numero_documento: string
  condicion_iva: 'RI' | 'Monotributo' | 'CF' | 'Exento'
  domicilio: string | null
  localidad: string | null
  provincia: string | null
  codigo_postal: string | null
  email: string | null
  telefono: string | null
  notas: string | null
  activo: boolean
  created_at: string
  updated_at: string
}

export interface ClienteCreate {
  razon_social: string
  tipo_documento: 'CUIT' | 'CUIL' | 'DNI' | 'LE' | 'LC' | 'Pasaporte' | 'CI'
  numero_documento: string
  condicion_iva: 'RI' | 'Monotributo' | 'CF' | 'Exento'
  domicilio?: string
  localidad?: string
  provincia?: string
  codigo_postal?: string
  email?: string
  telefono?: string
  notas?: string
}

export interface ClienteUpdate {
  razon_social?: string
  tipo_documento?: 'CUIT' | 'CUIL' | 'DNI' | 'LE' | 'LC' | 'Pasaporte' | 'CI'
  numero_documento?: string
  condicion_iva?: 'RI' | 'Monotributo' | 'CF' | 'Exento'
  domicilio?: string
  localidad?: string
  provincia?: string
  codigo_postal?: string
  email?: string
  telefono?: string
  notas?: string
  activo?: boolean
}

export interface ClienteListParams {
  page?: number
  per_page?: number
  search?: string
  activo?: boolean
}
