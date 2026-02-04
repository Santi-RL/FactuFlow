# Seguridad y certificados

## Archivos sensibles
- No commitear `.key`, `.crt`, `.pem`, `.p12`, `.pfx`.
- Los certificados van en `certs/` y la DB local en `data/` (gitignored).

## Almacenamiento recomendado
- Guardar en el filesystem el certificado y la clave.
- Persistir en DB solo metadatos del certificado.

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
