export const provinciasOptions = [
  { value: "Buenos Aires", label: "Buenos Aires" },
  { value: "CABA", label: "Ciudad Autónoma de Buenos Aires" },
  { value: "Catamarca", label: "Catamarca" },
  { value: "Chaco", label: "Chaco" },
  { value: "Chubut", label: "Chubut" },
  { value: "Córdoba", label: "Córdoba" },
  { value: "Corrientes", label: "Corrientes" },
  { value: "Entre Ríos", label: "Entre Ríos" },
  { value: "Formosa", label: "Formosa" },
  { value: "Jujuy", label: "Jujuy" },
  { value: "La Pampa", label: "La Pampa" },
  { value: "La Rioja", label: "La Rioja" },
  { value: "Mendoza", label: "Mendoza" },
  { value: "Misiones", label: "Misiones" },
  { value: "Neuquén", label: "Neuquén" },
  { value: "Río Negro", label: "Río Negro" },
  { value: "Salta", label: "Salta" },
  { value: "San Juan", label: "San Juan" },
  { value: "San Luis", label: "San Luis" },
  { value: "Santa Cruz", label: "Santa Cruz" },
  { value: "Santa Fe", label: "Santa Fe" },
  { value: "Santiago del Estero", label: "Santiago del Estero" },
  { value: "Tierra del Fuego", label: "Tierra del Fuego" },
  { value: "Tucumán", label: "Tucumán" },
];

const provinciasValues = new Set(provinciasOptions.map((option) => option.value));
const provinciasPorClave = new Map(
  provinciasOptions.flatMap((option) => {
    const aliases =
      option.value === "CABA"
        ? ["CABA", "CIUDAD AUTONOMA DE BUENOS AIRES", "CAPITAL FEDERAL"]
        : [option.value];
    return aliases.map((alias) => [normalizarClave(alias), option.value]);
  }),
);

export const esProvinciaArgentina = (value: string | null): value is string =>
  !!value && (provinciasValues.has(value) || provinciasPorClave.has(normalizarClave(value)));

export const normalizarProvinciaArgentina = (
  value: string | null,
): string | null => {
  if (!value) return null;
  return provinciasValues.has(value)
    ? value
    : provinciasPorClave.get(normalizarClave(value)) || null;
};

function normalizarClave(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toUpperCase();
}
