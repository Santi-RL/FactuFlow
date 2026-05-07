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
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Documentación API

Una vez iniciado el servidor, la documentación interactiva está disponible en:

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

## Endpoints Principales

### Autenticación

- `POST /api/auth/setup` - Crear primer usuario administrador
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Obtener usuario actual

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

### Emisión masiva

- `GET /api/lotes-comprobantes/plantilla` - Descargar plantilla oficial de Excel
- `POST /api/lotes-comprobantes/validar` - Validar y registrar un lote
- `POST /api/lotes-comprobantes/{id}/procesar` - Emitir los comprobantes válidos del lote
- `GET /api/lotes-comprobantes/{id}` - Ver estado y detalle del lote
- `GET /api/lotes-comprobantes/{id}/archivo-observado` - Descargar archivo observado con mensajes por fila

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

## Troubleshooting

### Error: "password cannot be longer than 72 bytes" al ejecutar tests

Esto no suele ser una contraseña real demasiado larga. En Windows se presenta por
una incompatibilidad entre `passlib 1.7.4` y `bcrypt >= 4`.

Solución:
- Asegurarse de tener `bcrypt<4` instalado (ya está fijado en `requirements.txt`).
- Si el entorno ya existía, reinstalar dependencias:

```bash
pip install -r requirements.txt --force-reinstall
```

## Estructura del Proyecto

```
backend/
├── app/
│   ├── main.py              # Aplicación FastAPI
│   ├── core/                # Configuración core
│   │   ├── config.py        # Settings
│   │   ├── database.py      # SQLAlchemy setup
│   │   └── security.py      # JWT, bcrypt
│   ├── models/              # Modelos SQLAlchemy
│   │   ├── usuario.py
│   │   ├── empresa.py
│   │   ├── cliente.py
│   │   ├── punto_venta.py
│   │   ├── certificado.py
│   │   ├── comprobante.py
│   │   └── comprobante_item.py
│   ├── schemas/             # Schemas Pydantic
│   │   ├── usuario.py
│   │   ├── empresa.py
│   │   ├── cliente.py
│   │   ├── punto_venta.py
│   │   └── certificado.py
│   ├── api/                 # Endpoints de API
│   │   ├── auth.py
│   │   ├── empresas.py
│   │   ├── clientes.py
│   │   ├── puntos_venta.py
│   │   ├── certificados.py
│   │   ├── arca.py
│   │   ├── comprobantes.py
│   │   ├── pdf.py
│   │   ├── reportes.py
│   │   └── health.py
│   ├── services/            # Lógica de negocio
│   ├── arca/                # Integración ARCA (WSAA/WSFEv1, crypto, cache, utils)
│   └── afip/                # Legacy (nomenclatura, sin codigo)
├── tests/                   # Tests
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_clientes.py
│   └── test_health.py
├── alembic/                 # Migraciones
├── data/                    # Datos locales/cache ARCA (gitignored)
├── certs/                   # Certificados ARCA (gitignored)
├── requirements.txt
├── requirements-dev.txt
└── pytest.ini
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
    "email": "admin@factuflow.com",
    "password": "admin123",
    "nombre": "Administrador"
  }'
```

### 2. Login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@factuflow.com",
    "password": "admin123"
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
- `ARCA_ENV` - Ambiente de ARCA (homologacion/produccion)
- `CERTS_PATH` - Carpeta donde se guardan certificados
- `BATCH_SYNC_LIMIT` - Corte entre procesamiento sincrono y background
- `BATCH_WORKER_ENABLED` - Worker para lotes grandes en segundo plano
- `CORS_ORIGINS` - Orígenes permitidos para CORS

## Licencia

Ver LICENSE en la raíz del proyecto.
