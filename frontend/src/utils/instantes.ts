export const ZONA_HORARIA_ARGENTINA = "America/Argentina/Buenos_Aires";

export interface OpcionesInstante {
  /** Sólo para campos cuya procedencia establece que los valores sin zona son UTC. */
  interpretarSinZonaComoUtc?: boolean;
}

const ISO_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,9}))?)?)?(Z|[+-]\d{2}:\d{2})?$/i;

/** Valida el calendario sin convertir una fecha o una hora de procedencia desconocida. */
export const analizarFechaHoraIso = (value: string) => {
  const match = value.trim().match(ISO_PATTERN);
  if (!match) return null;
  const [
    ,
    yearRaw,
    monthRaw,
    dayRaw,
    hourRaw = "00",
    minuteRaw = "00",
    secondRaw = "00",
    fractionRaw = "",
    zoneRaw,
  ] = match;
  const hasTime = Boolean(match[4]);
  const year = Number(yearRaw);
  const month = Number(monthRaw);
  const day = Number(dayRaw);
  const hour = Number(hourRaw);
  const minute = Number(minuteRaw);
  const second = Number(secondRaw);
  const millisecond = Number(fractionRaw.padEnd(3, "0").slice(0, 3));
  if (year < 1) return null;

  // Evita el tratamiento especial de Date.UTC para los años 00 a 99.
  const calendar = new Date(0);
  calendar.setUTCFullYear(year, month - 1, day);
  calendar.setUTCHours(hour, minute, second, millisecond);
  if (
    calendar.getUTCFullYear() !== year ||
    calendar.getUTCMonth() !== month - 1 ||
    calendar.getUTCDate() !== day ||
    calendar.getUTCHours() !== hour ||
    calendar.getUTCMinutes() !== minute ||
    calendar.getUTCSeconds() !== second
  )
    return null;

  const zone = zoneRaw?.toUpperCase() || null;
  if (zone && !hasTime) return null;
  let offsetMinutes = 0;
  if (zone && zone !== "Z") {
    const [offsetHour, offsetMinute] = zone.slice(1).split(":").map(Number);
    if (offsetHour > 23 || offsetMinute > 59) return null;
    offsetMinutes =
      (offsetHour * 60 + offsetMinute) * (zone[0] === "+" ? 1 : -1);
  }

  return {
    yearRaw,
    monthRaw,
    dayRaw,
    hourRaw,
    minuteRaw,
    zone,
    hasTime,
    milisegundosSinOffset: calendar.getTime(),
    offsetMinutes,
  };
};

/** Una fecha de calendario sin hora nunca se interpreta como un instante. */
export const parsearInstante = (
  value: string | Date | null | undefined,
  opciones: OpcionesInstante = {},
): Date | null => {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : new Date(value.getTime());
  }
  if (!value) return null;
  const partes = analizarFechaHoraIso(value);
  if (!partes?.hasTime) return null;
  if (!partes.zone && !opciones.interpretarSinZonaComoUtc) return null;
  return new Date(partes.milisegundosSinOffset - partes.offsetMinutes * 60_000);
};

const FORMATO_FECHA_HORA = new Intl.DateTimeFormat("es-AR", {
  timeZone: ZONA_HORARIA_ARGENTINA,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export const formatearFechaHoraArgentina = (
  value: string | Date | null | undefined,
  opciones: OpcionesInstante = {},
): string | null => {
  const instante = parsearInstante(value, opciones);
  return instante ? FORMATO_FECHA_HORA.format(instante) : null;
};
