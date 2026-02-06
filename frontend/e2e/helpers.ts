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

const unauthorized = (route: Route) => {
  return jsonResponse(route, 401, { detail: 'No autenticado' })
}

const hasAuthHeader = (route: Route) => {
  const headers = route.request().headers()
  const auth = headers['authorization'] || headers['Authorization']
  return Boolean(auth && String(auth).toLowerCase().startsWith('bearer '))
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
    nextClienteId: 1,
    puntosVenta: [
      { id: 1, numero: 1, nombre: 'PV 0001', activo: true, created_at: now, updated_at: now },
    ] as any[],
    certificados: [] as any[],
    nextCertificadoId: 1,
    comprobantes: [] as any[],
    nextComprobanteId: 1,
    lastCsr: null as null | { cuit: string; ambiente: string; keyFilename: string; nombre: string },
  }

  const handler = async (route: Route) => {
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
      if (!hasAuthHeader(route)) return unauthorized(route)
      return jsonResponse(route, 200, adminUser)
    }

    // Empresa
    if (path === '/api/empresas/1' && method === 'GET') {
      if (!hasAuthHeader(route)) return unauthorized(route)
      return jsonResponse(route, 200, empresa)
    }

    // Puntos de venta
    if (path === '/api/puntos-venta' && method === 'GET') {
      if (!hasAuthHeader(route)) return unauthorized(route)
      return jsonResponse(route, 200, state.puntosVenta)
    }

    // Certificados
    if (path === '/api/certificados' && method === 'GET') {
      if (!hasAuthHeader(route)) return unauthorized(route)
      return jsonResponse(route, 200, state.certificados)
    }

    if (path === '/api/certificados/alertas-vencimiento' && method === 'GET') {
      if (!hasAuthHeader(route)) return unauthorized(route)
      return jsonResponse(route, 200, [])
    }

    if (path === '/api/certificados/generar-csr' && method === 'POST') {
      if (!hasAuthHeader(route)) return unauthorized(route)
      const body = parseBody(route) as { cuit?: string; nombre_empresa?: string; ambiente?: string }
      if (!body.cuit || body.cuit.length !== 11) {
        return jsonResponse(route, 422, { detail: 'CUIT inválido' })
      }
      state.lastCsr = {
        cuit: body.cuit,
        ambiente: body.ambiente || 'homologacion',
        keyFilename: `cert_${body.cuit}_${body.ambiente || 'homologacion'}.key`,
        nombre: body.nombre_empresa || 'Empresa',
      }
      return jsonResponse(route, 200, {
        csr: '-----BEGIN CERTIFICATE REQUEST-----\nFAKE-CSR\n-----END CERTIFICATE REQUEST-----',
        key_filename: state.lastCsr.keyFilename,
        mensaje: 'CSR generado exitosamente.'
      })
    }

    if (path === '/api/certificados/subir-certificado' && method === 'POST') {
      if (!hasAuthHeader(route)) return unauthorized(route)
      const id = state.nextCertificadoId++
      // No parseamos multipart: el objetivo del E2E es validar el flujo UI.
      const csr = state.lastCsr
      const certificado = {
        id,
        cuit: csr?.cuit || empresa.cuit,
        nombre: csr?.nombre || 'Certificado E2E',
        ambiente: csr?.ambiente || 'homologacion',
        fecha_emision: now,
        fecha_vencimiento: '2030-01-01',
        dias_restantes: 999,
        activo: true,
        estado: 'valido',
        created_at: now,
        updated_at: now,
      }
      state.certificados.unshift(certificado)
      return jsonResponse(route, 201, certificado)
    }

    if (path.startsWith('/api/certificados/verificar-conexion/') && method === 'POST') {
      if (!hasAuthHeader(route)) return unauthorized(route)
      return jsonResponse(route, 200, {
        exito: true,
        mensaje: 'Conexión OK',
        estado_servidores: { aplicacion: 'OK', base_datos: 'OK', autenticacion: 'OK' }
      })
    }

    if (path.startsWith('/api/certificados/') && method === 'GET') {
      if (!hasAuthHeader(route)) return unauthorized(route)
      const id = Number(path.split('/').pop())
      const cert = state.certificados.find((c) => c.id === id)
      if (!cert) return jsonResponse(route, 404, { detail: 'Certificado no encontrado' })
      return jsonResponse(route, 200, cert)
    }

    // Clientes
    if (path === '/api/clientes' && method === 'GET') {
      if (!hasAuthHeader(route)) return unauthorized(route)
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
      if (!hasAuthHeader(route)) return unauthorized(route)
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
      if (!hasAuthHeader(route)) return unauthorized(route)
      const id = Number(path.split('/').pop())
      const cliente = state.clientes.find((c) => c.id === id)
      if (!cliente) {
        return jsonResponse(route, 404, { detail: 'Cliente no encontrado' })
      }
      return jsonResponse(route, 200, cliente)
    }

    if (path.startsWith('/api/clientes/') && method === 'PUT') {
      if (!hasAuthHeader(route)) return unauthorized(route)
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
      if (!hasAuthHeader(route)) return unauthorized(route)
      const id = Number(path.split('/').pop())
      state.clientes = state.clientes.filter((c) => c.id !== id)
      return route.fulfill({ status: 204, headers: corsHeaders })
    }

    // Comprobantes
    if ((path === '/api/comprobantes' || path === '/comprobantes') && method === 'GET') {
      if (!hasAuthHeader(route)) return unauthorized(route)
      return jsonResponse(route, 200, {
        items: [],
        total: 0,
        page: 1,
        per_page: 20,
        pages: 1
      })
    }

    if (
      (path.startsWith('/api/comprobantes/proximo-numero/') ||
        path.startsWith('/comprobantes/proximo-numero/')) &&
      method === 'GET'
    ) {
      if (!hasAuthHeader(route)) return unauthorized(route)
      const parts = path.split('/')
      const puntoVenta = Number(parts[parts.length - 2])
      const tipoComprobante = Number(parts[parts.length - 1])
      return jsonResponse(route, 200, {
        punto_venta: puntoVenta,
        tipo_comprobante: tipoComprobante,
        proximo_numero: 1
      })
    }

    if ((path === '/api/comprobantes/emitir' || path === '/comprobantes/emitir') && method === 'POST') {
      if (!hasAuthHeader(route)) return unauthorized(route)
      const body = parseBody(route) as any
      const id = state.nextComprobanteId++
      const resp = {
        exito: true,
        mensaje: 'Comprobante emitido',
        comprobante_id: null,
        cae: '12345678901234',
        cae_vencimiento: '20300101',
        total: 1210.0,
        errores: [],
        observaciones: [],
      }
      // Guardar algo minimo para futuras consultas (si la UI las hace).
      state.comprobantes.unshift({
        id,
        empresa_id: body.empresa_id ?? 1,
        punto_venta_id: body.punto_venta_id ?? 1,
        tipo_comprobante: body.tipo_comprobante ?? 6,
        numero: 1,
        fecha_emision: new Date().toISOString(),
        cliente_nombre: body.razon_social ?? 'Cliente',
        cliente_documento: body.numero_documento ?? '',
        total: resp.total,
        estado: 'autorizado',
      })
      return jsonResponse(route, 200, resp)
    }

    return jsonResponse(route, 404, { detail: 'Not mocked' })
  }

  // Endpoints con prefijo /api
  await page.route('**/api/**', handler)
  // Endpoints legacy sin /api (ej: /comprobantes/*)
  await page.route('**/comprobantes**', handler)
}

export const loginAsAdmin = async (page: Page) => {
  await page.goto('/login')
  await page.getByLabel(/correo electrónico/i).fill(adminCredentials.email)
  await page.getByLabel(/contraseña/i).fill(adminCredentials.password)
  await page.getByRole('button', { name: /ingresar/i }).click()
  await page.waitForURL((url) => url.pathname === '/' || url.pathname === '/dashboard')
}
