import { expect, test, type Page, type Route } from "@playwright/test";
import { loginAsAdmin, mockApi } from "./helpers";

const now = "2026-06-27T12:00:00.000Z";

const corsHeaders = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS",
  "access-control-allow-headers":
    "Content-Type, Authorization, X-Empresa-Id, X-Idempotency-Key, X-Confirmacion-Fecha-Fiscal, X-Confirmacion-Duplicado-Logico",
};

const storageResumen = {
  generated_at: now,
  estado: "necesita_atencion",
  total_bytes_usados: 78_643_200,
  total_bytes_recuperables: 23_040_000,
  storage_limit_bytes: 214_748_3648,
  disk_total_bytes: 53_687_091_200,
  disk_used_bytes: 18_450_000_000,
  disk_free_bytes: 35_237_091_200,
  categorias: [
    {
      clave: "lotes",
      nombre: "Lotes",
      bytes_usados: 35_840_000,
      bytes_recuperables: 18_432_000,
      items: 3,
      estado: "necesita_atencion",
      descripcion: "Detalle original de lotes cerrados.",
    },
    {
      clave: "logs",
      nombre: "Logs",
      bytes_usados: 6_144_000,
      bytes_recuperables: 4_608_000,
      items: 2,
      estado: "correcto",
      descripcion: "Logs antiguos administrados por FactuFlow.",
    },
    {
      clave: "certificados",
      nombre: "Certificados",
      bytes_usados: 128_000,
      bytes_recuperables: 0,
      items: 2,
      estado: "correcto",
      descripcion: "Certificados activos y archivos gestionados.",
    },
  ],
  emisores: [
    {
      empresa_id: 1,
      etiqueta: "Emisor demo · CUIT terminado en 6789",
      lotes: 4,
      filas_persistidas: 2400,
      filas_compactables: 1800,
      comprobantes: 1432,
      bytes_estimados: 35_840_000,
      bytes_recuperables: 18_432_000,
    },
    {
      empresa_id: 2,
      etiqueta: "Sucursal norte · CUIT terminado en 1111",
      lotes: 1,
      filas_persistidas: 120,
      filas_compactables: 0,
      comprobantes: 80,
      bytes_estimados: 1_024_000,
      bytes_recuperables: 0,
    },
  ],
};

const storageLotes = [
  {
    id: 501,
    empresa_id: 1,
    etiqueta_emisor: "Emisor demo · CUIT terminado en 6789",
    estado: "completado",
    total_filas: 1800,
    total_grupos: 1432,
    filas_persistidas: 1800,
    bytes_recuperables: 18_432_000,
    created_at: now,
    finished_at: now,
  },
];

const storageLogs = [
  {
    id: "log-soporte-2026-06",
    nombre: "backend-rotado-2026-06.log",
    categoria: "logs",
    bytes_usados: 4_608_000,
    bytes_recuperables: 4_608_000,
    descripcion: "Log rotado administrado por FactuFlow.",
    created_at: now,
  },
];

const storageTemporales = [
  {
    id: "tmp-export-observados",
    nombre: "export-observados-vencido.xlsx",
    categoria: "temporales",
    bytes_usados: 1_048_576,
    bytes_recuperables: 1_048_576,
    descripcion: "Temporal descargable vencido.",
    created_at: now,
  },
];

const storageCertificados = [
  {
    id: "cert-demo-huerfano",
    nombre: "certificado-demo-huerfano.crt",
    categoria: "certificados_huerfanos",
    bytes_usados: 8_192,
    bytes_recuperables: 8_192,
    descripcion: "Archivo gestionado no referenciado.",
    created_at: now,
  },
];

const exportacionPreparada = {
  token: "storage-e2e-token",
  estado: "preparada",
  archivo_nombre: "factuflow-almacenamiento-e2e.zip",
  checksum_sha256: "checksum-e2e",
  size_bytes: 9_216_000,
  created_at: now,
  downloaded_at: null,
  released_at: null,
  manifest: {},
};

const fulfillJson = async (route: Route, payload: unknown, status = 200) => {
  if (route.request().method().toUpperCase() === "OPTIONS") {
    await route.fulfill({
      status: 204,
      headers: corsHeaders,
    });
    return;
  }
  await route.fulfill({
    status,
    contentType: "application/json",
    headers: corsHeaders,
    body: JSON.stringify(payload),
  });
};

