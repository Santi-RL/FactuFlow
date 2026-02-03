/**
 * Tipos TypeScript para Comprobantes
 */

export interface ItemComprobante {
  id?: number
  codigo?: string
  descripcion: string
  cantidad: number
  unidad: string
  precio_unitario: number
  descuento_porcentaje: number
  iva_porcentaje: number
  subtotal?: number
  orden: number
  comprobante_id?: number
}

export interface EmitirComprobanteRequest {
  empresa_id: number
  punto_venta_id: number
  tipo_comprobante: number
  concepto: number
  
  // Cliente
  cliente_id?: number
  tipo_documento: number
  numero_documento: string
  razon_social: string
  condicion_iva: string
  domicilio?: string
  
  // Items
  items: ItemComprobante[]
  
  // Servicios
  fecha_servicio_desde?: string
  fecha_servicio_hasta?: string
  fecha_vto_pago?: string
  
  // Opcional
  observaciones?: string
  moneda: string
  cotizacion: number
}

export interface EmitirComprobanteResponse {
  exito: boolean
  comprobante_id?: number
  tipo_comprobante: number
  punto_venta: number
  numero: number
  fecha: string
  cae?: string
  cae_vencimiento?: string
  total: number
  mensaje: string
  errores: string[]
}

export interface Comprobante {
  id: number
  tipo_comprobante: number
  numero: number
  fecha_emision: string
  fecha_vencimiento?: string
  subtotal: number
  descuento: number
  iva_21: number
  iva_10_5: number
  iva_27: number
  otros_impuestos: number
  total: number
  cae?: string
  cae_vencimiento?: string
  estado: string
  moneda: string
  cotizacion: number
  observaciones?: string
  empresa_id: number
  punto_venta_id: number
  cliente_id: number
}

export interface ComprobanteDetalle extends Comprobante {
  items: ItemComprobante[]
  cliente_nombre?: string
  cliente_cuit?: string
  punto_venta_numero?: number
}

export interface ComprobanteListItem {
  id: number
  tipo_comprobante: number
  numero: number
  fecha_emision: string
  total: number
  estado: string
  cae?: string
  cliente_nombre: string
  cliente_documento: string
  punto_venta_numero: number
}

export interface PaginatedComprobantesResponse {
  items: ComprobanteListItem[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface ProximoNumeroResponse {
  punto_venta: number
  tipo_comprobante: number
  proximo_numero: number
}

// Tipos de comprobante
export const TIPOS_COMPROBANTE = {
  FACTURA_A: 1,
  NOTA_DEBITO_A: 2,
  NOTA_CREDITO_A: 3,
  FACTURA_B: 6,
  NOTA_DEBITO_B: 7,
  NOTA_CREDITO_B: 8,
  FACTURA_C: 11,
  NOTA_DEBITO_C: 12,
  NOTA_CREDITO_C: 13,
} as const

export const TIPOS_COMPROBANTE_NOMBRES: Record<number, string> = {
  1: 'Factura A',
  2: 'Nota de Débito A',
  3: 'Nota de Crédito A',
  6: 'Factura B',
  7: 'Nota de Débito B',
  8: 'Nota de Crédito B',
  11: 'Factura C',
  12: 'Nota de Débito C',
  13: 'Nota de Crédito C',
}

// Tipos de concepto
export const TIPOS_CONCEPTO = {
  PRODUCTOS: 1,
  SERVICIOS: 2,
  PRODUCTOS_Y_SERVICIOS: 3,
} as const

export const TIPOS_CONCEPTO_NOMBRES: Record<number, string> = {
  1: 'Productos',
  2: 'Servicios',
  3: 'Productos y Servicios',
}

// Tipos de documento
export const TIPOS_DOCUMENTO = {
  CUIT: 80,
  CUIL: 86,
  CDI: 87,
  LE: 89,
  LC: 90,
  CI_EXTRANJERA: 91,
  EN_TRAMITE: 92,
  ACTA_NACIMIENTO: 93,
  CI_BS_AS_RNP: 95,
  DNI: 96,
  PASAPORTE: 94,
  CI_POLICIA_FEDERAL: 0,
  CI_BUENOS_AIRES: 1,
  CI_CATAMARCA: 2,
  CI_CORDOBA: 3,
  CI_CORRIENTES: 4,
  CI_ENTRE_RIOS: 5,
  CI_JUJUY: 6,
  CI_MENDOZA: 7,
  CI_LA_RIOJA: 8,
  CI_SALTA: 9,
  CI_SAN_JUAN: 10,
  CI_SAN_LUIS: 11,
  CI_SANTA_FE: 12,
  CI_SANTIAGO_DEL_ESTERO: 13,
  CI_TUCUMAN: 14,
  CI_CHACO: 16,
  CI_CHUBUT: 17,
  CI_FORMOSA: 18,
  CI_MISIONES: 19,
  CI_NEUQUEN: 20,
  CI_LA_PAMPA: 21,
  CI_RIO_NEGRO: 22,
  CI_SANTA_CRUZ: 23,
  CI_TIERRA_DEL_FUEGO: 24,
} as const

export const TIPOS_DOCUMENTO_NOMBRES: Record<number, string> = {
  80: 'CUIT',
  86: 'CUIL',
  96: 'DNI',
  94: 'Pasaporte',
  99: 'Consumidor Final',
}

// Alícuotas de IVA
export const ALICUOTAS_IVA = [
  { value: 0, label: 'Exento / 0%', porcentaje: 0 },
  { value: 10.5, label: '10.5%', porcentaje: 10.5 },
  { value: 21, label: '21%', porcentaje: 21 },
  { value: 27, label: '27%', porcentaje: 27 },
]

// Condiciones IVA
export const CONDICIONES_IVA = [
  'Responsable Inscripto',
  'Monotributo',
  'Exento',
  'Consumidor Final',
  'Responsable No Inscripto',
]

// Estados de comprobante
export const ESTADOS_COMPROBANTE = {
  BORRADOR: 'borrador',
  PENDIENTE: 'pendiente',
  AUTORIZADO: 'autorizado',
  RECHAZADO: 'rechazado',
  ANULADO: 'anulado',
} as const

export const ESTADOS_COMPROBANTE_NOMBRES: Record<string, string> = {
  borrador: 'Borrador',
  pendiente: 'Pendiente',
  autorizado: 'Autorizado',
  rechazado: 'Rechazado',
  anulado: 'Anulado',
}
