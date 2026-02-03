# 🤖 Guía para Agentes de IA - FactuFlow

## Descripción del Proyecto

**FactuFlow** es un sistema de facturación electrónica para Argentina (ARCA) de código abierto. El objetivo es proporcionar una solución **liviana, self-hosted y user-friendly** para emitir comprobantes electrónicos válidos ante ARCA (Agencia de Recaudación y Control Aduanero, anteriormente conocida como AFIP).

### Propósito Principal
- Permitir a emprendedores y pequeñas empresas emitir facturas electrónicas sin depender de servicios de terceros
- Gestionar certificados ARCA de forma simple y guiada
- Integración completa con webservices ARCA (WSAA, WSFEv1)
- Interfaz moderna y fácil de usar para usuarios no técnicos

**Nota importante**: Los webservices de ARCA aún utilizan las URLs y nomenclatura heredadas de AFIP (ej: wsaa.afip.gov.ar, WSFEv1). Esto es normal y no afecta el funcionamiento del sistema.

---

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                      USUARIO FINAL                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  FRONTEND (Vue.js 3)                        │
│  - Interfaz web moderna con Tailwind CSS                   │
│  - Composition API + <script setup>                         │
│  - State management con Pinia                               │
│  - Puerto 8080                                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP/REST API
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  BACKEND (FastAPI)                          │
│  - API REST con documentación automática                   │
│  - Lógica de negocio y validaciones                        │
│  - Gestión de certificados X.509                           │
│  - Cliente SOAP para AFIP                                   │
│  - Puerto 8000                                              │
└─────────────────────────────────────────────────────────────┘
          │                                │
          │                                │
          ▼                                ▼
┌──────────────────┐           ┌──────────────────────┐
│  SQLite DB       │           │  Webservices ARCA    │
│  - Empresas      │           │  - WSAA (auth)       │
│  - Clientes      │           │  - WSFEv1 (facturas) │
│  - Comprobantes  │           │  - Homologación/Prod │
└──────────────────┘           └──────────────────────┘
```

---

## Stack Tecnológico

### Backend: Python 3.11+ con FastAPI

**Justificación:**
- FastAPI es extremadamente rápido (basado en Starlette y Pydantic)
- Tipado estático con type hints (mejora la mantenibilidad)
- Documentación automática con OpenAPI/Swagger
- Excelente manejo de certificados X.509 con librerías Python (cryptography, OpenSSL)
- Ideal para webservices SOAP (zeep, suds)

**Dependencias Principales:**
- `fastapi` - Framework web
- `uvicorn` - ASGI server
- `sqlalchemy` - ORM
- `alembic` - Migraciones de BD
- `pydantic` - Validación de datos
- `python-dotenv` - Variables de entorno
- `zeep` o `suds-jurko` - Cliente SOAP para ARCA
- `cryptography` - Manejo de certificados
- `pytest` - Testing

### Frontend: Vue.js 3 + Tailwind CSS

**Justificación:**
- Vue.js 3 es moderno, reactivo y fácil de aprender
- Composition API ofrece mejor organización del código
- Tailwind CSS permite crear UI atractivas rápidamente sin escribir CSS custom
- Vite ofrece desarrollo ultra-rápido con HMR

**Dependencias Principales:**
- `vue@3` - Framework reactivo
- `vue-router` - Enrutamiento
- `pinia` - State management
- `axios` - HTTP client
- `tailwindcss` - Utilidades CSS
- `vite` - Build tool
- `vitest` - Testing
- `typescript` (opcional pero recomendado)

### Base de Datos: SQLite (default) / PostgreSQL (opcional)

**Justificación:**
- SQLite es zero-config, perfecto para self-hosted
- No requiere servidor de BD separado
- Archivo único fácil de respaldar
- PostgreSQL como opción para instalaciones enterprise

### Despliegue: Docker + Docker Compose

**Justificación:**
- Un solo comando para levantar todo el stack
- Portabilidad entre diferentes sistemas operativos
- Aislamiento de dependencias
- Fácil de actualizar y mantener

---

## Convenciones de Código

### Python (Backend)

#### Estilo de Código
- **SIEMPRE** seguir PEP8
- Usar `black` para formateo automático (línea de 88 caracteres)
- Usar `pylint` o `ruff` para linting
- **Type hints obligatorios** en todas las funciones

```python
# ✅ BIEN
def calcular_total(items: list[dict], iva: float = 21.0) -> float:
    """
    Calcula el total de una factura incluyendo IVA.
    
    Args:
        items: Lista de items con 'precio' y 'cantidad'
        iva: Porcentaje de IVA (default 21%)
        
    Returns:
        Total con IVA incluido
    """
    subtotal = sum(item['precio'] * item['cantidad'] for item in items)
    return subtotal * (1 + iva / 100)

