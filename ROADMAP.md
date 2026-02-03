# 🗺️ Roadmap de Desarrollo - FactuFlow

Plan de desarrollo paso a paso para FactuFlow, organizado en fases incrementales.

---

## Fase 0: Fundación ✅ (En Progreso)

Establecer la estructura base del proyecto y configuración inicial.

- [x] Crear repositorio en GitHub
- [x] README.md inicial con descripción del proyecto
- [x] AGENTS.md con guías para desarrolladores e IA
- [x] ROADMAP.md (este archivo)
- [ ] Estructura de carpetas completa
- [ ] Configuración de Docker
  - [ ] `docker-compose.yml` con servicios backend y frontend
  - [ ] `Dockerfile` para backend (Python/FastAPI)
  - [ ] `Dockerfile` para frontend (Vue.js/Vite)
  - [ ] `.dockerignore` para ambos servicios
- [ ] GitHub Actions para CI básico
  - [ ] Workflow para tests de backend (pytest)
  - [ ] Workflow para tests de frontend (vitest)
  - [ ] Workflow para linting (black, pylint, eslint)
- [ ] Archivos de configuración
  - [ ] `.gitignore` completo (Python, Node, certificados, BD)
  - [ ] `.env.example` con variables de entorno
  - [ ] `LICENSE` (MIT)
  - [ ] `CONTRIBUTING.md` en español
  - [ ] `pyproject.toml` (black, pytest config)
  - [ ] `eslint.config.js` y `.prettierrc`
- [ ] Documentación base
  - [ ] `docs/setup/README.md` - Guía de instalación
  - [ ] `docs/certificates/README.md` - Guía de certificados
  - [ ] `docs/api/README.md` - API reference (placeholder)
  - [ ] `docs/user-guide/README.md` - Manual de usuario

---

## Fase 1: Backend Core

Desarrollo del backend con FastAPI, estructura modular y base de datos.

### 1.1 Configuración Inicial
- [ ] Setup de FastAPI con estructura modular
  - [ ] `app/main.py` con aplicación base
  - [ ] `app/core/config.py` con Settings (Pydantic)
  - [ ] `app/core/database.py` con SQLAlchemy setup
  - [ ] Middleware de CORS configurado
  - [ ] Logger configurado
- [ ] Configuración de SQLAlchemy
  - [ ] Base declarativa
  - [ ] Session management
  - [ ] Dependency injection para DB
- [ ] Setup de Alembic para migraciones
  - [ ] `alembic init`
  - [ ] Configuración de `env.py`
  - [ ] Primera migración: tablas iniciales

### 1.2 Modelos de Base de Datos
- [ ] Modelo `Empresa`
  - [ ] CUIT (único, obligatorio)
  - [ ] Razón social
  - [ ] Domicilio fiscal
  - [ ] Fecha de inicio de actividades
  - [ ] Configuración de puntos de venta
- [ ] Modelo `PuntoDeVenta`
  - [ ] Número de punto de venta
  - [ ] Descripción/alias
  - [ ] Relación con Empresa
- [ ] Modelo `Certificado`
  - [ ] CUIT relacionado
  - [ ] Alias del certificado
  - [ ] Fecha de emisión
  - [ ] Fecha de vencimiento
  - [ ] Path del archivo (NO el contenido)
  - [ ] Ambiente (homologación/producción)
  - [ ] Estado (activo/vencido/próximo a vencer)
- [ ] Modelo `Cliente`
  - [ ] CUIT/CUIL/DNI
  - [ ] Tipo de documento
  - [ ] Nombre/Razón social
  - [ ] Domicilio
  - [ ] Email (opcional)
  - [ ] Condición IVA
  - [ ] Relación con Empresa (multi-tenant)
- [ ] Modelo `Comprobante`
  - [ ] Tipo de comprobante (A, B, C, NC, ND)
  - [ ] Punto de venta
  - [ ] Número de comprobante
  - [ ] Fecha de emisión
  - [ ] CUIT emisor y receptor
  - [ ] Subtotal, IVA, total
  - [ ] CAE (Código de Autorización Electrónica)
  - [ ] Fecha de vencimiento del CAE
  - [ ] Estado (pendiente/autorizado/rechazado)
  - [ ] Relación con Cliente y Empresa
- [ ] Modelo `ComprobanteItem`
  - [ ] Descripción del producto/servicio
  - [ ] Cantidad
  - [ ] Precio unitario
  - [ ] Alícuota de IVA
  - [ ] Subtotal
  - [ ] Relación con Comprobante

