# Wizard de Certificados ARCA

## 📋 Descripción

El Wizard de Certificados ARCA es una funcionalidad completa que guía al usuario paso a paso en la configuración de certificados digitales necesarios para emitir facturas electrónicas ante ARCA.

## ✨ Características Implementadas

### Backend

#### Servicio de Certificados (`app/services/certificados_service.py`)
- ✅ Generación de clave privada RSA 2048 bits
- ✅ Generación de CSR (Certificate Signing Request) con datos ARCA
- ✅ Validación de certificados contra clave privada
- ✅ Extracción de información del certificado (fechas, CUIT, etc.)
- ✅ Cálculo de estado de certificados (válido, por vencer, vencido)
- ✅ Gestión de alertas de vencimiento
- ✅ Almacenamiento seguro con permisos restrictivos (chmod 400)

#### API Endpoints (`app/api/certificados.py`)

1. **POST `/api/certificados/generar-csr`**
   - Genera clave privada y CSR
   - Guarda la clave de forma segura en el servidor
   - Devuelve CSR para subir al portal de ARCA
   - Válida formato de CUIT (11 dígitos)

2. **POST `/api/certificados/subir-certificado`**
   - Upload multipart/form-data
   - Válida formato del certificado (.crt, .cer, .pem)
   - Verifica coincidencia con clave privada
   - Válida que el CUIT coincida
   - Verifica que no esté vencido
   - Crea registro en BD con metadata

3. **POST `/api/certificados/verificar-conexion/{id}`**
   - Prueba conexión con WSAA de ARCA
   - Válida que el certificado funcione
   - Devuelve estado de servidores ARCA

4. **GET `/api/certificados/alertas-vencimiento`**
   - Lista certificados próximos a vencer (≤30 días)
   - Calcula tipo de alerta (info/warning/danger)
   - Ordenados por urgencia

5. **GET `/api/certificados`**
   - Lista todos los certificados del usuario
   - Incluye campos calculados (dias_restantes, estado)

6. **GET `/api/certificados/{id}`**
   - Obtiene detalles de un certificado específico

7. **DELETE `/api/certificados/{id}`**
   - Elimina un certificado

#### Schemas (`app/schemas/certificado.py`)
- ✅ `GenerarCSRRequest` - Request para generar CSR
- ✅ `GenerarCSRResponse` - Response con CSR y nombre de archivo
- ✅ `VerificacionResponse` - Response de verificación de conexión
- ✅ `CertificadoAlerta` - Schema para alertas de vencimiento
- ✅ `CertificadoResponse` - Response con campos calculados (computed_field)

### Frontend

#### Componentes del Wizard

1. **`WizardProgress.vue`**
   - Barra de progreso visual con 5 pasos
   - Indicadores de estado (completado/actual/pendiente)
   - Responsive (muestra títulos cortos en móvil)

2. **`WizardStep1Intro.vue`**
   - Introducción amigable al proceso
   - Lista de requisitos
   - Tiempo estimado (10-15 minutos)
   - Diseño atractivo con emojis

3. **`WizardStep2GenerarCSR.vue`**
   - Formulario con validación
   - Input de CUIT con formato automático (XX-XXXXXXXX-X)
   - Selector de ambiente (Homologación/Producción)
   - Generación automática en servidor
   - Descarga automática del CSR
   - Alertas de seguridad sobre la clave privada

4. **`WizardStep3PortalArca.vue`**
   - Instrucciones paso a paso para el portal de ARCA
   - Botón para abrir portal en nueva pestaña
   - Checkbox de confirmación
   - Guía visual numerada

5. **`WizardStep4SubirCert.vue`**
   - Drag & drop para subir certificado
   - Validación de formato (.crt, .cer, .pem)
   - Preview de información del certificado
   - Manejo de errores descriptivos
   - Loading state durante validación

6. **`WizardStep5Verificar.vue`**
   - Test de conexión con ARCA
   - Estado de servidores
   - Manejo de éxito/error
   - Sugerencias de solución de problemas
   - Opción de reintentar

#### Componentes Auxiliares

1. **`CertificadoCard.vue`**
   - Card visual para mostrar certificado
   - Barra de progreso de validez
   - Badge de estado
   - Formateo de CUIT y fechas
   - Botones de acción (renovar/eliminar)

2. **`CertificadoEstado.vue`**
   - Badge de estado con colores
   - Estados: válido (verde), por vencer (amarillo), vencido (rojo)
   - Iconos visuales

#### Vistas Principales

1. **`CertificadosListView.vue`**
   - Listado de certificados en grid
   - Estado vacío atractivo
   - Alertas de certificados por vencer
   - Botón para agregar certificado
   - Confirmación de eliminación