const mockStorageApi = async (page: Page) => {
  await page.route("**/api/health/db", async (route) => {
    await fulfillJson(route, {
      status: "healthy",
      message: "Conexión a la base de datos OK",
    });
  });
  await page.route("**/api/arca/status", async (route) => {
    await fulfillJson(route, {
      ambiente: "produccion",
      certificado_activo: true,
      certificado_id: 1,
      certificado_nombre: "Certificado ficticio",
      certificado_vencimiento: "2028-05-04T00:00:00",
    });
  });
  await page.route("**/api/almacenamiento/resumen", async (route) => {
    await fulfillJson(route, storageResumen);
  });
  await page.route("**/api/almacenamiento/lotes-compactables", async (route) => {
    await fulfillJson(route, storageLotes);
  });
  await page.route("**/api/almacenamiento/logs", async (route) => {
    await fulfillJson(route, storageLogs);
  });
  await page.route("**/api/almacenamiento/temporales", async (route) => {
    await fulfillJson(route, storageTemporales);
  });
  await page.route(
    "**/api/almacenamiento/certificados-huerfanos",
    async (route) => {
      await fulfillJson(route, storageCertificados);
    },
  );
  await page.route("**/api/almacenamiento/exportaciones", async (route) => {
    await fulfillJson(route, exportacionPreparada);
  });
  await page.route(
    "**/api/almacenamiento/exportaciones/storage-e2e-token/descargar",
    async (route) => {
      if (route.request().method().toUpperCase() === "OPTIONS") {
        await route.fulfill({
          status: 204,
          headers: corsHeaders,
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/zip",
        headers: {
          ...corsHeaders,
          "access-control-expose-headers": "X-FactuFlow-Download-Token",
          "x-factuflow-download-token": "download-token-e2e",
        },
        body: "zip-e2e",
      });
    },
  );
  await page.route(
    "**/api/almacenamiento/exportaciones/storage-e2e-token/confirmar-descarga",
    async (route) => {
      await fulfillJson(route, {
        ...exportacionPreparada,
        estado: "descargada",
        downloaded_at: now,
      });
    },
  );
  await page.route(
    "**/api/almacenamiento/exportaciones/storage-e2e-token/confirmar-liberacion",
    async (route) => {
      await fulfillJson(route, {
        mensaje: "Espacio liberado en datos ficticios.",
        bytes_afectados: 23_040_000,
        items_afectados: 3,
      });
    },
  );
};

test("Sistema > Almacenamiento muestra y resguarda datos administrados sin exponer datos sensibles", async ({
  page,
}) => {
  await mockApi(page);
  await mockStorageApi(page);

  await loginAsAdmin(page);
  await Promise.all([
    page.waitForURL(/sistema/),
    page.getByTestId("nav-sistema").click(),
  ]);
  await page.getByRole("button", { name: "Almacenamiento" }).click();

  await expect(page.getByText("Uso medido")).toBeVisible();
  await expect(page.getByText("Lotes compactables")).toBeVisible();
  await expect(page.getByText("Uso por emisor")).toBeVisible();
  await expect(page.getByText("Emisor demo · CUIT terminado en 6789")).toHaveCount(
    2,
  );
  await expect(page.getByText("backend-rotado-2026-06.log")).toBeVisible();
  await expect(page.getByText("export-observados-vencido.xlsx")).toBeVisible();
  await expect(page.getByText("certificado-demo-huerfano.crt")).toBeVisible();

  const bodyText = await page.locator("main").innerText();
  expect(bodyText).not.toContain("20123456789");
  expect(bodyText).not.toContain("30712345678");
  expect(bodyText).not.toContain("C:\\");
  expect(bodyText).not.toContain("/var/");

  await page.getByRole("row", { name: /Lote #501/ }).getByRole("checkbox").check();
  await page.getByLabel(/backend-rotado-2026-06\.log/).check();
  await page.getByLabel(/export-observados-vencido\.xlsx/).check();
  await page.getByRole("button", { name: "Preparar ZIP" }).click();
  await expect(page.getByText("factuflow-almacenamiento-e2e.zip")).toBeVisible();

  await page.getByRole("button", { name: "Descargar resguardo" }).click();
  await expect(page.getByRole("button", { name: "Liberar espacio" })).toBeEnabled();
  await page.getByRole("button", { name: "Liberar espacio" }).click();
  await expect(page.getByText("Se compactarán o eliminarán")).toBeVisible();
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response
          .url()
          .includes(
            "/api/almacenamiento/exportaciones/storage-e2e-token/confirmar-liberacion",
          ) &&
        response.request().method() === "POST" &&
        response.status() === 200,
    ),
    page.getByRole("button", { name: "Ya lo descargué" }).click(),
  ]);
  await expect(
    page.getByRole("heading", { name: "Espacio liberado" }),
  ).toBeVisible();
  await expect(
    page.getByText("Espacio liberado en datos ficticios."),
  ).toBeVisible();
});