### 1.3 Schemas Pydantic
- [ ] `ClienteCreate`, `ClienteUpdate`, `ClienteResponse`
- [ ] `EmpresaCreate`, `EmpresaUpdate`, `EmpresaResponse`
- [ ] `ComprobanteCreate`, `ComprobanteResponse`
- [ ] `CertificadoCreate`, `CertificadoResponse`

### 1.4 API REST Básica
- [ ] Endpoints de Clientes
  - [ ] `GET /api/v1/clientes` - Listar clientes (con paginación)
  - [ ] `GET /api/v1/clientes/{id}` - Obtener cliente
  - [ ] `POST /api/v1/clientes` - Crear cliente
  - [ ] `PUT /api/v1/clientes/{id}` - Actualizar cliente
  - [ ] `DELETE /api/v1/clientes/{id}` - Eliminar cliente
- [ ] Endpoints de Empresas
  - [ ] `GET /api/v1/empresas` - Listar empresas
  - [ ] `GET /api/v1/empresas/{id}` - Obtener empresa
  - [ ] `POST /api/v1/empresas` - Crear empresa
  - [ ] `PUT /api/v1/empresas/{id}` - Actualizar empresa

### 1.5 Sistema de Autenticación
- [ ] Modelo `Usuario`
  - [ ] Username
  - [ ] Password hash (bcrypt)
  - [ ] Email
  - [ ] Rol (admin/usuario)
- [ ] JWT tokens para autenticación
- [ ] Endpoints de auth
  - [ ] `POST /api/v1/auth/login` - Login
  - [ ] `POST /api/v1/auth/logout` - Logout
  - [ ] `GET /api/v1/auth/me` - Usuario actual
- [ ] Middleware de autenticación
- [ ] Dependency para verificar permisos

### 1.6 Almacenamiento de Certificados
- [ ] Servicio de gestión de certificados
  - [ ] Almacenar en filesystem con permisos restrictivos (400)
  - [ ] Validar certificado X.509 al subir
  - [ ] Extraer información (CUIT, fechas)
  - [ ] Calcular días hasta vencimiento
- [ ] Endpoints de certificados
  - [ ] `POST /api/v1/certificados/upload` - Subir certificado
  - [ ] `GET /api/v1/certificados` - Listar certificados
  - [ ] `DELETE /api/v1/certificados/{id}` - Eliminar certificado
  - [ ] `GET /api/v1/certificados/{id}/status` - Estado del certificado

### 1.7 Tests Unitarios
- [ ] Fixtures de pytest (conftest.py)
- [ ] Tests de modelos
  - [ ] Test validaciones de CUIT
  - [ ] Test relaciones entre modelos
- [ ] Tests de endpoints
  - [ ] Tests CRUD de clientes
  - [ ] Tests CRUD de empresas
  - [ ] Tests de autenticación
- [ ] Coverage mínimo del 80%

---

## Fase 2: Integración ARCA

Integración completa con webservices de ARCA para autenticación y emisión de comprobantes.

**Nota**: Los webservices de ARCA mantienen las URLs y nombres legacy de AFIP (wsaa.afip.gov.ar, etc.) por compatibilidad técnica.

### 2.1 Cliente SOAP Genérico
- [ ] Configuración de zeep o suds
- [ ] Cliente SOAP base con manejo de errores
- [ ] Cache de WSDL
- [ ] Logging de requests/responses
- [ ] Timeout y reintentos configurables

### 2.2 WSAA (Web Service de Autenticación y Autorización)
- [ ] Generación de TRA (Ticket de Requerimiento de Acceso)
  - [ ] XML con servicio solicitado
  - [ ] Timestamp y expiración
  - [ ] Generación única (uniqueId)
- [ ] Firma de TRA con certificado
  - [ ] Cargar certificado .crt y clave .key
  - [ ] Firmar con OpenSSL/cryptography
  - [ ] Generar CMS (Cryptographic Message Syntax)
- [ ] Llamada al WSAA
  - [ ] `loginCms()` con CMS firmado
  - [ ] Parsear respuesta (Token y Sign)
  - [ ] Manejo de errores ARCA
- [ ] Cache de Token y Sign
  - [ ] Almacenar en BD o Redis
  - [ ] Auto-renovación antes de expiración
  - [ ] Invalidación manual
- [ ] Endpoints
  - [ ] `POST /api/v1/afip/wsaa/login` - Obtener Token y Sign
  - [ ] `GET /api/v1/afip/wsaa/status` - Estado de autenticación

### 2.3 WSFEv1 (Factura Electrónica)
- [ ] Configuración del cliente SOAP para WSFEv1
- [ ] `FECAESolicitar` - Solicitar CAE
  - [ ] Armar request con datos del comprobante
  - [ ] Incluir Token y Sign de WSAA
  - [ ] Parsear respuesta (CAE, vencimiento CAE)
  - [ ] Manejo de errores y observaciones
  - [ ] Actualizar comprobante en BD con CAE