2. **`CertificadoWizardView.vue`**
   - Orquestador del flujo completo
   - Manejo de estado entre pasos
   - Navegación adelante/atrás
   - Preservación de datos entre pasos

3. **`CertificadoExitoView.vue`**
   - Página de éxito con celebración
   - Resumen del certificado configurado
   - Acciones rápidas (Dashboard/Certificados)

#### Servicio API

**`certificados.service.ts`**
- ✅ Método `listar()` - Lista certificados
- ✅ Método `obtener(id)` - Obtiene un certificado
- ✅ Método `eliminar(id)` - Elimina certificado
- ✅ Método `generarCSR(data)` - Genera CSR
- ✅ Método `subirCertificado(file, ...)` - Upload certificado
- ✅ Método `verificarConexion(id)` - Verifica conexión
- ✅ Método `obtenerAlertasVencimiento()` - Obtiene alertas
- ✅ Método `descargarCSR(csr, cuit)` - Descarga CSR como archivo

#### Tipos TypeScript

**`certificado.ts`**
- ✅ Tipos completos para todos los schemas
- ✅ Union types para enums (AmbienteCertificado, EstadoCertificado, etc.)
- ✅ Interfaces para requests y responses

#### Integración

1. **Router (`router/index.ts`)**
   - `/certificados` - Listado
   - `/certificados/nuevo` - Wizard
   - `/certificados/:id/renovar` - Renovar certificado
   - `/certificados/:id/exito` - Página de éxito

2. **Sidebar (`Sidebar.vue`)**
   - Ítem "Certificados" con icono de llave (KeyIcon)
   - Badge rojo con número de certificados por vencer
   - Recarga automática cada 5 minutos

3. **Dashboard (`DashboardView.vue`)**
   - Alerta destacada de certificados por vencer
   - Muestra hasta 2 certificados con detalles
   - Botón directo a página de certificados

## 🎨 Diseño y UX

### Principios de Diseño

1. **User-Friendly**: Diseñado para usuarios no técnicos
2. **Guiado**: Wizard paso a paso sin posibilidad de confusión
3. **Visual**: Uso de emojis, colores e iconos para mejorar comprensión
4. **Feedback Claro**: Mensajes descriptivos de error/éxito en español
5. **Responsive**: Funciona en desktop y móvil

### Paleta de Colores

- **Válido**: Verde (bg-green-100, text-green-800)
- **Por Vencer**: Amarillo (bg-yellow-100, text-yellow-800)
- **Vencido**: Rojo (bg-red-100, text-red-800)
- **Info**: Azul (bg-blue-50, border-blue-500)
- **Primario**: Azul (bg-blue-600)

### Textos en Español

- ✅ Todos los textos de UI en español argentino
- ✅ Mensajes de error amigables y descriptivos
- ✅ Instrucciones claras paso a paso
- ✅ Uso de vocabulario local (CUIT, ARCA, facturación)

## 📁 Estructura de Archivos

```
backend/
├── app/
│   ├── api/
│   │   └── certificados.py          # Endpoints
│   ├── models/
│   │   └── certificado.py           # Modelo existente
│   ├── schemas/
│   │   └── certificado.py           # Schemas extendidos
│   └── services/
│       └── certificados_service.py  # Servicio nuevo
└── tests/
    └── test_certificados.py         # Tests

frontend/
├── src/
│   ├── components/
│   │   ├── certificados/
│   │   │   ├── CertificadoCard.vue
│   │   │   ├── CertificadoEstado.vue
│   │   │   ├── WizardProgress.vue
│   │   │   ├── WizardStep1Intro.vue
│   │   │   ├── WizardStep2GenerarCSR.vue
│   │   │   ├── WizardStep3PortalArca.vue
│   │   │   ├── WizardStep4SubirCert.vue
│   │   │   └── WizardStep5Verificar.vue
│   │   └── layout/
│   │       └── Sidebar.vue          # Actualizado
│   ├── services/
│   │   └── certificados.service.ts  # Servicio API
│   ├── types/
│   │   └── certificado.ts           # Tipos
│   ├── views/
│   │   ├── certificados/
│   │   │   ├── CertificadosListView.vue
│   │   │   ├── CertificadoWizardView.vue
│   │   │   └── CertificadoExitoView.vue
│   │   └── dashboard/
│   │       └── DashboardView.vue    # Actualizado
│   └── router/
│       └── index.ts                 # Rutas agregadas
```

## 🔒 Seguridad

### Medidas Implementadas

