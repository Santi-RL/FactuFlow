import { expect, test } from "@playwright/test";
import { loginAsAdmin, mockApi } from "./helpers";

test.describe("Emisión masiva", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await loginAsAdmin(page);
    await Promise.all([
      page.waitForResponse(
        (response) =>
          new URL(response.url()).pathname === "/api/perfiles-carga-masiva" &&
          response.ok(),
      ),
      page.waitForURL(/comprobantes\/lotes/),
      page.getByTestId("nav-lotes-comprobantes").click(),
    ]);
  });

  test("debe permitir cambiar la empresa activa", async ({ page }) => {
    await expect(page.getByLabel(/emisor activo/i)).toBeVisible();
    await Promise.all([
      page.waitForResponse(
        (response) =>
          new URL(response.url()).pathname === "/api/perfiles-carga-masiva" &&
          response.request().headers()["x-empresa-id"] === "2" &&
          response.ok(),
      ),
      page.getByLabel(/emisor activo/i).selectOption("2"),
    ]);
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
    await page.getByRole("button", { name: /emitir con esta fecha/i }).click();

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

  test("advierte una segunda carga contablemente equivalente sin avisar duplicados anónimos internos", async ({
    page,
  }) => {
    let processRequests = 0;
    page.on("request", (request) => {
      if (/\/api\/lotes-comprobantes\/\d+\/procesar/.test(request.url())) {
        processRequests += 1;
      }
    });

    const prepareFile = async (name: string) => {
      await page.locator('input[type="file"]').setInputFiles({
        name,
        mimeType:
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        buffer: Buffer.from(`contenido visual ${name}`),
      });
      await page.getByRole("radio", { name: /productos/i }).check();
      await page
        .getByRole("radio", { name: /utilizar la descripción del archivo/i })
        .check();
      await page
        .getByRole("radio", { name: /^utilizar la fecha del archivo$/i })
        .first()
        .check();
      await page.getByTestId("validar-lote-final").click();
      await expect(page.getByText(/archivo validado/i)).toBeVisible();
    };

    await prepareFile("ventas-anonimas-original.xlsx");
    await expect(page.getByTestId("resumen-control-duplicados")).toHaveCount(0);
    await page
      .getByRole("button", { name: /emitir comprobantes válidos/i })
      .click();
    await page.getByRole("button", { name: /emitir con esta fecha/i }).click();
    await expect(
      page.getByRole("main").getByText("Completado", { exact: true }).first(),
    ).toBeVisible();

    await page.setViewportSize({ width: 390, height: 844 });
    await prepareFile("ventas-anonimas-reordenadas.xlsx");
    await expect(page.getByTestId("resumen-control-duplicados")).toContainText(
      "Hay coincidencias que requieren revisión",
    );
    await page
      .getByRole("button", { name: /emitir comprobantes válidos/i })
      .click();
    await page.getByRole("button", { name: /emitir con esta fecha/i }).click();

    const dialog = page.getByRole("dialog", {
      name: /coincide por completo con otro ya emitido/i,
    });
    await expect(dialog).toBeVisible();
    await page.evaluate(() => {
      document.body.style.zoom = "150%";
    });
    await expect(dialog).toBeVisible();
    const review = dialog.getByRole("button", { name: "Volver a revisar" });
    await expect(review).toBeFocused();
    await expect(dialog).toContainText("Usuario de emisión no registrado");
    const checkbox = dialog.getByRole("checkbox");
    await expect(checkbox).not.toBeChecked();
    await checkbox.focus();
    await checkbox.press("Enter");
    await expect(checkbox).not.toBeChecked();
    expect(processRequests).toBe(2);
    await checkbox.press("Space");
    await expect(checkbox).toBeChecked();
    const accept = dialog.getByRole("button", {
      name: "Emitir como operaciones nuevas",
    });
    await expect(accept).toBeEnabled();
    await accept.dblclick();
    await expect(dialog).toHaveCount(0);
    expect(processRequests).toBe(3);
    await expect(
      page.getByRole("main").getByText("Completado", { exact: true }).first(),
    ).toBeVisible();
  });
});
