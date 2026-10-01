import { describe, expect, it } from "vitest";
import { condicionIvaReceptorValida } from "./condicion-iva-receptor";

describe("matriz de condición IVA del receptor", () => {
  it.each([1, 2, 3, 6, 7, 8, 11, 12, 13])(
    "respeta la clase del tipo %i",
    (tipo) => {
      for (const valor of ["RI", "Monotributo", "Exento", "CF"]) {
        const esperada =
          tipo >= 11 ||
          (tipo <= 3 ? ["RI", "Monotributo"] : ["Exento", "CF"]).includes(
            valor,
          );
        expect(condicionIvaReceptorValida(valor, tipo)).toBe(esperada);
      }
      for (const valor of ["", "RNI", "Responsable No Inscripto", "Otra"]) {
        expect(condicionIvaReceptorValida(valor, tipo)).toBe(false);
      }
    },
  );
});
