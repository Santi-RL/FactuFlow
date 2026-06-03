# FactuFlow

Sistema de facturacion electronica ARCA enfocado en usuarios administrativos no tecnicos, con emision individual y emision masiva por lote.

## Estado actual

Version actual: `0.2.0-mvp`

En este momento el proyecto esta en una etapa post-piloto productivo: el MVP ya
fue validado en homologacion y tambien se uso en produccion real controlada. El
trabajo actual se concentra en consolidar operacion, documentacion, despliegue y
robustez sin perder las reglas fiscales criticas.

El corte `0.2.0-mvp` del 2026-05-22 es la linea base actual. El historial
anterior queda resumido en `CHANGELOG.md`; no debe confundirse con el estado
operativo vigente.

Capacidades actuales:

- configuracion inicial de empresa y usuario administrador propietario
- gestion de usuarios desde la aplicacion: solo administradores pueden crear,
  desactivar, reactivar o resetear usuarios
- emision individual de comprobantes con CAE
- emision masiva desde Excel con validacion previa, seguimiento del lote y archivo observado
- certificados por empresa y ambiente
- PDF de comprobantes y reportes basicos de ventas, IVA y ranking de clientes
- selector de emisor activo para que un contador independiente o estudio chico
  opere varios CUITs sin mezclar informacion
- todos los usuarios activos pueden operar todos los emisores configurados; el
  rol administrador se reserva para administrar usuarios
- uso productivo real controlado con evidencia privada local; no se versionan
  CUITs, CAEs, comprobantes, Excels ni logs privados

## Alcance de producto

FactuFlow es una herramienta para facturar. No esta planificado incorporar
manejo de cuentas corrientes, stock ni catalogos como modulos del producto.

Las integraciones externas quedan como evolucion futura, posterior a tener la
facturacion madura y productiva estable. Su objetivo sera obtener datos desde
otras fuentes o aplicaciones, o enviar datos hacia ellas, aprovechando la API
del sistema.

El modelo multiemisor vigente es: un usuario puede administrar varios emisores,
pero siempre opera con un emisor activo explicito por vez. No esta planificada
por ahora una administracion central compleja con permisos finos, reportes
globales y operacion simultanea entre multiples emisores.

La observabilidad operativa estandar es parte del alcance post-piloto: el
sistema debe explicar con lenguaje simple que paso, que impacto tiene y cual es
el proximo paso seguro en emisiones, lotes, errores ARCA, reconciliaciones,
estado del sistema y backups. Las herramientas avanzadas de monitoreo quedan
para una etapa posterior.

## Lo mas importante del MVP

- la interfaz prioriza tareas guiadas, mensajes claros y contexto para personal administrativo
- la emision masiva usa una plantilla Excel fija con `comprobante_ref` para agrupar varias filas en un mismo comprobante
- cada lote pertenece a un solo emisor activo
- clientes, certificados, puntos de venta, comprobantes, lotes, PDFs y reportes
  deben quedar siempre aislados por emisor activo
- hasta `100` comprobantes se procesan en la misma sesion; lotes mas grandes quedan en cola persistente y se procesan en segundo plano
- los reportes solo consideran comprobantes autorizados
- ninguna emision real debe usar la fecha del dia como default fiscal; la fecha
  debe ser explicita y confirmada por el usuario antes de solicitar CAE

## Puesta en marcha

### Windows local con launcher

Para una PC local de desarrollo o QA, usar:

```bash
.\FactuFlow Local.vbs
```

El launcher inicia backend y frontend en segundo plano sin dejar una ventana de
PowerShell abierta, muestra un icono junto al reloj de Windows y abre
`http://localhost:8080` cuando FactuFlow esta listo. El menu del icono permite
abrir la app, consultar estado, reiniciar o detener servicios y abrir los logs
locales en `.tmp/local-launcher/`. El acceso `FactuFlow Local.cmd` queda como
compatibilidad y delega en el mismo launcher oculto.

Esta opcion no es un instalador ni configura inicio automatico con Windows.
El uso local con launcher ya esta implementado y testeado hasta nivel
desarrollo/QA; el siguiente hito de despliegue es una instalacion en VPS con
Docker produccion y PostgreSQL.

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

Antes de operar el VPS con emisores reales hay una pregunta tecnica pendiente:
validar si los certificados productivos actuales pueden migrarse desde el
entorno local al VPS conservando clave, archivo y configuracion, o si conviene
generar certificados nuevos para el servidor. La distribucion comercial
instalable queda para despues de estabilizar el producto funcionando en VPS.

### Desarrollo local tecnico

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

### Crear usuario administrador o propietario

En una instalación nueva, la pantalla `Configurar sistema` solo aparece cuando
no existe ningún usuario. Ese flujo crea el primer usuario administrador
propietario y el primer emisor.

Una vez creado al menos un usuario, el alta pública queda cerrada. Los nuevos
usuarios se crean desde el menú `Usuarios`, visible únicamente para
administradores.

Para crear tu usuario propietario o promover un usuario existente a administrador
desde consola:

```bash
cd backend
.venv\Scripts\python.exe -m app.scripts.create_admin_user
```

El comando pide email, nombre y contraseña por consola. Si se ejecuta contra una
base con `DATABASE_URL` de PostgreSQL, crea el administrador en esa base. Si ya
existe un usuario con ese email, lo activa, lo deja como administrador y permite
resetear su contraseña.

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
