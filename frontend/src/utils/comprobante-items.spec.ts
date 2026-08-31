import { describe, expect, it } from "vitest";
import type { ItemComprobante } from "@/types/comprobante";
import {
  calcularImportesItems,
  crearItemsEmision,
  mensajeErrorItemsApi,
  subtotalItem,
} from "./comprobante-items";

const item = (): ItemComprobante => ({
  codigo: "A",
  descripcion: "Prueba",
  cantidad: 2,
  unidad: "unidad",
  precio_unitario: 100,
  descuento_porcentaje: 10,
  iva_porcentaje: 21,
  orden: 4,
});

describe("ítems de emisión PF-03B", () => {
  it("separa campos de respuesta sin alterar valores fiscales", () => {
    const editable = { ...item(), subtotal: 999, id: 8, comprobante_id: 10 };
    const [dto] = crearItemsEmision([editable]);
    expect(dto).toEqual({ ...item(), orden: 0 });
    expect(Object.keys(dto).sort()).toEqual(
      [
        "codigo",
        "descripcion",
        "cantidad",
        "unidad",
        "precio_unitario",
        "descuento_porcentaje",
        "iva_porcentaje",
        "orden",
      ].sort(),
    );
    expect(editable.subtotal).toBe(999);
  });

  it.each([0, 100])(
    "conserva descuento %s y precio cero explícito",
    (descuento) => {
      const dato = { ...item(), descuento_porcentaje: descuento };
      expect(calcularImportesItems([dato]).error).toBeNull();
      expect(subtotalItem(dato)).toBe(descuento === 0 ? 200 : 0);
      expect(subtotalItem({ ...dato, precio_unitario: 0 })).toBe(0);
    },
  );

  it.each([
    { descuento_porcentaje: -1 },
    { descuento_porcentaje: 101 },
    { descuento_porcentaje: NaN },
    { descuento_porcentaje: Infinity },
    { cantidad: Infinity },
    { cantidad: -Infinity },
    { cantidad: 0 },
    { precio_unitario: NaN },
    { precio_unitario: -1 },
    { iva_porcentaje: Infinity },
    { cantidad: 1e308, precio_unitario: 1e308 },
  ])("no produce importes con datos inválidos %j", (cambio) => {
    expect(
      calcularImportesItems([{ ...item(), ...cambio }]).totales,
    ).toBeNull();
    expect(subtotalItem({ ...item(), ...cambio })).toBeNull();
  });

  it("detecta desbordamiento al sumar ítems válidos", () => {
    const dato = {
      ...item(),
      cantidad: 1,
      precio_unitario: 1e308,
      descuento_porcentaje: 0,
      iva_porcentaje: 0,
    };
    expect(calcularImportesItems([dato]).error).toBeNull();
    expect(calcularImportesItems([dato, dato]).totales).toBeNull();
  });

  it("traduce 422 por ubicación sin revelar input, contexto ni mensajes crudos", () => {
    expect(
      mensajeErrorItemsApi([
        {
          loc: ["body", "items", 1, "descuento_porcentaje"],
          type: "less_than_equal",
          input: "privado",
          ctx: { dato: "privado" },
          msg: "privado",
        },
      ]),
    ).toBe("Ítem 2: El descuento debe ser un número entre 0 y 100.");
    expect(
      mensajeErrorItemsApi([
        { loc: ["body", "items", 0, "instruccion"], type: "extra_forbidden" },
      ]),
    ).toContain("datos no admitidos");
    expect(mensajeErrorItemsApi({ mensaje: "Error distinto" })).toBeNull();
  });
});
