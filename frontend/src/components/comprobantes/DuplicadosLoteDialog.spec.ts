import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";

import type {
  ControlDuplicadosLote,
  DuplicadosCoincidenciasPage,
} from "@/types/lote-comprobante";
import DuplicadosLoteDialog from "./DuplicadosLoteDialog.vue";

const controlCompleto = (
  overrides: Partial<ControlDuplicadosLote> = {},
): ControlDuplicadosLote => ({
  version: "duplicados_lotes/v2",
  cobertura: "completa",
  estado: "requiere_confirmacion",
  evidencia_id: "v2.evidencia-uno",
  datos_hash: "datos-uno",
  seleccion_hash: "seleccion-uno",
  tipos_coincidencia: ["historica_completa"],
  cantidad_actual: 50,
  cantidad_afectada: 50,
  importe_actual: "250000.00",
  importe_afectado: "250000.00",
  importes_actuales: {
    por_moneda: [{ moneda: "PES", importe: "250000.00", cantidad: 50 }],
    cantidad_sin_moneda_acreditada: 0,
  },
  importes_afectados: {
    por_moneda: [{ moneda: "PES", importe: "250000.00", cantidad: 50 }],
    cantidad_sin_moneda_acreditada: 0,
  },
  antecedentes_resumen: [
    {
      origen: "lote",
      lote_id: 18,
      nombre_archivo: "Ventas abril.xlsx",
      comprobante_ref: null,
      tipo_coincidencia: "historica_completa",
      cobertura: "completa",
      cantidad_lote_anterior: 50,
      cantidad_coincidente: 50,
      cantidad_autorizada: 50,
      cantidad_solo_validada: 0,
      cantidad_reservada_en_curso: 0,
      cantidad_fallida: 0,
      cantidad_incierta: 0,
      importe_lote_anterior: "250000.00",
      importe_lote_actual: "250000.00",
      importe_afectado: "250000.00",
      importes_lote_actual: {
        por_moneda: [{ moneda: "PES", importe: "250000.00", cantidad: 50 }],
        cantidad_sin_moneda_acreditada: 0,
      },
      importes_lote_anterior: {
        por_moneda: [{ moneda: "PES", importe: "250000.00", cantidad: 50 }],
        cantidad_sin_moneda_acreditada: 0,
      },
      importes_afectados: {
        por_moneda: [{ moneda: "PES", importe: "250000.00", cantidad: 50 }],
        cantidad_sin_moneda_acreditada: 0,
      },
      emitido_desde: "2026-04-15T13:35:00Z",
      emitido_hasta: "2026-04-15T13:36:00Z",
      hora_confiable: true,
      solicitantes: [
        { usuario_id: 7, nombre: "Operador de ejemplo", estado: "registrado" },
      ],
    },
  ],
  aceptacion_requerida: true,
  aceptacion_habilitada: true,
  bloqueo_operacion_ajena: null,
  detalle_url: "/api/lotes-comprobantes/20/coincidencias",
  ...overrides,
});

const details: DuplicadosCoincidenciasPage = {
  items: [
    {
      grupo_actual_id: 1,
      comprobante_actual_ref: "LOTE-ACTUAL-001",
      origen: "lote",
      tipo_coincidencia: "historica_completa",
      campos_coincidentes: ["contenido_completo"],
      lote_anterior_id: 18,
      grupo_anterior_id: 2,
      comprobante_anterior_ref: null,
      operacion_anterior_ref: "operacion-opaca",
      estado_grupo_anterior: "autorizado",
      importe: "5000.00",
      moneda: "PES",
      cotizacion: "1.00",
      solicitantes: [],
      solicitud_emision_at: null,
      solicitud_arca_at: null,
      resultado_fiscal_at: null,
      hora_confiable: false,
    },
  ],
  page: 1,
  per_page: 50,
  total: 51,
  total_pages: 2,
};

const antecedenteIndividual = () => ({
  ...controlCompleto().antecedentes_resumen[0],
  origen: "comprobante_individual" as const,
  lote_id: null,
  nombre_archivo: null,
  comprobante_ref: "COMP-ANTERIOR",
  tipo_coincidencia: "historica_individual_legacy" as const,
  cantidad_lote_anterior: null,
  importe_lote_anterior: null,
});

const wrappers: VueWrapper[] = [];
const render = (control = controlCompleto(), acceptanceAvailable = true) => {
  const wrapper = mount(DuplicadosLoteDialog, {
    attachTo: document.body,
    props: { show: true, control, acceptanceAvailable },
  });
  wrappers.push(wrapper);
  return wrapper;
};

afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  document.body.innerHTML = "";
});

