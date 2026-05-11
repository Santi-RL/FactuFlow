import { describe, expect, it } from "vitest";

import {
  esProvinciaArgentina,
  normalizarProvinciaArgentina,
} from "./provincias";

describe("provincias", () => {
  it("normaliza variantes de provincias argentinas", () => {
    expect(normalizarProvinciaArgentina("BUENOS AIRES")).toBe("Buenos Aires");
    expect(normalizarProvinciaArgentina("Cordoba")).toBe("Córdoba");
    expect(normalizarProvinciaArgentina("Ciudad Autonoma de Buenos Aires")).toBe(
      "CABA",
    );
  });

  it("rechaza valores que no pertenecen al catalogo", () => {
    expect(esProvinciaArgentina("IMPUESTOS/REGIMENES")).toBe(false);
    expect(normalizarProvinciaArgentina("IMPUESTOS/REGIMENES")).toBeNull();
  });
});
