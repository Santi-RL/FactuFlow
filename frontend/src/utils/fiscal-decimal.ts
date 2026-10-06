/** Lecturas fiscales JSON exactas; number se admite para respuestas históricas. */
export type FiscalDecimal = string | number;

/** Presentación decimal sin convertir el coeficiente a Number. */
export function formatearDecimalFiscal(
  value: FiscalDecimal,
  minimumFractionDigits = 0,
): string {
  const source = String(value);
  const match = source.match(/^(-?)(\d+)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/);
  if (!match) return source;
  const [, sign, integer, fraction = "", exponent = "0"] = match;
  const offset = Number(exponent);
  // Un exponente enorme permanece visible y exacto sin expandirse en memoria.
  if (!Number.isSafeInteger(offset) || Math.abs(offset) > 1000) {
    return source.replace(".", ",");
  }
  let digits = integer + fraction;
  let point = integer.length + offset;
  if (point <= 0) {
    digits = "0".repeat(-point + 1) + digits;
    point = 1;
  }
  if (point > digits.length) digits = digits.padEnd(point, "0");
  const whole = digits.slice(0, point).replace(/^0+(?=\d)/, "");
  const decimal = digits
    .slice(point)
    .replace(/0+$/, "")
    .padEnd(minimumFractionDigits, "0");
  const negative = sign && /[1-9]/.test(digits) ? "-" : "";
  return (
    negative +
    whole.replace(/\B(?=(\d{3})+(?!\d))/g, ".") +
    (decimal ? "," + decimal : "")
  );
}

export function decimalEsPositivo(value: FiscalDecimal): boolean {
  const coefficient = String(value).split(/[eE]/)[0];
  return !coefficient.startsWith("-") && /[1-9]/.test(coefficient);
}