- [ ] `FECompUltimoAutorizado` - Último comprobante
  - [ ] Obtener último número de comprobante por tipo y punto de venta
  - [ ] Cache local para optimización
- [ ] `FECompConsultar` - Consultar comprobante
  - [ ] Buscar comprobante ya emitido
  - [ ] Verificar estado en ARCA
- [ ] Métodos de parámetros
  - [ ] `FEParamGetTiposCbte` - Tipos de comprobante
  - [ ] `FEParamGetTiposDoc` - Tipos de documento
  - [ ] `FEParamGetTiposIva` - Tipos de IVA
  - [ ] `FEParamGetMonedas` - Monedas
  - [ ] `FEParamGetPtosVenta` - Puntos de venta habilitados
  - [ ] Cache de parámetros en BD (actualizar diariamente)

### 2.4 Manejo de Errores ARCA
- [ ] Excepciones personalizadas
  - [ ] `ARCAAuthError` - Error de autenticación
  - [ ] `ARCAValidationError` - Error de validación
  - [ ] `ARCAConnectionError` - Error de conexión
  - [ ] `ARCAServiceError` - Error del servicio
- [ ] Códigos de error ARCA mapeados
- [ ] Mensajes de error amigables en español
- [ ] Reintentos automáticos (con backoff exponencial)
- [ ] Logging detallado de errores

### 2.5 Modo Homologación vs Producción
- [ ] Variable de entorno `ARCA_ENV` (homologacion/produccion)
- [ ] URLs de webservices según ambiente
- [ ] Validación de certificados según ambiente
- [ ] Advertencias visibles en UI cuando está en producción
- [ ] CUIT de prueba para homologación (20409378472)

### 2.6 Tests con Mocks
- [ ] Mocks de respuestas WSAA
  - [ ] Login exitoso
  - [ ] Error de certificado
  - [ ] Error de servicio
- [ ] Mocks de respuestas WSFEv1
  - [ ] CAE otorgado
  - [ ] Comprobante rechazado
  - [ ] Errores de validación
- [ ] Tests de integración (con ARCA homologación)
  - [ ] Solo si hay certificados de test
  - [ ] No ejecutar en CI (usar mocks)

---

## Fase 3: Frontend Básico

Desarrollo del frontend con Vue.js 3, Tailwind CSS y componentes reutilizables.

### 3.1 Configuración Inicial
- [ ] Setup de Vite + Vue 3 + TypeScript
- [ ] Configuración de Tailwind CSS
  - [ ] `tailwind.config.js` con tema customizado
  - [ ] Colores primarios, secundarios
  - [ ] Fuentes tipográficas
- [ ] Configuración de Vue Router
- [ ] Configuración de Pinia (store)
- [ ] Configuración de Axios
  - [ ] Instancia configurada con baseURL
  - [ ] Interceptors para auth (JWT)
  - [ ] Interceptors para errores

### 3.2 Layout Principal
- [ ] Componente `AppLayout.vue`
  - [ ] Estructura con sidebar + main content
  - [ ] Header con logo y usuario
  - [ ] Responsive (mobile-first)
- [ ] Componente `Sidebar.vue`
  - [ ] Menú de navegación
  - [ ] Items activos destacados
  - [ ] Iconos (usar @heroicons/vue)
  - [ ] Colapsable en mobile
- [ ] Componente `Header.vue`
  - [ ] Logo de FactuFlow
  - [ ] Usuario logueado
  - [ ] Menú de usuario (perfil, logout)
  - [ ] Notificaciones (vencimiento de certificados)

### 3.3 Sistema de Rutas
- [ ] Rutas públicas
  - [ ] `/login` - Login
  - [ ] `/` - Redirect según auth
- [ ] Rutas protegidas (requieren auth)
  - [ ] `/dashboard` - Dashboard principal
  - [ ] `/clientes` - Listado de clientes
  - [ ] `/clientes/nuevo` - Crear cliente
  - [ ] `/clientes/:id` - Editar cliente
  - [ ] `/comprobantes` - Listado de comprobantes
  - [ ] `/comprobantes/nuevo` - Nueva factura
  - [ ] `/configuracion` - Configuración de empresa
  - [ ] `/certificados` - Gestión de certificados
- [ ] Guards de navegación
  - [ ] Verificar autenticación
  - [ ] Redirect a /login si no autenticado

### 3.4 Store Global (Pinia)
- [ ] Store `useAuthStore`
  - [ ] Estado: user, token, isAuthenticated
  - [ ] Actions: login, logout, checkAuth
  - [ ] Persistencia en localStorage