describe("DuplicadosLoteDialog", () => {
  it("prioriza revisar y exige el checkbox antes de aceptar una coincidencia completa", async () => {
    const wrapper = render();
    await flushPromises();

    const review = Array.from(document.querySelectorAll("button")).find(
      (button) => button.textContent?.trim() === "Volver a revisar",
    ) as HTMLButtonElement;
    const accept = Array.from(document.querySelectorAll("button")).find(
      (button) =>
        button.textContent?.trim() === "Emitir como operaciones nuevas",
    ) as HTMLButtonElement;
    const checkbox = document.querySelector(
      'input[type="checkbox"]',
    ) as HTMLInputElement;

    expect(document.body.textContent).toContain(
      "Este lote coincide por completo con otro ya emitido",
    );
    expect(document.body.textContent).toContain("Ventas abril.xlsx");
    expect(document.activeElement).toBe(review);
    expect(checkbox.checked).toBe(false);
    expect(accept.disabled).toBe(true);

    checkbox.focus();
    checkbox.click();
    await flushPromises();
    expect(document.activeElement).toBe(checkbox);
    expect(accept.disabled).toBe(false);
    await accept.click();
    expect(wrapper.emitted("accept")).toHaveLength(1);
  });

  it("usa el texto específico para coincidencias internas y no inventa un lote anterior", async () => {
    render(
      controlCompleto({
        tipos_coincidencia: ["interna_receptor"],
        antecedentes_resumen: [],
        cantidad_actual: 3,
        cantidad_afectada: 2,
      }),
    );
    await flushPromises();
    expect(document.body.textContent).toContain(
      "Hay comprobantes del mismo receptor dentro del lote",
    );
    expect(document.body.textContent).toContain(
      "Confirmo que los comprobantes señalados corresponden a operaciones distintas",
    );
    expect(document.body.textContent).not.toContain("Archivo anterior");
  });

  it.each([
    {
      name: "interna y lote anterior",
      tipos: ["interna_receptor", "historica_completa"] as const,
      antecedentes: controlCompleto().antecedentes_resumen,
      clausulas: [
        "los comprobantes señalados corresponden a operaciones distintas",
        "estos comprobantes corresponden a operaciones nuevas, distintas de las del lote anterior",
      ],
    },
    {
      name: "interna y comprobante individual anterior",
      tipos: ["interna_receptor", "historica_individual_legacy"] as const,
      antecedentes: [antecedenteIndividual()],
      clausulas: [
        "los comprobantes señalados corresponden a operaciones distintas",
        "estos comprobantes corresponden a operaciones nuevas, distintas de la del comprobante anterior",
      ],
    },
    {
      name: "lote y comprobante individual anteriores",
      tipos: ["historica_completa", "historica_individual_legacy"] as const,
      antecedentes: [
        ...controlCompleto().antecedentes_resumen,
        antecedenteIndividual(),
      ],
      clausulas: [
        "estos comprobantes corresponden a operaciones nuevas, distintas de las del lote anterior",
        "estos comprobantes corresponden a operaciones nuevas, distintas de la del comprobante anterior",
      ],
    },
    {
      name: "interna, lote y comprobante individual anteriores",
      tipos: [
        "interna_receptor",
        "historica_completa",
        "historica_individual_legacy",
      ] as const,
      antecedentes: [
        ...controlCompleto().antecedentes_resumen,
        antecedenteIndividual(),
      ],
      clausulas: [
        "los comprobantes señalados corresponden a operaciones distintas",
        "estos comprobantes corresponden a operaciones nuevas, distintas de las del lote anterior",
        "estos comprobantes corresponden a operaciones nuevas, distintas de la del comprobante anterior",
      ],
    },
  ])(
    "incluye todas las cláusulas y exige aceptar cuando combina $name",
    async ({ tipos, antecedentes, clausulas }) => {
      const wrapper = render(
        controlCompleto({
          tipos_coincidencia: [...tipos],
          antecedentes_resumen: antecedentes,
        }),
      );
      await flushPromises();

      const checkbox = document.querySelector(
        'input[type="checkbox"]',
      ) as HTMLInputElement;
      const accept = Array.from(document.querySelectorAll("button")).find(
        (button) =>
          button.textContent?.trim() === "Emitir como operaciones nuevas",
      ) as HTMLButtonElement;

      clausulas.forEach((clausula) =>
        expect(document.body.textContent).toContain(clausula),
      );
      expect(document.querySelectorAll('input[type="checkbox"]')).toHaveLength(
        1,
      );
      expect(checkbox.checked).toBe(false);
      expect(accept.disabled).toBe(true);

      checkbox.click();
      await flushPromises();
      expect(accept.disabled).toBe(false);
      await accept.click();
      expect(wrapper.emitted("accept")).toHaveLength(1);
    },
  );

  it("distingue coincidencia parcial e historia individual con datos desconocidos", async () => {
    const individual = {
      ...antecedenteIndividual(),
      emitido_desde: null,
      hora_confiable: false,
      solicitantes: [],
    };
    render(
      controlCompleto({
        tipos_coincidencia: [
          "historica_parcial_receptor",
          "historica_individual_legacy",
        ],
        cantidad_actual: 10,
        cantidad_afectada: 2,
        antecedentes_resumen: [individual],
      }),
    );
    await flushPromises();
    expect(document.body.textContent).toContain(
      "2 de 10 comprobantes coinciden",
    );
    expect(document.body.textContent).toContain(
      "Comprobante anterior COMP-ANTERIOR",
    );
    expect(document.body.textContent).toContain(
      "Usuario de emisión no registrado",
    );
    expect(document.body.textContent).toContain("Fecha y hora no registradas");
  });

  it("concuerda las cantidades singulares del título, resumen y antecedente", async () => {
    const antecedente = {
      ...controlCompleto().antecedentes_resumen[0],
      cantidad_lote_anterior: 1,
      cantidad_coincidente: 1,
      cantidad_autorizada: 1,
      cantidad_solo_validada: 1,
      cantidad_reservada_en_curso: 1,
      cantidad_fallida: 1,
      cantidad_incierta: 1,
    };
    render(
      controlCompleto({
        tipos_coincidencia: ["historica_parcial_receptor"],
        cantidad_actual: 1,
        cantidad_afectada: 1,
        antecedentes_resumen: [antecedente],
      }),
    );
    await flushPromises();

    expect(document.body.textContent).toContain("1 de 1 comprobante coincide");
    expect(document.body.textContent).toContain("1 coincidente;");
    expect(document.body.textContent).toContain(
      "1 autorizado, 1 pendiente, 1 en proceso, 1 fallido, 1 incierto",
    );
    expect(document.body.textContent).not.toContain("1 comprobantes");
    expect(document.body.textContent).not.toContain("1 coincidentes");
    expect(document.body.textContent).not.toContain("1 autorizados");
  });

  it("no atribuye emisión completa cuando un lote de contenido igual tuvo resultado parcial", async () => {
    const partialHistory = {
      ...controlCompleto().antecedentes_resumen[0],
      cantidad_autorizada: 20,
      cantidad_fallida: 80,
    };
    render(
      controlCompleto({
        antecedentes_resumen: [partialHistory],
        cantidad_actual: 100,
        cantidad_afectada: 100,
      }),
    );
    await flushPromises();
    expect(document.body.textContent).toContain(
      "coincide por completo con el contenido de otro lote",
    );
    expect(document.body.textContent).toContain("20 autorizados");
    expect(document.body.textContent).toContain("80 fallidos");
    expect(document.body.textContent).not.toContain(
      "coincide por completo con otro ya emitido",
    );
  });

  it("desglosa monedas sin sumarlas y señala importes sin moneda acreditada", async () => {
    render(
      controlCompleto({
        importe_actual: null,
        importe_afectado: null,
        importes_actuales: {
          por_moneda: [
            { moneda: "DOL", importe: "100.00", cantidad: 1 },
            { moneda: "PES", importe: "5000.00", cantidad: 2 },
          ],
          cantidad_sin_moneda_acreditada: 1,
        },
        importes_afectados: {
          por_moneda: [{ moneda: "DOL", importe: "100.00", cantidad: 1 }],
          cantidad_sin_moneda_acreditada: 1,
        },
      }),
    );
    await flushPromises();
    expect(document.body.textContent).toContain("US$ 100,00 en 1 comprobante");
    expect(document.body.textContent).toContain("$ 5.000,00 en 2 comprobantes");
    expect(document.body.textContent).toContain(
      "1 comprobante sin moneda acreditada",
    );
    expect(document.body.textContent).not.toContain("5.100");
  });

  it("Escape vuelve a revisar y Enter implícito no acepta", async () => {
    const wrapper = render();
    await flushPromises();
    const checkbox = document.querySelector(
      'input[type="checkbox"]',
    ) as HTMLInputElement;
    checkbox.click();
    checkbox.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
    expect(wrapper.emitted("accept")).toBeUndefined();
    checkbox.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    );
    expect(wrapper.emitted("review")).toHaveLength(1);
  });

  it("consulta detalle y lote anterior sin perder la advertencia", async () => {
    const wrapper = render();
    await flushPromises();
    const detailsButton = Array.from(document.querySelectorAll("button")).find(
      (button) => button.textContent?.trim() === "Ver coincidencias",
    ) as HTMLButtonElement;
    await detailsButton.click();
    expect(wrapper.emitted("requestDetails")?.[0]).toEqual([1]);
    await wrapper.setProps({ details });
    expect(document.body.textContent).toContain("Coincidencia con el lote 18");
    expect(document.body.textContent).toContain(
      "Comprobante actual LOTE-ACTUAL-001",
    );
    expect(document.body.textContent).toContain(
      "Usuario de emisión no registrado",
    );

    const back = document.querySelector("[data-return]") as HTMLButtonElement;
    (document.activeElement as HTMLElement).dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Tab",
        shiftKey: true,
        bubbles: true,
      }),
    );
    expect(document.activeElement).toBe(back);
    await back.click();
    await flushPromises();
    const recreatedDetailsButton = Array.from(
      document.querySelectorAll("button"),
    ).find((button) => button.textContent?.trim() === "Ver coincidencias");
    expect(document.activeElement).toBe(recreatedDetailsButton);

    const priorButton = Array.from(document.querySelectorAll("button")).find(
      (button) => button.textContent?.trim() === "Ver lote anterior",
    ) as HTMLButtonElement;
    await priorButton.click();
    expect(document.body.textContent).toContain("Lote anterior 18");
    expect(document.body.textContent).toContain("50 autorizados");
  });

  it("limpia la decisión y devuelve el foco cuando cambia la evidencia", async () => {
    const wrapper = render();
    await flushPromises();
    (
      document.querySelector('input[type="checkbox"]') as HTMLInputElement
    ).click();
    await flushPromises();
    await wrapper.setProps({
      control: controlCompleto({ evidencia_id: "v2.evidencia-dos" }),
      acceptanceAvailable: false,
    });
    await flushPromises();
    expect(document.querySelector('input[type="checkbox"]')).toBeNull();
    expect(document.body.textContent).toContain(
      "solicitá la emisión nuevamente para decidir sobre la evidencia actual",
    );
    expect((document.activeElement as HTMLElement).textContent?.trim()).toBe(
      "Volver a revisar",
    );
  });

  it("no ofrece excepción cuando otra operación relevante está en curso", async () => {
    render(
      controlCompleto({
        estado: "operacion_en_curso",
        aceptacion_habilitada: false,
        bloqueo_operacion_ajena: {
          referencia: "seguimiento-externo",
          estado: "incierta",
          cantidad_afectada: 4,
          detectado_at: "2026-04-15T13:35:00Z",
        },
      }),
    );
    await flushPromises();
    expect(document.body.textContent).toContain(
      "otra emisión coincidente en curso",
    );
    expect(document.body.textContent).toContain("seguimiento-externo");
    expect(document.body.textContent).not.toContain(
      "Emitir como operaciones nuevas",
    );
    expect(document.querySelector('input[type="checkbox"]')).toBeNull();
  });

  it("no inventa hora para una fecha sin hora ni convierte un offset inválido", async () => {
    const first = {
      ...controlCompleto().antecedentes_resumen[0],
      lote_id: 18,
      emitido_desde: "2026-04-15",
      emitido_hasta: "2026-04-15",
    };
    const second = {
      ...controlCompleto().antecedentes_resumen[0],
      lote_id: 19,
      emitido_desde: "2026-04-15T10:35:00+99:99",
      emitido_hasta: "2026-04-15T10:35:00+99:99",
    };
    render(controlCompleto({ antecedentes_resumen: [first, second] }));
    await flushPromises();
    expect(document.body.textContent).toContain(
      "15/04/2026 (hora no registrada)",
    );
    expect(document.body.textContent).toContain(
      "Fecha y hora históricas no comprobables",
    );
  });

  it("convierte el historial confiable con zona y conserva la incertidumbre del resto", async () => {
    const original = controlCompleto().antecedentes_resumen[0];
    render(controlCompleto({
      antecedentes_resumen: [
        {
          ...original,
          lote_id: 18,
          emitido_desde: "2026-01-01T01:00:00Z",
          emitido_hasta: "2026-01-01T01:00:00Z",
        },
        {
          ...original,
          lote_id: 19,
          emitido_desde: "2026-01-01T01:00:00",
          emitido_hasta: "2026-01-01T01:00:00",
        },
        {
          ...original,
          lote_id: 20,
          emitido_desde: "2026-01-01T01:00:00Z",
          emitido_hasta: "2026-01-01T01:00:00Z",
          hora_confiable: false,
        },
      ],
    }));
    await flushPromises();

    expect(document.body.textContent).toContain("31/12/2025, 22:00");
    expect(document.body.textContent).toContain(
      "01/01/2026 01:00 (zona horaria no registrada)",
    );
    expect(document.body.textContent).toContain(
      "01/01/2026 (hora histórica no comprobable)",
    );
  });
});
