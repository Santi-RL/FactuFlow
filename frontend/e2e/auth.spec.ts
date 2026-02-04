import { test, expect } from '@playwright/test'

/**
 * Tests E2E para autenticación de FactuFlow
 */

test.describe('Autenticación', () => {
  test('debe mostrar la página de login', async ({ page }) => {
    await page.goto('/login')
    
    // Verificar elementos de la página de login
    await expect(page.getByRole('heading', { name: /iniciar sesión/i })).toBeVisible()
    await expect(page.getByLabel(/usuario/i)).toBeVisible()
    await expect(page.getByLabel(/contraseña/i)).toBeVisible()
    await expect(page.getByRole('button', { name: /ingresar/i })).toBeVisible()
  })

  test('debe mostrar error con credenciales inválidas', async ({ page }) => {
    await page.goto('/login')
    
    // Completar formulario con datos inválidos
    await page.getByLabel(/usuario/i).fill('usuario_invalido')
    await page.getByLabel(/contraseña/i).fill('password_invalida')
    await page.getByRole('button', { name: /ingresar/i }).click()
    
    // Verificar mensaje de error
    await expect(page.getByText(/credenciales incorrectas|usuario o contraseña/i)).toBeVisible()
  })

  test('debe redirigir a dashboard después de login exitoso', async ({ page }) => {
    await page.goto('/login')
    
    // Completar formulario con datos válidos (mock)
    await page.getByLabel(/usuario/i).fill('admin')
    await page.getByLabel(/contraseña/i).fill('admin123')
    await page.getByRole('button', { name: /ingresar/i }).click()
    
    // Verificar redirección al dashboard
    await expect(page).toHaveURL(/dashboard/)
  })

  test('debe redirigir a login si no está autenticado', async ({ page }) => {
    // Intentar acceder a ruta protegida
    await page.goto('/clientes')
    
    // Debe redirigir a login
    await expect(page).toHaveURL(/login/)
  })
})