# ❌ MAL (sin type hints, sin docstring)
def calcular_total(items, iva=21):
    subtotal = sum(item['precio'] * item['cantidad'] for item in items)
    return subtotal * (1 + iva / 100)
```

#### Docstrings
- **SIEMPRE** en español
- Formato Google Style o NumPy Style
- Documentar parámetros, retornos y excepciones

#### Estructura de Archivos
- Usar imports absolutos desde `app/`
- Agrupar imports: stdlib, third-party, local
- Un modelo por archivo en `models/`
- Servicios agrupados por dominio en `services/`

### Vue.js (Frontend)

#### Estilo de Componentes
- **SIEMPRE** usar Composition API con `<script setup>`
- Preferir TypeScript cuando sea posible
- Props con validación de tipos

```vue
<!-- ✅ BIEN -->
<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  cliente: {
    nombre: string
    cuit: string
  }
}

const props = defineProps<Props>()
const mostrarDetalles = ref(false)

const cuitFormateado = computed(() => {
  const cuit = props.cliente.cuit
  return `${cuit.slice(0, 2)}-${cuit.slice(2, 10)}-${cuit.slice(10)}`
})
</script>

<template>
  <div class="cliente-card">
    <h3>{{ cliente.nombre }}</h3>
    <p class="text-gray-600">{{ cuitFormateado }}</p>
  </div>
</template>
```

#### Nombrado
- Componentes en PascalCase: `BotonPrimario.vue`, `ModalCliente.vue`
- Props en camelCase: `nombreCliente`, `mostrarModal`
- Events en kebab-case: `@cliente-guardado`, `@modal-cerrado`

#### Tailwind CSS
- Preferir utilidades de Tailwind sobre CSS custom
- Usar `@apply` solo para componentes muy reutilizados
- Mantener clases ordenadas: layout → spacing → colors → typography

### Git Commits

#### Conventional Commits en Español
- `feat:` - Nueva funcionalidad
- `fix:` - Corrección de bug
- `docs:` - Documentación
- `style:` - Formato, punto y coma faltante, etc.
- `refactor:` - Refactorización de código
- `test:` - Agregar o modificar tests
- `chore:` - Tareas de mantenimiento

```bash
# ✅ Ejemplos válidos
feat: agregar wizard de certificados ARCA
fix: corregir cálculo de IVA en facturas tipo B
docs: actualizar guía de instalación con Docker
refactor: extraer lógica de WSAA a servicio separado
test: agregar tests para modelo Comprobante
chore: actualizar dependencias de FastAPI

