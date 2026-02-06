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
    await expect(page.getByTestId('sidebar-logo')).toBeVisible()
    await expect(page.getByTestId('nav-dashboard')).toBeVisible()
    await expect(page.getByTestId('nav-clientes')).toBeVisible()
    await expect(page.getByTestId('nav-comprobantes')).toBeVisible()
    await expect(page.getByTestId('nav-certificados')).toBeVisible()
    await expect(page.getByTestId('nav-reportes')).toBeVisible()
  })

  test('debe navegar a la página de clientes', async ({ page }) => {
    await page.getByTestId('nav-clientes').click()
    await expect(page).toHaveURL(/clientes/)
    await expect(page.getByTestId('page-title')).toHaveText(/clientes/i)
  })

  test('debe navegar a la página de comprobantes', async ({ page }) => {
    await page.getByTestId('nav-comprobantes').click()
    await expect(page).toHaveURL(/comprobantes/)
    await expect(page.getByTestId('page-title')).toHaveText(/comprobantes/i)
  })

  test('debe navegar a la página de certificados', async ({ page }) => {
    await page.getByTestId('nav-certificados').click()
    await expect(page).toHaveURL(/certificados/)
    await expect(page.getByTestId('page-title')).toHaveText(/certificados/i)
  })

  test('debe navegar a la página de reportes', async ({ page }) => {
    await page.getByTestId('nav-reportes').click()
    await expect(page).toHaveURL(/reportes/)
    await expect(page.getByTestId('page-title')).toHaveText(/reportes/i)
  })
})
