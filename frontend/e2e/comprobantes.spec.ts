import { test, expect } from '@playwright/test'

/**
 * Tests E2E para emisión de comprobantes en FactuFlow
 */

test.describe('Emisión de Comprobantes', () => {
  // Antes de cada test, simular login
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel(/usuario/i).fill('admin')
    await page.getByLabel(/contraseña/i).fill('admin123')
    await page.getByRole('button', { name: /ingresar/i }).click()
    await page.waitForURL(/dashboard/)
    await page.getByRole('link', { name: /comprobantes/i }).click()
    await page.waitForURL(/comprobantes/)
  })

  test('debe mostrar botón para crear nueva factura', async ({ page }) => {
    await expect(page.getByRole('button', { name: /nueva factura/i })).toBeVisible()
  })

  test('debe abrir formulario de nueva factura', async ({ page }) => {
    await page.getByRole('button', { name: /nueva factura/i }).click()
    
    // Verificar que se abre el formulario
    await expect(page).toHaveURL(/comprobantes\/nuevo/)
    await expect(page.getByLabel(/tipo.*comprobante/i)).toBeVisible()
    await expect(page.getByLabel(/punto.*venta/i)).toBeVisible()
  })

  test('debe seleccionar tipo de comprobante', async ({ page }) => {
    await page.getByRole('button', { name: /nueva factura/i }).click()
    await page.waitForURL(/comprobantes\/nuevo/)
    
    // Seleccionar Factura A
    await page.getByLabel(/tipo.*comprobante/i).selectOption('1') // Factura A
    
    // El formulario debe actualizarse según el tipo
    await expect(page.getByText(/factura a/i)).toBeVisible()
  })

  test('debe agregar items a la factura', async ({ page }) => {
    await page.getByRole('button', { name: /nueva factura/i }).click()
    await page.waitForURL(/comprobantes\/nuevo/)
    
    // Agregar un item
    await page.getByRole('button', { name: /agregar item/i }).click()
    
    // Verificar que aparece el formulario de item
    await expect(page.getByLabel(/descripción/i)).toBeVisible()
    await expect(page.getByLabel(/cantidad/i)).toBeVisible()
    await expect(page.getByLabel(/precio/i)).toBeVisible()
  })

  test('debe calcular totales automáticamente', async ({ page }) => {
    await page.getByRole('button', { name: /nueva factura/i }).click()
    await page.waitForURL(/comprobantes\/nuevo/)
    
    // Completar tipo de comprobante
    await page.getByLabel(/tipo.*comprobante/i).selectOption('1')
    await page.getByLabel(/punto.*venta/i).selectOption({ index: 0 })
    
    // Agregar un item con valores
    await page.getByRole('button', { name: /agregar item/i }).click()
    await page.getByLabel(/descripción/i).first().fill('Servicio de consultoría')
    await page.getByLabel(/cantidad/i).first().fill('1')
    await page.getByLabel(/precio/i).first().fill('1000')
    
    // Verificar que se calcula el total
    await expect(page.getByText(/1\.000|1000/)).toBeVisible()
  })

  test('debe mostrar vista previa antes de emitir', async ({ page }) => {
    await page.getByRole('button', { name: /nueva factura/i }).click()
    await page.waitForURL(/comprobantes\/nuevo/)
    
    // Completar formulario básico
    await page.getByLabel(/tipo.*comprobante/i).selectOption('1')
    
    // Click en vista previa
    await page.getByRole('button', { name: /vista previa/i }).click()
    
    // Verificar que se muestra el modal de preview
    await expect(page.getByText(/confirmar|emitir/i)).toBeVisible()
  })
})
