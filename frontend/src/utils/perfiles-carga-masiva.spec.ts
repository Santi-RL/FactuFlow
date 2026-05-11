import { describe, expect, it } from "vitest";

import type { PerfilCargaMasiva } from "@/types/perfil-carga-masiva";
import {
  resolverPerfilCargaMasiva,
  seleccionarPerfilInicial,
} from "./perfiles-carga-masiva";

const crearPerfil = (
  overrides: Partial<PerfilCargaMasiva["configuracion_json"]> = {},
): PerfilCargaMasiva => ({
  id: 1,
  empresa_id: 1,
  nombre: "Servicios mensuales",
  descripcion: null,
  es_predeterminado: true,
  activo: true,
  created_at: "2026-05-09T00:00:00",
  updated_at: "2026-05-09T00:00:00",
  configuracion_json: {
    version: 1,
    formato_importacion_version_id: 10,
    punto_venta: { modo: "archivo", numero: null },
    concepto_modo: "servicios",
    descripcion_item_modo: "fija",
    descripcion_item_fija: "Ajuste",
    fecha_emision: { modo: "ultimo_dia_mes_anterior" },
    periodo_servicio: { modo: "mes_anterior_completo" },
    fecha_vto_pago: { modo: "emision_mas_dias", dias: 10 },
    ...overrides,
  },
});

describe("resolverPerfilCargaMasiva", () => {
  it("resuelve ultimo dia del mes anterior y vencimiento relativo", () => {
    const result = resolverPerfilCargaMasiva(
      crearPerfil(),
      new Date(2026, 4, 9),
    );

    expect(result.formatoVersionId).toBe(10);
    expect(result.opciones.punto_venta_modo).toBe("archivo");
    expect(result.opciones.punto_venta_numero).toBeUndefined();
    expect(result.opciones.fecha_emision_modo).toBe("fija");
    expect(result.opciones.fecha_emision_fija).toBe("2026-04-30");
    expect(result.opciones.fecha_servicio_desde_fija).toBe("2026-04-01");
    expect(result.opciones.fecha_servicio_hasta_fija).toBe("2026-04-30");
    expect(result.opciones.fecha_vto_pago_fija).toBe("2026-05-10");
  });

  it("resuelve fecha personalizada, mes actual completo y mismo dia de emision", () => {
    const result = resolverPerfilCargaMasiva(
      crearPerfil({
        fecha_emision: { modo: "personalizada", fecha: "2026-05-09" },
        periodo_servicio: { modo: "mes_actual_completo" },
        fecha_vto_pago: { modo: "mismo_dia_emision" },
      }),
      new Date(2026, 4, 9),
    );

    expect(result.opciones.fecha_emision_fija).toBe("2026-05-09");
    expect(result.opciones.fecha_servicio_desde_fija).toBe("2026-05-01");
    expect(result.opciones.fecha_servicio_hasta_fija).toBe("2026-05-31");
    expect(result.opciones.fecha_vto_pago_fija).toBe("2026-05-09");
  });

  it("deja modos de archivo sin convertir a fechas fijas", () => {
    const result = resolverPerfilCargaMasiva(
      crearPerfil({
        fecha_emision: { modo: "archivo" },
        periodo_servicio: { modo: "archivo" },
        fecha_vto_pago: { modo: "archivo" },
      }),
      new Date(2026, 4, 9),
    );

    expect(result.opciones.fecha_emision_modo).toBe("archivo");
    expect(result.opciones.fecha_emision_fija).toBeUndefined();
    expect(result.opciones.fecha_servicio_desde_modo).toBe("archivo");
    expect(result.opciones.fecha_vto_pago_modo).toBe("archivo");
  });

  it("resuelve punto de venta fijo del perfil", () => {
    const result = resolverPerfilCargaMasiva(
      crearPerfil({
        punto_venta: { modo: "fijo", numero: 13 },
      }),
      new Date(2026, 4, 9),
    );

    expect(result.opciones.punto_venta_modo).toBe("fijo");
    expect(result.opciones.punto_venta_numero).toBe(13);
  });
});

describe("seleccionarPerfilInicial", () => {
  it("autoaplica el unico perfil disponible", () => {
    const perfil = crearPerfil();
    expect(seleccionarPerfilInicial([perfil])).toBe(perfil);
  });

  it("autoaplica el predeterminado cuando hay varios", () => {
    const primero = crearPerfil({ concepto_modo: "productos" });
    const segundo = {
      ...crearPerfil({ concepto_modo: "servicios" }),
      id: 2,
      es_predeterminado: false,
    };

    expect(seleccionarPerfilInicial([segundo, primero])).toBe(primero);
  });

  it("no autoaplica si hay varios sin predeterminado", () => {
    const primero = { ...crearPerfil(), es_predeterminado: false };
    const segundo = { ...crearPerfil(), id: 2, es_predeterminado: false };

    expect(seleccionarPerfilInicial([primero, segundo])).toBeNull();
  });
});
