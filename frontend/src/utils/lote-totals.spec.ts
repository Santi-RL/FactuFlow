import { describe, expect, it } from "vitest";

import type {
  LoteComprobanteDetalle,
  LoteComprobanteFila,
  LoteComprobanteGrupo,
} from "@/types/lote-comprobante";
import {
  calcularTotalesListosParaEmitir,
  parseImporteLote,
} from "./lote-totals";

const grupo = (
  comprobanteRef: string,
  totalEstimado: number,
  estado = "validado",
): LoteComprobanteGrupo => ({
  id: Number(comprobanteRef.replace(/\D/g, "")) || 1,
  comprobante_ref: comprobanteRef,
  orden: 1,
  estado,
  tipo_comprobante: 6,
  concepto: 2,
  punto_venta_numero: 5,
  cliente_documento: "0",
  cliente_razon_social: "A CONSUMIDOR FINAL",
  fecha_emision: "2026-04-30",
  fecha_servicio_desde: "2026-04-01",
  fecha_servicio_hasta: "2026-04-30",
  fecha_vto_pago: "2026-04-30",
  total_estimado: totalEstimado,
  mensajes_json: [],
  cae: null,
  numero_asignado: null,
  comprobante_id: null,
});

const fila = (
  comprobanteRef: string,
  precioUnitario: string | number,
  ivaPorcentaje: string | number,
  estado = "validado",
): LoteComprobanteFila => ({
  id: Number(comprobanteRef.replace(/\D/g, "")) || 1,
  fila_excel: 2,
  comprobante_ref: comprobanteRef,
  estado,
  datos_json: {
    item_cantidad: 1,
    item_precio_unitario: precioUnitario,
    item_descuento_porcentaje: 0,
    item_iva_porcentaje: ivaPorcentaje,
  },
  mensajes_json: [],
});

const lote = (
  grupos: LoteComprobanteGrupo[],
  filas: LoteComprobanteFila[],
): LoteComprobanteDetalle => ({
  id: 1,
  nombre_archivo: "lote.xlsx",
  archivo_hash: "hash",
  estado: "validado",
  modo_procesamiento: "sincronico",
  procesamiento_async: false,
  total_filas: filas.length,
  total_grupos: grupos.length,
  grupos_validos: grupos.filter((item) => item.estado === "validado").length,
  grupos_con_error: grupos.filter((item) => item.estado === "con_error").length,
  grupos_emitidos: 0,
  grupos_fallidos: 0,
  grupos_reconciliados_externos: 0,
  grupos_descartados: 0,
  mensaje_resumen: null,
  metadata_json: null,
  mapeo_usado_json: null,
  headers_detectados_json: null,
  started_at: null,
  finished_at: null,
  compactado_at: null,
  created_at: "2026-05-11T01:00:00",
  updated_at: "2026-05-11T01:00:00",
  empresa_id: 8,
  usuario_id: 1,
  formato_importacion_id: 3,
  formato_importacion_version_id: 6,
  grupos,
  filas,
});

describe("calcularTotalesListosParaEmitir", () => {
  it("suma neto, IVA 21, IVA 10.5 y total de grupos validados", () => {
    const totales = calcularTotalesListosParaEmitir(
      lote(
        [grupo("FILA-00002", 1210), grupo("FILA-00003", 1105)],
        [fila("FILA-00002", 1000, 21), fila("FILA-00003", 1000, 10.5)],
      ),
    );

    expect(totales).toEqual({
      comprobantes: 2,
      neto: 2000,
      iva21: 210,
      iva105: 105,
      total: 2315,
      valoresInvalidos: 0,
    });
  });

  it("ignora grupos observados y reproduce redondeo por comprobante", () => {
    const totales = calcularTotalesListosParaEmitir(
      lote(
        [grupo("FILA-00002", 91874.52), grupo("FILA-00003", 0, "con_error")],
        [
          fila("FILA-00002", "75929.35537190083", 21),
          fila("FILA-00003", "90000", 21, "con_error"),
        ],
      ),
    );

    expect(totales.comprobantes).toBe(1);
    expect(totales.neto).toBe(75929.36);
    expect(totales.iva21).toBe(15945.16);
    expect(totales.iva105).toBe(0);
    expect(totales.total).toBe(91874.52);
    expect(totales.valoresInvalidos).toBe(0);
  });

  it("interpreta importes con separadores locales argentinos", () => {
    const totales = calcularTotalesListosParaEmitir(
      lote(
        [grupo("FILA-00002", 0), grupo("FILA-00003", 0)],
        [
          fila("FILA-00002", "1.234,56", "21"),
          fila("FILA-00003", "$ 1.234,56", "10,5"),
        ],
      ),
    );

    expect(totales.neto).toBe(2469.12);
    expect(totales.iva21).toBe(259.26);
    expect(totales.iva105).toBe(129.63);
    expect(totales.total).toBe(2858.01);
    expect(totales.valoresInvalidos).toBe(0);
    expect(parseImporteLote("1234,56")).toBe(1234.56);
  });

  it("marca datos_json nulo como valor invalido", () => {
    const filaSinDatos = fila("FILA-00002", 100, 21);
    filaSinDatos.datos_json = null;

    const totales = calcularTotalesListosParaEmitir(
      lote([grupo("FILA-00002", 0)], [filaSinDatos]),
    );

    expect(totales.neto).toBe(0);
    expect(totales.total).toBe(0);
    expect(totales.valoresInvalidos).toBe(1);
  });

  it("marca campos numericos requeridos faltantes como invalidos", () => {
    const filaSinPrecio = fila("FILA-00002", 100, 21);
    filaSinPrecio.datos_json = {
      item_cantidad: 1,
      item_descuento_porcentaje: 0,
      item_iva_porcentaje: 21,
    };

    const totales = calcularTotalesListosParaEmitir(
      lote([grupo("FILA-00002", 0)], [filaSinPrecio]),
    );

    expect(totales.neto).toBe(0);
    expect(totales.total).toBe(0);
    expect(totales.valoresInvalidos).toBe(1);
  });
  it("marca formatos numericos ambiguos en lugar de convertirlos a cero", () => {
    const totales = calcularTotalesListosParaEmitir(
      lote([grupo("FILA-00002", 0)], [fila("FILA-00002", "1.234", 21)]),
    );

    expect(totales.neto).toBe(0);
    expect(totales.total).toBe(0);
    expect(totales.valoresInvalidos).toBe(1);
  });
});
