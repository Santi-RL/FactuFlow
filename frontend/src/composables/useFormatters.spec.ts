import { describe, expect, it } from "vitest";

import { formatearFecha, formatearMoneda } from "./useFormatters";

describe("monedas nominales", () => {
  it("conserva signo y precisión e identifica dólares y códigos desconocidos", () => {
    expect(formatearMoneda("-0.01", "DOL")).toBe("-USD\u00a00,01");
    expect(formatearMoneda("100000000000000000000000.01", "XYZ")).toContain(
      "XYZ\u00a0100.000.000.000.000.000.000.000,01",
    );
    expect(formatearMoneda("100", null)).toContain("Moneda sin acreditar");
  });
});

describe("formatearFecha", () => {
  it("formatea strings ISO YYYY-MM-DD sin desplazar la fecha", () => {
    expect(formatearFecha("2026-12-31")).toBe("31/12/2026");
    expect(formatearFecha("2026-01-05")).toBe("05/01/2026");
    expect(formatearFecha("2026-05-15")).toBe("15/05/2026");
  });

  it("formatea strings ISO con hora usando solo la fecha local declarada", () => {
    expect(formatearFecha("2026-12-31T23:59:59Z")).toBe("31/12/2026");
  });

  it("soporta fechas argentinas DD/MM/AAAA como formato de primera clase", () => {
    expect(formatearFecha("31/12/2026")).toBe("31/12/2026");
    expect(formatearFecha("05/01/2026")).toBe("05/01/2026");
    expect(formatearFecha("29/02/2024")).toBe("29/02/2024");
  });

  it("formatea objetos Date válidos", () => {
    expect(formatearFecha(new Date(2026, 11, 31))).toBe("31/12/2026");
  });

  it("devuelve vacío para strings vacíos o Date inválidos", () => {
    expect(formatearFecha("")).toBe("");
    expect(formatearFecha("   ")).toBe("");
    expect(formatearFecha(new Date("fecha inválida"))).toBe("");
  });

  it("devuelve strings no soportados o fechas inválidas sin inventar una fecha", () => {
    expect(formatearFecha("2026-02-31")).toBe("2026-02-31");
    expect(formatearFecha("31/02/2026")).toBe("31/02/2026");
    expect(formatearFecha("29/02/2026")).toBe("29/02/2026");
    expect(formatearFecha("1/1/2026")).toBe("1/1/2026");
    expect(formatearFecha("fecha pendiente")).toBe("fecha pendiente");
  });
});
