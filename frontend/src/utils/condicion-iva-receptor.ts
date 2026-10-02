import { CONDICIONES_IVA } from "@/types/comprobante";

const aliases: Record<string, string> = {
  ri: "Responsable Inscripto",
  "responsable inscripto": "Responsable Inscripto",
  "iva responsable inscripto": "Responsable Inscripto",
  monotributo: "Monotributo",
  "responsable monotributo": "Monotributo",
  exento: "Exento",
  "iva sujeto exento": "Exento",
  cf: "Consumidor Final",
  "consumidor final": "Consumidor Final",
  consumidor_final: "Consumidor Final",
};

export function nombreCondicionIvaReceptor(valor: string): string | null {
  return aliases[valor.trim().replace(/\s+/g, " ").toLowerCase()] ?? null;
}

export function condicionesIvaReceptor(tipo: number): string[] {
  if ([1, 2, 3].includes(tipo)) return CONDICIONES_IVA.slice(0, 2);
  if ([6, 7, 8].includes(tipo)) return CONDICIONES_IVA.slice(2);
  if ([11, 12, 13].includes(tipo)) return [...CONDICIONES_IVA];
  return [];
}

export function condicionIvaReceptorValida(
  valor: string,
  tipo: number,
): boolean {
  const nombre = nombreCondicionIvaReceptor(valor);
  return nombre !== null && condicionesIvaReceptor(tipo).includes(nombre);
}
