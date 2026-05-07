# FactuFlow

Sistema de facturacion electronica ARCA enfocado en usuarios administrativos no tecnicos, con emision individual y emision masiva por lote.

## Estado actual

Version actual: `0.2.0-mvp`

En este momento el proyecto esta orientado a cerrar un MVP funcional en `homologacion` con estas capacidades:

- configuracion inicial de empresa y usuario administrador
- emision individual de comprobantes con CAE
- emision masiva desde Excel con validacion previa, seguimiento del lote y archivo observado
- certificados por empresa y ambiente
- PDF de comprobantes y reportes basicos de ventas, IVA y ranking de clientes
- selector de emisor activo para usuarios administradores

## Lo mas importante del MVP

- la interfaz prioriza tareas guiadas, mensajes claros y contexto para personal administrativo
- la emision masiva usa una plantilla Excel fija con `comprobante_ref` para agrupar varias filas en un mismo comprobante
- cada lote pertenece a un solo emisor activo
- hasta `100` comprobantes se procesan en la misma sesion; lotes mas grandes quedan en cola persistente y se procesan en segundo plano
- los reportes solo consideran comprobantes autorizados

## Puesta en marcha

### Docker

```bash
cp .env.example .env
docker-compose up --build
```

Backend: `http://localhost:8000`

Frontend: `http://localhost:8080`

El perfil local usa PostgreSQL, monta el codigo del backend y ejecuta `alembic upgrade head` antes de iniciar la API con reload.

### Docker produccion / VPS

```bash
cp .env.production.example .env.production
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

El perfil productivo no monta el codigo fuente, usa PostgreSQL, exige secretos y deja persistidos datos, certificados y logs en rutas configurables.

### Desarrollo local

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

### Crear usuario administrador

Para crear tu usuario propietario o promover un usuario existente a administrador:

```bash
cd backend
.venv\Scripts\python.exe -m app.scripts.create_admin_user
```

El comando pide email, nombre y contrasena por consola. Si se ejecuta contra una base
con `DATABASE_URL` de PostgreSQL, crea el administrador en esa base. Si ya existe un
usuario con ese email, lo activa, lo deja como administrador y permite resetear su
contrasena.

## Variables de entorno relevantes

- `ARCA_ENV`: `homologacion` o `produccion`
- `CERTS_PATH`: carpeta de certificados
- `BATCH_SYNC_LIMIT`: maximo de comprobantes para procesamiento sincrono
- `BATCH_MAX_ROWS`: limite de filas del Excel
- `BATCH_MAX_GROUPS`: limite de comprobantes por lote
- `BATCH_WORKER_ENABLED`: habilita procesamiento en segundo plano de lotes grandes
- `DATABASE_URL`: PostgreSQL recomendado para operacion real
- `CORS_ORIGINS`: orígenes permitidos

Se mantiene compatibilidad con variables legacy `AFIP_*` cuando todavia existan integraciones viejas.

## Documentacion

- [docs/README.md](docs/README.md)
- [docs/agents/README.md](docs/agents/README.md)
- [backend/README.md](backend/README.md)
- [CHANGELOG.md](CHANGELOG.md)
- [ROADMAP.md](ROADMAP.md)

## Licencia

MIT. Revisa [LICENSE](LICENSE).
