import { describe, expect, it } from "vitest";

import {
  analizarFechaHoraIso,
  formatearFechaHoraArgentina,
  parsearInstante,
} from "./instantes";

describe("instantes operativos", () => {
  it.each([
    "2026-10-03T12:30:00Z",
    "2026-10-03T09:30:00-03:00",
    "2026-10-03T14:30:00+02:00",
  ])("conserva el mismo instante y la hora argentina para %s", (value) => {
    expect(parsearInstante(value)?.toISOString()).toBe(
      "2026-10-03T12:30:00.000Z",
    );
    expect(formatearFechaHoraArgentina(value)).toBe("03/10/2026, 09:30");
  });

  it("interpreta UTC sin zona únicamente cuando el consumidor declara ese contrato", () => {
    expect(parsearInstante("2026-10-03T12:30:00")).toBeNull();
    expect(formatearFechaHoraArgentina("2026-10-03T12:30:00")).toBeNull();
    expect(
      formatearFechaHoraArgentina("2026-10-03T12:30:00", {
        interpretarSinZonaComoUtc: true,
      }),
    ).toBe("03/10/2026, 09:30");
  });

  it.each([
    ["2026-01-01T01:00:00Z", "31/12/2025, 22:00"],
    ["2026-03-01T01:00:00Z", "28/02/2026, 22:00"],
    ["2024-03-01T01:00:00Z", "29/02/2024, 22:00"],
    ["2026-10-03T03:00:00Z", "03/10/2026, 00:00"],
  ])("cambia correctamente día, mes o año para %s", (value, esperado) => {
    expect(formatearFechaHoraArgentina(value)).toBe(esperado);
  });

  it("conserva fracciones del backend hasta la precisión de milisegundos de JavaScript", () => {
    expect(parsearInstante("2026-10-03T12:30:00.123456Z")?.toISOString()).toBe(
      "2026-10-03T12:30:00.123Z",
    );
  });

  it.each([
    "2026-02-29T12:00:00Z",
    "2026-02-31T12:00:00Z",
    "2026-13-01T12:00:00Z",
    "2026-10-03T24:00:00Z",
    "2026-10-03T12:60:00Z",
    "2026-10-03T12:00:60Z",
    "2026-10-03T12:00:00+99:99",
    "2026-10-03T12:00:00+03:60",
    "03/10/2026 12:00",
    "2026-10-03 12:00:00",
    "sin fecha",
  ])("rechaza calendario, hora, offset o formato inválido: %s", (value) => {
    expect(
      parsearInstante(value, { interpretarSinZonaComoUtc: true }),
    ).toBeNull();
    expect(formatearFechaHoraArgentina(value)).toBeNull();
  });

  it("no transforma fechas fiscales o de calendario en instantes", () => {
    expect(analizarFechaHoraIso("2026-10-03")?.hasTime).toBe(false);
    expect(
      parsearInstante("2026-10-03", { interpretarSinZonaComoUtc: true }),
    ).toBeNull();
    expect(parsearInstante("2026-10-03Z")).toBeNull();
  });

  it("maneja ausencia y Date inválido sin lanzar excepciones de formato", () => {
    expect(formatearFechaHoraArgentina(null)).toBeNull();
    expect(formatearFechaHoraArgentina("")).toBeNull();
    expect(formatearFechaHoraArgentina(new Date(Number.NaN))).toBeNull();
  });
});