# ❌ Ejemplos inválidos
added wizard  # No usar inglés, no usar pasado
fix bug  # Muy vago, sin descripción
WIP  # Evitar commits work-in-progress en main
```

---

## Estructura de Carpetas Detallada

```
FactuFlow/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # Punto de entrada FastAPI
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py          # Dependencias comunes (DB, auth)
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── router.py    # Router principal
│   │   │       ├── clientes.py  # Endpoints de clientes
│   │   │       ├── empresas.py  # Endpoints de empresas
│   │   │       ├── comprobantes.py
│   │   │       └── afip.py      # Endpoints de integración ARCA (legacy name)
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py        # Configuración (Settings)
│   │   │   ├── security.py      # Auth, passwords, tokens
│   │   │   └── database.py      # Setup de SQLAlchemy
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # Base class para modelos
│   │   │   ├── empresa.py
│   │   │   ├── cliente.py
│   │   │   ├── comprobante.py
│   │   │   ├── comprobante_item.py
│   │   │   └── certificado.py   # Metadatos, NO el archivo
│   │   ├── schemas/             # Pydantic schemas
│   │   │   ├── __init__.py
│   │   │   ├── cliente.py
│   │   │   ├── empresa.py
│   │   │   └── comprobante.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── cliente_service.py
│   │   │   ├── comprobante_service.py
│   │   │   └── certificado_service.py
│   │   └── afip/
│   │       ├── __init__.py
│   │       ├── wsaa.py           # Web Service Autenticación
│   │       ├── wsfe.py           # Web Service Factura Electrónica
│   │       ├── soap_client.py    # Cliente SOAP genérico
│   │       └── exceptions.py     # Excepciones específicas ARCA
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py           # Fixtures de pytest
│   │   ├── test_clientes.py
│   │   ├── test_comprobantes.py
│   │   └── test_afip/
│   │       ├── test_wsaa.py
│   │       └── test_wsfe.py
│   ├── alembic/                  # Migraciones de BD
│   │   ├── versions/
│   │   └── env.py
│   ├── requirements.txt
│   ├── requirements-dev.txt      # Deps de desarrollo
│   ├── pyproject.toml            # Config de black, pytest, etc.
│   ├── Dockerfile
│   └── .dockerignore
│
├── frontend/
│   ├── public/
│   │   └── favicon.ico
│   ├── src/
│   │   ├── main.ts               # Punto de entrada
│   │   ├── App.vue
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.vue
│   │   │   │   ├── Header.vue
│   │   │   │   └── Footer.vue
│   │   │   ├── ui/               # Componentes base
│   │   │   │   ├── Button.vue
│   │   │   │   ├── Input.vue
│   │   │   │   ├── Modal.vue
│   │   │   │   ├── Table.vue
│   │   │   │   └── Card.vue
│   │   │   └── facturacion/      # Componentes de dominio
│   │   │       ├── FormCliente.vue
│   │   │       ├── FormFactura.vue
│   │   │       └── VistaPrevia.vue
│   │   ├── views/
│   │   │   ├── Dashboard.vue
│   │   │   ├── Clientes.vue
│   │   │   ├── Comprobantes.vue
│   │   │   ├── Configuracion.vue
│   │   │   └── WizardCertificados.vue
│   │   ├── stores/
│   │   │   ├── user.ts
│   │   │   ├── empresa.ts
│   │   │   └── comprobantes.ts
│   │   ├── services/
│   │   │   ├── api.ts            # Cliente Axios configurado
│   │   │   ├── clientes.ts
│   │   │   ├── comprobantes.ts
│   │   │   └── afip.ts
│   │   ├── router/
│   │   │   └── index.ts
│   │   ├── assets/
│   │   │   ├── styles/
│   │   │   │   └── main.css
│   │   │   └── images/
│   │   └── types/                # TypeScript types
│   │       └── index.ts
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── Dockerfile
│   └── .dockerignore
│
├── docs/
│   ├── setup/
│   │   ├── README.md
│   │   ├── docker.md
│   │   └── manual.md
│   ├── certificates/
│   │   ├── README.md
│   │   ├── generar-csr.md
│   │   ├── obtener-certificado.md
│   │   └── renovacion.md
│   ├── api/
│   │   └── README.md             # Generado de OpenAPI
│   └── user-guide/
│       ├── README.md
│       ├── configuracion-inicial.md
│       ├── emitir-factura.md
│       └── reportes.md
│
├── data/                          # SQLite database (gitignored)
│   └── .gitkeep
│
├── certs/                         # Certificados ARCA (gitignored)
│   └── .gitkeep
│
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Tests y lint
│       └── deploy.yml             # Deploy (futuro)
│
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
├── ROADMAP.md
├── LICENSE
├── CONTRIBUTING.md
└── AGENTS.md                      # Este archivo
```

---

## Flujo de Trabajo para Contribuir

### 1. Fork y Clone

```bash
# Fork en GitHub, luego:
git clone https://github.com/TU-USUARIO/FactuFlow.git
cd FactuFlow
git remote add upstream https://github.com/Santi-RL/FactuFlow.git
```

### 2. Crear Branch

```bash
# Branch desde main
git checkout main
git pull upstream main
git checkout -b feat/nombre-descriptivo

# Ejemplos:
# feat/wizard-certificados
# fix/calculo-iva-tipo-b
# docs/guia-certificados
```

### 3. Desarrollar con Tests

- Escribir tests ANTES o en paralelo al código
- Backend: `pytest` con coverage mínimo del 80%
- Frontend: `vitest` para lógica, Playwright/Cypress para E2E

```bash
# Backend
cd backend
python -m pytest tests/ -v --cov=app

# Frontend
cd frontend
npm run test
```

### 4. Asegurar que Pasa CI

```bash
# Lint y formato
cd backend
black app/ tests/
pylint app/

