import {
  formatearDecimalFiscal,
  type FiscalDecimal,
} from "@/utils/fiscal-decimal";

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

/** Convierte sólo una fecha argentina completa y válida al contrato ISO. */
export const fechaArgentinaAIso = (valor: string): string => {
  const partes = ARGENTINE_DATE_PATTERN.exec(valor);
  if (!partes) return "";
  const [, dia, mes, anio] = partes;
  const fecha = new Date(0);
  fecha.setUTCFullYear(Number(anio), Number(mes) - 1, Number(dia));
  return Number(anio) > 0 && fecha.getUTCFullYear() === Number(anio)
    && fecha.getUTCMonth() + 1 === Number(mes) && fecha.getUTCDate() === Number(dia)
    ? `${anio}-${mes}-${dia}`
    : "";
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
    const [dia, mes, anio] = isoMatch
      ? [thirdPart, secondPart, firstPart]
      : [firstPart, secondPart, thirdPart];
    const visible = [dia, mes, anio].join("/");
    return fechaArgentinaAIso(visible) ? visible : fecha;
  }

  if (Number.isNaN(fecha.getTime())) {
    return "";
  }

  return formatearFechaLocal(fecha);
};

/**
 * Presenta el importe nominal en su moneda, sin conversión ni pérdida decimal.
 */
export const formatearMoneda = (
  valor: FiscalDecimal,
  moneda: string | null = "PES",
): string => {
  const formatted = formatearDecimalFiscal(valor, 2);
  const etiqueta =
    moneda === "PES"
      ? "$"
      : moneda === "DOL"
        ? "USD"
        : moneda || "Moneda sin acreditar";
  return formatted.startsWith("-")
    ? `-${etiqueta}\u00a0${formatted.slice(1)}`
    : `${etiqueta}\u00a0${formatted}`;
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
