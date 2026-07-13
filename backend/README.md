# FactuFlow Backend

Backend de FactuFlow - Sistema de Facturación Electrónica ARCA - Argentina.

## Tecnologías

- **FastAPI** - Framework web moderno y rápido
- **SQLAlchemy 2.0** - ORM con soporte async
- **PostgreSQL / SQLite dev** - Base de datos
- **Alembic** - Migraciones de base de datos
- **Pydantic** - Validación de datos
- **JWT** - Autenticación con tokens
- **Bcrypt** - Hashing de contraseñas

## Instalación

### 1. Crear entorno virtual

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Para tests, lint y formato
```

### 3. Configurar variables de entorno

```bash
cp ../.env.example .env
# Editar .env y configurar las variables necesarias
```

### 4. Crear directorios necesarios

```bash
mkdir -p data certs logs
```

### 5. Ejecutar migraciones

```bash
alembic upgrade head
```

## Ejecución

### Desarrollo

```bash
uvicorn app.main:app --reload --port 8000
```

### Producción

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Mientras el procesamiento de lotes siga embebido en el backend, producción debe
usar un único proceso Uvicorn y `BATCH_WORKER_ENABLED=true`. No aumentar
`--workers` sin separar antes el worker de lotes en un servicio dedicado.

Con PostgreSQL, la configuración predeterminada y máxima reserva `4` conexiones
para la API, sin overflow, y `1` conexión dedicada para el worker. El pool API
puede reducirse dentro de `1..4`; el timeout de adquisición es `5 s` y una
retención de conexión de `10 s` genera un warning sanitizado. Las sesiones API
son lazy: no ocupan una conexión hasta el primer SQL necesario, incluida la
autenticación. SQLite comparte un único engine entre API y worker por diseño;
esa condición no es una degradación.

## Documentación API

Una vez iniciado el servidor, la documentación interactiva está disponible en:

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

## Endpoints Principales

### Autenticación

- `POST /api/auth/setup` - Crear primer usuario administrador
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Obtener usuario actual

### Usuarios

- `GET /api/usuarios` - Listar usuarios (solo administradores)
- `POST /api/usuarios` - Crear usuario (solo administradores)
- `PUT /api/usuarios/{id}` - Actualizar usuario (solo administradores)
- `POST /api/usuarios/{id}/reset-password` - Restablecer contraseña

### Empresas

- `GET /api/empresas` - Listar empresas
- `POST /api/empresas` - Crear empresa
- `GET /api/empresas/{id}` - Obtener empresa
- `PUT /api/empresas/{id}` - Actualizar empresa
- `DELETE /api/empresas/{id}` - Eliminar empresa

### Clientes

- `GET /api/clientes` - Listar clientes (con paginación y búsqueda)
- `POST /api/clientes` - Crear cliente
- `GET /api/clientes/{id}` - Obtener cliente
- `PUT /api/clientes/{id}` - Actualizar cliente
- `DELETE /api/clientes/{id}` - Desactivar cliente

### Puntos de Venta

- `GET /api/puntos-venta` - Listar puntos de venta
- `POST /api/puntos-venta` - Crear punto de venta
- `PUT /api/puntos-venta/{id}` - Actualizar punto de venta
- `DELETE /api/puntos-venta/{id}` - Desactivar punto de venta

### Certificados

- `GET /api/certificados` - Listar certificados
- `GET /api/certificados/{id}` - Obtener certificado
- `DELETE /api/certificados/{id}` - Eliminar certificado

### Health

- `GET /api/health` - Health check básico
- `GET /api/health/db` - Health check de base de datos
- `GET /api/health/worker` - Estado administrativo sanitizado del worker y pools

El health del worker requiere un administrador. Expone `separation_required`,
`separated` y métricas allowlist, sin DSN, credenciales ni errores internos
crudos. Los timeouts y las desconexiones de base responden `503` con mensaje
sanitizado y `Retry-After: 2`.

### Emisión masiva

- `GET /api/lotes-comprobantes/plantilla` - Descargar plantilla oficial de Excel
- `POST /api/lotes-comprobantes/validar` - Validar y registrar un lote
- `POST /api/lotes-comprobantes/{id}/procesar` - Emitir los comprobantes válidos del lote
- `GET /api/lotes-comprobantes/{id}/seguimiento` - Polling allowlist de estado y contadores
- `GET /api/lotes-comprobantes/{id}/resumen` - Ver resumen fiscal liviano del lote
- `GET /api/lotes-comprobantes/{id}/grupos` - Ver grupos del lote con paginación
- `GET /api/lotes-comprobantes/{id}` - Ver estado y detalle del lote
- `GET /api/lotes-comprobantes/{id}/archivo-observado` - Descargar archivo observado con mensajes por fila

### Plantillas y perfiles de carga masiva

- `GET /api/formatos-importacion` - Listar plantillas/formato de importación
- `POST /api/formatos-importacion/analizar-excel` - Analizar encabezados de un Excel
- `POST /api/formatos-importacion/detectar` - Detectar candidatos de plantilla
- `GET /api/perfiles-carga-masiva` - Listar perfiles del emisor activo
- `POST /api/perfiles-carga-masiva` - Crear perfil de carga masiva

### Sistema y almacenamiento

- `GET /api/almacenamiento/uso` - Diagnóstico resumido de uso
- `POST /api/almacenamiento/resguardos` - Preparar ZIP de resguardo
- `POST /api/almacenamiento/liberar` - Liberar espacio con confirmación

## Testing

### Ejecutar todos los tests

```bash
pytest
```

### Ejecutar tests con coverage

```bash
pytest --cov=app --cov-report=html
```

### Ejecutar tests específicos

```bash
pytest tests/test_auth.py -v
pytest tests/test_clientes.py::test_create_cliente -v
```

### Integración PostgreSQL desechable

El marker `integration` está registrado en `pytest.ini`. Las pruebas requieren
que `FACTUFLOW_TEST_POSTGRES_URL` apunte a una instancia PostgreSQL desechable
configurada fuera del repositorio:

```bash
pytest -m integration tests/integration/test_pool_capacity_postgresql.py -q
pytest -m integration tests/integration/test_integridad_fiscal_postgresql.py -q
```

La primera verifica cuatro conexiones API más una conexión dedicada del worker.
La segunda recrea únicamente el schema de la base desechable y valida la
migración PF-01B, constraints, estados, CAE, concurrencia y preflight con datos
sintéticos. Exige además `FACTUFLOW_TEST_POSTGRES_ALLOW_SCHEMA_RESET=1` y que el
nombre de la base incluya `test`, `tmp`, `temp` o `pf01b`; sin ambas condiciones
falla antes de conectarse. Ninguna prueba llama a ARCA ni declara un despliegue. No ejecutarlas contra
una instalación operativa ni guardar la URL o sus credenciales en Git. Ver
`docs/agents/testing.md`.

## Troubleshooting

### Error: "password cannot be longer than 72 bytes" al ejecutar tests

Esto no suele ser una contraseña real demasiado larga. En Windows se presenta por
una incompatibilidad entre `passlib 1.7.4` y `bcrypt >= 4`.

Solución:
- Asegurarse de tener `bcrypt<4` instalado (ya está fijado en `requirements.txt`).
- Si el entorno ya existía, reinstalar dependencias:

```bash
pip install -r requirements.txt --force-reinstall
pip install -r requirements-dev.txt --force-reinstall
```

## Estructura del Proyecto

Mapa resumido. Para el detalle vigente de módulos y ownership, usar `docs/agents/structure.md`.

```text
backend/
├── app/main.py              # Entrada FastAPI y registro de routers
├── app/api/                 # Endpoints REST por dominio
├── app/arca/                # Integración ARCA: WSAA, WSFEv1, SOAP, cache y crypto
├── app/core/                # Configuración, base de datos y seguridad
├── app/models/              # Modelos SQLAlchemy
├── app/schemas/             # Schemas Pydantic
├── app/services/            # Lógica de negocio
├── app/scripts/             # Scripts operativos internos
├── app/templates/           # Plantillas HTML/PDF
├── app/afip/                # Carpeta legacy de nomenclatura, sin código operativo
├── tests/                   # Tests pytest
├── alembic/                 # Migraciones
├── data/                    # Datos locales/cache ARCA (gitignored)
└── certs/                   # Certificados ARCA (gitignored)
```
## Primeros Pasos

### 1. Setup Inicial

```bash
# Iniciar el servidor
uvicorn app.main:app --reload

