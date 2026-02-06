import { test, expect } from '@playwright/test'
import { mockApi, loginAsAdmin } from './helpers'

/**
 * Tests E2E para emisión de comprobantes en FactuFlow
 */

test.describe('Emisión de Comprobantes', () => {
  // Antes de cada test, simular login
  test.beforeEach(async ({ page }) => {
    await mockApi(page)
    await loginAsAdmin(page)
    await page.getByTestId('nav-comprobantes').click()
    await page.waitForURL(/comprobantes/)
  })

  test('debe mostrar botón para crear nueva factura', async ({ page }) => {
    await expect(
      page.getByTestId('comprobantes-nueva-factura')
    ).toBeVisible()
  })

  test('debe abrir formulario de nueva factura', async ({ page }) => {
    await page.getByTestId('comprobantes-nueva-factura').click()
    
    // Verificar que se abre el formulario
    await expect(page).toHaveURL(/comprobantes\/nuevo/)
    await expect(page.getByTestId('page-title')).toHaveText(/nueva factura/i)
    await expect(page.getByLabel(/tipo de comprobante/i)).toBeVisible()
    await expect(page.getByLabel(/punto de venta/i)).toBeVisible()
  })

  test('debe seleccionar tipo de comprobante', async ({ page }) => {
    await page.getByTestId('comprobantes-nueva-factura').click()
    await page.waitForURL(/comprobantes\/nuevo/)
    
    // Seleccionar Factura A
    await page.getByLabel(/tipo de comprobante/i).selectOption('1') // Factura A
    
    // El formulario debe actualizarse según el tipo
    await expect(page.getByLabel(/tipo de comprobante/i)).toHaveValue('1')
  })

  test('debe agregar items a la factura', async ({ page }) => {
    await page.getByTestId('comprobantes-nueva-factura').click()
    await page.waitForURL(/comprobantes\/nuevo/)
    
    // Agregar un item
    await page.getByRole('button', { name: /agregar ítem|agregar item/i }).click()
    
    // Verificar que aparece el formulario de item
    await expect(page.getByLabel(/descripción/i).first()).toBeVisible()
    await expect(page.getByLabel(/cantidad/i).first()).toBeVisible()
    await expect(page.getByLabel(/precio unitario/i).first()).toBeVisible()
  })

  test('debe calcular totales automáticamente', async ({ page }) => {
    await page.getByTestId('comprobantes-nueva-factura').click()
    await page.waitForURL(/comprobantes\/nuevo/)
    
    // Completar tipo de comprobante
    await page.getByLabel(/tipo de comprobante/i).selectOption('1')
    await page.getByLabel(/punto de venta/i).selectOption({ index: 0 })
    
    // Agregar un item con valores
    await page.getByRole('button', { name: /agregar ítem|agregar item/i }).click()
    await page.getByLabel(/descripción/i).first().fill('Servicio de consultoría')
    await page.getByLabel(/cantidad/i).first().fill('1')
    await page.getByLabel(/precio unitario/i).first().fill('1000')
    
    // Verificar que se calcula el total (1000 + IVA 21% = 1210)
    await expect(page.getByText('TOTAL:', { exact: true })).toBeVisible()
    await expect(page.getByText(/1\.210/)).toBeVisible()
  })

  test('debe mostrar vista previa antes de emitir', async ({ page }) => {
    await page.getByTestId('comprobantes-nueva-factura').click()
    await page.waitForURL(/comprobantes\/nuevo/)
    
    // Completar formulario básico
    await page.getByLabel(/tipo de comprobante/i).selectOption('1')
    await page.getByTestId('cliente-nuevo-manual').click()
    await page.getByLabel(/número/i).fill('20123456789')
    await page.getByLabel(/condición iva/i).selectOption({ label: 'Responsable Inscripto' })
    await page.getByLabel(/razón social/i).fill('Cliente Preview')
    await page.getByLabel(/descripción/i).first().fill('Servicio de prueba')
    await page.getByLabel(/cantidad/i).first().fill('1')
    await page.getByLabel(/precio unitario/i).first().fill('1000')
    
    // Click en vista previa
    await page.getByTestId('comprobante-vista-previa').click()
    
    // Verificar que se muestra el modal de preview
    await expect(
      page.getByTestId('comprobante-confirmar-emitir')
    ).toBeVisible()
  })

  test('debe emitir comprobante (mock) al confirmar desde la vista previa', async ({ page }) => {
    await page.getByTestId('comprobantes-nueva-factura').click()
    await page.waitForURL(/comprobantes\/nuevo/)

    await page.getByLabel(/tipo de comprobante/i).selectOption('6') // Factura B
    await page.getByLabel(/punto de venta/i).selectOption({ index: 0 })

    // Cliente manual
    await page.getByTestId('cliente-nuevo-manual').click()
    await page.getByLabel(/número/i).fill('20123456789')
    await page.getByLabel(/condición iva/i).selectOption({ label: 'Responsable Inscripto' })
    await page.getByLabel(/razón social/i).fill('Cliente Emitir')

    // Item
    await page.getByLabel(/descripción/i).first().fill('Servicio de prueba')
    await page.getByLabel(/cantidad/i).first().fill('1')
    await page.getByLabel(/precio unitario/i).first().fill('1000')

    // Abrir preview y confirmar
    await page.getByTestId('comprobante-vista-previa').click()
    await expect(page.getByTestId('comprobante-confirmar-emitir')).toBeVisible()

    // Preparar espera de emisión y aceptar alert() de éxito
    const emitirRequest = page.waitForRequest((req) => {
      const url = req.url()
      return (
        (url.includes('/comprobantes/emitir') || url.includes('/api/comprobantes/emitir')) &&
        req.method() === 'POST'
      )
    })
    const [dialog] = await Promise.all([
      page.waitForEvent('dialog'),
      page.getByTestId('comprobante-confirmar-emitir').click(),
    ])
    await dialog.accept()
    await emitirRequest

    // Debe volver al listado
    await expect(page).toHaveURL(/comprobantes$/)
  })
})