cd ../frontend
npm run lint
npm run format
```

### 5. Commit y Push

```bash
git add .
git commit -m "feat: agregar validación de CUIT argentino"
git push origin feat/nombre-descriptivo
```

### 6. Abrir Pull Request

- Título descriptivo en español
- Descripción clara: qué problema resuelve, cómo lo resuelve
- Screenshots si hay cambios visuales
- Mencionar issue relacionado: "Closes #123"

---

## Comandos Útiles para Desarrollo

### Docker Compose

```bash
# Levantar todo el stack
docker-compose up -d

# Ver logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Reconstruir después de cambios
docker-compose up -d --build

# Bajar todo
docker-compose down

# Bajar y eliminar volúmenes (¡cuidado!)
docker-compose down -v
```

### Backend (FastAPI)

```bash
cd backend

# Crear virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Correr servidor de desarrollo
uvicorn app.main:app --reload --port 8000

# Tests
pytest tests/ -v
pytest tests/ -v --cov=app --cov-report=html

# Lint
black app/ tests/
pylint app/

# Crear migración
alembic revision --autogenerate -m "descripción"
alembic upgrade head
```

### Frontend (Vue.js)

```bash
cd frontend

# Instalar dependencias
npm install

# Servidor de desarrollo
npm run dev

# Build para producción
npm run build

# Preview de build
npm run preview

# Tests
npm run test
npm run test:ui  # Interface de Vitest

# Lint y formato
npm run lint
npm run format

# Type checking
npm run type-check
```

---

## Integración con ARCA

### WSAA (Web Service de Autenticación y Autorización)

El WSAA es el servicio de autenticación de ARCA (ex-AFIP). Funciona así:

1. **Generar TRA (Ticket de Requerimiento de Acceso)**
   - XML con datos del servicio solicitado (ej: "wsfe")
   - Incluye tiempo de expiración (máx 24hs)

2. **Firmar TRA con Certificado**
   - Usar la clave privada (.key) para firmar
   - Genera CMS (Cryptographic Message Syntax)

3. **Enviar CMS al WSAA**
   - Método `loginCms()`
   - Devuelve Token y Sign

4. **Usar Token y Sign en otros servicios**
   - Válidos por el tiempo especificado en TRA
   - Cada webservice de ARCA requiere Token y Sign

**Endpoints:**
- Homologación: `https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl`
- Producción: `https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl`

### WSFEv1 (Factura Electrónica versión 1)

Servicio para emitir facturas electrónicas.

**Métodos principales:**

- `FECAESolicitar`: Solicitar CAE (Código de Autorización Electrónica)
- `FECompUltimoAutorizado`: Obtener último número de comprobante
- `FECompConsultar`: Consultar un comprobante emitido
- `FEParamGetTiposCbte`: Tipos de comprobante (A, B, C, etc.)
- `FEParamGetTiposDoc`: Tipos de documento (CUIT, DNI, etc.)
- `FEParamGetTiposIva`: Tipos de IVA
- `FEParamGetMonedas`: Monedas disponibles

**Endpoints:**
- Homologación: `https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL`
- Producción: `https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL`

### Certificados X.509

**Proceso de obtención:**

1. **Generar CSR (Certificate Signing Request)**
   ```bash
   openssl req -new -newkey rsa:2048 -nodes \
     -keyout clave.key \
     -out certificado.csr
   ```

2. **Subir CSR a ARCA**
   - Ingresar a ARCA con Clave Fiscal (portal heredado de AFIP)
   - Administrador de Relaciones → Certificados
   - Subir CSR
   - Descargar certificado (.crt)

3. **Almacenar de forma segura**
   - ⚠️ NUNCA commitear a Git
   - Almacenar en filesystem con permisos restrictivos
   - Guardar en BD solo metadatos (CUIT, vencimiento, alias)

**Renovación:**
- Los certificados vencen (generalmente 1-2 años)
- Alertar al usuario 30, 15, 7 días antes
- Wizard de renovación similar al de creación

### Homologación vs Producción

**Homologación (Testing):**
- Para desarrollo y pruebas
- CUIT de prueba: 20409378472
- No genera obligaciones fiscales reales
- Certificados de homologación separados

**Producción:**
- Para facturación real
- Genera obligaciones fiscales ante ARCA
- Requiere certificados de producción
- ⚠️ Validar exhaustivamente antes de usar

**Variable de entorno:**
```bash
ARCA_ENV=homologacion  # o "produccion"
# También acepta AFIP_ENV por compatibilidad
```

---

## Guía de Testing

### Backend (pytest)

#### Estructura de Tests

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)
```