1. **Almacenamiento de Claves**
   - Permisos restrictivos (chmod 400)
   - Solo lectura para el propietario
   - Ubicación configurable vía `settings.certs_path`

2. **Validaciones**
   - Formato de CUIT (11 dígitos)
   - Formato de certificado (.crt, .cer, .pem)
   - Coincidencia certificado-clave privada
   - Verificación de fechas de validez
   - CUIT del certificado coincide con el solicitado

3. **Autenticación**
   - Todos los endpoints requieren autenticación
   - Usuarios solo ven sus propios certificados
   - Admins pueden ver todos

4. **Sanitización**
   - Paths absolutos manejados de forma segura
   - Validación de tipos con Pydantic
   - Manejo de errores sin exponer información sensible

## 🚀 Uso

### Flujo del Usuario

1. **Inicio**: Usuario hace clic en "Certificados" en sidebar
2. **Listado**: Ve estado vacío o certificados existentes
3. **Wizard**: Hace clic en "+ Agregar certificado"
4. **Paso 1**: Lee introducción y requisitos
5. **Paso 2**: Completa formulario y genera CSR
6. **Paso 3**: Sigue instrucciones para portal ARCA
7. **Paso 4**: Sube certificado descargado de ARCA
8. **Paso 5**: Autoriza el servicio `WSFE` en ARCA para ese certificado
9. **Paso 6**: Verifica conexión con ARCA
10. **Éxito**: Ve página de cierre

### Alertas de Vencimiento

- Dashboard muestra alerta si hay certificados ≤30 días
- Sidebar muestra badge rojo con cantidad
- Certificados por vencer tienen barra amarilla/roja

## 🧪 Testing

### Tests Backend

- ✅ Test de listado vacío
- ✅ Test de generación de CSR
- ✅ Test de validación de CUIT inválido
- ✅ Test de ambiente inválido
- ✅ Test de alertas vacías
- ✅ Test de verificación con certificado inexistente
- ✅ Test de métodos del servicio (calcular_estado, get_tipo_alerta)

### Tests Manuales Recomendados

1. **Flujo completo del wizard**
   - Generar CSR
   - Subir certificado válido
   - Verificar conexión

2. **Validaciones**
   - CUIT inválido
   - Certificado inválido
   - Certificado que no coincide con clave

3. **Responsive**
   - Probar en móvil
   - Probar en tablet
   - Probar en desktop

4. **Alertas**
   - Crear certificado próximo a vencer
   - Verificar alerta en dashboard
   - Verificar badge en sidebar

## 📝 Notas Técnicas

### Dependencias Backend

- `cryptography`: Manejo de certificados X.509
- `FastAPI`: Framework web
- `Pydantic`: Validación de datos
- `SQLAlchemy`: ORM

### Dependencias Frontend

- `Vue 3`: Framework reactivo
- `TypeScript`: Tipado estático
- `Tailwind CSS`: Estilos
- `@heroicons/vue`: Iconos
- `axios`: Cliente HTTP

### Variables de Entorno

```bash
# Backend
CERTS_PATH=./certs                    # Path de certificados
AFIP_CERTS_PATH=./certs              # Alias compatible
ARCA_ENV=homologacion                # Ambiente ARCA
```

## 🐛 Solución de Problemas

### Error: "Clave privada no encontrada"

- Asegurarse de generar CSR primero
- Verificar que key_filename sea correcto
- Verificar permisos de directorio certs/

### Error: "Certificado no coincide con clave privada"

- Verificar que el certificado descargado sea del CSR correcto
- Generar nuevo CSR si es necesario

### Error: "No se pudo conectar con ARCA"

- Verificar conectividad a internet
- Verificar que el servicio esté autorizado en ARCA
- Intentar nuevamente más tarde (puede ser problema temporal de ARCA)

## 🎯 Próximos Pasos

- [ ] Screenshots de la UI
- [ ] Video demo del wizard completo
- [ ] Ampliar E2E con Playwright cuando el flujo de certificados necesite cobertura navegada completa
- [x] Documentación de usuario final en `docs/user-guide/README.md` y `docs/certificates/README.md`
- [ ] Guía detallada del portal ARCA con capturas sanitizadas, sin CUIT ni datos privados
- [ ] Soporte para renovación automática
- [ ] Notificaciones por email de vencimiento

## 📚 Referencias

- [ARCA - Web Services](https://www.afip.gob.ar/ws/)
- [WSAA Especificaciones](https://www.afip.gob.ar/ws/WSAA/Especificacion_Tecnica_WSAA_1.2.0.pdf)
- [Certificados ARCA](https://www.afip.gob.ar/ws/documentación/certificados.asp)
