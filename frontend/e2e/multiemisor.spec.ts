import { expect, test, type Route } from "@playwright/test";

import { loginAsUser, mockApi } from "./helpers";

const now = "2026-09-01T12:00:00.000Z";
const empresas = [
  {
    id: 1,
    razon_social: "Empresa Test S.A.",
    cuit: "20123456789",
    condicion_iva: "RI",
    domicilio: "Av. Siempre Viva 123",
    localidad: "Buenos Aires",
    provincia: "Buenos Aires",
    codigo_postal: "1000",
    email: null,
    telefono: null,
    inicio_actividades: "2020-01-01",
    logo: null,
    created_at: now,
    updated_at: now,
  },
  {
    id: 2,
    razon_social: "Sucursal Norte SRL",
    cuit: "30712345678",
    condicion_iva: "RI",
    domicilio: "Calle Falsa 742",
    localidad: "Córdoba",
    provincia: "Córdoba",
    codigo_postal: "5000",
    email: null,
    telefono: null,
    inicio_actividades: "2021-05-01",
    logo: null,
    created_at: now,
    updated_at: now,
  },
];

const responderJson = (route: Route, status: number, body: unknown) =>
  route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });

test("operador A/B no ve C y una revocación abierta limpia el contexto", async ({
  page,
}) => {
  await mockApi(page);
  let empresaIds = [1, 2];

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const headers = request.headers();
    const empresaId = Number(headers["x-empresa-id"] || 0);

    if (url.pathname === "/api/auth/me" && method === "GET") {
      return responderJson(route, 200, {
        id: 2,
        email: "usuario.local@example.test",
        nombre: "Usuario",
        empresa_id: empresaIds.length === 1 ? empresaIds[0] : null,
        empresa_ids: empresaIds,
        puede_crear_editar_emisores: false,
        activo: true,
        es_admin: false,
        created_at: now,
        ultimo_login: null,
      });
    }
    if (url.pathname === "/api/empresas" && method === "GET") {
      return responderJson(
        route,
        200,
        empresas.filter((empresa) => empresaIds.includes(empresa.id)),
      );
    }
    if (empresaId && !empresaIds.includes(empresaId)) {
      return responderJson(route, 403, {
        detail: "No tenés permiso para operar el emisor seleccionado",
      });
    }
    return route.fallback();
  });

  await loginAsUser(page, false);

  const selector = page.getByLabel(/emisor activo/i);
  await expect(selector).toHaveValue("");
  await expect(selector.locator('option[value="1"]')).toHaveCount(1);
  await expect(selector.locator('option[value="2"]')).toHaveCount(1);
  await expect(selector.locator('option[value="3"]')).toHaveCount(0);

  await selector.selectOption("1");
  await expect(selector).toHaveValue("1");

  const estadoManipulacion = await page.evaluate(async () => {
    const token = window.localStorage.getItem("token");
    const response = await fetch("/api/clientes", {
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Empresa-Id": "3",
      },
    });
    return response.status;
  });
  expect(estadoManipulacion).toBe(403);

  empresaIds = [2];
  await page.getByTestId("nav-clientes").click();

  await expect(page.getByText("Acceso al emisor revocado")).toBeVisible();
  await expect(selector).toHaveValue("");
  await expect(selector.locator('option[value="1"]')).toHaveCount(0);
  await expect(selector.locator('option[value="2"]')).toHaveCount(1);
});
