import { test, expect } from "@playwright/test";
import { mockApi, loginAsAdmin } from "./helpers";

/**
 * Tests E2E para emisión de comprobantes en FactuFlow
 */

test.describe("Emisión de Comprobantes", () => {
  // Antes de cada test, simular login
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await loginAsAdmin(page);
    await Promise.all([
      page.waitForURL(/comprobantes/),
      page.getByTestId("nav-comprobantes").click(),
    ]);
  });

  test("debe mostrar botón para crear nueva factura", async ({ page }) => {
    await expect(page.getByTestId("comprobantes-nueva-factura")).toBeVisible();
  });

  test("debe abrir formulario de nueva factura", async ({ page }) => {
    await Promise.all([
      page.waitForURL(/comprobantes\/nuevo/),
      page.getByTestId("comprobantes-nueva-factura").click(),
    ]);

    // Verificar que se abre el formulario
    await expect(page).toHaveURL(/comprobantes\/nuevo/);
    await expect(page.getByTestId("page-title")).toHaveText(/nueva factura/i);
    await expect(page.getByLabel(/tipo de comprobante/i)).toBeVisible();
    await expect(page.getByLabel(/punto de venta/i)).toBeVisible();
  });

  test("debe seleccionar tipo de comprobante", async ({ page }) => {
    await Promise.all([
      page.waitForURL(/comprobantes\/nuevo/),
      page.getByTestId("comprobantes-nueva-factura").click(),
    ]);

    // Seleccionar Factura A
    await page.getByLabel(/tipo de comprobante/i).selectOption("1"); // Factura A

    // El formulario debe actualizarse según el tipo
    await expect(page.getByLabel(/tipo de comprobante/i)).toHaveValue("1");
  });

  test("debe agregar items a la factura", async ({ page }) => {
    await Promise.all([
      page.waitForURL(/comprobantes\/nuevo/),
      page.getByTestId("comprobantes-nueva-factura").click(),
    ]);

    // Agregar un item
    await page
      .getByRole("button", { name: /agregar ítem|agregar item/i })
      .click();

    // Verificar que aparece el formulario de item
    await expect(page.getByLabel(/descripción/i).first()).toBeVisible();
    await expect(page.getByLabel(/cantidad/i).first()).toBeVisible();
    await expect(page.getByLabel(/precio unitario/i).first()).toBeVisible();
  });

  test("debe calcular totales automáticamente", async ({ page }) => {
    await Promise.all([
      page.waitForURL(/comprobantes\/nuevo/),
      page.getByTestId("comprobantes-nueva-factura").click(),
    ]);

    // Completar tipo de comprobante
    await page.getByLabel(/tipo de comprobante/i).selectOption("1");
    await page.getByLabel(/punto de venta/i).selectOption({ index: 0 });

    // Agregar un item con valores
    await page
      .getByRole("button", { name: /agregar ítem|agregar item/i })
      .click();
    await page
      .getByLabel(/descripción/i)
      .first()
      .fill("Servicio de consultoría");
    await page
      .getByLabel(/cantidad/i)
      .first()
      .fill("1");
    await page
      .getByLabel(/precio unitario/i)
      .first()
      .fill("1000");

    // Verificar que se calcula el total (1000 + IVA 21% = 1210)
    await expect(page.getByText("TOTAL:", { exact: true })).toBeVisible();
    await expect(page.getByText(/1\.210/)).toBeVisible();
  });

  test("debe mostrar vista previa antes de emitir", async ({ page }) => {
    await Promise.all([
      page.waitForURL(/comprobantes\/nuevo/),
      page.getByTestId("comprobantes-nueva-factura").click(),
    ]);

    // Completar formulario básico
    await page.getByLabel(/tipo de comprobante/i).selectOption("1");
    await page.getByLabel(/concepto/i).selectOption("1");
    await page.locator('input[type="date"]').first().fill("2026-03-09");
    await page.getByTestId("cliente-nuevo-manual").click();
    await page.getByLabel(/número/i).fill("20123456789");
    await page
      .getByLabel(/condición iva/i)
      .selectOption({ label: "Responsable Inscripto" });
    await page.getByLabel(/razón social/i).fill("Cliente Preview");
    await page
      .getByLabel(/descripción/i)
      .first()
      .fill("Servicio de prueba");
    await page
      .getByLabel(/cantidad/i)
      .first()
      .fill("1");
    await page
      .getByLabel(/precio unitario/i)
      .first()
      .fill("1000");

    // Click en vista previa
    await page.getByTestId("comprobante-vista-previa").click();

    // Verificar que se muestra el modal de preview
    await expect(
      page.getByTestId("comprobante-confirmar-emitir"),
    ).toBeVisible();
  });

  test("debe emitir comprobante (mock) al confirmar desde la vista previa", async ({
    page,
  }) => {
    await Promise.all([
      page.waitForURL(/comprobantes\/nuevo/),
      page.getByTestId("comprobantes-nueva-factura").click(),
    ]);

    await page.getByLabel(/tipo de comprobante/i).selectOption("6"); // Factura B
    await page.getByLabel(/punto de venta/i).selectOption({ index: 0 });
    await page.getByLabel(/concepto/i).selectOption("1");
    await page.locator('input[type="date"]').first().fill("2026-03-09");

    // Cliente manual
    await page.getByTestId("cliente-nuevo-manual").click();
    await page.getByLabel(/número/i).fill("20123456789");
    await page
      .getByLabel(/condición iva/i)
      .selectOption({ label: "Responsable Inscripto" });
    await page.getByLabel(/razón social/i).fill("Cliente Emitir");

    // Item
    await page
      .getByLabel(/descripción/i)
      .first()
      .fill("Servicio de prueba");
    await page
      .getByLabel(/cantidad/i)
      .first()
      .fill("1");
    await page
      .getByLabel(/precio unitario/i)
      .first()
      .fill("1000");

    // Abrir preview y confirmar
    await page.getByTestId("comprobante-vista-previa").click();
    await expect(
      page.getByTestId("comprobante-confirmar-emitir"),
    ).toBeVisible();

    await page.getByTestId("comprobante-confirmar-emitir").click();
    await expect(
      page.getByRole("button", { name: /emitir con esta fecha/i }),
    ).toBeVisible();

    const emitirRequest = page.waitForRequest((req) => {
      const url = req.url();
      return (
        (url.includes("/comprobantes/emitir") ||
          url.includes("/api/comprobantes/emitir")) &&
        req.method() === "POST"
      );
    });
    await Promise.all([
      page.getByRole("button", { name: /emitir con esta fecha/i }).click(),
      emitirRequest,
    ]);

    // Debe volver al listado
    await expect(page).toHaveURL(/comprobantes$/);
    await expect(page.getByText(/comprobante emitido/i)).toBeVisible();
  });
  test("debe conservar clave y payload al verificar una emisión incierta", async ({
    page,
  }) => {
    const solicitudes: Array<{ clave: string; payload: unknown }> = [];

    await page.route("**/api/comprobantes/emitir", async (route) => {
      if (route.request().method() !== "POST") {
        await route.fallback();
        return;
      }

      solicitudes.push({
        clave: route.request().headers()["x-idempotency-key"] || "",
        payload: route.request().postDataJSON(),
      });
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        headers: {
          "access-control-allow-origin": "*",
        },
        body: JSON.stringify({
          detail: {
            exito: false,
            tipo_comprobante: 6,
            punto_venta: 1,
            numero: 1,
            fecha: "2026-03-09",
            cae: null,
            cae_vencimiento: null,
            total: 1210,
            mensaje: "Respuesta incierta",
            errores: ["No reintentar con otra clave"],
            requiere_reconciliacion: true,
            categoria_error: "arca_respuesta_incierta",
          },
        }),
      });
    });

    await Promise.all([
      page.waitForURL(/comprobantes\/nuevo/),
      page.getByTestId("comprobantes-nueva-factura").click(),
    ]);

    await page.getByLabel(/tipo de comprobante/i).selectOption("6");
    await page.getByLabel(/punto de venta/i).selectOption({ index: 0 });
    await page.getByLabel(/concepto/i).selectOption("1");
    await page.locator('input[type="date"]').first().fill("2026-03-09");
    await page.getByTestId("cliente-nuevo-manual").click();
    await page.getByLabel(/número/i).fill("20123456789");
    await page
      .getByLabel(/condición iva/i)
      .selectOption({ label: "Responsable Inscripto" });
    await page.getByLabel(/razón social/i).fill("Cliente Incierto");
    await page
      .getByLabel(/descripción/i)
      .first()
      .fill("Servicio de prueba");
    await page
      .getByLabel(/cantidad/i)
      .first()
      .fill("1");
    await page
      .getByLabel(/precio unitario/i)
      .first()
      .fill("1000");

    await page.getByTestId("comprobante-vista-previa").click();
    await page.getByTestId("comprobante-confirmar-emitir").click();
    await page.getByRole("button", { name: /emitir con esta fecha/i }).click();

    await expect(page.getByTestId("operacion-incierta")).toBeVisible();
    await expect(page.getByTestId("formulario-emision")).toHaveAttribute(
      "inert",
      "",
    );
    await expect(page.getByTestId("comprobante-emitir")).toBeDisabled();
    await page.getByTestId("verificar-operacion-incierta").click();
    await expect.poll(() => solicitudes.length).toBe(2);

    expect(solicitudes[1].clave).toBe(solicitudes[0].clave);
    expect(solicitudes[1].payload).toEqual(solicitudes[0].payload);
    await expect(page.getByTestId("operacion-incierta")).toBeVisible();
  });
});
