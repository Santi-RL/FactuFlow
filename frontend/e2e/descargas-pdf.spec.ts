import { test, expect } from "@playwright/test";
import { mockApi, loginAsAdmin } from "./helpers";

test("PDF por fila y ZIP de resultados entre páginas sin emisión", async ({
  page,
}, testInfo) => {
  await mockApi(page);
  await page.route("**/comprobantes*", (route) =>
    route.request().isNavigationRequest() ? route.continue() : route.fallback(),
  );
  const fila = (id: number) => ({
    id,
    tipo_comprobante: 11,
    numero: id,
    punto_venta_numero: 5,
    fecha_emision: "2026-11-01",
    total: 100,
    moneda: "PES",
    estado: "autorizado",
    cae: "12345678901234",
    cliente_nombre: "Cliente sintético",
  });
  await page.route(/\/api\/comprobantes\/(\?.*)?$/, (route) => {
    const pagina = Number(
      new URL(route.request().url()).searchParams.get("page") || 1,
    );
    return route.fulfill({
      json: {
        items: [fila(pagina === 1 ? 1 : 21)],
        total: 25,
        page: pagina,
        per_page: 20,
        pages: 2,
      },
    });
  });
  await page.route("**/api/pdf/seleccion*", (route) =>
    route.fulfill({
      json: { ids: Array.from({ length: 25 }, (_, i) => i + 1), total: 25 },
    }),
  );
  await page.route("**/api/pdf/comprobante/1", (route) =>
    route.fulfill({
      contentType: "application/pdf",
      body: "%PDF-sintetico",
      headers: {
        "Content-Disposition":
          'attachment; filename="FACTURA_C_0005-00000001.pdf"',
      },
    }),
  );
  let recibidos: number[] = [];
  let fallo = false;
  await page.route("**/api/pdf/zip", (route) => {
    recibidos = route.request().postDataJSON().ids;
    return fallo
      ? route.fulfill({
          status: 409,
          json: {
            detail: {
              fallidos: [
                {
                  comprobante_id: 2,
                  comprobante: "Factura_C_0005-00000002.pdf",
                  mensaje: "El PDF no está disponible.",
                },
              ],
            },
          },
        })
      : route.fulfill({ contentType: "application/zip", body: "PK-sintetico" });
  });
  let emisiones = 0;
  page.on("request", (r) => {
    if (r.url().includes("/emitir")) emisiones++;
  });
  await loginAsAdmin(page);
  await page.goto("/comprobantes");
  const casillaPagina = page.getByRole("checkbox", {
    name: "Seleccionar esta página",
    exact: true,
  });
  await casillaPagina.focus();
  await page.keyboard.press("Space");
  await expect(page.getByText("1 seleccionado", { exact: true })).toBeVisible();
  await page.keyboard.press("Space");
  await expect(
    page.getByText("0 seleccionados", { exact: true }),
  ).toBeVisible();
  const [pdf] = await Promise.all([
    page.waitForEvent("download"),
    page
      .getByRole("button", { name: "Descargar PDF 0005-00000001", exact: true })
      .click(),
  ]);
  expect(pdf.suggestedFilename()).toBe("FACTURA_C_0005-00000001.pdf");
  await expect(page).toHaveURL(/\/comprobantes$/);
  await page
    .getByRole("button", { name: "Seleccionar los 25 resultados filtrados" })
    .click();
  await expect(
    page.getByText("25 seleccionados", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Siguiente", exact: true }).click();
  await page
    .getByRole("checkbox", {
      name: "Seleccionar comprobante 0005-00000021",
      exact: true,
    })
    .uncheck();
  const [zip] = await Promise.all([
    page.waitForEvent("download"),
    page
      .getByRole("button", { name: "Descargar 24 PDF en ZIP", exact: true })
      .click(),
  ]);
  expect(zip.suggestedFilename()).toBe("Comprobantes_24.zip");
  expect(recibidos).toHaveLength(24);
  expect(recibidos).not.toContain(21);
  fallo = true;
  let archivos = 0;
  page.on("download", () => archivos++);
  await page
    .getByRole("button", { name: "Descargar 24 PDF en ZIP", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("No se descargó el ZIP");
  await expect(page.getByRole("alert")).toContainText("00000002");
  expect(archivos).toBe(0);
  expect(emisiones).toBe(0);
  await page.screenshot({
    path: testInfo.outputPath("descargas-listado-sintetico.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: testInfo.outputPath("descargas-listado-movil-sintetico.png"),
    fullPage: true,
  });
});
