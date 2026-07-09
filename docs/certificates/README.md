# Certificados ARCA - Guía Completa

Todo lo que necesitás saber sobre certificados digitales para facturar con ARCA (Agencia de Recaudación y Control Aduanero).

**Nota importante**: Aunque el organismo cambió su nombre a ARCA, el portal web y algunos sistemas aún pueden mostrar "AFIP" en las URLs y referencias técnicas. Esto es normal y no afecta el funcionamiento.

## ¿Qué es un Certificado Digital?

Un certificado digital es como un **DNI electrónico** para tu empresa. Te permite:
- Identificarte de forma segura ante ARCA
- Firmar digitalmente tus comprobantes
- Comunicarte con los webservices de ARCA

**Nota técnica**: Los webservices de ARCA mantienen las URLs con "afip.gov.ar" por compatibilidad técnica (ej: wsaa.afip.gov.ar). Esto es normal.

### Componentes del Certificado

1. **Certificado (.crt)**: La parte pública, identifica a tu empresa
2. **Clave Privada (.key)**: La parte privada, **NUNCA compartir**
3. **CSR**: Solicitud de certificado que enviás a ARCA

---

## Paso 1: Generar CSR (Certificate Signing Request)

### Opción A: Desde FactuFlow

En el wizard de certificados de FactuFlow:
1. Ir a `Certificados` y elegir `Nuevo certificado`.
2. Confirmar emisor activo, ambiente, CUIT y nombre del certificado.
3. Presionar `Generar CSR`.
4. Descargar el CSR para cargarlo en el portal de ARCA.
5. Conservar la clave privada generada por FactuFlow. El sistema la guarda en la carpeta configurada de certificados y la necesitará para validar el `.crt` que devuelva ARCA.

Si ya generaste un CSR desde este sistema, el wizard permite continuar sin volver a crearlo y seleccionar la clave privada existente para ese CUIT y ambiente.

### Opción B: Manualmente con OpenSSL

```bash
# Instalar OpenSSL (si no lo tenés)
# Ubuntu/Debian:
sudo apt install openssl

# macOS:
brew install openssl

# Windows: Descargar desde https://slproweb.com/products/Win32OpenSSL.html

# Generar CSR y clave privada
openssl req -new -newkey rsa:2048 -nodes \
  -keyout clave_privada.key \
  -out certificado.csr

# Te pedirá completar:
# - Country Name: AR
# - State: Buenos Aires (o tu provincia)
# - Locality: CABA (o tu ciudad)
# - Organization Name: Tu Razón Social
# - Organizational Unit: Puede dejarse vacío
# - Common Name: Tu CUIT (ej: 20123456789)
# - Email: tu-email@ejemplo.com
```

**⚠️ IMPORTANTE**: La clave privada (`clave_privada.key`) es **ULTRA SECRETA**. Guardala en un lugar seguro y nunca la compartas.

---

## Paso 2: Obtener Certificado desde ARCA

### Para Homologación (Testing)

1. **Ingresar a ARCA con Clave Fiscal**
   - URL: https://auth.afip.gov.ar/contribuyente_/login.xhtml (portal heredado)
   - Usar tu CUIT y Clave Fiscal nivel 3 o superior

2. **Ir a Administrador de Relaciones**
   - Menú: "Administrador de Relaciones de Clave Fiscal"
   - O buscar "Certificados Digitales"

3. **Crear Nueva Relación**
   - Clic en "Nueva Relación"
   - Seleccionar: "Certificado Digital"

4. **Seleccionar Servicio**
   - Servicio: **wsfe** (Web Service de Factura Electrónica)
   - Ambiente: **Homologación**

5. **Cargar CSR**
   - Copiar el contenido del archivo `.csr`
   - Pegarlo en el campo de texto
   - Clic en "Crear"

6. **Descargar Certificado**
   - Se generará inmediatamente
   - Clic en "Descargar"
   - Guardar como `certificado_homologacion.crt`