- [ ] Store `useEmpresaStore`
  - [ ] Estado: empresa actual
  - [ ] Actions: fetchEmpresa, updateEmpresa
- [ ] Store `useComprobantesStore`
  - [ ] Estado: lista de comprobantes
  - [ ] Actions: fetchComprobantes, createComprobante
  - [ ] Filtros y paginación

### 3.5 Componentes Base (UI)
- [ ] `Button.vue`
  - [ ] Variantes: primary, secondary, danger, ghost
  - [ ] Tamaños: sm, md, lg
  - [ ] Estados: loading, disabled
- [ ] `Input.vue`
  - [ ] Text, number, email, password
  - [ ] Label, placeholder, error message
  - [ ] Validación visual
- [ ] `Select.vue`
  - [ ] Dropdown con opciones
  - [ ] Búsqueda (opcional)
  - [ ] Multi-select (opcional)
- [ ] `Modal.vue`
  - [ ] Overlay con contenido
  - [ ] Tamaños: sm, md, lg, xl
  - [ ] Botones de acción
  - [ ] Close al hacer click fuera
- [ ] `Table.vue`
  - [ ] Headers personalizables
  - [ ] Sorting por columna
  - [ ] Paginación integrada
  - [ ] Acciones por fila
- [ ] `Card.vue`
  - [ ] Container con sombra
  - [ ] Header, body, footer opcionales
- [ ] `Alert.vue`
  - [ ] Tipos: success, error, warning, info
  - [ ] Dismissable
- [ ] `Badge.vue`
  - [ ] Variantes de color
  - [ ] Tamaños

### 3.6 Páginas Principales
- [ ] `Login.vue`
  - [ ] Formulario de login
  - [ ] Validación de campos
  - [ ] Manejo de errores
  - [ ] Redirect después de login
- [ ] `Dashboard.vue`
  - [ ] Resumen de ventas del mes
  - [ ] Últimas facturas emitidas
  - [ ] Alertas (certificados por vencer)
  - [ ] Gráficos (opcional, con Chart.js)
- [ ] `Clientes.vue`
  - [ ] Listado de clientes en tabla
  - [ ] Búsqueda por nombre/CUIT
  - [ ] Botón "Nuevo Cliente"
  - [ ] Acciones: ver, editar, eliminar
  - [ ] Paginación
- [ ] `ClienteForm.vue`
  - [ ] Formulario de cliente (crear/editar)
  - [ ] Validación de CUIT
  - [ ] Todos los campos del modelo
  - [ ] Guardar y volver
- [ ] `Configuracion.vue`
  - [ ] Datos de la empresa
  - [ ] Puntos de venta
  - [ ] Configuración ARCA (homologación/producción)

---

## Fase 4: Wizard de Certificados (CRÍTICO)

El Wizard de Certificados es la funcionalidad MÁS IMPORTANTE para la UX. Debe ser extremadamente guiado.

### 4.1 Diseño del Wizard
- [ ] Componente `WizardCertificados.vue`
  - [ ] Steps visuales (1, 2, 3, 4, 5)
  - [ ] Navegación adelante/atrás
  - [ ] Validación por step
  - [ ] Progreso guardado (puede salir y volver)

### 4.2 Step 1: Introducción
- [ ] Explicación sencilla de qué es un certificado
  - [ ] "Es como un DNI digital para tu empresa"
  - [ ] "Te permite comunicarte con ARCA de forma segura"
- [ ] Diferencia homologación vs producción
  - [ ] "Homologación es para probar, producción es para facturas reales"
- [ ] Advertencia de seguridad
  - [ ] "Guardá el certificado en un lugar seguro"
  - [ ] "No lo compartas con nadie"
- [ ] Botón "Continuar"

### 4.3 Step 2: Generar CSR
- [ ] Explicación de qué es un CSR
  - [ ] "Es una solicitud de certificado que vas a enviar a ARCA"
- [ ] Dos opciones:
  - [ ] **Opción A**: Generar CSR desde FactuFlow
    - [ ] Formulario con datos (CUIT, nombre, etc.)
    - [ ] Botón "Generar CSR y Clave"
    - [ ] Descarga automática de CSR y .key
    - [ ] **ADVERTENCIA**: Guardar .key en lugar seguro
  - [ ] **Opción B**: Ya tengo un CSR
    - [ ] Skip a Step 3
- [ ] Comando manual (para usuarios avanzados):
  ```bash
  openssl req -new -newkey rsa:2048 -nodes \
    -keyout clave.key -out certificado.csr
  ```
- [ ] Botón "Ya tengo mi CSR, continuar"

