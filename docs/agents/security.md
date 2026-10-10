# Seguridad y certificados

## Archivos sensibles
- No commitear `.key`, `.crt`, `.pem`, `.p12`, `.pfx`.
- Los certificados van en `certs/` y la DB local en `data/` (gitignored).
- No commitear CUITs reales, nombres de clientes o emisores reales,
  credenciales, tokens, CAEs reales, capturas privadas, PDFs, Excel de clientes,
  bases locales, logs de producción ni evidencia de debug local.
- La documentación versionada debe usar datos sintéticos o redactados. La
  evidencia operativa privada queda fuera del repo, por ejemplo en `.tmp/`,
  `private/`, `evidence/`, `factuflow-documentacion-base/`, `output/`,
  `data/`, `backend/data/` o `certs/`.
- Si un dato real es necesario para retomar una operación, referenciarlo como
  "evidencia local privada" y no copiar el valor al archivo versionado.
- El JSON del inventario PF-19A está sanitizado, pero sigue siendo evidencia
  privada: conserva IDs operativos, punto de venta y tipo de comprobante. Debe
  guardarse únicamente en una ruta ignorada; nunca en el repositorio, tickets o
  evidencia pública.

## Almacenamiento recomendado

El resumen PF-11/PF-15 es una proyección privada producida por el responsable de
instalación y validada antes de su publicación atómica. Restringir permisos y
montar sólo el resumen con lectura para el runtime; nunca el almacén de backups.
La aplicación valida estructura/vínculos, no los archivos de prueba originales.
No confundir una proyección declarada con procedencia autenticada de un paquete
de importación. Formato en [evidencia de recuperación](../setup/recovery-evidence.md).
- Guardar en el filesystem el certificado y la clave.
- Crear claves privadas nuevas con permisos restrictivos desde la apertura del
  archivo y cifrarlas antes de persistirlas.
- Persistir en DB solo metadatos del certificado.
- No asumir que un registro activo implica material utilizable: comprobar `.crt`
  y `.key` como archivos dentro de `CERTS_PATH` antes de habilitar ARCA.
- Registrar rutas faltantes solo en logs privados; las respuestas HTTP deben
  usar mensajes genéricos sin revelar rutas internas.
- Mantener separados:
  - proyecto público: código, migraciones, tests con fixtures sintéticos,
    documentación general y ejemplos sin datos reales
  - entorno privado: `.env*`, bases SQLite/PostgreSQL locales, certificados,
    constancias ARCA reales, archivos Excel/PDF de clientes, screenshots,
    trazas Playwright, logs, auditorías locales, planes privados de cambio y
    scripts exploratorios de debug

## Dependencias y cadena de construcción

### Propuestas de Dependabot

La configuración versionada vive en
[`.github/dependabot.yml`](../../.github/dependabot.yml) y se aplica desde la
rama predeterminada del repositorio. Revisa npm en `frontend/`, los archivos
requirements de ejecución y desarrollo en `backend/` y las referencias de GitHub Actions.
Las actualizaciones ordinarias se programan los lunes a las 09:00 en
`America/Argentina/Buenos_Aires`, con límites de tres PRs npm, tres Python y dos
de Actions. Esos límites y la revisión semanal no limitan las propuestas de
seguridad.

- Vitest y su proveedor de cobertura avanzan juntos, incluidas actualizaciones
  mayores y de seguridad, por su compatibilidad de versiones.
- ESLint, pytest y Actions agrupan únicamente cambios menores y parches;
  las demás actualizaciones se revisan en PRs individuales. No se ignoran
  versiones mayores ni dependencias fiscales, criptográficas, de PDF o persistencia.
- Alertas y actualizaciones automáticas de seguridad son ajustes de GitHub,
  independientes del archivo de revisiones ordinarias. Comprobarlos en la
  configuración de seguridad del repositorio; la ausencia de un PR no demuestra
  que no existan vulnerabilidades ni que haya una corrección disponible.
- Dependabot propone cambios: no fusiona ni despliega. Cada PR conserva las
  puertas de CI y la revisión proporcional al riesgo. Un salto mayor puede
  requerir adaptar código, configuración y compatibilidad; no aprobarlo sólo
  porque se generó automáticamente.
- Las imágenes Docker quedan fuera de esta configuración inicial. Node, Python
  y PostgreSQL requieren coordinar contratos de versiones y validar las imágenes
  correspondientes; el bot no sustituye esa comprobación.

Referencia: [opciones oficiales de Dependabot](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference).

### Auditorías y construcción

