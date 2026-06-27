import { expect, test } from "@playwright/test";
import { loginAsAdmin, mockApi } from "./helpers";

test.describe("Emisión masiva", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await loginAsAdmin(page);
    await Promise.all([
      page.waitForURL(/comprobantes\/lotes/),
      page.getByTestId("nav-lotes-comprobantes").click(),
    ]);
  });

  test("debe permitir cambiar la empresa activa", async ({ page }) => {
    await expect(page.getByLabel(/emisor activo/i)).toBeVisible();
    await page.getByLabel(/emisor activo/i).selectOption("2");
    await expect(page.getByLabel(/emisor activo/i)).toHaveValue("2");
    await expect(
      page.getByText("Sucursal Norte SRL", { exact: true }).first(),
    ).toBeVisible();
  });

  test("debe validar y procesar un lote", async ({ page }) => {
    await page.locator('input[type="file"]').setInputFiles({
      name: "lote-prueba.xlsx",
      mimeType:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      buffer: Buffer.from("archivo e2e"),
    });

    await page.getByRole("radio", { name: /productos/i }).check();
    await page
      .getByRole("radio", { name: /utilizar la descripción del archivo/i })
      .check();
    await page
      .getByRole("radio", { name: /^utilizar la fecha del archivo$/i })
      .first()
      .check();

    await expect(page.getByTestId("validar-lote-final")).toBeEnabled();
    await page.getByTestId("validar-lote-final").click();

    await expect(page.getByText(/archivo validado/i)).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /lote-e2e-1\.xlsx/i }),
    ).toBeVisible();
    await expect(
      page.getByText("Totales listos para emitir", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText(/Siguiente acción:/i)).toBeVisible();
    await expect(
      page.getByText("Resumen operativo completo", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /emitir comprobantes válidos/i }),
    ).toBeEnabled();

    await page
      .getByRole("button", { name: /emitir comprobantes válidos/i })
      .click();
    await page
      .getByRole("button", { name: /emitir con esta fecha/i })
      .click();

    await expect(
      page.getByText(/lote procesado|emisión iniciada/i),
    ).toBeVisible();
    await expect(
      page.getByRole("main").getByText("Completado", { exact: true }).first(),
    ).toBeVisible();
    await expect(
      page
        .getByRole("main")
        .getByText(/todos los comprobantes del lote fueron emitidos/i)
        .first(),
    ).toBeVisible();
  });
});
