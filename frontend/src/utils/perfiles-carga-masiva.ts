import type {
  PerfilCargaMasiva,
  PerfilCargaMasivaConfiguracion,
} from "@/types/perfil-carga-masiva";
import type { LoteOpcionesFechas } from "@/types/lote-comprobante";

export interface PerfilAplicadoLote {
  formatoVersionId: number | "";
  opciones: LoteOpcionesFechas;
}

const pad = (value: number) => String(value).padStart(2, "0");

export const formatLocalDate = (date: Date): string => {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
    date.getDate(),
  )}`;
};

const buildLocalDate = (
  year: number,
  month: number,
  day: number,
): Date | null => {
  if (!year || !month || !day) return null;
  const parsed = new Date(year, month - 1, day);
  if (
    parsed.getFullYear() !== year ||
    parsed.getMonth() !== month - 1 ||
    parsed.getDate() !== day
  ) {
    return null;
  }
  return parsed;
};

const parseLocalDate = (value?: string): Date | null => {
  const text = value?.trim();
  if (!text) return null;
  const iso = text.match(/^(\d{4})-(\d{2})-(\d{2})(?:$|[T ])/);
  if (iso) {
    return buildLocalDate(Number(iso[1]), Number(iso[2]), Number(iso[3]));
  }
  const argentina = text.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (argentina) {
    return buildLocalDate(
      Number(argentina[3]),
      Number(argentina[2]),
      Number(argentina[1]),
    );
  }
  return null;
};

const normalizeLocalDate = (value?: string): string | undefined => {
  const parsed = parseLocalDate(value);
  return parsed ? formatLocalDate(parsed) : undefined;
};

const addDays = (date: Date, days: number): Date => {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
};

const firstDayOfMonth = (baseDate: Date): Date => {
  return new Date(baseDate.getFullYear(), baseDate.getMonth(), 1);
};

const lastDayOfMonth = (baseDate: Date): Date => {
  return new Date(baseDate.getFullYear(), baseDate.getMonth() + 1, 0);
};

const firstDayOfPreviousMonth = (baseDate: Date): Date => {
  return new Date(baseDate.getFullYear(), baseDate.getMonth() - 1, 1);
};

const lastDayOfPreviousMonth = (baseDate: Date): Date => {
  return new Date(baseDate.getFullYear(), baseDate.getMonth(), 0);
};

export const configuracionPerfilVacia = (): PerfilCargaMasivaConfiguracion => ({
  version: 1,
  formato_importacion_version_id: null,
  punto_venta: { modo: "archivo", numero: null },
  concepto_modo: "",
  descripcion_item_modo: "",
  descripcion_item_fija: "",
  fecha_emision: { modo: "manual" },
  periodo_servicio: { modo: "manual" },
  fecha_vto_pago: { modo: "manual" },
});

export const seleccionarPerfilInicial = (
  perfiles: PerfilCargaMasiva[],
): PerfilCargaMasiva | null => {
  if (perfiles.length === 1) return perfiles[0];
  return perfiles.find((perfil) => perfil.es_predeterminado) || null;
};

export const resolverPerfilCargaMasiva = (
  perfil: PerfilCargaMasiva,
  baseDate?: Date,
): PerfilAplicadoLote => {
  const config = perfil.configuracion_json || configuracionPerfilVacia();
  const fechaEmision = resolverFechaEmision(config);
  const periodo = resolverPeriodoServicio(config, baseDate);
  const vencimiento = resolverVencimiento(config, fechaEmision);

  return {
    formatoVersionId: config.formato_importacion_version_id || "",
    opciones: {
      concepto_modo: config.concepto_modo || "",
      punto_venta_modo:
        config.punto_venta?.modo === "fijo" ? "fijo" : "archivo",
      punto_venta_numero:
        config.punto_venta?.modo === "fijo"
          ? Number(config.punto_venta.numero || 0) || undefined
          : undefined,
      descripcion_item_modo: config.descripcion_item_modo || "",
      descripcion_item_fija: config.descripcion_item_fija || undefined,
      fecha_emision_modo: fechaEmision.modo,
      fecha_emision_fija: fechaEmision.fecha,
      fecha_servicio_desde_modo: periodo.desdeModo,
      fecha_servicio_desde_fija: periodo.desde,
      fecha_servicio_hasta_modo: periodo.hastaModo,
      fecha_servicio_hasta_fija: periodo.hasta,
      fecha_vto_pago_modo: vencimiento.modo,
      fecha_vto_pago_fija: vencimiento.fecha,
    },
  };
};

const resolverFechaEmision = (
  config: PerfilCargaMasivaConfiguracion,
): { modo: "archivo" | "fija" | ""; fecha?: string } => {
  const regla = config.fecha_emision || { modo: "manual" };
  if (regla.modo === "archivo") return { modo: "archivo" };

  if (regla.modo === "personalizada") {
    const fecha = normalizeLocalDate(regla.fecha);
    if (fecha) return { modo: "fija", fecha };
  }
  return { modo: "", fecha: undefined };
};

const resolverPeriodoServicio = (
  config: PerfilCargaMasivaConfiguracion,
  baseDate?: Date,
): {
  desdeModo: "archivo" | "fija" | "";
  hastaModo: "archivo" | "fija" | "";
  desde?: string;
  hasta?: string;
} => {
  const regla = config.periodo_servicio || { modo: "manual" };
  if (regla.modo === "archivo") {
    return { desdeModo: "archivo", hastaModo: "archivo" };
  }
  if (regla.modo === "mes_anterior_completo") {
    if (!baseDate) return { desdeModo: "", hastaModo: "" };
    return {
      desdeModo: "fija",
      hastaModo: "fija",
      desde: formatLocalDate(firstDayOfPreviousMonth(baseDate)),
      hasta: formatLocalDate(lastDayOfPreviousMonth(baseDate)),
    };
  }
  if (regla.modo === "mes_actual_completo") {
    if (!baseDate) return { desdeModo: "", hastaModo: "" };
    return {
      desdeModo: "fija",
      hastaModo: "fija",
      desde: formatLocalDate(firstDayOfMonth(baseDate)),
      hasta: formatLocalDate(lastDayOfMonth(baseDate)),
    };
  }
  if (regla.modo === "personalizado") {
    const desde = normalizeLocalDate(regla.desde);
    const hasta = normalizeLocalDate(regla.hasta);
    if (desde && hasta && hasta >= desde) {
      return {
        desdeModo: "fija",
        hastaModo: "fija",
        desde,
        hasta,
      };
    }
  }
  return { desdeModo: "", hastaModo: "" };
};

const resolverVencimiento = (
  config: PerfilCargaMasivaConfiguracion,
  fechaEmision: { modo: "archivo" | "fija" | ""; fecha?: string },
): { modo: "archivo" | "fija" | ""; fecha?: string } => {
  const regla = config.fecha_vto_pago || { modo: "manual" };
  if (regla.modo === "archivo") return { modo: "archivo" };
  if (regla.modo === "personalizada") {
    const fecha = normalizeLocalDate(regla.fecha);
    if (fecha) return { modo: "fija", fecha };
  }
  if (regla.modo === "mismo_dia_emision" && fechaEmision.fecha) {
    return { modo: "fija", fecha: fechaEmision.fecha };
  }
  if (regla.modo === "emision_mas_dias" && fechaEmision.fecha) {
    const emision = parseLocalDate(fechaEmision.fecha);
    if (!emision) return { modo: "" };
    return {
      modo: "fija",
      fecha: formatLocalDate(addDays(emision, Number(regla.dias || 0))),
    };
  }
  return { modo: "", fecha: undefined };
};
