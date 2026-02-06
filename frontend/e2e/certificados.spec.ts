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
    await page.getByTestId('nav-certificados').click()
    await page.waitForURL(/certificados/)
  })

  test('debe mostrar lista de certificados', async ({ page }) => {
    await expect(page.getByTestId('page-title')).toHaveText(/certificados/i)
  })

  test('debe tener botón para nuevo certificado', async ({ page }) => {
    await expect(
      page.getByTestId('certificados-agregar')
    ).toBeVisible()
  })

  test('debe abrir wizard al hacer click en nuevo certificado', async ({ page }) => {
    await page.getByTestId('certificados-agregar').click()
    
    // Verificar que se abre el wizard
    await expect(page).toHaveURL(/certificados\/nuevo/)
    
    // Verificar Step 1 - Introducción
    await expect(
      page.getByRole('heading', { name: /configuremos tu certificado/i })
    ).toBeVisible()
  })

  test('debe navegar entre pasos del wizard', async ({ page }) => {
    await page.getByTestId('certificados-agregar').click()
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
    await page.getByTestId('certificados-agregar').click()
    await page.waitForURL(/certificados\/nuevo/)
    
    // Ir al paso 2
    await page.getByRole('button', { name: /comenzar|continuar|siguiente/i }).click()
    
    // Verificar campos del formulario CSR
    await expect(page.getByLabel(/cuit/i)).toBeVisible()
    await expect(page.getByLabel(/ambiente/i)).toBeVisible()
  })

  test('debe validar CUIT en formulario CSR', async ({ page }) => {
    await page.getByTestId('certificados-agregar').click()
    await page.waitForURL(/certificados\/nuevo/)
    
    // Ir al paso 2
    await page.getByRole('button', { name: /comenzar|continuar|siguiente/i }).click()
    
    // Ingresar CUIT inválido
    await page.getByLabel(/cuit/i).fill('123')
    await page.getByLabel(/nombre de la empresa/i).fill('Empresa Test')
    
    // El botón debe estar deshabilitado
    await expect(page.getByTestId('cert-wizard-generar')).toBeDisabled()
  })

  test('debe completar el wizard completo (mock) hasta la pantalla de éxito', async ({ page }) => {
    await page.getByTestId('certificados-agregar').click()
    await page.waitForURL(/certificados\/nuevo/)

    // Step 1 -> Step 2
    await page.getByRole('button', { name: /comenzar|continuar|siguiente/i }).click()

    // Step 2: generar CSR
    await page.getByLabel(/cuit/i).fill('20-12345678-9')
    await page.getByLabel(/nombre de la empresa/i).fill('Empresa Test')
    await page.getByTestId('cert-wizard-generar').click()
    await page.getByTestId('cert-wizard-step2-next').click()

    // Step 3: confirmar que ya tengo el certificado
    await expect(
      page.getByRole('heading', { name: /obtené tu certificado en el portal de arca/i })
    ).toBeVisible()
    await page.getByRole('checkbox').check()
    await page.getByTestId('cert-wizard-step3-next').click()

    // Step 4: subir certificado
    await expect(page.getByRole('heading', { name: /subí tu certificado/i })).toBeVisible()
    await page.getByTestId('cert-wizard-file').setInputFiles({
      name: 'certificado.crt',
      mimeType: 'application/x-x509-ca-cert',
      buffer: Buffer.from(
        '-----BEGIN CERTIFICATE-----\\nFAKE\\n-----END CERTIFICATE-----\\n'
      ),
    })
    await expect(page.getByTestId('cert-wizard-step4-next')).toBeVisible()
    await page.getByTestId('cert-wizard-step4-next').click()

    // Step 5: verificar
    await expect(page.getByTestId('cert-wizard-verificar')).toBeVisible()
    await page.getByTestId('cert-wizard-verificar').click()
    await expect(page.getByTestId('cert-wizard-finish')).toBeVisible()
    await page.getByTestId('cert-wizard-finish').click()

    // Exito
    await expect(page).toHaveURL(/certificados\/\d+\/exito/)
    await expect(page.getByRole('heading', { name: /felicitaciones/i })).toBeVisible()
  })
})
