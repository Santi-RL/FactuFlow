# Documentación de la API REST

Documentación completa de la API REST de FactuFlow.

## URL Base

- **Desarrollo**: `http://localhost:8000`
- **Producción**: `https://tu-dominio.com`

## Autenticación

La API usa **JWT (JSON Web Tokens)** para autenticación.

### Obtener Token

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "tu-password"
}
```

**Respuesta:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com"
  }
}
```

### Usar Token

Incluir en el header `Authorization` de todas las requests:

```http
GET /api/v1/clientes
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Endpoints

### Clientes

#### Listar Clientes

```http
GET /api/v1/clientes
Authorization: Bearer {token}
```

**Query Parameters:**
- `page` (opcional): Número de página (default: 1)
- `per_page` (opcional): Items por página (default: 20, max: 100)
- `q` (opcional): Búsqueda por nombre o CUIT

**Respuesta:**
```json
{
  "data": [
    {
      "id": 1,
      "nombre": "Juan Pérez",
      "cuit": "20123456789",
      "tipo_documento": "CUIT",
      "condicion_iva": "Responsable Inscripto",
      "email": "juan@example.com",
      "domicilio": "Av. Corrientes 1234, CABA",
      "activo": true,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "pages": 8
  }
}
```

#### Obtener Cliente

```http
GET /api/v1/clientes/{id}
Authorization: Bearer {token}
```

#### Crear Cliente

```http
POST /api/v1/clientes
Authorization: Bearer {token}
Content-Type: application/json

{
  "nombre": "María García",
  "cuit": "27234567890",
  "tipo_documento": "CUIT",
  "condicion_iva": "Monotributista",
  "email": "maria@example.com",
  "domicilio": "Calle Falsa 123, CABA"
}
```

#### Actualizar Cliente

```http
PUT /api/v1/clientes/{id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "email": "nuevo-email@example.com",
  "domicilio": "Nueva dirección 456"
}
```

#### Eliminar Cliente

```http
DELETE /api/v1/clientes/{id}
Authorization: Bearer {token}
```

---

### Comprobantes

#### Listar Comprobantes

```http
GET /api/v1/comprobantes
Authorization: Bearer {token}
```

**Query Parameters:**
- `tipo` (opcional): Filtrar por tipo (1=Factura A, 6=Factura B, etc.)
- `desde` (opcional): Fecha desde (ISO 8601)
- `hasta` (opcional): Fecha hasta (ISO 8601)
- `cliente_id` (opcional): Filtrar por cliente
- `estado` (opcional): autorizado, rechazado, pendiente

#### Obtener Comprobante

```http
GET /api/v1/comprobantes/{id}
Authorization: Bearer {token}
```

#### Emitir Comprobante

```http
POST /api/v1/comprobantes
Authorization: Bearer {token}
Content-Type: application/json

{
  "tipo_cbte": 1,
  "punto_vta": 1,
  "cliente_id": 5,
  "fecha_cbte": "2024-01-20",
  "items": [
    {
      "descripcion": "Servicio de consultoría",
      "cantidad": 10,
      "precio_unitario": 1000.00,
      "alicuota_iva": 21.0
    }
  ],
  "observaciones": "Factura por servicios prestados"
}
```

**Respuesta:**
```json
{
  "id": 123,
  "tipo_cbte": 1,
  "punto_vta": 1,
  "nro_cbte": 456,
  "cae": "12345678901234",
  "vto_cae": "2024-01-30",
  "fecha_cbte": "2024-01-20",
  "subtotal": 10000.00,
  "iva": 2100.00,
  "total": 12100.00,
  "estado": "autorizado",
  "created_at": "2024-01-20T15:30:00Z"
}
```

#### Descargar PDF

```http
GET /api/v1/comprobantes/{id}/pdf
Authorization: Bearer {token}
```

**Respuesta:** Archivo PDF

---

### Certificados ARCA

#### Listar Certificados

```http
GET /api/v1/certificados
Authorization: Bearer {token}
```

#### Subir Certificado

```http
POST /api/v1/certificados/upload
Authorization: Bearer {token}
Content-Type: multipart/form-data

certificado: [archivo .crt]
clave_privada: [archivo .key]
alias: "Certificado Producción 2024"
ambiente: "homologacion"
```

#### Estado del Certificado

```http
GET /api/v1/certificados/{id}/status
Authorization: Bearer {token}
```

**Respuesta:**
```json
{
  "id": 1,
  "cuit": "20123456789",
  "alias": "Certificado Producción 2024",
  "ambiente": "homologacion",
  "fecha_emision": "2024-01-01",
  "fecha_vencimiento": "2026-01-01",
  "dias_restantes": 365,
  "estado": "activo",
  "warnings": []
}
```

---

## Códigos de Error

| Código | Descripción |
|--------|-------------|
| 200 | OK - Éxito |
| 201 | Created - Recurso creado |
| 204 | No Content - Eliminado exitosamente |
| 400 | Bad Request - Datos inválidos |
| 401 | Unauthorized - No autenticado |
| 403 | Forbidden - Sin permisos |
| 404 | Not Found - Recurso no encontrado |
| 422 | Unprocessable Entity - Error de validación |
| 500 | Internal Server Error - Error del servidor |

---

## Documentación Interactiva

FactuFlow incluye documentación interactiva generada automáticamente:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

Podés probar todos los endpoints directamente desde el navegador.

---

## Rate Limiting

Para proteger el servidor, hay límites de requests:
- **Autenticados**: 1000 requests/hora
- **No autenticados**: 100 requests/hora

Si excedés el límite, recibirás:
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Demasiados requests. Intentá de nuevo en 30 minutos."
  }
}
```

---

## Versionado

La API usa versionado en la URL (`/api/v1/`). Cambios que rompen compatibilidad incrementarán la versión (`/api/v2/`).

---

## Soporte

- 📖 Documentación completa: http://localhost:8000/docs
- 💬 Discussions: https://github.com/Santi-RL/FactuFlow/discussions
- 🐛 Issues: https://github.com/Santi-RL/FactuFlow/issues