### 4.4 Step 3: Obtener Certificado desde ARCA
- [ ] Guía paso a paso con screenshots:
  1. "Ingresá a ARCA con tu Clave Fiscal"
  2. "Andá a: Administrador de Relaciones → Certificados Digitales"
  3. "Hacé click en 'Nuevo Certificado'"
  4. "Seleccioná el servicio: wsfe (Factura Electrónica)"
  5. "Copiá y pegá tu CSR en el campo"
  6. "Descargá el certificado (.crt)"
- [ ] Links directos:
  - [ ] [ARCA Homologación](https://auth.afip.gov.ar/contribuyente_/...)
  - [ ] [ARCA Producción](https://auth.afip.gov.ar/contribuyente_/...)
- [ ] Checkbox "Ya descargué mi certificado .crt"
- [ ] Botón "Continuar"

### 4.5 Step 4: Subir Certificado a FactuFlow
- [ ] Upload de certificado .crt
  - [ ] Drag & drop o click para seleccionar
  - [ ] Validación de archivo (.crt o .pem)
  - [ ] Preview de información extraída:
    - [ ] CUIT
    - [ ] Fecha de emisión
    - [ ] Fecha de vencimiento
    - [ ] Días restantes
- [ ] Upload de clave privada .key (si no se generó en Step 2)
  - [ ] Validación de que coincide con .crt
- [ ] Alias del certificado (opcional)
  - [ ] Ej: "Certificado Producción 2024"
- [ ] Ambiente (homologación/producción)
- [ ] Botón "Subir Certificado"

### 4.6 Step 5: Verificación y Test
- [ ] Test de conexión con ARCA
  - [ ] Llamar a WSAA con el certificado
  - [ ] Intentar obtener Token y Sign
  - [ ] Mostrar resultado:
    - [ ] ✅ "Conexión exitosa. Tu certificado funciona correctamente"
    - [ ] ❌ "Error: [descripción del error]"
- [ ] Si hay error:
  - [ ] Sugerencias de troubleshooting
  - [ ] Botón "Intentar de nuevo"
  - [ ] Botón "Volver al paso anterior"
- [ ] Si es exitoso:
  - [ ] Felicitaciones 🎉
  - [ ] "Ya podés empezar a facturar"
  - [ ] Botón "Ir al Dashboard"

### 4.7 Wizard de Renovación
- [ ] Detectar certificados próximos a vencer
- [ ] Wizard similar pero simplificado:
  - [ ] Step 1: Generar nuevo CSR (con mismos datos)
  - [ ] Step 2: Obtener nuevo certificado de ARCA
  - [ ] Step 3: Subir y reemplazar
  - [ ] Step 4: Verificar
- [ ] Mantener histórico de certificados antiguos

### 4.8 Alertas de Vencimiento
- [ ] Sistema de alertas en Header/Dashboard
  - [ ] 30 días antes: alerta amarilla "Tu certificado vence en X días"
  - [ ] 15 días antes: alerta naranja "Renová tu certificado pronto"
  - [ ] 7 días antes: alerta roja "URGENTE: Renová tu certificado"
  - [ ] Vencido: error crítico "Certificado vencido, no podés facturar"
- [ ] Badge en sidebar junto a "Certificados"
- [ ] Email/notificación (futuro)

### 4.9 Indicador Visual de Estado
- [ ] En página de Certificados, mostrar:
  - [ ] 🟢 Activo (más de 30 días)
  - [ ] 🟡 Próximo a vencer (30-15 días)
  - [ ] 🟠 Crítico (15-7 días)
  - [ ] 🔴 Por vencer (menos de 7 días)
  - [ ] ⚫ Vencido
- [ ] Días restantes en número grande
- [ ] Botón "Renovar" visible

---

## Fase 5: Emisión de Comprobantes

Funcionalidad completa para emitir facturas, notas de crédito y débito.

### 5.1 Formulario de Nueva Factura
- [ ] Página `NuevaFactura.vue`
- [ ] **Paso 1: Tipo de Comprobante**
  - [ ] Selección: Factura A, B, C, Nota de Crédito, Nota de Débito
  - [ ] Explicación de cada tipo:
    - [ ] Factura A: Para responsables inscriptos (discrimina IVA)
    - [ ] Factura B: Para consumidores finales y monotributistas
    - [ ] Factura C: Para operaciones exentas
  - [ ] Punto de venta (dropdown de puntos habilitados)
  - [ ] Número de comprobante (autocompletado desde último autorizado)
- [ ] **Paso 2: Cliente**
  - [ ] Búsqueda de cliente existente (por nombre o CUIT)
  - [ ] O "Carga Rápida" de cliente nuevo
    - [ ] Campos mínimos: CUIT, Nombre, Condición IVA
    - [ ] Guardar cliente en BD automáticamente
  - [ ] Validación de CUIT
  - [ ] Mostrar condición IVA del cliente
- [ ] **Paso 3: Items**
  - [ ] Tabla de items
  - [ ] Agregar item:
    - [ ] Descripción (textarea)
    - [ ] Cantidad (number)
    - [ ] Precio unitario (number)
    - [ ] Alícuota IVA (dropdown: 0%, 10.5%, 21%, 27%)
    - [ ] Subtotal (calculado automáticamente)
  - [ ] Editar item
  - [ ] Eliminar item
  - [ ] Cálculo en tiempo real:
    - [ ] Subtotal
    - [ ] IVA (desglosado por alícuota)
    - [ ] Total
- [ ] **Paso 4: Vista Previa**
  - [ ] Preview del comprobante formateado
  - [ ] Todos los datos visibles
  - [ ] Advertencia: "Este comprobante se enviará a ARCA"
  - [ ] Botones:
    - [ ] "Volver a editar"
    - [ ] "Emitir Comprobante"

### 5.2 Emisión a ARCA
- [ ] Al hacer click en "Emitir":
  - [ ] Validar todos los datos
  - [ ] Loading spinner
  - [ ] Llamar a servicio backend
- [ ] Backend:
  - [ ] Obtener Token y Sign (WSAA)
  - [ ] Obtener último comprobante autorizado
  - [ ] Armar request de FECAESolicitar
  - [ ] Enviar a ARCA WSFEv1
  - [ ] Parsear respuesta
- [ ] Manejo de respuesta:
  - [ ] **Éxito**: CAE obtenido
    - [ ] Guardar comprobante en BD con CAE
    - [ ] Mostrar modal de éxito con CAE y vencimiento
    - [ ] Opciones: "Ver Comprobante", "Imprimir", "Enviar por Email"
  - [ ] **Rechazo**: ARCA rechazó
    - [ ] Mostrar errores de ARCA en español
    - [ ] Sugerencias de corrección
    - [ ] Volver a editar
  - [ ] **Error**: Error técnico
    - [ ] Mostrar error
    - [ ] Opción de reintentar
    - [ ] Guardar como borrador (para no perder datos)

### 5.3 Listado de Comprobantes
- [ ] Página `Comprobantes.vue`
- [ ] Tabla con columnas:
  - [ ] Tipo de comprobante (badge con color)
  - [ ] Número (formato: 0001-00000123)
  - [ ] Fecha
  - [ ] Cliente
  - [ ] Total
  - [ ] CAE
  - [ ] Estado (badge: Autorizado/Rechazado/Pendiente)
  - [ ] Acciones
- [ ] Filtros:
  - [ ] Por tipo de comprobante
  - [ ] Por fecha (rango)
  - [ ] Por cliente
  - [ ] Por estado
- [ ] Búsqueda por número de comprobante o CAE
- [ ] Paginación
- [ ] Botón "Nueva Factura"

### 5.4 Detalle de Comprobante
- [ ] Página `DetalleComprobante.vue`
- [ ] Vista completa del comprobante:
  - [ ] Header: Logo, datos de empresa emisora
  - [ ] Tipo y número de comprobante (grande)
  - [ ] CAE y vencimiento CAE
  - [ ] Fecha de emisión
  - [ ] Datos del cliente
  - [ ] Tabla de items
  - [ ] Subtotal, IVA, Total
  - [ ] Código QR (según normativa ARCA)
  - [ ] Leyendas legales
- [ ] Acciones:
  - [ ] Imprimir (abre PDF)
  - [ ] Descargar PDF
  - [ ] Enviar por email
  - [ ] Reimprimir (para comprobantes antiguos)
  - [ ] Anular (si está permitido)

---

## Fase 6: PDF y Reportes

Generación de PDFs legales y reportes de gestión.

### 6.1 Generación de PDF
- [ ] Servicio backend para generar PDF
  - [ ] Librería: ReportLab (Python) o WeasyPrint
  - [ ] Template HTML/CSS para factura
- [ ] Formato del PDF:
  - [ ] Header con logo y datos de empresa
  - [ ] Tipo de comprobante y letra (A/B/C) grande
  - [ ] Número de comprobante con formato
  - [ ] CAE y vencimiento CAE destacados
  - [ ] Código QR según normativa ARCA:
    - [ ] Contiene: URL de verificación, CUIT, tipo cbte, punto vta, número, CAE
    - [ ] Posición: esquina inferior derecha
  - [ ] Datos del cliente
  - [ ] Tabla de items con bordes
  - [ ] Subtotal, IVA desglosado, Total
  - [ ] Leyendas legales:
    - [ ] "Documento no válido como factura" (si es copia)
    - [ ] Texto legal según tipo de comprobante
- [ ] Endpoint: `GET /api/v1/comprobantes/{id}/pdf`
  - [ ] Generar PDF on-the-fly
  - [ ] O usar PDF cacheado (si ya fue generado)
  - [ ] Content-Type: application/pdf

### 6.2 Código QR
- [ ] Generar QR según especificación ARCA
- [ ] Formato del QR:
  ```
  https://www.afip.gob.ar/fe/qr/?p=BASE64_DATA
  ```
  - [ ] BASE64_DATA contiene JSON con datos del comprobante
- [ ] Librería: `qrcode` (Python) o `qrcode.js` (JS)
- [ ] Incluir en PDF
- [ ] Mostrar en vista web del comprobante

### 6.3 Envío de Email
- [ ] Configuración SMTP en .env
  ```
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=tu-email@gmail.com
  SMTP_PASSWORD=tu-password
  ```
- [ ] Servicio de envío de emails
  - [ ] Librería: `fastapi-mail` o `smtplib`
  - [ ] Template HTML para email
  - [ ] Adjuntar PDF
- [ ] Endpoint: `POST /api/v1/comprobantes/{id}/enviar-email`
  - [ ] Body: { "destinatario": "email@example.com" }
  - [ ] Validar email
  - [ ] Enviar async (Celery o BackgroundTasks)
  - [ ] Notificar éxito/error
- [ ] En frontend:
  - [ ] Modal "Enviar por Email"
  - [ ] Input de email (pre-llenado con email del cliente)
  - [ ] Botón "Enviar"
  - [ ] Feedback visual

### 6.4 Reportes Básicos
- [ ] **Reporte: Ventas por Período**
  - [ ] Filtrar por rango de fechas
  - [ ] Agrupado por día/semana/mes
  - [ ] Mostrar:
    - [ ] Cantidad de comprobantes
    - [ ] Total facturado
    - [ ] Total IVA
  - [ ] Gráfico de barras (opcional)
  - [ ] Exportar a Excel/CSV
- [ ] **Reporte: IVA Ventas**
  - [ ] Filtrar por mes
  - [ ] Listado de comprobantes con IVA discriminado
  - [ ] Totales por alícuota (10.5%, 21%, 27%)
  - [ ] Exportar para libro IVA Digital
- [ ] **Reporte: Listado de Clientes**
  - [ ] Todos los clientes con datos de contacto
  - [ ] Total facturado por cliente
  - [ ] Último comprobante emitido
  - [ ] Exportar a Excel/CSV

---

## Fase 7: Pulido y Release

Optimización, testing exhaustivo y preparación para el lanzamiento de v1.0.0.

### 7.1 Testing End-to-End
- [ ] Setup de Playwright o Cypress
- [ ] Tests E2E críticos:
  - [ ] Login y autenticación
  - [ ] Crear cliente
  - [ ] Emitir factura completa (mock de ARCA)
  - [ ] Generar PDF
  - [ ] Wizard de certificados (mock de ARCA)
- [ ] Tests en diferentes navegadores
  - [ ] Chrome
  - [ ] Firefox
  - [ ] Safari
  - [ ] Edge
- [ ] Tests responsive
  - [ ] Desktop (1920x1080)
  - [ ] Tablet (768x1024)
  - [ ] Mobile (375x667)

### 7.2 Documentación de Usuario
- [ ] Manual de usuario completo
  - [ ] Instalación con Docker
  - [ ] Instalación manual (sin Docker)
  - [ ] Configuración inicial
  - [ ] Wizard de certificados (paso a paso con screenshots)
  - [ ] Crear clientes
  - [ ] Emitir facturas
  - [ ] Generar reportes
  - [ ] Troubleshooting
  - [ ] FAQ
- [ ] Videos tutoriales (opcional)
  - [ ] Instalación
  - [ ] Primera factura
  - [ ] Certificados ARCA
- [ ] Documentación técnica
  - [ ] Arquitectura del sistema
  - [ ] API Reference (auto-generada con OpenAPI)
  - [ ] Guía de desarrollo
  - [ ] Guía de despliegue en VPS

### 7.3 Optimización de Rendimiento
- [ ] Backend:
  - [ ] Índices en BD (CUIT, fechas, números de comprobante)
  - [ ] Cache de parámetros ARCA (Redis o memoria)
  - [ ] Compresión de responses (gzip)
  - [ ] Paginación eficiente
  - [ ] N+1 queries resueltas
- [ ] Frontend:
  - [ ] Lazy loading de rutas
  - [ ] Code splitting
  - [ ] Compresión de assets
  - [ ] Optimización de imágenes
  - [ ] Service Worker para PWA (opcional)
- [ ] Docker:
  - [ ] Multi-stage builds para reducir tamaño
  - [ ] Health checks
  - [ ] Resource limits

### 7.4 Revisión de Seguridad
- [ ] Checklist de seguridad:
  - [ ] Ningún secreto en código
  - [ ] .gitignore excluye certificados y .env
  - [ ] Variables sensibles en .env
  - [ ] CORS configurado correctamente
  - [ ] Rate limiting en endpoints públicos
  - [ ] Validación de inputs (Pydantic + sanitización)
  - [ ] Protección contra SQL injection (usar ORM)
  - [ ] Protección contra XSS (Vue escapa por default)
  - [ ] HTTPS obligatorio en producción
  - [ ] Passwords hasheados (bcrypt)
  - [ ] JWT tokens con expiración
  - [ ] Certificados almacenados con permisos restrictivos
- [ ] Auditoría de dependencias
  - [ ] `pip check` para backend
  - [ ] `npm audit` para frontend
  - [ ] Actualizar dependencias vulnerables

### 7.5 Preparación de Release
- [ ] Versionado semántico (1.0.0)
- [ ] Changelog detallado
- [ ] Release notes en español
- [ ] Tag de Git: `v1.0.0`
- [ ] Compilar imágenes Docker
  - [ ] Publicar en Docker Hub (opcional)
- [ ] Crear release en GitHub
  - [ ] Binarios (si aplica)
  - [ ] Assets (logos, screenshots)
  - [ ] Notas de la versión

### 7.6 Demo Online (Opcional)
- [ ] Desplegar en VPS de prueba
  - [ ] DigitalOcean, Linode, o Hetzner
  - [ ] Dominio: demo.factuflow.com (o similar)
- [ ] Configurar HTTPS (Let's Encrypt)
- [ ] Datos de demo precargados
  - [ ] Empresa de prueba
  - [ ] Clientes de ejemplo
  - [ ] Facturas ya emitidas (en homologación)
- [ ] Usuario demo:
  - [ ] username: demo
  - [ ] password: demo2024
- [ ] Banner visible: "MODO DEMO - DATOS DE PRUEBA"
- [ ] Reset automático cada 24hs

---

## Futuras Funcionalidades (Post v1.0)

Ideas para versiones futuras (no prioritarias):

### Multi-Empresa
- [ ] Permitir gestionar múltiples empresas desde una instalación
- [ ] Selector de empresa activa
- [ ] Aislamiento de datos por empresa

### Productos y Stock
- [ ] Catálogo de productos/servicios
- [ ] Códigos de barra
- [ ] Control de stock básico
- [ ] Alertas de stock bajo

### Presupuestos y Remitos
- [ ] Generar presupuestos (no fiscales)
- [ ] Convertir presupuesto a factura
- [ ] Remitos (comprobantes no fiscales)

### Recibos y Cobranzas
- [ ] Registro de pagos
- [ ] Recibos de pago
- [ ] Estado de cuenta por cliente
- [ ] Recordatorios de pago

### Integraciones
- [ ] Mercado Pago (botón de pago en factura)
- [ ] Exportar a contabilidad (formatos estándar)
- [ ] Webhook para notificaciones externas

### Mobile App
- [ ] App nativa o PWA
- [ ] Emitir facturas desde móvil
- [ ] Scanner de código de barras
- [ ] Notificaciones push

### Más Webservices ARCA
- [ ] WSFEX (Factura Exportación)
- [ ] WSMTXCA (Monotributo)
- [ ] Padrón ARCA (validar CUIT)

---

## Criterios de Completitud

Para considerar cada fase completa:
- ✅ Código implementado y funcional
- ✅ Tests escritos y pasando (>80% coverage)
- ✅ Documentación actualizada
- ✅ Sin bugs críticos conocidos
- ✅ Revisado por al menos otro desarrollador (PR)

---

## Contacto y Colaboración

Para colaborar en alguna fase específica:
1. Revisar issues en GitHub etiquetados con la fase
2. Comentar en el issue que querés trabajar
3. Seguir el flujo de CONTRIBUTING.md
4. Abrir PR cuando esté listo

---

**Última actualización**: 2024
**Versión actual**: Fase 0 (en progreso)
**Próxima meta**: Completar Fase 0 y comenzar Fase 1 (Backend Core)

---

*Este roadmap es un documento vivo y puede modificarse según las necesidades del proyecto y feedback de la comunidad.*
