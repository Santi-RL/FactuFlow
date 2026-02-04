import { test, expect } from '@playwright/test'
import { mockApi, loginAsAdmin } from './helpers'

/**
 * Tests E2E para autenticación de FactuFlow
 */

test.describe('Autenticación', () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page)
  })

  test('debe mostrar la página de login', async ({ page }) => {
    await page.goto('/login')
    
    // Verificar elementos de la página de login
    await expect(page.getByRole('heading', { name: /iniciar sesión/i })).toBeVisible()
    await expect(page.getByLabel(/correo electrónico/i)).toBeVisible()
    await expect(page.getByLabel(/contraseña/i)).toBeVisible()
    await expect(page.getByRole('button', { name: /ingresar/i })).toBeVisible()
  })

  test('debe mostrar error con credenciales inválidas', async ({ page }) => {
    await page.goto('/login')
    
    // Completar formulario con datos inválidos
    await page.getByLabel(/correo electrónico/i).fill('usuario_invalido@factuflow.com')
    await page.getByLabel(/contraseña/i).fill('password_invalida')
    await page.getByRole('button', { name: /ingresar/i }).click()
    
    // Verificar mensaje de error
    await expect(page.getByText(/email o contraseña incorrectos|credenciales incorrectas/i)).toBeVisible()
  })

  test('debe redirigir a dashboard después de login exitoso', async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('debe redirigir a login si no está autenticado', async ({ page }) => {
    // Intentar acceder a ruta protegida
    await page.goto('/clientes')
    
    // Debe redirigir a login
    await expect(page).toHaveURL(/login/)
  })
})
