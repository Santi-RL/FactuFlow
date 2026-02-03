/**
 * Tipos para Certificados ARCA
 */

export type AmbienteCertificado = 'homologacion' | 'produccion'
export type EstadoCertificado = 'valido' | 'por_vencer' | 'vencido'
export type TipoAlerta = 'info' | 'warning' | 'danger'

export interface Certificado {
  id: number
  nombre: string
  cuit: string
  fecha_emision: string
  fecha_vencimiento: string
  ambiente: AmbienteCertificado
  archivo_crt: string
  archivo_key: string
  activo: boolean
  empresa_id: number
  created_at: string
  updated_at: string
  dias_restantes: number
  estado: EstadoCertificado
}

export interface GenerarCSRRequest {
  cuit: string
  nombre_empresa: string
  ambiente: AmbienteCertificado
}

export interface GenerarCSRResponse {
  csr: string
  key_filename: string
  mensaje: string
}

export interface VerificacionResponse {
  exito: boolean
  mensaje: string
  estado_servidores?: {
    aplicacion?: string
    base_datos?: string
    autenticacion?: string
  }
  error?: string
}

export interface CertificadoAlerta {
  id: number
  cuit: string
  nombre: string
  dias_restantes: number
  fecha_vencimiento: string
  ambiente: AmbienteCertificado
  tipo_alerta: TipoAlerta
}
