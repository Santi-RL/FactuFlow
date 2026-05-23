# Seguridad y certificados

## Archivos sensibles
- No commitear `.key`, `.crt`, `.pem`, `.p12`, `.pfx`.
- Los certificados van en `certs/` y la DB local en `data/` (gitignored).
- No commitear CUITs reales, nombres de clientes o emisores reales,
  credenciales, tokens, CAEs reales, capturas privadas, PDFs, Excel de clientes,
  bases locales, logs de produccion ni evidencia de debug local.
- La documentacion versionada debe usar datos sinteticos o redactados. La
  evidencia operativa privada queda fuera del repo, por ejemplo en `.tmp/`,
  `private/`, `evidence/`, `factuflow-documentacion-base/`, `output/`,
  `data/`, `backend/data/` o `certs/`.
- Si un dato real es necesario para retomar una operacion, referenciarlo como
  "evidencia local privada" y no copiar el valor al archivo versionado.

## Almacenamiento recomendado
- Guardar en el filesystem el certificado y la clave.
- Persistir en DB solo metadatos del certificado.
- Mantener separados:
  - proyecto publico: codigo, migraciones, tests con fixtures sinteticos,
    documentacion general y ejemplos sin datos reales
  - entorno privado: `.env*`, bases SQLite/PostgreSQL locales, certificados,
    constancias ARCA reales, archivos Excel/PDF de clientes, screenshots,
    trazas Playwright, logs, auditorias locales, planes privados de cambio y
    scripts exploratorios de debug

## Aislamiento por emisor

- FactuFlow usa un modelo multiemisor con un emisor activo explicito por vez,
  orientado a contadores independientes y estudios chicos.
- Clientes, certificados, puntos de venta, comprobantes, lotes, PDFs, reportes,
  perfiles de carga masiva y formatos de importacion deben quedar siempre
  scopiados al emisor activo.
- Ningun flujo debe reutilizar silenciosamente datos de otro emisor. Ante duda,
  bloquear la operacion y pedir una seleccion o validacion explicita.
- Los cambios que toquen emision, lotes, certificados, puntos de venta,
  clientes, reportes o PDFs deben considerar pruebas de regresion multiemisor.

## Checklist antes de commit

Ejecutar una revision minima:

```bash
git status --short --untracked-files=all
git diff --cached --name-only
git grep -n -E "[0-9]{11}|password|secret|token|CAE|BEGIN (RSA |EC |)PRIVATE KEY"
```

Si el cambio incluye evidencia local o datos reales, moverla a una carpeta
ignorada y dejar solo una descripcion redactada en la documentacion.

## Variables de entorno relevantes
- `APP_SECRET_KEY`
- `DATABASE_URL`
- `CERTS_PATH`
- `AFIP_CERTS_PATH`
- `AFIP_ENV`
- `CORS_ORIGINS`

## Nota de nomenclatura
- `AFIP_*` se mantiene por compatibilidad, pero la documentación nueva debe referir a ARCA.

## Referencias útiles
- Guía de certificados de usuario: `docs/certificates/README.md`
