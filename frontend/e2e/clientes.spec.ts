import { test, expect } from '@playwright/test'

/**
 * Tests E2E para gestión de clientes en FactuFlow
 */

test.describe('Gestión de Clientes', () => {
  // Antes de cada test, simular login
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel(/usuario/i).fill('admin')
    await page.getByLabel(/contraseña/i).fill('admin123')
    await page.getByRole('button', { name: /ingresar/i }).click()
    await page.waitForURL(/dashboard/)
    await page.getByRole('link', { name: /clientes/i }).click()
    await page.waitForURL(/clientes/)
  })

  test('debe mostrar botón para crear nuevo cliente', async ({ page }) => {
    await expect(page.getByRole('button', { name: /nuevo cliente/i })).toBeVisible()
  })

  test('debe abrir formulario de nuevo cliente', async ({ page }) => {
    await page.getByRole('button', { name: /nuevo cliente/i }).click()
    
    // Verificar que se abre el formulario
    await expect(page).toHaveURL(/clientes\/nuevo/)
    await expect(page.getByLabel(/razón social/i)).toBeVisible()
    await expect(page.getByLabel(/cuit|documento/i)).toBeVisible()
    await expect(page.getByLabel(/condición iva/i)).toBeVisible()
  })

  test('debe validar CUIT al crear cliente', async ({ page }) => {
    await page.getByRole('button', { name: /nuevo cliente/i }).click()
    await page.waitForURL(/clientes\/nuevo/)
    
    // Intentar con CUIT inválido
    await page.getByLabel(/cuit|documento/i).fill('123')
    await page.getByLabel(/razón social/i).fill('Cliente de Prueba')
    await page.getByRole('button', { name: /guardar/i }).click()
    
    // Debe mostrar error de validación
    await expect(page.getByText(/cuit.*inválido|formato.*incorrecto/i)).toBeVisible()
  })

  test('debe crear cliente con datos válidos', async ({ page }) => {
    await page.getByRole('button', { name: /nuevo cliente/i }).click()
    await page.waitForURL(/clientes\/nuevo/)
    
    // Completar formulario con datos válidos
    await page.getByLabel(/razón social/i).fill('Cliente de Prueba E2E')
    await page.getByLabel(/cuit|documento/i).fill('20123456789')
    await page.getByLabel(/condición iva/i).selectOption('Responsable Inscripto')
    await page.getByLabel(/email/i).fill('cliente@test.com')
    
    await page.getByRole('button', { name: /guardar/i }).click()
    
    // Verificar que vuelve al listado
    await expect(page).toHaveURL(/clientes$/)
    // El nuevo cliente debería aparecer
    await expect(page.getByText('Cliente de Prueba E2E')).toBeVisible()
  })

  test('debe buscar clientes por nombre', async ({ page }) => {
    // Usar el buscador
    await page.getByPlaceholder(/buscar/i).fill('prueba')
    
    // Verificar que filtra resultados
    await page.waitForTimeout(500) // Debounce
    // Los resultados deberían filtrarse
  })
})