# En otra terminal, crear el primer usuario admin
curl -X POST http://localhost:8000/api/auth/setup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin.local@example.test",
    "password": "CAMBIAR_EN_LOCAL",
    "nombre": "Administrador"
  }'
```

### 2. Login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin.local@example.test",
    "password": "CAMBIAR_EN_LOCAL"
  }'
```

### 3. Usar el token

```bash
# Copiar el access_token de la respuesta anterior
TOKEN="your_access_token_here"

# Obtener datos del usuario
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

## Variables de Entorno

Ver `.env.example` en la raíz del proyecto para todas las variables disponibles.

Principales:

- `APP_SECRET_KEY` - Clave secreta para JWT (⚠️ cambiar en producción)
- `DATABASE_URL` - URL de conexión a la base de datos
- `DATABASE_API_POOL_SIZE` - Pool API PostgreSQL, rango `1..4`, default `4`
- `DATABASE_API_MAX_OVERFLOW` - Overflow API, fijo en `0`
- `DATABASE_WORKER_POOL_SIZE` - Pool dedicado del worker, fijo en `1`
- `DATABASE_POOL_TIMEOUT_SECONDS` - Timeout de adquisición, default `5`
- `DATABASE_POOL_HOLD_WARNING_SECONDS` - Warning de retención, default `10`
- `ARCA_ENV` - Ambiente de ARCA (`homologacion`/`produccion`)
- `CERTS_PATH` - Carpeta donde se guardan certificados
- `CERTIFICATE_MAX_UPLOAD_BYTES` - Tamaño máximo para subir certificados ARCA
- `BATCH_SYNC_LIMIT` - Corte entre procesamiento síncrono y background
- `BATCH_WORKER_ENABLED` - Worker para lotes grandes en segundo plano
- `CORS_ORIGINS` - Orígenes permitidos para CORS

## Licencia

Ver LICENSE en la raíz del proyecto.
