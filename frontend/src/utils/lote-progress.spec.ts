import { describe, expect, it } from "vitest";

import type { LoteComprobante } from "@/types/lote-comprobante";
import { calcularProgresoLote, formatDuration } from "./lote-progress";

const crearLote = (overrides: Partial<LoteComprobante> = {}): LoteComprobante => ({
  id: 1,
  nombre_archivo: "lote.xlsx",
  archivo_hash: "hash",
  estado: "validado",
  modo_procesamiento: "sincronico",
  procesamiento_async: false,
  total_filas: 3,
  total_grupos: 3,
  grupos_validos: 3,
  grupos_con_error: 0,
  grupos_emitidos: 0,
  grupos_fallidos: 0,
  mensaje_resumen: null,
  metadata_json: null,
  mapeo_usado_json: null,
  headers_detectados_json: null,
  started_at: null,
  finished_at: null,
  created_at: "2026-05-10T12:00:00",
  updated_at: "2026-05-10T12:00:00",
  empresa_id: 1,
  usuario_id: null,
  formato_importacion_id: null,
  formato_importacion_version_id: null,
  ...overrides,
});

describe("formatDuration", () => {
  it("formatea minutos y segundos", () => {
    expect(formatDuration(42)).toBe("00:42");
    expect(formatDuration(75)).toBe("01:15");
  });

  it("incluye horas si corresponde", () => {
    expect(formatDuration(3661)).toBe("01:01:01");
  });
});

describe("calcularProgresoLote", () => {
  it("calcula progreso parcial sobre comprobantes emitibles", () => {
    const progreso = calcularProgresoLote(
      crearLote({
        estado: "procesando",
        grupos_validos: 2,
        grupos_emitidos: 1,
        grupos_fallidos: 1,
        grupos_con_error: 5,
        started_at: "2026-05-10T12:00:00",
      }),
      new Date("2026-05-10T12:01:00"),
    );

    expect(progreso.procesados).toBe(2);
    expect(progreso.pendientes).toBe(2);
    expect(progreso.totalEmitible).toBe(4);
    expect(progreso.porcentaje).toBe(50);
    expect(progreso.transcurridoTexto).toBe("01:00");
    expect(progreso.restanteTexto).toBe("01:00");
  });

  it("muestra estimando cuando no hay comprobantes procesados", () => {
    const progreso = calcularProgresoLote(
      crearLote({ estado: "en_cola", grupos_validos: 3 }),
      new Date("2026-05-10T12:00:30"),
      new Date("2026-05-10T12:00:00"),
    );

    expect(progreso.estaEnCola).toBe(true);
    expect(progreso.porcentaje).toBe(0);
    expect(progreso.transcurridoTexto).toBe("00:30");
    expect(progreso.restanteTexto).toBe("Estimando...");
  });

  it("usa finished_at para lotes completados", () => {
    const progreso = calcularProgresoLote(
      crearLote({
        estado: "completado",
        grupos_validos: 0,
        grupos_emitidos: 3,
        started_at: "2026-05-10T12:00:00",
        finished_at: "2026-05-10T12:02:00",
      }),
      new Date("2026-05-10T12:10:00"),
    );

    expect(progreso.porcentaje).toBe(100);
    expect(progreso.transcurridoTexto).toBe("02:00");
    expect(progreso.restanteTexto).toBe("Estimando...");
  });
});
