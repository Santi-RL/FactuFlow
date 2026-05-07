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
    await expect(page.getByLabel(/empresa activa/i)).toBeVisible();
    await page.getByLabel(/empresa activa/i).selectOption("2");
    await expect(page.getByLabel(/empresa activa/i)).toHaveValue("2");
    await expect(
      page.getByText("Sucursal Norte SRL", { exact: true }),
    ).toBeVisible();
  });

  test("debe validar y procesar un lote", async ({ page }) => {
    await page.locator('input[type="file"]').setInputFiles({
      name: "lote-prueba.xlsx",
      mimeType:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      buffer: Buffer.from("archivo e2e"),
    });

    await page.getByRole("button", { name: /validar lote/i }).click();

    await expect(page.getByText(/archivo validado/i)).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /lote-e2e-1\.xlsx/i }),
    ).toBeVisible();
    await expect(page.getByText(/listos para emitir/i)).toBeVisible();
    await expect(
      page.getByRole("button", { name: /emitir comprobantes validos/i }),
    ).toBeEnabled();

    await page
      .getByRole("button", { name: /emitir comprobantes validos/i })
      .click();

    await expect(
      page.getByText(/lote procesado|emision iniciada/i),
    ).toBeVisible();
    await expect(
      page.getByRole("main").getByText("Completado", { exact: true }).first(),
    ).toBeVisible();
    await expect(
      page
        .getByRole("main")
        .getByText(/todos los comprobantes del lote fueron emitidos/i),
    ).toBeVisible();
  });
});
