/**
 * Composable para formateo de datos
 */

const ISO_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})(?:T.*)?$/;
const ARGENTINE_DATE_PATTERN = /^(\d{2})\/(\d{2})\/(\d{4})$/;

const DATE_FORMAT_OPTIONS: Intl.DateTimeFormatOptions = {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
};

const formatearFechaLocal = (fecha: Date): string => {
  return fecha.toLocaleDateString("es-AR", DATE_FORMAT_OPTIONS);
};

const esFechaCalendarioValida = (
  fecha: Date,
  year: number,
  month: number,
  day: number,
): boolean => {
  return (
    fecha.getFullYear() === year &&
    fecha.getMonth() === month - 1 &&
    fecha.getDate() === day
  );
};

/**
 * Formatea una fecha en formato DD/MM/AAAA.
 * Maneja fechas ISO y argentinas DD/MM/AAAA sin conversión de zona horaria,
 * validando fechas de calendario reales antes de formatear.
 */
export const formatearFecha = (fecha: string | Date): string => {
  if (typeof fecha === "string") {
    const valor = fecha.trim();

    if (!valor) {
      return "";
    }

    const isoMatch = valor.match(ISO_DATE_PATTERN);
    const argentinaMatch = valor.match(ARGENTINE_DATE_PATTERN);

    const match = isoMatch ?? argentinaMatch;
    if (!match) {
      return fecha;
    }

    const [, firstPart, secondPart, thirdPart] = match;
    const year = Number(isoMatch ? firstPart : thirdPart);
    const month = Number(secondPart);
    const day = Number(isoMatch ? thirdPart : firstPart);
    const date = new Date(year, month - 1, day);

    if (!esFechaCalendarioValida(date, year, month, day)) {
      return fecha;
    }

    return formatearFechaLocal(date);
  }

  if (Number.isNaN(fecha.getTime())) {
    return "";
  }

  return formatearFechaLocal(fecha);
};

/**
 * Formatea un valor como moneda argentina (ARS)
 */
export const formatearMoneda = (valor: number): string => {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    minimumFractionDigits: 2,
  }).format(valor);
};

/**
 * Formatea un CUIT argentino (XX-XXXXXXXX-X)
 */
export const formatearCUIT = (cuit: string): string => {
  if (!cuit) return "";
  if (cuit.length !== 11) return cuit;
  return `${cuit.slice(0, 2)}-${cuit.slice(2, 10)}-${cuit.slice(10)}`;
};

/**
 * Formatea un número con separador de miles
 */
export const formatearNumero = (valor: number): string => {
  return new Intl.NumberFormat("es-AR").format(valor);
};

/**
 * Composable que exporta todas las funciones de formateo
 */
export function useFormatters() {
  return {
    formatearFecha,
    formatearMoneda,
    formatearCUIT,
    formatearNumero,
  };
}
