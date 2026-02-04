import { test, expect } from '@playwright/test'
import { mockApi, loginAsAdmin } from './helpers'

/**
 * Tests E2E para el Wizard de Certificados ARCA en FactuFlow
 */

test.describe('Wizard de Certificados', () => {
  // Antes de cada test, simular login
  test.beforeEach(async ({ page }) => {
    await mockApi(page)
    await loginAsAdmin(page)
    await page.getByRole('link', { name: /certificados/i }).click()
    await page.waitForURL(/certificados/)
  })

  test('debe mostrar lista de certificados', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /certificados/i })).toBeVisible()
  })

  test('debe tener botón para nuevo certificado', async ({ page }) => {
    await expect(
      page.getByRole('button', {
        name: /agregar certificado|nuevo certificado|configurar certificado/i
      })
    ).toBeVisible()
  })

  test('debe abrir wizard al hacer click en nuevo certificado', async ({ page }) => {
    await page.getByRole('button', {
      name: /agregar certificado|nuevo certificado|configurar certificado/i
    }).click()
    
    // Verificar que se abre el wizard
    await expect(page).toHaveURL(/certificados\/nuevo/)
    
    // Verificar Step 1 - Introducción
    await expect(
      page.getByRole('heading', { name: /configuremos tu certificado/i })
    ).toBeVisible()
  })

  test('debe navegar entre pasos del wizard', async ({ page }) => {
    await page.getByRole('button', {
      name: /agregar certificado|nuevo certificado|configurar certificado/i
    }).click()
    await page.waitForURL(/certificados\/nuevo/)
    
    // Verificar indicador de progreso (5 pasos)
    await expect(
      page.getByRole('heading', { name: /configuremos tu certificado/i })
    ).toBeVisible()
    
    // Avanzar al paso 2
    await page.getByRole('button', { name: /comenzar|continuar|siguiente/i }).click()
    await expect(
      page.getByRole('heading', { name: /generación de clave privada/i })
    ).toBeVisible()
  })

  test('debe mostrar formulario de CSR en paso 2', async ({ page }) => {
    await page.getByRole('button', {
      name: /agregar certificado|nuevo certificado|configurar certificado/i
    }).click()
    await page.waitForURL(/certificados\/nuevo/)
    
    // Ir al paso 2
    await page.getByRole('button', { name: /comenzar|continuar|siguiente/i }).click()
    
    // Verificar campos del formulario CSR
    await expect(page.getByLabel(/cuit/i)).toBeVisible()
    await expect(page.getByLabel(/ambiente/i)).toBeVisible()
  })

  test('debe validar CUIT en formulario CSR', async ({ page }) => {
    await page.getByRole('button', {
      name: /agregar certificado|nuevo certificado|configurar certificado/i
    }).click()
    await page.waitForURL(/certificados\/nuevo/)
    
    // Ir al paso 2
    await page.getByRole('button', { name: /comenzar|continuar|siguiente/i }).click()
    
    // Ingresar CUIT inválido
    await page.getByLabel(/cuit/i).fill('123')
    await page.getByLabel(/nombre de la empresa/i).fill('Empresa Test')
    
    // El botón debe estar deshabilitado
    await expect(page.getByRole('button', { name: /generar/i })).toBeDisabled()
  })

  test('debe mostrar instrucciones del portal ARCA en paso 3', async ({ page }) => {
    await page.getByRole('button', {
      name: /agregar certificado|nuevo certificado|configurar certificado/i
    }).click()
    await page.waitForURL(/certificados\/nuevo/)
    
    // Navegar hasta paso 3
    await page.getByRole('button', { name: /comenzar|continuar|siguiente/i }).click()
    // Completar paso 2
    await page.getByLabel(/cuit/i).fill('20123456789')
    await page.getByLabel(/nombre de la empresa/i).fill('Empresa Test')
    await page.getByRole('button', { name: /generar/i }).click()
    await page.getByRole('button', { name: /siguiente/i }).click()
    
    // Verificar instrucciones del portal ARCA
    await expect(
      page.getByRole('heading', { name: /obtené tu certificado en el portal de arca/i })
    ).toBeVisible()
  })
})
