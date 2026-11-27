import { describe, expect, it } from "vitest";
import { ejemploVisible } from "./ejemplo-plantilla";

describe("ejemplos de plantillas nuevas, existentes y clonadas", () => {
  it.each([
    ["fecha_origen", "2026-05-31", "31/05/2026"],
    ["fecha_emision", "2026-02-30", "2026-02-30"],
    ["importe_total", "10000.01", "10.000,01"],
    ["item_precio_unitario", "1234.1234560", "1.234,1234560"],
    ["item_iva_porcentaje", "10.5", "10,5"],
    ["item_cantidad", "1.234", "1.234"],
    ["item_codigo", "000001", "000001"],
    ["importe_total", "Ver el resumen", "Ver el resumen"],
  ])("%s conserva el sentido de %s", (campo, entrada, esperado) => {
    expect(ejemploVisible(campo, entrada)).toBe(esperado);
    expect(ejemploVisible(campo, esperado)).toBe(esperado);
  });
});
