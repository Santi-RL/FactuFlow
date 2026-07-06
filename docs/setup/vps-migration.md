# Migración local a VPS

Última actualización: 2026-06-04

Este runbook prepara una migración privada y repetible desde la instalación
local SQLite hacia PostgreSQL, sin desplegar todavía en el VPS real.

La primera restauración debe ensayarse en PostgreSQL local o en un entorno de
prueba descartable. No se solicita CAE, no se emite ningún comprobante y no se
hacen llamadas ARCA durante la exportación o importación.

## Alcance migrado

La migración conserva los datos necesarios para continuar operando desde el
VPS sin perder continuidad fiscal local:

- emisores, usuarios, clientes y puntos de venta
- certificados activos y sus archivos `.crt` / `.key`
- formatos de importación, versiones, campos y reglas
- perfiles de carga masiva
- comprobantes y sus ítems, preservando IDs y numeración local

Quedan fuera del paquete:

- lotes de comprobantes, grupos, filas y eventos de lote
- eventos de sistema y exportaciones de almacenamiento
- PDFs, XLSX, observados, temporales, cachés, logs y evidencia privada

La SQLite local queda como archivo histórico privado y no se versiona.

## Herramienta

El script vive en:

```bash
backend/app/scripts/vps_migration.py
```

Subcomandos disponibles:

- `preflight`: válida SQLite local, Alembic head, tablas esperadas y
  certificados activos.
- `export`: genera un paquete privado en `.tmp/vps-migration/<timestamp>/`.
- `import`: restaura el paquete sobre PostgreSQL limpio ya migrado con Alembic.
- `validate`: compara datos restaurados y válida disponibilidad básica.

## Preflight local