#### Ejemplo de Test

```python
# tests/test_clientes.py
def test_crear_cliente(client):
    """Debe crear un cliente con datos válidos"""
    response = client.post(
        "/api/v1/clientes",
        json={
            "nombre": "Juan Pérez",
            "cuit": "20123456789",
            "email": "juan@example.com"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["nombre"] == "Juan Pérez"
    assert data["cuit"] == "20123456789"
    assert "id" in data

def test_crear_cliente_cuit_invalido(client):
    """No debe crear cliente con CUIT inválido"""
    response = client.post(
        "/api/v1/clientes",
        json={
            "nombre": "Juan Pérez",
            "cuit": "123",  # CUIT inválido
            "email": "juan@example.com"
        }
    )
    assert response.status_code == 422
```

#### Mocks para ARCA

```python
# tests/test_afip/test_wsfe.py
from unittest.mock import Mock, patch

def test_solicitar_cae(client, db):
    """Debe solicitar CAE a ARCA correctamente"""
    
    # Mock de la respuesta de ARCA
    mock_response = Mock()
    mock_response.FECAESolicitarResult.FeDetResp.FECAEDetResponse = [
        Mock(
            CAE="12345678901234",
            CAEFchVto="20241231",
            Resultado="A"
        )
    ]
    
    with patch('app.afip.wsfe.Cliente') as mock_cliente:
        mock_cliente.return_value.service.FECAESolicitar.return_value = mock_response
        
        response = client.post(
            "/api/v1/comprobantes/solicitar-cae",
            json={
                "tipo_cbte": 1,
                "punto_vta": 1,
                "items": [...]
            }
        )
        
        assert response.status_code == 200
        assert response.json()["cae"] == "12345678901234"
```

### Frontend (Vitest)

#### Configuración

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'jsdom',
  },
})
```

#### Ejemplo de Test

```typescript
// src/components/__tests__/FormCliente.spec.ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FormCliente from '../FormCliente.vue'

describe('FormCliente', () => {
  it('valida CUIT correctamente', async () => {
    const wrapper = mount(FormCliente)
    
    const input = wrapper.find('input[name="cuit"]')
    await input.setValue('20123456789')
    
    expect(wrapper.vm.cuitValido).toBe(true)
  })
  
  it('muestra error con CUIT inválido', async () => {
    const wrapper = mount(FormCliente)
    
    const input = wrapper.find('input[name="cuit"]')
    await input.setValue('123')
    await wrapper.find('form').trigger('submit')
    
    expect(wrapper.text()).toContain('CUIT inválido')
  })
})
```

---

## Notas Importantes sobre Seguridad

### 🔒 Certificados y Claves Privadas

**⚠️ NUNCA, BAJO NINGUNA CIRCUNSTANCIA, COMMITEAR:**
- Archivos `.key` (claves privadas)
- Archivos `.crt` (certificados)
- Archivos `.p12` o `.pfx` (keystores)
- Archivos `.pem` (cualquier formato PEM)

**Cómo manejar certificados:**

1. **En .gitignore** (ya incluido):
   ```
   *.key
   *.crt
   *.pem
   *.p12
   *.pfx
   certs/
   !certs/.gitkeep
   ```

2. **Almacenamiento en filesystem:**
   ```python
   # Permisos restrictivos (solo lectura para la app)
   import os
   import stat
   
   cert_path = "/app/certs/certificado.crt"
   os.chmod(cert_path, stat.S_IRUSR)  # 400 - solo lectura para owner
   ```

3. **En BD solo metadatos:**
   ```python
   class Certificado(Base):
       __tablename__ = "certificados"
       
       id = Column(Integer, primary_key=True)
       cuit = Column(String(11), nullable=False)
       alias = Column(String(100))  # "Certificado Producción"
       fecha_emision = Column(DateTime)
       fecha_vencimiento = Column(DateTime)
       archivo_path = Column(String(255))  # Path, NO el contenido
       ambiente = Column(Enum("homologacion", "produccion"))
   ```

### 🔐 Variables Sensibles

**Variable de entorno:**
```bash
# .env (gitignored)
APP_SECRET_KEY=gen3r4r-c0n-secrets.token_urlsafe()
DATABASE_URL=sqlite:///./data/factuflow.db
ARCA_CERTS_PATH=/app/certs
# También acepta AFIP_CERTS_PATH por compatibilidad
```

**NUNCA hardcodear:**
```python
# ❌ MAL
SECRET_KEY = "mi-clave-secreta-123"

