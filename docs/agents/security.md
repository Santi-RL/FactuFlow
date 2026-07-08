# Seguridad y certificados

## Archivos sensibles
- No commitear `.key`, `.crt`, `.pem`, `.p12`, `.pfx`.
- Los certificados van en `certs/` y la DB local en `data/` (gitignored).
- No commitear CUITs reales, nombres de clientes o emisores reales,
  credenciales, tokens, CAEs reales, capturas privadas, PDFs, Excel de clientes,
  bases locales, logs de producción ni evidencia de debug local.
- La documentación versionada debe usar datos sinteticos o redactados. La
  evidencia operativa privada queda fuera del repo, por ejemplo en `.tmp/`,
  `private/`, `evidence/`, `factuflow-documentacion-base/`, `output/`,
  `data/`, `backend/data/` o `certs/`.
- Si un dato real es necesario para retomar una operación, referenciarlo como
  "evidencia local privada" y no copiar el valor al archivo versionado.

## Almacenamiento recomendado
- Guardar en el filesystem el certificado y la clave.
- Persistir en DB solo metadatos del certificado.
- Mantener separados:
  - proyecto público: código, migraciones, tests con fixtures sinteticos,
    documentación general y ejemplos sin datos reales
  - entorno privado: `.env*`, bases SQLite/PostgreSQL locales, certificados,
    constancias ARCA reales, archivos Excel/PDF de clientes, screenshots,
    trazas Playwright, logs, auditorias locales, planes privados de cambio y
    scripts exploratorios de debug

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
  clientes, reportes o PDFs deben considerar pruebas de regresion multiemisor.

## Cambios fiscales críticos

- Antes de modificar emisión fiscal, ARCA/WSFE, CAE, numeración, fechas
  fiscales, comprobantes, notas de crédito/débito, reintentos, reconciliación,
  certificados, puntos de venta, migraciones fiscales o confirmaciones
  irreversibles, completar `docs/agents/fiscal-change-checklist.md`.
- El diseño debe identificar invariantes, estados, fallos intermedios,
  concurrencia, constraints, reconciliación y matriz de tests antes del código.
- Si se usa `autoreview`, hacerlo de forma escalonada y crítica: `gpt-5.5 low`,
  luego `medium`, luego `high` solo cuando el nivel anterior quede sin
  hallazgos aceptados. No aplicar hallazgos automáticamente.

## Checklist antes de commit

Ejecutar una revision mínima:

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
- `ARCA_PRIVATE_KEY_PASSWORD`
- `ARCA_MIGRATION_TARGET_KEY_PASSWORD` solo para exportación local privada
- `ARCA_MIGRATION_SOURCE_KEY_PASSWORD` solo si las claves fuente ya están
  cifradas
- `AFIP_CERTS_PATH`
- `AFIP_ENV`
- `CORS_ORIGINS`

## Nota de nomenclatura
- `AFIP_*` se mantiene por compatibilidad, pero la documentación nueva debe referir a ARCA.

## Referencias útiles
- Guía de certificados de usuario: `docs/certificates/README.md`
