# Certificados ARCA - Guía Completa

Última revisión: 03/10/2026

Todo lo que necesitás saber sobre certificados digitales para facturar con ARCA (Agencia de Recaudación y Control Aduanero).

**Nota importante**: Aunque el organismo cambió su nombre a ARCA, el portal web y algunos sistemas aún pueden mostrar "AFIP" en las URLs y referencias técnicas. Esto es normal y no afecta el funcionamiento.

## ¿Qué es un Certificado Digital?

Un certificado digital es como un **DNI electrónico** para tu empresa. Te permite:
- Identificarte de forma segura ante ARCA
- Autenticar y firmar las solicitudes de acceso a los servicios de ARCA
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

Esta opción es una referencia técnica para trabajar fuera del wizard. La
interfaz actual de FactuFlow requiere una clave administrada por el sistema;
no permite subir una clave privada externa. Para completar el alta desde la
aplicación, usá la opción A.

```bash
# Instalar OpenSSL (si no lo tenés)
# Ubuntu/Debian:
sudo apt install openssl

# macOS:
brew install openssl

# Windows: Descargar desde https://slproweb.com/products/Win32OpenSSL.html

# Generar CSR y clave privada
openssl req -new -newkey rsa:2048 \
  -keyout clave_privada.key \
  -out certificado.csr

# Te pedirá completar:
# - Country Name: AR
# - State: Buenos Aires (o tu provincia)
# - Locality: CABA (o tu ciudad)
# - Organization Name: Tu Razón Social
# - Organizational Unit: Puede dejarse vacío
# - Common Name: Alias del certificado
# - Email: tu-email@ejemplo.com
```

El CSR para ARCA debe incluir además `serialNumber=CUIT <CUIT_TITULAR>`;
el formulario interactivo básico anterior no lo agrega automáticamente.
Consultar el [procedimiento oficial de CSR](https://www.arca.gob.ar/ws/WSASS/html/generarcsr.html)
para configurar ese campo. Conservar la clave cifrada y su contraseña en el
resguardo privado; nunca usar identificadores ajenos como datos de prueba.

**⚠️ IMPORTANTE**: La clave privada (`clave_privada.key`) es **ULTRA SECRETA**. Guardala en un lugar seguro y nunca la compartas.

---

## Paso 2: Obtener Certificado desde ARCA

### Para Homologación (Testing)

1. Ingresar al portal de ARCA con la clave fiscal de una persona física y
   adherir a **WSASS**, si todavía no está habilitado.
2. Abrir WSASS y usar **Nuevo certificado** con el CSR correspondiente al
   titular autenticado.
3. Guardar el certificado emitido en formato PEM.
4. En **Crear autorización a servicio**, autorizar `wsfe` para el CUIT
   representado que se va a operar en homologación.

El [manual oficial de WSASS](https://www.arca.gob.ar/ws/WSASS/html/index.html)
detalla la creación del certificado y la autorización. El CUIT del titular del
certificado puede diferir del emisor representado; ambos deben corresponder a
la relación autorizada.

**Nota**: El portal puede mostrar "AFIP" en algunas referencias, pero el certificado es válido para ARCA.

### Para Producción

**⚠️ SOLO después de probar extensivamente en homologación**

1. Ingresar al portal de ARCA y abrir **Administración de Certificados Digitales**.
2. Crear el alias y cargar el CSR para obtener el certificado.
3. Abrir **Administrador de Relaciones de Clave Fiscal** y asociar el alias
   del computador al servicio `wsfe` para el CUIT representado.

Los portales y las autorizaciones difieren entre ambientes. Consultar la
[guía oficial de WSAA y certificados](https://www.arca.gob.ar/ws/documentacion/wsaa.asp)
antes de configurar una relación.

**Diferencias importantes:**
- La emisión de comprobantes autorizados en producción genera obligaciones
  fiscales reales; crear o verificar un certificado no emite comprobantes
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
   - Subir certificado `.crt`, `.cer` o `.pem` descargado de ARCA
   - FactuFlow usa la clave privada generada y administrada en el paso del CSR;
     no se sube la clave desde el navegador
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

La fecha de vencimiento está contenida en cada certificado. FactuFlow informa
esa fecha y los días restantes; no debe asumirse una duración fija.

### Sistema de Alertas de FactuFlow

FactuFlow muestra el estado y los días restantes al consultar certificados:
- hasta 30 días: advertencia de vencimiento próximo;
- hasta 7 días: alerta de mayor urgencia;
- vencido: el certificado no permite emitir.

Estas señales forman parte de la aplicación; no implican un envío de correo ni
una notificación externa programada.

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
   - Generar o seleccionar la clave administrada y subir el nuevo certificado
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
productivos activos pueden migrarse con la
[guía técnica de migración](../setup/vps-migration.md). La configuración y
evidencia de la instalación se conservan en su plano de control privado.

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
- Formato incorrecto (debe ser .crt, .cer o .pem)

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

### Generar Certificados de Test

Usar WSASS y un titular autorizado, con autorización explícita al CUIT
representado. No se ofrece un CUIT compartido de libre uso. Configurar
FactuFlow con `ARCA_ENV=homologacion`; los certificados de ese entorno no
permiten emitir comprobantes productivos.

---

## Múltiples Certificados

Podés tener múltiples certificados en FactuFlow:
- Uno para homologación, otro para producción
- Diferentes CUITs (si gestionás múltiples empresas)

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
Si creés que está comprometido, suspender su uso y seguir el procedimiento del
portal oficial del ambiente correspondiente. Revocar un certificado y quitar
su autorización a un servicio son operaciones distintas; consultar la
[documentación de certificados](https://www.arca.gob.ar/ws/documentacion/certificados.asp).

**¿Los certificados tienen costo?**
No, ARCA los emite gratuitamente.

**¿Necesito certificado para cada punto de venta?**
No, un certificado sirve para todos los puntos de venta de un CUIT.
