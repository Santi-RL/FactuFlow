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

const parseLocalDate = (value?: string): Date | null => {
  if (!value) return null;
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day);
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
  const fechaEmision = resolverFechaEmision(config, baseDate);
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
  baseDate?: Date,
): { modo: "archivo" | "fija" | ""; fecha?: string } => {
  const regla = config.fecha_emision || { modo: "manual" };
  if (regla.modo === "archivo") return { modo: "archivo" };
  if (regla.modo === "ultimo_dia_mes_anterior") {
    if (!baseDate) return { modo: "", fecha: undefined };
    return {
      modo: "fija",
      fecha: formatLocalDate(lastDayOfPreviousMonth(baseDate)),
    };
  }
  if (regla.modo === "personalizada" && regla.fecha) {
    return { modo: "fija", fecha: regla.fecha };
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
  if (regla.modo === "personalizado" && regla.desde && regla.hasta) {
    return {
      desdeModo: "fija",
      hastaModo: "fija",
      desde: regla.desde,
      hasta: regla.hasta,
    };
  }
  return { desdeModo: "", hastaModo: "" };
};

const resolverVencimiento = (
  config: PerfilCargaMasivaConfiguracion,
  fechaEmision: { modo: "archivo" | "fija" | ""; fecha?: string },
): { modo: "archivo" | "fija" | ""; fecha?: string } => {
  const regla = config.fecha_vto_pago || { modo: "manual" };
  if (regla.modo === "archivo") return { modo: "archivo" };
  if (regla.modo === "personalizada" && regla.fecha) {
    return { modo: "fija", fecha: regla.fecha };
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