# ✅ BIEN
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    secret_key: str
    database_url: str
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### 🔒 Encriptación de Datos Sensibles

Para datos sensibles en BD (ej: datos bancarios de clientes):

```python
from cryptography.fernet import Fernet

class EncryptionService:
    def __init__(self, key: bytes):
        self.cipher = Fernet(key)
    
    def encrypt(self, data: str) -> str:
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        return self.cipher.decrypt(encrypted_data.encode()).decode()
```

### 🛡️ Seguridad en API

- **CORS:** Configurar orígenes permitidos
- **Rate Limiting:** Limitar requests por IP
- **Input Validation:** Siempre validar con Pydantic
- **SQL Injection:** Usar ORM (SQLAlchemy), nunca raw SQL
- **XSS:** Vue.js escapa por default, cuidado con v-html

---

## Convenciones de Respuestas de API

### Estructura de Respuestas Exitosas

```json
{
  "data": {
    "id": 1,
    "nombre": "Juan Pérez",
    "cuit": "20123456789"
  },
  "message": "Cliente creado exitosamente"
}
```

### Estructura de Errores

```json
{
  "error": {
    "code": "CUIT_INVALIDO",
    "message": "El CUIT ingresado no es válido",
    "details": {
      "field": "cuit",
      "value": "123"
    }
  }
}
```

### Códigos HTTP

- `200 OK` - GET exitoso
- `201 Created` - POST exitoso
- `204 No Content` - DELETE exitoso
- `400 Bad Request` - Error de validación
- `401 Unauthorized` - No autenticado
- `403 Forbidden` - No autorizado
- `404 Not Found` - Recurso no encontrado
- `422 Unprocessable Entity` - Error de validación de Pydantic
- `500 Internal Server Error` - Error del servidor

---

## Idioma en el Proyecto

### Documentación de Usuario
- **Español (Argentina)**: README, guías, mensajes de UI
- Usar vocabulario local: "CUIT", "factura", "comprobante"

### Código y Comentarios Técnicos
- **Inglés o Español**: A criterio del desarrollador
- Variables y funciones en inglés es aceptable
- Comentarios y docstrings preferiblemente en español

### Mensajes de UI
- **Español (Argentina)**
- Amigables y claros para usuarios no técnicos

```python
# Ejemplos de mensajes
"El certificado vencerá en 7 días"
"Error al conectar con ARCA. Por favor, verificá tu conexión."
"Factura emitida exitosamente. CAE: 12345678901234"
```

---

## Recursos Útiles

### Documentación AFIP
- [AFIP - Desarrolladores](https://www.afip.gob.ar/ws/)
- [WSAA Especificaciones](https://www.afip.gob.ar/ws/WSAA/Especificacion_Tecnica_WSAA_1.2.0.pdf)
- [WSFEv1 Especificaciones](https://www.afip.gob.ar/ws/WSFEV1/WSFEV1-especificacion.pdf)

### Tecnologías
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Vue.js 3 Docs](https://vuejs.org/)
- [Tailwind CSS](https://tailwindcss.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Pinia](https://pinia.vuejs.org/)

### Herramientas
- [Online CUIT Validator](https://www.cuil.org.ar/)
- [OpenSSL Commands](https://www.openssl.org/docs/manmaster/man1/)

---

## Contacto y Soporte

- **Issues**: [GitHub Issues](https://github.com/Santi-RL/FactuFlow/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Santi-RL/FactuFlow/discussions)
- **Email**: Disponible en el perfil del mantenedor

---

## Principios de Diseño

1. **Simplicidad primero**: Si hay dos formas de hacer algo, elegir la más simple
2. **Usuario no técnico en mente**: La UI debe ser comprensible sin conocimientos de facturación
3. **Seguridad por defecto**: Permisos restrictivos, validación exhaustiva
4. **Self-hosted friendly**: Zero-config cuando sea posible, SQLite por default
5. **Documentación abundante**: Mejor sobre-documentar que sub-documentar

---

**¡Bienvenido a FactuFlow! 🚀**

Si tenés dudas, abrí un issue o discussion en GitHub. Todas las contribuciones son bienvenidas.
