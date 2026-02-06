import { test, expect } from '@playwright/test'
import { mockApi, loginAsAdmin } from './helpers'

/**
 * Tests E2E para gestión de clientes en FactuFlow
 */

test.describe('Gestión de Clientes', () => {
  // Antes de cada test, simular login
  test.beforeEach(async ({ page }) => {
    await mockApi(page)
    await loginAsAdmin(page)
    await page.getByTestId('nav-clientes').click()
    await page.waitForURL(/clientes/)
  })

  test('debe mostrar botón para crear nuevo cliente', async ({ page }) => {
    await expect(page.getByTestId('clientes-nuevo')).toBeVisible()
  })

  test('debe abrir formulario de nuevo cliente', async ({ page }) => {
    await page.getByTestId('clientes-nuevo').click()
    
    // Verificar que se abre el formulario
    await expect(page).toHaveURL(/clientes\/nuevo/)
    await expect(page.getByLabel(/razón social/i)).toBeVisible()
    await expect(page.getByLabel(/número de documento/i)).toBeVisible()
    await expect(page.getByLabel(/condición iva/i)).toBeVisible()
  })

  test('debe validar CUIT al crear cliente', async ({ page }) => {
    await page.getByTestId('clientes-nuevo').click()
    await page.waitForURL(/clientes\/nuevo/)
    
    // Intentar con CUIT inválido
    await page.getByLabel(/número de documento/i).fill('123')
    await page.getByLabel(/razón social/i).fill('Cliente de Prueba')
    await page.getByRole('button', { name: /crear cliente|guardar/i }).click()
    
    // Debe mostrar error de validación
    await expect(page.getByText(/cuit.*inválido|formato.*incorrecto/i)).toBeVisible()
  })

  test('debe crear cliente con datos válidos', async ({ page }) => {
    await page.getByTestId('clientes-nuevo').click()
    await page.waitForURL(/clientes\/nuevo/)
    
    // Completar formulario con datos válidos
    await page.getByLabel(/razón social/i).fill('Cliente de Prueba E2E')
    await page.getByLabel(/número de documento/i).fill('20123456789')
    await page.getByLabel(/condición iva/i).selectOption({ label: 'Responsable Inscripto' })
    await page.getByLabel(/email/i).fill('cliente@test.com')
    
    await page.getByRole('button', { name: /crear cliente|guardar/i }).click()
    
    // Verificar que vuelve al listado
    await expect(page).toHaveURL(/clientes$/)
    // El nuevo cliente debería aparecer
    await expect(page.getByText('Cliente de Prueba E2E')).toBeVisible()
  })

  test('debe buscar clientes por nombre', async ({ page }) => {
    // Crear 2 clientes para verificar filtro
    for (const razonSocial of ['Cliente Alpha', 'Cliente Beta']) {
      await page.getByTestId('clientes-nuevo').click()
      await page.waitForURL(/clientes\/nuevo/)
      await page.getByLabel(/razón social/i).fill(razonSocial)
      await page.getByLabel(/número de documento/i).fill('20123456789')
      await page.getByLabel(/condición iva/i).selectOption({ label: 'Responsable Inscripto' })
      await page.getByRole('button', { name: /crear cliente|guardar/i }).click()
      await expect(page).toHaveURL(/clientes$/)
    }

    // Buscar
    const searchInput = page.getByPlaceholder(/buscar/i)
    const searchRequest = page.waitForRequest((req) => {
      try {
        const url = new URL(req.url())
        return (
          url.pathname === '/api/clientes' &&
          (url.searchParams.get('search') || '').toLowerCase() === 'beta'
        )
      } catch {
        return false
      }
    })
    await searchInput.fill('beta')
    await searchRequest

    // Verificar filtro (Beta visible, Alpha no)
    await expect(page.getByText('Cliente Beta')).toBeVisible()
    await expect(page.locator('text=Cliente Alpha')).toHaveCount(0)
  })
})
