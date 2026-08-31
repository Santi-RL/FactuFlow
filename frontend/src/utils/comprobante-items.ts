import type { ItemComprobanteCreate } from "@/types/comprobante";

export const crearItemsEmision = (
  items: ItemComprobanteCreate[],
): ItemComprobanteCreate[] =>
  items.map((item, orden) => ({
    codigo: item.codigo,
    descripcion: item.descripcion,
    cantidad: item.cantidad,
    unidad: item.unidad,
    precio_unitario: item.precio_unitario,
    descuento_porcentaje: item.descuento_porcentaje,
    iva_porcentaje: item.iva_porcentaje,
    orden,
  }));

export const errorImportesItem = (
  item: ItemComprobanteCreate,
): string | null => {
  if (!Number.isFinite(item.cantidad) || item.cantidad <= 0)
    return "La cantidad debe ser un número mayor a cero.";
  if (!Number.isFinite(item.precio_unitario) || item.precio_unitario < 0)
    return "El precio unitario debe ser un número mayor o igual a cero.";
  if (
    !Number.isFinite(item.descuento_porcentaje) ||
    item.descuento_porcentaje < 0 ||
    item.descuento_porcentaje > 100
  )
    return "El descuento debe ser un número entre 0 y 100.";
  if (!Number.isFinite(item.iva_porcentaje) || item.iva_porcentaje < 0)
    return "La alícuota de IVA debe ser un número válido.";
  return null;
};

export const subtotalItem = (item: ItemComprobanteCreate): number | null => {
  if (errorImportesItem(item)) return null;
  const bruto = item.cantidad * item.precio_unitario;
  const subtotal = bruto - bruto * (item.descuento_porcentaje / 100);
  return Number.isFinite(subtotal) ? subtotal : null;
};

export const calcularImportesItems = (items: ItemComprobanteCreate[]) => {
  const totales = { subtotal: 0, iva21: 0, iva105: 0, iva27: 0, total: 0 };
  for (const [index, item] of items.entries()) {
    const error = errorImportesItem(item);
    const subtotal = subtotalItem(item);
    if (error || subtotal === null)
      return {
        totales: null,
        error: `Ítem ${index + 1}: ${error ?? "No se puede calcular un importe válido."}`,
      };
    totales.subtotal += subtotal;
    if (item.iva_porcentaje === 21) totales.iva21 += subtotal * 0.21;
    else if (item.iva_porcentaje === 10.5) totales.iva105 += subtotal * 0.105;
    else if (item.iva_porcentaje === 27) totales.iva27 += subtotal * 0.27;
    totales.total =
      totales.subtotal + totales.iva21 + totales.iva105 + totales.iva27;
    if (!Object.values(totales).every(Number.isFinite))
      return {
        totales: null,
        error: "Los ítems no permiten calcular un total válido.",
      };
  }
  return { totales, error: null };
};

export const mensajeErrorItemsApi = (detail: unknown): string | null => {
  if (!Array.isArray(detail)) return null;
  for (const error of detail) {
    if (!error || !Array.isArray(error.loc) || error.loc[1] !== "items")
      continue;
    const index = error.loc[2];
    const prefijo =
      Number.isInteger(index) && index >= 0 ? `Ítem ${index + 1}: ` : "";
    const campos: Record<string, string> = {
      cantidad: "Revisá la cantidad; debe ser un número mayor a cero.",
      precio_unitario:
        "Revisá el precio unitario; debe ser un número mayor o igual a cero.",
      descuento_porcentaje: "El descuento debe ser un número entre 0 y 100.",
      iva_porcentaje: "Revisá la alícuota de IVA.",
      descripcion: "Revisá la descripción del ítem.",
      unidad: "Revisá la unidad del ítem.",
      orden: "Revisá el orden del ítem.",
    };
    if (error.type === "extra_forbidden")
      return `${prefijo}Se enviaron datos no admitidos. Recargá la pantalla y revisá el ítem.`;
    return (
      prefijo +
      (campos[error.loc[3]] ??
        "Revisá los ítems y sus importes antes de emitir.")
    );
  }
  return null;
};
