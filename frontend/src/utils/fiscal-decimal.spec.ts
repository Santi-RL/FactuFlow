import { describe, expect, it } from "vitest";
import { decimalEsPositivo, formatearDecimalFiscal } from "./fiscal-decimal";
import { formatearMoneda } from "@/composables/useFormatters";

describe("lecturas fiscales exactas", () => {
  it("conserva centavos fuera de la capacidad de Number y todas las cifras variables", () => {
    expect(formatearMoneda("10000000000000000000000000.01")).toBe("$\u00a010.000.000.000.000.000.000.000.000,01");
    expect(formatearDecimalFiscal("1.00005")).toBe("1,00005");
    expect(formatearDecimalFiscal("0.1234567890123456789012345678")).toBe("0,1234567890123456789012345678");
  });

  it("presenta exponentes sin desarrollar tamaños enormes ni usar su magnitud como positividad", () => {
    expect(formatearDecimalFiscal("1E200000")).toBe("1E200000");
    expect(formatearDecimalFiscal("12345E-7")).toBe("0,0012345");
    expect(formatearDecimalFiscal("-0E200000", 2)).toBe("-0E200000");
    expect(decimalEsPositivo("0E200000")).toBe(false);
    expect(decimalEsPositivo("1E-200000")).toBe(true);
    expect(decimalEsPositivo("-1.01")).toBe(false);
  });

  it("admite respuestas históricas numéricas y ceros equivalentes", () => {
    expect(formatearMoneda(1234.5)).toBe("$\u00a01.234,50");
    expect(formatearMoneda("-12.01")).toBe("-$\u00a012,01");
    expect(formatearMoneda("-0.00")).toBe("$\u00a00,00");
    expect(formatearDecimalFiscal("1.0000")).toBe("1");
  });
});
