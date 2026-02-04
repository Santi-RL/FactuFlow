/**
 * Composable para formateo de datos
 */

/**
 * Formatea una fecha en formato DD/MM/YYYY
 */
export const formatearFecha = (fecha: string | Date): string => {
  const date = typeof fecha === 'string' ? new Date(fecha) : fecha
  return date.toLocaleDateString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  })
}

/**
 * Formatea un valor como moneda argentina (ARS)
 */
export const formatearMoneda = (valor: number): string => {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    minimumFractionDigits: 2
  }).format(valor)
}

/**
 * Formatea un CUIT argentino (XX-XXXXXXXX-X)
 */
export const formatearCUIT = (cuit: string): string => {
  if (!cuit || cuit.length !== 11) return cuit
  return `${cuit.slice(0, 2)}-${cuit.slice(2, 10)}-${cuit.slice(10)}`
}

/**
 * Formatea un número con separador de miles
 */
export const formatearNumero = (valor: number): string => {
  return new Intl.NumberFormat('es-AR').format(valor)
}

/**
 * Composable que exporta todas las funciones de formateo
 */
export function useFormatters() {
  return {
    formatearFecha,
    formatearMoneda,
    formatearCUIT,
    formatearNumero
  }
}