- El frontend usa Tailwind 4 y conserva el contrato de navegadores y foco de
  [`frontend/README.md`](../../frontend/README.md#navegadores-compatibles).
  Las futuras actualizaciones deben validar ese contrato; la auditoría no
  sustituye comprobaciones visuales ni de accesibilidad.
- La CI bloquea vulnerabilidades conocidas en dependencias de Python y del
  frontend mediante `pip-audit -r requirements-dev.txt` y
  `npm audit --audit-level=low`, incluidas las herramientas de desarrollo.
  El manifiesto Python incluye `requirements.txt`, por lo que cubre ambos
  conjuntos. Dependabot también revisa ambos; confirmar el estado de sus alertas
  después de integrar una corrección, sin descartarlas manualmente.
- Los lockfiles son parte del comportamiento reproducible: cualquier cambio en
  ellos activa la matriz completa, aunque no cambie código de aplicación.
- Las alertas de herramientas exclusivas de desarrollo deben revisarse y quedar
  documentadas. Si su corrección exige migraciones mayores incompatibles, se
  planifican como una unidad técnica separada, sin usar `npm audit fix --force`
  ni debilitar las auditorías productivas.
- El servidor de desarrollo, el modo UI de tests y las herramientas de build no
  deben exponerse en producción ni en redes no confiables.
- Los hashes bcrypt existentes conservan prefijo, costo 12 y codificación UTF-8.
  La integración directa con bcrypt mantiene los límites históricos (4096
  caracteres de entrada y 72 bytes efectivos) y el rechazo de caracteres nulos.

## Migración local a VPS

- El runbook vigente está en `docs/setup/vps-migration.md`.
- Los paquetes de migración generados en `.tmp/vps-migration/<timestamp>/` son
  privados: contienen datos operativos, comprobantes, metadatos de certificados
  y claves privadas re-cifradas. No se commitean ni se comparten en tickets,
  chats o evidencia pública.
- `preflight` debe bloquear si un certificado activo no tiene `.crt` y `.key`
  resolubles dentro de `CERTS_PATH`. No se exportan certificados incompletos ni
  rutas fuera de la carpeta gestionada.
- `export` re-cifra las claves privadas activas con
  `ARCA_MIGRATION_TARGET_KEY_PASSWORD`. Esa contraseña debe coincidir luego con
  `ARCA_PRIVATE_KEY_PASSWORD` en el `.env.production` destino.
- `import` solo debe ejecutarse sobre PostgreSQL limpio, ya migrado con Alembic
  al head del paquete. No debe borrar ni mezclar datos operativos existentes.
- La instalación local y el VPS no deben operar simultáneamente con los mismos
  certificados productivos. Si el VPS reemplaza al entorno local, la SQLite
  queda como histórico privado; si ambos van a operar, generar certificados
  separados.
- La preparación y el ensayo de migración no solicitan CAE ni emiten
  comprobantes. Cualquier validación contra ARCA posterior debe limitarse a
  consultas seguras y explícitas.

## Aislamiento por emisor

- FactuFlow usa un modelo multiemisor con un emisor activo explícito por vez,
  orientado a contadores independientes y estudios chicos.
- Clientes, certificados, puntos de venta, comprobantes, lotes, PDFs, reportes,
  perfiles de carga masiva y formatos de importación deben quedar siempre
  scopiados al emisor activo.
- Ningún flujo debe reutilizar silenciosamente datos de otro emisor. Ante duda,
  bloquear la operación y pedir una selección o validación explícita.
- Los cambios que toquen emisión, lotes, certificados, puntos de venta,
  clientes, reportes o PDFs deben considerar pruebas de regresión multiemisor.

## Administración de emisores

- Los administradores operan todos los emisores. Los operadores solo pueden
  consultar y operar los incluidos en `usuario_emisor_acceso`; el campo legacy
  `usuarios.empresa_id`, el JWT, Pinia y el almacenamiento web nunca conceden
  autoridad.
- Un operador con `puede_crear_editar_emisores=true` puede crear un emisor y
  recibe su asignación en la misma transacción. Para editar necesita además una
  asignación vigente. El borrado, los usuarios, `Sistema`, almacenamiento y las
  plantillas globales permanecen reservados a administradores.
- La creación sin autenticación existe únicamente para el bootstrap, cuando no
  hay usuarios. Ocultar controles en frontend no reemplaza la autorización del
  backend.
- La edición de identidad fiscal sigue bloqueada cuando existe historial
  operativo o fiscal, incluso para administradores.
- Una revocación se aplica desde el siguiente control backend. Las solicitudes
  individuales ya aceptadas y los lotes ya confirmados o encolados pueden
  terminar; no habilita nuevas cargas, confirmaciones, reintentos,
  reconciliaciones ni consultas sin acceso vigente.
- El contrato completo, concurrencia, rollback y matriz de pruebas están en
  `docs/agents/pf-06-08-permisos-multiemisor-design.md`.

## Errores HTTP y logs

- Los errores inesperados de emisión deben registrar el detalle y el traceback
  en logs privados, pero responder por HTTP con un mensaje genérico.
- Nunca devolver por API textos de excepción que puedan contener credenciales,
  URLs de base de datos, rutas de certificados, claves o detalles internos.
- Un error inesperado no habilita un reintento automático: primero se revisan
  logs, intento fiscal e idempotencia para determinar si ARCA pudo haber
  autorizado el comprobante.
- Los logs privados pueden conservar identificadores operativos mínimos para
  correlación. Nunca deben registrar secretos, credenciales, material de
  certificados, payloads fiscales, receptores, importes ni mensajes crudos del
  inventario.

## Cambios fiscales críticos

- Antes de modificar emisión fiscal, ARCA/WSFE, CAE, numeración, fechas
  fiscales, comprobantes, notas de crédito/débito, reintentos, reconciliación,
  certificados, puntos de venta, migraciones fiscales o confirmaciones
  irreversibles, completar `docs/agents/fiscal-change-checklist.md`.
- El diseño debe identificar invariantes, estados, fallos intermedios,
  concurrencia, constraints, reconciliación y matriz de tests antes del código.
- Si se usa `autoreview`, la única configuración de cierre es Codex
  `gpt-5.6-sol medium`, indicada explícitamente así:
  `--engine codex --model gpt-5.6-sol --thinking medium`. No aplicar hallazgos
  automáticamente, cambiar manualmente de modelo/esfuerzo ni ejecutar revisiones
  incrementales o redundantes. Si un
  hallazgo aceptado cambia código, repetir las pruebas y la misma revisión.

## Checklist antes de commit

El login limita intentos con presupuestos por cuenta, origen y proceso antes
de bcrypt, y respuestas `429` con espera temporal. El runtime de un proceso y
la confianza de proxies delimitan esta protección; contrato y límites en
[SC-08](sc-08-login-recuperacion-design.md).
Para recuperar una contraseña sin modificar permisos, usar el restablecimiento
administrativo o `app.scripts.reset_user_password` desde la consola autorizada
de la instalación. `create_admin_user` es un alta/promoción con otros efectos.
La recuperación de credenciales no requiere restaurar ni borrar datos.

Los tokens nuevos de login se vinculan mediante una versión opaca a la
credencial verificada. Ambos controles de autenticación rechazan versiones
distintas de la vigente, además de la revocación temporal. La compatibilidad de
sesiones anteriores y los límites del cierre están en
[SC-11](sc-11-login-reset-design.md). No registrar contraseñas, hashes ni tokens
en logs o evidencia pública.

Ejecutar una revisión mínima:

```bash
git status --short --untracked-files=all
git diff --cached --name-only
git grep -n -E "[0-9]{11}|password|secret|token|CAE|BEGIN (RSA |EC |)PRIVATE KEY"
```

Si el cambio incluye evidencia local o datos reales, moverla a una carpeta
ignorada y dejar solo una descripción redactada en la documentación.

## Variables de entorno relevantes
- `APP_SECRET_KEY`: en producción debe ser una clave larga generada con
  `secrets.token_urlsafe(32)`; el backend rechaza valores vacíos, cortos o
  placeholders públicos.
- `DATABASE_URL`
- `CERTS_PATH`
- `CERTIFICATE_MAX_UPLOAD_BYTES`
- `ARCA_PRIVATE_KEY_PASSWORD`
- `ARCA_MIGRATION_TARGET_KEY_PASSWORD` solo para exportación local privada
- `ARCA_MIGRATION_SOURCE_KEY_PASSWORD` solo si las claves fuente ya están
  cifradas
- `ARCA_ENV`: enum estricto; solo `homologacion` o `produccion`. `AFIP_ENV` es
  un alias legacy y `ARCA_ENV` tiene precedencia. Si ambos faltan usa
  `homologacion`; un valor presente vacío o inválido impide iniciar.
- `ARCA_PUNTOS_BLOQUEADOS_PREAUTORIZACION`: configuración fiscal privada. Sus
  tuplas reales no se versionan ni se exponen completas. Es una denegación
  adicional PF-19A: nunca promueve RECE ni sustituye la autoridad durable
  PF-19B.
- `PF19B_SQLITE_BACKUP_CONFIRMED=1` y `PF19B_SQLITE_BACKUP_PATH`: opt-in de una
  sola ejecución para upgrade o downgrade PF-19B sobre SQLite física. La ruta
  debe apuntar a un backup distinto, privado, no vacío y semánticamente idéntico
  a la fuente; no dejar estas variables persistidas ni versionar el archivo.
- `AFIP_CERTS_PATH`
- `AFIP_ENV`
- `CORS_ORIGINS`

## Nota de nomenclatura
- `AFIP_*` se mantiene por compatibilidad, pero la documentación nueva debe referir a ARCA.

## Referencias útiles
- Guía de certificados de usuario: `docs/certificates/README.md`