**Nota**: El portal puede mostrar "AFIP" en algunas referencias, pero el certificado es válido para ARCA.

### Para Producción

**⚠️ SOLO después de probar extensivamente en homologación**

Los pasos son idénticos, pero seleccionando **Producción** en lugar de Homologación.

**Diferencias importantes:**
- Certificados de producción generan obligaciones fiscales REALES
- No se pueden usar certificados de homologación en producción ni viceversa
- Cada ambiente requiere su propio certificado

---

## Paso 3: Subir Certificado a FactuFlow

### Desde la Interfaz Web

1. **Ir a "Certificados"** en el menú de FactuFlow

2. **Clic en "Nuevo Certificado"**

3. **Completar wizard:**

   **Paso 1: Seleccionar Ambiente**
   - ○ Homologación (para pruebas)
   - ○ Producción (para facturación real)

   **Paso 2: Subir Archivos**
   - Subir certificado `.crt` descargado de ARCA
   - Subir clave privada `.key` generada en Paso 1
   - El archivo de certificado debe ser pequeño; si supera
     `CERTIFICATE_MAX_UPLOAD_BYTES`, FactuFlow lo rechaza antes de guardarlo

   **Paso 3: Verificar Datos**
   - FactuFlow extraerá automáticamente:
     - CUIT
     - Fecha de vencimiento
     - Días restantes
   - Confirmar que son correctos

   **Paso 4: Alias (opcional)**
   - Ej: "Certificado Producción 2024"

   **Paso 5: Prueba de conexión**
   - FactuFlow probará la conexión con ARCA
   - ✅ Si es exitoso, el certificado está listo
   - ❌ Si hay error, revisar:
     - ¿El certificado corresponde a la clave privada?
     - ¿El ambiente es correcto?
     - ¿El certificado no está vencido?

**Nota técnica**: La conexión usa los webservices heredados con URLs "afip.gov.ar". Esto es esperado y correcto.

---

## Vencimiento y Renovación

### ¿Cuándo vencen los certificados?

Los certificados de ARCA tienen validez de **1 o 2 años** (según configuración).

### Sistema de Alertas de FactuFlow

FactuFlow te alertará automáticamente:
- 🟡 **30 días antes**: "Tu certificado vence en X días"
- 🟠 **15 días antes**: "Renová tu certificado pronto"
- 🔴 **7 días antes**: "URGENTE: Renová tu certificado"
- ⛔ **Vencido**: "No podés facturar con certificado vencido"

### Renovar Certificado

1. **Generar nuevo CSR** (repetir Paso 1)
   - Podés usar los mismos datos
   - Se generará nueva clave privada

2. **Solicitar nuevo certificado en ARCA** (repetir Paso 2)
   - El proceso es idéntico
   - ARCA te dará un nuevo certificado

3. **Reemplazar en FactuFlow**
   - Ir a "Certificados"
   - Clic en "Renovar" en el certificado actual
   - Subir nuevo certificado y clave
   - FactuFlow mantendrá historial del antiguo

**⚠️ IMPORTANTE**: Renovar ANTES del vencimiento. Si el certificado vence, no podrás facturar hasta renovarlo.

---

## Seguridad de Certificados

### ✅ Buenas Prácticas

- **Guardar clave privada en lugar seguro**
  - Disco externo encriptado
  - Gestor de contraseñas
  - Nunca en email o nube sin encriptar

- **Backups**
  - Tener copia de respaldo de certificado y clave
  - En caso de pérdida, podés revocar y generar nuevo

- **Permisos restrictivos**
  - En Linux/Mac: `chmod 400 clave_privada.key`
  - Solo el usuario dueño puede leer

- **Nunca commitear a Git**
  - FactuFlow tiene `.gitignore` configurado
  - Verificar igual antes de cualquier commit

### ❌ Qué NO hacer

