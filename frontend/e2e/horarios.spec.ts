import { expect, test } from "@playwright/test";
import { loginAsAdmin, mockApi } from "./helpers";

for (const timezoneId of ["UTC", "Asia/Tokyo"]) {
  test.describe(`Hora argentina con navegador ${timezoneId}`, () => {
    test.use({ timezoneId });

    test("muestra la carga del lote en Argentina sin emitir", async ({ page }) => {
      await mockApi(page);
      let solicitudesEmision = 0;
      page.on("request", (request) => {
        if (
          request.method() === "POST" &&
          /\/api\/(?:lotes-comprobantes\/\d+\/(?:procesar|reintentar-fallidos)|comprobantes\/emitir)(?:\?|$)/.test(
            request.url(),
          )
        ) {
          solicitudesEmision += 1;
        }
      });
      await loginAsAdmin(page);
      await page.getByTestId("nav-lotes-comprobantes").click();
      await page.waitForURL(/comprobantes\/lotes/);
      await page.locator('input[type="file"]').setInputFiles({
        name: "lote-horarios-sintetico.xlsx",
        mimeType:
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        buffer: Buffer.from("archivo sintético de horarios"),
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

      // El mock registra 12:00 UTC: debe verse 09:00 en Argentina en ambos browsers.
      await expect(
        page.getByText(/Cargado 09\/03\/2026.*09:00/).first(),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: /emitir comprobantes válidos/i }),
      ).toBeEnabled();
      expect(solicitudesEmision).toBe(0);
    });
  });
}
