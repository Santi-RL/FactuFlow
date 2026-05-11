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
}

const ESTADOS_TOTALIZABLES = new Set(["validado"]);

const toNumber = (value: string | number | null | undefined): number => {
  if (value === null || value === undefined || value === "") return 0;
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  const normalized = value.replace(/\$/g, "").replace(/\s/g, "").replace(",", ".");
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
};

const roundMoney = (value: number): number => Math.round(value * 100) / 100;

const calcularFila = (fila: LoteComprobanteFila) => {
  const datos = fila.datos_json || {};
  const cantidad = toNumber(datos.item_cantidad);
  const precioUnitario = toNumber(datos.item_precio_unitario);
  const descuentoPorcentaje = toNumber(datos.item_descuento_porcentaje);
  const ivaPorcentaje = toNumber(datos.item_iva_porcentaje);
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
      totales.neto += item.neto;
      if (item.ivaPorcentaje === 21) {
        totales.iva21 += item.neto * 0.21;
      } else if (item.ivaPorcentaje === 10.5) {
        totales.iva105 += item.neto * 0.105;
      }
      return totales;
    },
    { neto: 0, iva21: 0, iva105: 0 },
  );

  const neto = roundMoney(acumulado.neto);
  const iva21 = roundMoney(acumulado.iva21);
  const iva105 = roundMoney(acumulado.iva105);
  const totalEstimado = toNumber(grupo.total_estimado);

  return {
    neto,
    iva21,
    iva105,
    total: totalEstimado || roundMoney(neto + iva21 + iva105),
  };
};

export const calcularTotalesListosParaEmitir = (
  lote: LoteComprobanteDetalle | null,
): LoteTaxTotals => {
  if (!lote) {
    return { comprobantes: 0, neto: 0, iva21: 0, iva105: 0, total: 0 };
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
        };
      },
      { comprobantes: 0, neto: 0, iva21: 0, iva105: 0, total: 0 },
    );
};
