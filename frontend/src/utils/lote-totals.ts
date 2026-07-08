import type {
  LoteComprobanteDetalle,
  LoteComprobanteFila,
  LoteComprobanteGrupo,
} from "@/types/lote-comprobante";

export interface LoteTaxTotals {
  comprobantes: number;
  neto: number;
  iva21: number;
  iva105: number;
  total: number;
  valoresInvalidos: number;
}

const ESTADOS_TOTALIZABLES = new Set(["validado"]);

const parseNumericString = (value: string): number | null => {
  const unsigned = value
    .replace(/\$/g, "")
    .replace(/\s/g, "")
    .replace(/\u00a0/g, "")
    .trim();
  if (!unsigned) return 0;

  const sign = unsigned.startsWith("-") ? "-" : "";
  const normalizedSign = unsigned.replace(/^[+-]/, "");
  if (!/^\d[\d.,]*$/.test(normalizedSign)) return null;

  const lastComma = normalizedSign.lastIndexOf(",");
  const lastDot = normalizedSign.lastIndexOf(".");
  let normalized = normalizedSign;

  if (lastComma >= 0 && lastDot >= 0) {
    normalized =
      lastComma > lastDot
        ? normalizedSign.replace(/\./g, "").replace(",", ".")
        : normalizedSign.replace(/,/g, "");
  } else if (lastComma >= 0) {
    normalized = normalizedSign.replace(",", ".");
  } else if ((normalizedSign.match(/\./g) || []).length > 1) {
    normalized = normalizedSign.replace(/\./g, "");
  } else if (/^\d{1,3}\.\d{3}$/.test(normalizedSign)) {
    return null;
  }

  const parsed = Number(`${sign}${normalized}`);
  return Number.isFinite(parsed) ? parsed : null;
};

type NumericValue = string | number | null | undefined;

const toNumber = (value: NumericValue): number | null => {
  if (value === null || value === undefined || value === "") return 0;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const parsed = parseNumericString(value);
  return parsed === null ? null : parsed;
};

const toNumberOrZero = (value: NumericValue): number => {
  const parsed = toNumber(value);
  return parsed === null ? 0 : parsed;
};

const isMissingNumber = (value: NumericValue): boolean =>
  value === null ||
  value === undefined ||
  (typeof value === "string" && value.trim() === "");

const toRequiredNumber = (value: NumericValue): number | null => {
  if (isMissingNumber(value)) return null;
  return toNumber(value);
};

export const parseImporteLote = (
  value: string | number | null | undefined,
): number | null => toNumber(value);

const roundMoney = (value: number): number => Math.round(value * 100) / 100;

const calcularFila = (fila: LoteComprobanteFila) => {
  const datos = fila.datos_json;
  if (!datos) return null;

  const cantidad = toRequiredNumber(datos.item_cantidad);
  const precioUnitario = toRequiredNumber(datos.item_precio_unitario);
  const ivaPorcentaje = toRequiredNumber(datos.item_iva_porcentaje);
  const descuentoPorcentaje = toNumber(datos.item_descuento_porcentaje);
  if (
    cantidad === null ||
    precioUnitario === null ||
    ivaPorcentaje === null ||
    descuentoPorcentaje === null
  ) {
    return null;
  }

  const bruto = cantidad * precioUnitario;
  const neto = bruto - bruto * (descuentoPorcentaje / 100);

  return {
    neto,
    ivaPorcentaje,
  };
};

const calcularTotalGrupo = (
  grupo: LoteComprobanteGrupo,
  filas: LoteComprobanteFila[],
) => {
  const acumulado = filas.reduce(
    (totales, fila) => {
      const item = calcularFila(fila);
      if (!item) {
        totales.valoresInvalidos += 1;
        return totales;
      }
      totales.neto += item.neto;
      if (item.ivaPorcentaje === 21) {
        totales.iva21 += item.neto * 0.21;
      } else if (item.ivaPorcentaje === 10.5) {
        totales.iva105 += item.neto * 0.105;
      }
      return totales;
    },
    { neto: 0, iva21: 0, iva105: 0, valoresInvalidos: 0 },
  );

  const neto = roundMoney(acumulado.neto);
  const iva21 = roundMoney(acumulado.iva21);
  const iva105 = roundMoney(acumulado.iva105);
  const totalEstimado = toNumberOrZero(grupo.total_estimado);

  return {
    neto,
    iva21,
    iva105,
    total: totalEstimado || roundMoney(neto + iva21 + iva105),
    valoresInvalidos: acumulado.valoresInvalidos,
  };
};

export const calcularTotalesListosParaEmitir = (
  lote: LoteComprobanteDetalle | null,
): LoteTaxTotals => {
  if (!lote) {
    return {
      comprobantes: 0,
      neto: 0,
      iva21: 0,
      iva105: 0,
      total: 0,
      valoresInvalidos: 0,
    };
  }

  const filasPorGrupo = new Map<string, LoteComprobanteFila[]>();
  lote.filas
    .filter((fila) => ESTADOS_TOTALIZABLES.has(fila.estado))
    .forEach((fila) => {
      const actuales = filasPorGrupo.get(fila.comprobante_ref) || [];
      actuales.push(fila);
      filasPorGrupo.set(fila.comprobante_ref, actuales);
    });

  return lote.grupos
    .filter((grupo) => ESTADOS_TOTALIZABLES.has(grupo.estado))
    .reduce<LoteTaxTotals>(
      (totales, grupo) => {
        const filasGrupo = filasPorGrupo.get(grupo.comprobante_ref) || [];
        const totalGrupo = calcularTotalGrupo(grupo, filasGrupo);
        return {
          comprobantes: totales.comprobantes + 1,
          neto: roundMoney(totales.neto + totalGrupo.neto),
          iva21: roundMoney(totales.iva21 + totalGrupo.iva21),
          iva105: roundMoney(totales.iva105 + totalGrupo.iva105),
          total: roundMoney(totales.total + totalGrupo.total),
          valoresInvalidos:
            totales.valoresInvalidos + totalGrupo.valoresInvalidos,
        };
      },
      {
        comprobantes: 0,
        neto: 0,
        iva21: 0,
        iva105: 0,
        total: 0,
        valoresInvalidos: 0,
      },
    );
};