Ejecutar desde el repo:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.scripts.vps_migration preflight
```

La fuente predeterminada es `backend/data/factuflow.db` y `CERTS_PATH` se
resuelve como `backend/certs` si no se configura otra ruta.

El preflight debe bloquear si:

- la SQLite no existe o no está en el head Alembic vigente
- faltan tablas esperadas
- existe un certificado activo sin `.crt` y `.key` resolubles dentro de
  `CERTS_PATH`
- se intenta operar con un estado que no puede migrarse de forma segura

En la instalación local actual hay que corregir primero el certificado activo
que no resuelve sus archivos privados antes de exportar.

## Exportar paquete privado

Definir una contraseña nueva y fuerte para cifrar las claves privadas que se
usarán en producción. Esa misma contraseña debe quedar luego como
`ARCA_PRIVATE_KEY_PASSWORD` en el `.env.production` destino.

```powershell
cd backend
$env:ARCA_MIGRATION_TARGET_KEY_PASSWORD="<clave-larga-nueva>"
.\.venv\Scripts\python.exe -m app.scripts.vps_migration export --non-interactive
```

Si las claves fuente ya estuvieran cifradas con otra contraseña:

```powershell
$env:ARCA_MIGRATION_SOURCE_KEY_PASSWORD="<clave-local-actual>"
```

El paquete generado incluye:

- `manifest.json` con versión de paquete, scope, Alembic head, conteos,
  checksums y tablas excluidas
- `data/*.jsonl` con filas exportadas por tabla
- `certs/*.crt` y `certs/*.key` de certificados activos
- `env.production.required.example` con variables requeridas sin secretos reales

El paquete es material privado. No se debe commitear, copiar a tickets ni subir
a servicios externos.

## Ensayo en PostgreSQL local

Crear una base PostgreSQL limpia de prueba. Puede usarse Docker local con un
volumen descartable:

```powershell
docker run --name factuflow-migration-postgres --rm -d `
  -e POSTGRES_DB=factuflow_migration `
  -e POSTGRES_USER=factuflow `
  -e POSTGRES_PASSWORD=<password-de-prueba> `
  -p 15432:5432 postgres:16-alpine
```

Preparar un `.env.production` privado de ensayo con, como mínimo:

```bash
APP_SECRET_KEY=<clave-de-ensayo>
ARCA_PRIVATE_KEY_PASSWORD=<misma-clave-usada-en-ARCA_MIGRATION_TARGET_KEY_PASSWORD>
POSTGRES_DB=factuflow_migration
POSTGRES_USER=factuflow
POSTGRES_PASSWORD=<password-de-prueba>
ARCA_ENV=produccion
CORS_ORIGINS=http://localhost:8080
VITE_API_URL=http://localhost:8000
FACTUFLOW_CERTS_DIR=<ruta-absoluta-a-certs-restaurados>
```

La carpeta indicada por `FACTUFLOW_CERTS_DIR` puede no existir todavía; el
importador la crea al restaurar los certificados.

Ejecutar Alembic sobre la base limpia:

```powershell
cd backend
$env:DATABASE_URL="postgresql+asyncpg://factuflow:<password-de-prueba>@localhost:15432/factuflow_migration"
.\.venv\Scripts\alembic.exe upgrade head
```

Importar el paquete:

```powershell
.\.venv\Scripts\python.exe -m app.scripts.vps_migration import `
  ..\.tmp\vps-migration\<timestamp> `
  --database-url $env:DATABASE_URL `
  --production-env ..\.env.production `
  --target-certs-dir <ruta-absoluta-a-certs-restaurados>
```

El importador acepta la URL productiva `postgresql+asyncpg://` y la convierte a
un driver síncrono para insertar datos. Rechaza cualquier destino que no sea
PostgreSQL, exige que la base esté en el mismo head Alembic del paquete, no
modifica `alembic_version`, verifica que el destino esté limpio y ajusta
secuencias `SERIAL/IDENTITY` al máximo ID restaurado.

La base limpia puede contener los formatos globales seed creados por Alembic;
el importador los reemplaza por los formatos del paquete. Si encuentra usuarios,
emisores, clientes, certificados, comprobantes, perfiles, lotes, eventos o
exportaciones previas, bloquea la restauración.

## Validar restauración

```powershell
.\.venv\Scripts\python.exe -m app.scripts.vps_migration validate `
  ..\.tmp\vps-migration\<timestamp> `
  --database-url $env:DATABASE_URL `
  --production-env ..\.env.production `
  --target-certs-dir <ruta-absoluta-a-certs-restaurados>
```

Validaciones esperadas:

- conteos de tablas incluidas coinciden con el manifiesto
- tablas excluidas quedan vacías
- claves privadas restauradas abren con `ARCA_PRIVATE_KEY_PASSWORD`
- secuencias PostgreSQL quedan por encima del mayor ID restaurado
- opcionalmente, `--api-url http://localhost:8000` verifica `/api/health`
- opcionalmente, `--login-email` prueba login sin mostrar la contraseña

Después del import, levantar el backend contra esa base de ensayo con
`ARCA_ENV=produccion`, `CERTS_PATH` apuntando a la carpeta restaurada y
`ARCA_PRIVATE_KEY_PASSWORD` igual a la contraseña usada al exportar.

Verificar desde UI o API:

1. Login.
2. Emisores, usuarios, clientes y puntos de venta.
3. Certificados activos y lectura de clave privada.
4. Comprobantes, ítems y reportes básicos.
5. `proximo-numero` solo como verificación segura de numeración, sin emitir CAE
   y sin ejecutar flujos de emisión.

## Bloqueos de seguridad

- No ejecutar `export` si `preflight` falla.
- No migrar certificados activos incompletos.
- No reutilizar la contraseña local si se define una nueva política de secretos
  para producción.
- No importar sobre una base PostgreSQL con datos operativos.
- No operar simultáneamente la instalación local y el VPS con los mismos
  certificados productivos. El VPS debe reemplazar al entorno local operativo o
  usar certificados nuevos.
- No versionar paquetes, bases, certificados, claves privadas, `.env.production`,
  logs ni evidencia de ensayo.
