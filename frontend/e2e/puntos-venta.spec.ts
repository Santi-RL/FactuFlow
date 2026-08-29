import { expect, test } from "@playwright/test";

import { loginAsUser, mockApi } from "./helpers";

test.describe("Puntos de venta", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await loginAsUser(page);
  });

  test("un usuario común puede comprobar con ARCA sin acceder a la importación", async ({
    page,
  }) => {
    await page.goto("/puntos-venta");

    await expect(
      page.getByRole("heading", { name: "Puntos de venta" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Comprobar con ARCA" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Importar constancia" }),
    ).toHaveCount(0);

    const comprobacion = page.waitForRequest(
      (request) =>
        request.method() === "POST" &&
        request.url().endsWith("/api/puntos-venta/sincronizar-arca"),
    );
    await page.getByRole("button", { name: "Comprobar con ARCA" }).click();
    await comprobacion;

    await expect(page.getByText("Comprobación completa")).toBeVisible();
    await expect(
      page.getByText("Listo para emitir", { exact: true }),
    ).toBeVisible();
  });
});
