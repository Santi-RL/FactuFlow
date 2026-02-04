import { defineConfig, devices } from '@playwright/test'

/**
 * Configuración de Playwright para tests E2E de FactuFlow
 * 
 * Documentación: https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  // Directorio de tests
  testDir: './e2e',
  
  // Ejecutar tests en paralelo dentro del mismo archivo
  fullyParallel: true,
  
  // No permitir test.only en CI
  forbidOnly: !!process.env.CI,
  
  // Reintentos en CI
  retries: process.env.CI ? 2 : 0,
  
  // Workers en CI
  workers: process.env.CI ? 1 : undefined,
  
  // Reporter
  reporter: [
    ['html', { open: 'never' }],
    ['list']
  ],
  
  // Configuración global de tests
  use: {
    // URL base de la aplicación
    baseURL: 'http://localhost:8080',
    
    // Capturar screenshot solo en fallos
    screenshot: 'only-on-failure',
    
    // Grabar video solo en fallos
    video: 'retain-on-failure',
    
    // Trace para debugging
    trace: 'on-first-retry',
    
    // Viewport por defecto
    viewport: { width: 1280, height: 720 },
    
    // Ignorar errores HTTPS en desarrollo
    ignoreHTTPSErrors: true,
  },

  // Proyectos para diferentes navegadores
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    // Tests en móvil
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'mobile-safari',
      use: { ...devices['iPhone 12'] },
    },
  ],

  // Servidor de desarrollo local
  webServer: {
    command: 'npm run preview',
    url: 'http://localhost:8080',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
})
