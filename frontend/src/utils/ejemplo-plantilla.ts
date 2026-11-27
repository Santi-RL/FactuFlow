import { formatearFecha } from "@/composables/useFormatters";

const fechas = new Set(["fecha_origen", "fecha_emision", "fecha_servicio_desde",
  "fecha_servicio_hasta", "fecha_vto_pago", "asociado_fecha"]);
const decimales = new Set(["importe_total", "item_cantidad", "item_precio_unitario",
  "item_descuento_porcentaje", "item_iva_porcentaje"]);

/** Sólo ejemplos administrativos. Un texto ambiguo puede haber sido escrito en argentino. */
export function ejemploVisible(campo: string, ejemplo: string): string {
  if (fechas.has(campo) && /^\d{4}-\d{2}-\d{2}$/.test(ejemplo))
    return formatearFecha(ejemplo);
  if (!decimales.has(campo) || /^-?\d{1,3}(?:\.\d{3})+$/.test(ejemplo)) return ejemplo;
  const partes = /^(-?\d+)(?:\.(\d+))?$/.exec(ejemplo);
  if (!partes) return ejemplo;
  const entero = partes[1].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return partes[2] ? entero + "," + partes[2] : entero;
}
