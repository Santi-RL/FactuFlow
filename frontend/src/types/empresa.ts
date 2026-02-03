export interface Empresa {
  id: number
  razon_social: string
  cuit: string
  condicion_iva: 'RI' | 'Monotributo' | 'Exento'
  domicilio: string
  localidad: string
  provincia: string
  codigo_postal: string
  email: string | null
  telefono: string | null
  inicio_actividades: string
  logo: string | null
  created_at: string
  updated_at: string
}

export interface EmpresaCreate {
  razon_social: string
  cuit: string
  condicion_iva: 'RI' | 'Monotributo' | 'Exento'
  domicilio: string
  localidad: string
  provincia: string
  codigo_postal: string
  email?: string
  telefono?: string
  inicio_actividades: string
  logo?: string
}

export interface EmpresaUpdate {
  razon_social?: string
  cuit?: string
  condicion_iva?: 'RI' | 'Monotributo' | 'Exento'
  domicilio?: string
  localidad?: string
  provincia?: string
  codigo_postal?: string
  email?: string
  telefono?: string
  inicio_actividades?: string
  logo?: string
}
