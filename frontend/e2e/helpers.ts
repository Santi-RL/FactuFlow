import type { Page, Route } from '@playwright/test'

const now = new Date().toISOString()

const adminUser = {
  id: 1,
  email: 'admin@factuflow.com',
  nombre: 'Admin',
  empresa_id: 1,
  activo: true,
  es_admin: true,
  created_at: now,
  ultimo_login: null
}

const empresa = {
  id: 1,
  razon_social: 'Empresa Test S.A.',
  cuit: '20123456789',
  condicion_iva: 'RI',
  domicilio: 'Av. Siempre Viva 123',
  localidad: 'Buenos Aires',
  provincia: 'Buenos Aires',
  codigo_postal: '1000',
  email: 'contacto@empresa.com',
  telefono: '011-1234-5678',
  inicio_actividades: '2020-01-01',
  logo: null,
  created_at: now,
  updated_at: now
}

export const adminCredentials = {
  email: adminUser.email,
  password: 'admin123'
}

const corsHeaders = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET,POST,PUT,DELETE,OPTIONS',
  'access-control-allow-headers': 'Content-Type, Authorization',
}

const jsonResponse = (route: Route, status: number, payload: unknown) => {
  return route.fulfill({
    status,
    contentType: 'application/json',
    headers: corsHeaders,
    body: JSON.stringify(payload)
  })
}

const parseBody = (route: Route) => {
  const raw = route.request().postData()
  if (!raw) return {}
  try {
    return JSON.parse(raw)
  } catch {
    return {}
  }
}

export const mockApi = async (page: Page) => {
  const state = {
    clientes: [] as any[],
    nextClienteId: 1
  }

  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method().toUpperCase()

    if (method === 'OPTIONS') {
      return route.fulfill({
        status: 204,
        headers: corsHeaders
      })
    }

    // Auth
    if (path === '/api/auth/login' && method === 'POST') {
      const body = parseBody(route) as { email?: string; password?: string }
      if (body.email === adminCredentials.email && body.password === adminCredentials.password) {
        return jsonResponse(route, 200, {
          access_token: 'e2e-token',
          token_type: 'bearer',
          user: adminUser
        })
      }
      return jsonResponse(route, 401, { detail: 'Email o contraseña incorrectos' })
    }

    if (path === '/api/auth/me' && method === 'GET') {
      return jsonResponse(route, 200, adminUser)
    }

    // Empresa
    if (path === '/api/empresas/1' && method === 'GET') {
      return jsonResponse(route, 200, empresa)
    }

    // Certificados
    if (path === '/api/certificados' && method === 'GET') {
      return jsonResponse(route, 200, [])
    }

    if (path === '/api/certificados/alertas-vencimiento' && method === 'GET') {
      return jsonResponse(route, 200, [])
    }

    if (path === '/api/certificados/generar-csr' && method === 'POST') {
      const body = parseBody(route) as { cuit?: string; nombre_empresa?: string; ambiente?: string }
      if (!body.cuit || body.cuit.length !== 11) {
        return jsonResponse(route, 422, { detail: 'CUIT inválido' })
      }
      return jsonResponse(route, 200, {
        csr: '-----BEGIN CERTIFICATE REQUEST-----\nFAKE-CSR\n-----END CERTIFICATE REQUEST-----',
        key_filename: `cert_${body.cuit}_${body.ambiente || 'homologacion'}.key`,
        mensaje: 'CSR generado exitosamente.'
      })
    }

    // Clientes
    if (path === '/api/clientes' && method === 'GET') {
      const pageParam = Number(url.searchParams.get('page') || 1)
      const perPage = Number(url.searchParams.get('per_page') || 30)
      const search = (url.searchParams.get('search') || '').toLowerCase()

      const filtered = search
        ? state.clientes.filter((cliente) => {
            return (
              String(cliente.razon_social || '').toLowerCase().includes(search) ||
              String(cliente.numero_documento || '').toLowerCase().includes(search)
            )
          })
        : state.clientes

      const total = filtered.length
      const pages = Math.max(1, Math.ceil(total / perPage))
      const start = (pageParam - 1) * perPage
      const items = filtered.slice(start, start + perPage)

      return jsonResponse(route, 200, {
        items,
        total,
        page: pageParam,
        per_page: perPage,
        pages
      })
    }

    if (path === '/api/clientes' && method === 'POST') {
      const body = parseBody(route) as any
      if (!body.numero_documento || String(body.numero_documento).length < 11) {
        return jsonResponse(route, 422, { detail: 'CUIT inválido' })
      }
      const cliente = {
        id: state.nextClienteId++,
        empresa_id: 1,
        razon_social: body.razon_social,
        tipo_documento: body.tipo_documento,
        numero_documento: body.numero_documento,
        condicion_iva: body.condicion_iva,
        domicilio: body.domicilio ?? null,
        localidad: body.localidad ?? null,
        provincia: body.provincia ?? null,
        codigo_postal: body.codigo_postal ?? null,
        email: body.email ?? null,
        telefono: body.telefono ?? null,
        notas: body.notas ?? null,
        activo: true,
        created_at: now,
        updated_at: now
      }
      state.clientes.unshift(cliente)
      return jsonResponse(route, 201, cliente)
    }

    if (path.startsWith('/api/clientes/') && method === 'GET') {
      const id = Number(path.split('/').pop())
      const cliente = state.clientes.find((c) => c.id === id)
      if (!cliente) {
        return jsonResponse(route, 404, { detail: 'Cliente no encontrado' })
      }
      return jsonResponse(route, 200, cliente)
    }

    if (path.startsWith('/api/clientes/') && method === 'PUT') {
      const id = Number(path.split('/').pop())
      const cliente = state.clientes.find((c) => c.id === id)
      if (!cliente) {
        return jsonResponse(route, 404, { detail: 'Cliente no encontrado' })
      }
      const body = parseBody(route) as any
      Object.assign(cliente, body, { updated_at: now })
      return jsonResponse(route, 200, cliente)
    }

    if (path.startsWith('/api/clientes/') && method === 'DELETE') {
      const id = Number(path.split('/').pop())
      state.clientes = state.clientes.filter((c) => c.id !== id)
      return route.fulfill({ status: 204, headers: corsHeaders })
    }

    // Comprobantes
    if (path === '/api/comprobantes' && method === 'GET') {
      return jsonResponse(route, 200, {
        items: [],
        total: 0,
        page: 1,
        per_page: 20,
        pages: 0
      })
    }

    if (path.startsWith('/api/comprobantes/proximo-numero/') && method === 'GET') {
      const parts = path.split('/')
      const puntoVenta = Number(parts[parts.length - 2])
      const tipoComprobante = Number(parts[parts.length - 1])
      return jsonResponse(route, 200, {
        punto_venta: puntoVenta,
        tipo_comprobante: tipoComprobante,
        proximo_numero: 1
      })
    }

    return jsonResponse(route, 404, { detail: 'Not mocked' })
  })
}

export const loginAsAdmin = async (page: Page) => {
  await page.goto('/login')
  await page.getByLabel(/correo electrónico/i).fill(adminCredentials.email)
  await page.getByLabel(/contraseña/i).fill(adminCredentials.password)
  await page.getByRole('button', { name: /ingresar/i }).click()
  await page.waitForURL((url) => url.pathname === '/' || url.pathname === '/dashboard')
}
