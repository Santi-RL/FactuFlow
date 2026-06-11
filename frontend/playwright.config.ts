import { defineConfig, devices } from "@playwright/test";

const fullBrowserMatrix = process.env.E2E_FULL_BROWSER_MATRIX === "1";
const externalServer = process.env.E2E_EXTERNAL_SERVER === "1";
const e2eHost = "127.0.0.1";
const e2ePort = Number(process.env.E2E_PORT || 18080);
const e2eBaseURL = `http://${e2eHost}:${e2ePort}`;

const chromiumProject = {
  name: "chromium",
  use: { ...devices["Desktop Chrome"] },
};

const fullBrowserProjects = [
  chromiumProject,
  {
    name: "firefox",
    use: { ...devices["Desktop Firefox"] },
  },
  {
    name: "webkit",
    use: { ...devices["Desktop Safari"] },
  },
  {
    name: "mobile-chrome",
    use: { ...devices["Pixel 5"] },
  },
  {
    name: "mobile-safari",
    use: { ...devices["iPhone 12"] },
  },
];

/**
 * Configuración de Playwright para tests E2E de FactuFlow
 *
 * Documentación: https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  // Directorio de tests
  testDir: "./e2e",

  // Ejecutar tests en paralelo dentro del mismo archivo
  fullyParallel: false,

  // No permitir test.only en CI
  forbidOnly: !!process.env.CI,

  // Reintentos en CI
  retries: process.env.CI ? 2 : 0,

  // Un solo worker mantiene estables los mocks E2E y replica CI.
  workers: 1,

  // Reporter
  reporter: [["html", { open: "never" }], ["list"]],

  // Configuración global de tests
  use: {
    // URL base de la aplicación
    baseURL: e2eBaseURL,

    // Capturar screenshot solo en fallos
    screenshot: "only-on-failure",

    // Grabar video solo en fallos
    video: "retain-on-failure",

    // Trace para debugging
    trace: "on-first-retry",

    // Viewport por defecto
    viewport: { width: 1280, height: 720 },

    // Ignorar errores HTTPS en desarrollo
    ignoreHTTPSErrors: true,
  },

  // Suite estable por defecto. La matriz completa se ejecuta solo bajo pedido
  // con E2E_FULL_BROWSER_MATRIX=1.
  projects: fullBrowserMatrix ? fullBrowserProjects : [chromiumProject],

  ...(externalServer
    ? {}
    : {
        // Servidor local determinístico para E2E. No reutilizar dev servers activos:
        // pueden servir módulos fuente de Vite y volver los mocks demasiado amplios.
        webServer: {
          command:
            `node ./node_modules/vite/bin/vite.js --host ${e2eHost} --port ${e2ePort} --strictPort`,
          url: e2eBaseURL,
          reuseExistingServer: false,
          timeout: 120 * 1000,
        },
      }),
});
