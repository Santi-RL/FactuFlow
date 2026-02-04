# Changelog

Todos los cambios notables de este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Versionado Semántico](https://semver.org/lang/es/).

## [1.0.0] - 2026-02-04

### 🎉 Primera versión estable

Esta es la primera versión estable de FactuFlow, un sistema de facturación electrónica
para Argentina que integra con ARCA (ex-AFIP).

### ✨ Características Principales

#### Sistema de Autenticación
- Login/logout con JWT tokens
- Gestión de usuarios con roles (admin/usuario)
- Configuración inicial guiada (setup wizard)
- Persistencia de sesión con refresh tokens

#### Gestión de Empresas
- Configuración de datos fiscales del emisor
- Soporte para múltiples puntos de venta
- Configuración de condición IVA
- Almacenamiento de logo para PDFs

#### Gestión de Clientes
- CRUD completo de clientes
- Validación de CUIT/CUIL/DNI argentinos
- Búsqueda y filtrado avanzado
- Historial de comprobantes por cliente

#### Wizard de Certificados ARCA
- Generación de CSR y clave privada
- Guía paso a paso con screenshots
- Upload y validación de certificados X.509
- Verificación de conexión con ARCA
- Alertas de vencimiento (30, 15, 7 días)
- Soporte para homologación y producción

#### Emisión de Comprobantes
- Facturas tipo A, B y C
- Notas de Crédito y Débito
- Cálculo automático de IVA (0%, 10.5%, 21%, 27%)
- Vista previa antes de emitir
- Integración con WSFEv1 de ARCA
- Obtención de CAE en tiempo real
- Guardado automático de comprobantes

#### Generación de PDFs
- Template profesional según normativa argentina
- Código QR según especificación ARCA
- Datos fiscales completos
- Descarga y visualización en navegador

#### Sistema de Reportes
- Reporte de ventas por período
- Subdiario IVA para declaración jurada
- Ranking de clientes por facturación
- Filtros por fecha, tipo y cliente

### 🔧 Mejoras Técnicas

#### Backend (FastAPI)
- API REST completa con documentación OpenAPI
- Async/await para mejor rendimiento
- SQLAlchemy 2.0 con soporte async
- Migraciones con Alembic
- Validación con Pydantic v2
- Índices optimizados en base de datos

#### Frontend (Vue.js 3)
- Composition API con `<script setup>`
- TypeScript para type safety
- Tailwind CSS para estilos
- Lazy loading de rutas
- Pinia para state management
- Diseño responsive (mobile-first)

#### Docker
- Docker Compose para desarrollo
- Multi-stage builds optimizados
- Health checks configurados
- Volúmenes para persistencia

### 🔐 Seguridad

- Certificados almacenados con permisos restrictivos (400)
- Claves privadas nunca en repositorio
- Validación exhaustiva de inputs
- Protección CSRF y XSS
- CORS configurado correctamente
- Passwords hasheados con bcrypt
- JWT con expiración configurable

### 📚 Documentación

- README completo en español
- Guía de instalación (Docker y manual)
- Manual de usuario detallado
- Guía de certificados ARCA
- Documentación de API (auto-generada)
- CONTRIBUTING.md para colaboradores

### 🧪 Testing

- Tests unitarios con pytest
- Coverage de código
- Tests de servicios y endpoints
- Fixtures reutilizables
- Configuración de CI/CD

---

## [0.6.0] - 2026-02-03

### Añadido
- Sistema completo de generación de PDFs
- Código QR según especificación ARCA
- Reportes de ventas por período
- Subdiario IVA para DDJJ
- Ranking de clientes

## [0.5.0] - 2026-02-02

### Añadido
- Formulario completo de emisión de facturas
- Integración con WSFEv1 de ARCA
- Obtención de CAE
- Listado y detalle de comprobantes
- Cálculo automático de totales e IVA

## [0.4.0] - 2026-02-01

### Añadido
- Wizard completo de certificados
- Generación de CSR
- Validación de certificados X.509
- Verificación de conexión con ARCA
- Alertas de vencimiento

## [0.3.0] - 2026-01-31

### Añadido
- Frontend completo con Vue.js 3
- Layout responsive con sidebar
- CRUD de clientes
- Configuración de empresa
- Dashboard inicial

## [0.2.0] - 2026-01-30

### Añadido
- Integración con ARCA (WSAA + WSFEv1)
- Cliente SOAP para webservices
- Autenticación con certificados
- Manejo de errores ARCA

## [0.1.0] - 2026-01-29

### Añadido
- Estructura inicial del proyecto
- Backend con FastAPI
- Modelos de base de datos
- API REST básica
- Configuración de Docker
- Documentación inicial

---

## Tipos de Cambios

- **Añadido** para funcionalidades nuevas.
- **Cambiado** para cambios en funcionalidades existentes.
- **Obsoleto** para funcionalidades que serán eliminadas próximamente.
- **Eliminado** para funcionalidades eliminadas.
- **Corregido** para corrección de bugs.
- **Seguridad** para vulnerabilidades.

---

[1.0.0]: https://github.com/Santi-RL/FactuFlow/releases/tag/v1.0.0
[0.6.0]: https://github.com/Santi-RL/FactuFlow/releases/tag/v0.6.0
[0.5.0]: https://github.com/Santi-RL/FactuFlow/releases/tag/v0.5.0
[0.4.0]: https://github.com/Santi-RL/FactuFlow/releases/tag/v0.4.0
[0.3.0]: https://github.com/Santi-RL/FactuFlow/releases/tag/v0.3.0
[0.2.0]: https://github.com/Santi-RL/FactuFlow/releases/tag/v0.2.0
[0.1.0]: https://github.com/Santi-RL/FactuFlow/releases/tag/v0.1.0
