import { test, expect } from '@playwright/test'
import { mockApi, loginAsAdmin } from './helpers'

/**
 * Tests E2E para navegación básica de FactuFlow
 */

// Fixture para usuario autenticado
test.describe('Navegación', () => {
  // Antes de cada test, simular login
  test.beforeEach(async ({ page }) => {
    await mockApi(page)
    await loginAsAdmin(page)
  })

  test('debe mostrar el sidebar con menú de navegación', async ({ page }) => {
    // Verificar items del sidebar
    await expect(page.getByRole('link', { name: /dashboard/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /clientes/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /comprobantes/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /certificados/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /reportes/i })).toBeVisible()
  })

  test('debe navegar a la página de clientes', async ({ page }) => {
    await page.getByRole('link', { name: /clientes/i }).click()
    await expect(page).toHaveURL(/clientes/)
    await expect(page.getByRole('heading', { name: /clientes/i })).toBeVisible()
  })

  test('debe navegar a la página de comprobantes', async ({ page }) => {
    await page.getByRole('link', { name: /comprobantes/i }).click()
    await expect(page).toHaveURL(/comprobantes/)
    await expect(page.getByRole('heading', { name: /^comprobantes$/i })).toBeVisible()
  })

  test('debe navegar a la página de certificados', async ({ page }) => {
    await page.getByRole('link', { name: /certificados/i }).click()
    await expect(page).toHaveURL(/certificados/)
    await expect(page.getByRole('heading', { name: /^certificados arca$/i })).toBeVisible()
  })

  test('debe navegar a la página de reportes', async ({ page }) => {
    await page.getByRole('link', { name: /reportes/i }).click()
    await expect(page).toHaveURL(/reportes/)
    await expect(page.getByRole('heading', { name: /^📊\s*reportes$/i })).toBeVisible()
  })
})