- ❌ Compartir la clave privada por email, WhatsApp, etc.
- ❌ Subirla a repositorios públicos (GitHub, GitLab)
- ❌ Dejarla en carpetas compartidas sin encriptar
- ❌ Usar el mismo certificado en múltiples instalaciones de FactuFlow

## Migración a VPS

Cuando el VPS va a reemplazar la instalación local operativa, los certificados
productivos activos pueden migrarse con el runbook privado
`docs/setup/vps-migration.md`.

Condiciones:

- Todos los certificados activos deben tener `.crt` y `.key` resolubles dentro
  de `CERTS_PATH`; si falta alguno, el preflight bloquea la exportación.
- Las claves privadas exportadas se re-cifran con una contraseña nueva para
  producción.
- El `.env.production` destino debe usar esa misma contraseña en
  `ARCA_PRIVATE_KEY_PASSWORD`.
- La SQLite local queda como histórico privado y no debe seguir operando en
  paralelo con el VPS usando los mismos certificados.

Si se necesita operar dos instalaciones al mismo tiempo, generar certificados
separados para reducir el riesgo de exposición o uso cruzado.

---

## Troubleshooting

### Error: "Certificado inválido"

**Posibles causas:**
- El archivo no es un certificado válido
- Está corrupto o incompleto
- Formato incorrecto (debe ser .crt o .pem)

**Solución:**
- Descargar nuevamente desde ARCA
- Verificar que se copió completo (debe empezar con `-----BEGIN CERTIFICATE-----`)

### Error: "La clave privada no corresponde al certificado"

**Causa:**
- El .key y el .crt no fueron generados juntos

**Solución:**
- Asegurarse de usar la clave que se generó en el mismo CSR
- Si la perdiste, generar nuevo CSR y obtener nuevo certificado

### Error: "Certificado vencido"

**Solución:**
- Generar nuevo certificado (ver sección Renovación)

### Error al conectar con ARCA

**Posibles causas:**
- Sin conexión a internet
- ARCA en mantenimiento
- Certificado de ambiente incorrecto (homologación vs producción)

**Solución:**
- Verificar conexión
- Intentar más tarde
- Verificar que el ambiente sea correcto

---

## Certificados para Testing

### CUIT de Prueba

Para homologación, podés usar el CUIT de prueba de ARCA:
- **CUIT**: 20409378472
- Disponible para todos
- Solo válido en ambiente de homologación

### Generar Certificados de Test

El proceso es idéntico, pero:
1. Usar el CUIT de prueba (o tu CUIT en homologación)
2. Seleccionar ambiente "Homologación" en ARCA
3. Usar en FactuFlow con `ARCA_ENV=homologacion`

---

## Múltiples Certificados

Podés tener múltiples certificados en FactuFlow:
- Uno para homologación, otro para producción
- Diferentes CUITs (si gestiónás múltiples empresas)

FactuFlow seleccionará automáticamente el certificado correcto según:
- El CUIT de la empresa
- El ambiente configurado (homologación/producción)

---

## Soporte

¿Problemas con certificados?
- 📖 Consultar [FAQ](#faq)
- 💬 [GitHub Discussions](https://github.com/Santi-RL/FactuFlow/discussions)
- 🐛 [Reportar Issue](https://github.com/Santi-RL/FactuFlow/issues)

---

## FAQ

**¿Puedo usar el mismo certificado en múltiples computadoras?**
Técnicamente sí, pero NO es recomendable por seguridad. Si necesitás usar FactuFlow en múltiples lugares, considerá generar certificados separados.

**¿Qué pasa si pierdo la clave privada?**
Tendrás que generar un nuevo CSR y obtener un nuevo certificado. Los comprobantes anteriores siguen siendo válidos.

**¿Puedo revocar un certificado?**
Sí, desde ARCA → Administrador de Relaciones → Certificados → Revocar. Útil si creés que está comprometido.

**¿Los certificados tienen costo?**
No, ARCA los emite gratuitamente.

**¿Necesito certificado para cada punto de venta?**
No, un certificado sirve para todos los puntos de venta de un CUIT.
