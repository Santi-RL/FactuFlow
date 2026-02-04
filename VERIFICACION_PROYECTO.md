# 🔍 Verificación Total del Proyecto FactuFlow

**Fecha**: 4 de Febrero de 2026  
**Versión Analizada**: 0.1.0  
**Autor**: Auditoría Automatizada

---

## 📋 Resumen Ejecutivo

Se ha realizado una verificación exhaustiva del proyecto FactuFlow, un sistema de facturación electrónica con integración ARCA (ex-AFIP). Este documento detalla los hallazgos organizados en:

1. **Bugs y Problemas Detectados** - Requieren corrección antes de producción
2. **Modificaciones Recomendadas** - Mejoras de seguridad, logging y usabilidad
3. **Oportunidades de Optimización** - Mejoras de rendimiento y mantenibilidad

---

## ✅ Estado de Tests

### Backend (Python/FastAPI)
```
Total: 84 tests
Resultado: ✅ 84 passed (100%)
Tiempo: 11.47 segundos
```

### Frontend (Vue/TypeScript)
```
Tests unitarios: ⚠️ Sin tests configurados
Tests E2E: Configurados con Playwright pero no ejecutados
```

---

## 🐛 Bugs y Problemas Detectados

### 🔴 CRÍTICOS (Corregir antes de producción)

#### 1. Falta de Configuración de Logging Centralizado
**Ubicación**: `backend/app/main.py`  
**Problema**: El proyecto usa `logging.getLogger(__name__)` en varios módulos pero no hay configuración centralizada del logger. Los logs no se guardan en archivo ni tienen formato consistente.

**Impacto**: En producción no habrá forma de revisar logs históricos para detectar problemas de facturación.

**Solución Recomendada**:
```python
# En main.py agregar al inicio
import logging

logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(settings.log_file or 'logs/factuflow.log')
    ]
)
```

---

#### 2. Falta de Logging en Operaciones Críticas de Facturación
**Ubicación**: `backend/app/services/facturacion_service.py`  
**Problema**: El método `emitir_comprobante` no registra suficiente información sobre las operaciones realizadas.

**Impacto**: Cuando un cliente reporte un problema con una factura, no habrá registro detallado para investigar.

**Líneas Afectadas**:
- Línea 57-158: El flujo completo de emisión solo registra errores, no operaciones exitosas
- No se registra el CAE obtenido ni el número de comprobante emitido

**Solución Recomendada**:
```python
# Agregar después de línea 125 (emisión exitosa)
logger.info(
    f"Comprobante emitido: Tipo={request.tipo_comprobante} "
    f"PV={punto_venta.numero} Nro={proximo} CAE={resultado.cae} "
    f"Cliente={request.razon_social} Total={totales['total']}"
)
```

---

#### 3. Discrepancia entre Modelo Cliente en BD vs FacturacionService
**Ubicación**: `backend/app/services/facturacion_service.py` (líneas 396-410)  
**Problema**: El modelo `Cliente` tiene campos `razon_social` y `numero_documento`, pero el servicio de facturación intenta usar `nombre`, `cuit` y `dni` que no existen.

**Código Problemático** (línea 399-406):
```python
cliente = Cliente(
    empresa_id=request.empresa_id,
    nombre=request.razon_social,  # ❌ Cliente no tiene 'nombre', tiene 'razon_social'
    cuit=request.numero_documento if request.tipo_documento == 80 else None,  # ❌ No existe 'cuit'
    dni=request.numero_documento if request.tipo_documento == 96 else None,   # ❌ No existe 'dni'
    ...
)
```

**Modelo Real** (`backend/app/models/cliente.py`):
```python
razon_social = Column(String(255), nullable=False)
tipo_documento = Column(String(20), nullable=False)
numero_documento = Column(String(20), nullable=False)
```

**Impacto**: La creación automática de clientes fallará en runtime.

---

#### 4. Atributo `numero_documento` falta en Modelo Cliente
**Ubicación**: `backend/app/services/pdf_service.py` (línea 98)  
**Problema**: Se accede a `comprobante.cliente.numero_documento` pero este atributo no está definido correctamente en todos los lugares.

```python
"nroDocRec": int(comprobante.cliente.numero_documento.replace("-", "")),
```

**Impacto**: Generación de PDFs podría fallar para algunos clientes.

---

#### 5. datetime.utcnow() está deprecado
**Ubicación**: Múltiples archivos  
- `backend/app/core/security.py` (líneas 63, 65)
- `backend/app/models/*.py` (todos los modelos)

**Problema**: Python 3.12+ marca `datetime.utcnow()` como deprecado en favor de `datetime.now(timezone.utc)`.

**Impacto**: Warnings en producción y eventual rotura en futuras versiones de Python.

---

### 🟠 MODERADOS (Corregir en próxima iteración)

#### 6. Falta de Autenticación en Endpoint PDF
**Ubicación**: `backend/app/api/pdf.py`  
**Problema**: Los endpoints de PDF no verifican que el usuario tenga acceso al comprobante solicitado.

```python
@router.get("/comprobante/{comprobante_id}")
async def descargar_pdf_comprobante(
    comprobante_id: int, 
    db: AsyncSession = Depends(get_db)  # ⚠️ Falta Depends(get_current_user)
):
```

**Impacto**: Cualquier persona podría descargar cualquier factura conociendo el ID.

---

#### 7. Falta de Validación CUIT con Dígito Verificador
**Ubicación**: `backend/app/schemas/comprobante.py`  
**Problema**: El campo `numero_documento` no valida el algoritmo de verificación de CUIT argentino.

**Impacto**: Se podrían emitir facturas con CUITs inválidos que ARCA rechazará.

**Solución Recomendada**: Usar la función `validate_cuit` existente en `backend/app/arca/utils.py`:
```python
@field_validator("numero_documento")
@classmethod
def validate_cuit(cls, v, info):
    if info.data.get("tipo_documento") == 80:  # CUIT
        from app.arca.utils import validate_cuit
        if not validate_cuit(v):
            raise ValueError("CUIT inválido")
    return v
```

---

#### 8. Hardcoded TODO en Servicio de Facturación
**Ubicación**: `backend/app/services/facturacion_service.py`  
**Problema**: Línea 82-83 tiene ambiente hardcodeado:
```python
ambiente=ArcaAmbiente.HOMOLOGACION,  # TODO: Obtener de empresa
```

**Impacto**: Todas las facturas irán a homologación, nunca a producción.

---

#### 9. Puntos de Venta Hardcodeados en Frontend
**Ubicación**: `frontend/src/views/comprobantes/ComprobanteNuevoView.vue` (líneas 67-69)  
**Problema**:
```javascript
puntosVenta.value = [
  { id: 1, numero: 1, descripcion: 'Punto de Venta 1' }
]
```

**Impacto**: Los usuarios no podrán usar puntos de venta reales.

---

#### 10. Variable No Usada que Podría Indicar Lógica Incompleta
**Ubicación**: `backend/app/api/certificados.py` (línea 416)  
```python
ticket = await wsaa_client.login(...)  # F841: never used
```

**Impacto**: Posible falta de verificación de validez del ticket.

---

### 🟡 MENORES (Mejorar cuando sea posible)

#### 11. Errores de Tipo (mypy) en Múltiples Archivos
**Total**: 57 errores de tipos  
**Archivos Principales**:
- `app/services/reportes_service.py` (15 errores)
- `app/services/certificados_service.py` (8 errores)
- `app/arca/wsfev1.py` (12 errores)

**Ejemplos**:
- Uso de `Column[int]` donde se espera `int`
- Incompatibilidad entre tipos de retorno

---

#### 12. Imports No Usados (Ruff)
**Total**: 32 imports no usados  
**Archivos Principales**:
- `app/api/certificados.py`
- `app/api/comprobantes.py`
- `app/arca/crypto.py`
- `tests/test_*.py`

---

#### 13. Comparación con True (PEP8)
**Ubicación**: `backend/app/api/arca.py` (línea 78)  
```python
Certificado.activo == True  # Debería ser: Certificado.activo.is_(True)
```

---

## 🔒 Seguridad

### Vulnerabilidades en Dependencias

#### Backend (Python)
- ✅ **Pillow 10.3.0**: Actualizado (vulnerabilidad buffer overflow corregida)
- ✅ **WeasyPrint 68.0**: Actualizado (vulnerabilidad SSRF corregida)
- ✅ No se detectaron vulnerabilidades conocidas

#### Frontend (Node.js)
```
7 vulnerabilidades de severidad MODERADA:

1. esbuild <=0.24.2 - Cualquier sitio web puede enviar requests al servidor de desarrollo
2. vite 0.11.0 - 6.1.6 - Depende de esbuild vulnerable
3. vitest - Depende de vite vulnerable
4. vue-template-compiler >=2.0.0 - XSS del lado cliente
5. @vue/language-core - Depende de vue-template-compiler vulnerable
6. vue-tsc - Depende de @vue/language-core vulnerable
```

**Corrección**: Ejecutar `npm audit fix --force` (requiere breaking changes)

### Recomendaciones de Seguridad

#### 1. Secret Key por Defecto
**Ubicación**: `backend/app/core/config.py` (línea 25-28)  
**Problema**:
```python
secret_key: str = Field(
    default="cambiar-esto-en-produccion-usar-secrets-token_urlsafe",
    ...
)
```

**Riesgo**: Si no se configura en producción, los JWT serán predecibles.

**Solución**: Validar que no sea el valor por defecto en producción:
```python
@field_validator("secret_key")
@classmethod
def check_secret_key(cls, v, info):
    if info.data.get("app_env") == "production":
        if "cambiar" in v.lower():
            raise ValueError("APP_SECRET_KEY debe configurarse en producción")
    return v
```

---

#### 2. Almacenamiento de Claves Privadas
**Ubicación**: `backend/app/services/certificados_service.py`  
**Observación**: Las claves privadas se guardan con permisos 0o400, lo cual es correcto.

**Mejora Recomendada**: Encriptar las claves en reposo con una master key.

---

#### 3. Rate Limiting No Implementado
**Impacto**: El endpoint `/api/auth/login` es vulnerable a ataques de fuerza bruta.

**Solución Recomendada**: Implementar rate limiting con `slowapi` o similar.

---

## 📝 Logging Recomendado

### Eventos que Deben Registrarse

#### OBLIGATORIOS (Críticos para auditoría fiscal)
1. ✅ Emisión de comprobantes (CAE, número, monto)
2. ✅ Errores de conexión con ARCA
3. ❌ **FALTA**: Consultas de comprobantes
4. ❌ **FALTA**: Acceso a PDFs
5. ❌ **FALTA**: Intentos de login fallidos

#### RECOMENDADOS (Para debugging)
1. ❌ **FALTA**: Inicio/fin de sesiones
2. ❌ **FALTA**: Cambios en configuración de empresa
3. ❌ **FALTA**: Modificación de certificados

### Formato de Log Sugerido
```python
# Estructura para auditoría
{
    "timestamp": "2026-02-04T20:00:00Z",
    "level": "INFO",
    "module": "facturacion",
    "action": "emitir_comprobante",
    "user_id": 1,
    "empresa_id": 1,
    "data": {
        "tipo": 6,
        "numero": 100,
        "cae": "12345678901234",
        "total": 1500.00
    }
}
```

---

## 👥 Usabilidad para Usuarios No Técnicos

### Problemas Detectados en UI

#### 1. Mensajes de Error Técnicos
**Ubicación**: `frontend/src/views/comprobantes/ComprobanteNuevoView.vue`  
**Problema** (línea 235):
```javascript
alert(`❌ Error al emitir comprobante:\n\n${resultado.mensaje}\n\n${resultado.errores.join('\n')}`)
```

**Mejora**: Reemplazar `alert()` por un modal más amigable con sugerencias de solución.

---

#### 2. Falta de Tooltips y Ayuda Contextual
**Problema**: Campos como "Concepto" o "Tipo de Comprobante" no tienen explicaciones para usuarios sin experiencia contable.

**Mejora Recomendada**:
- Agregar iconos de ayuda (?) con tooltips explicativos
- Ejemplo: "Concepto: Productos (bienes materiales), Servicios (trabajo realizado), o ambos"

---

#### 3. Warnings en Props de Componentes Vue
**Total**: 14 warnings de ESLint  
**Problema**: Props sin valores por defecto pueden causar errores visuales.

**Archivos Afectados**:
- `BaseInput.vue`
- `BaseSelect.vue`
- `BaseCard.vue`
- `BaseAlert.vue`
- `BaseModal.vue`
- `Pagination.vue`

---

#### 4. Falta de Validación en Tiempo Real
**Ubicación**: Formulario de nueva factura  
**Problema**: La validación solo ocurre al intentar emitir.

**Mejora**: Validar mientras el usuario escribe (debounced) para:
- CUIT (validar dígito verificador)
- Montos (formato correcto)
- Fechas (no futuras para servicios ya prestados)

---

#### 5. Confirmación Débil para Acciones Irreversibles
**Ubicación**: `ComprobanteNuevoView.vue` (línea 246)
```javascript
if (confirm('¿Está seguro que desea cancelar?...'))
```

**Problema**: Para emitir una factura real (operación irreversible y con consecuencias legales) solo hay un modal simple.

**Mejora Recomendada**:
- Modal de doble confirmación
- Checkbox: "Entiendo que esta factura será reportada a ARCA"
- Resumen claro de todos los datos antes de confirmar

---

## ⚡ Oportunidades de Optimización

### Performance

#### 1. Consultas N+1 en Listados
**Ubicación**: `backend/app/api/comprobantes.py` (línea 54-58)  
**Problema**: Se usa `joinedload` correctamente, pero se podría optimizar más.

**Mejora**: Para listados grandes, usar paginación del lado de base de datos con `selectinload` para relaciones.

---

#### 2. Cache de Tipos de ARCA
**Ubicación**: `backend/app/api/arca.py`  
**Problema**: Cada llamada a `/api/arca/tipos-comprobante` hace una request a ARCA.

**Mejora**: Cachear los tipos (cambian muy raramente) con TTL de 24 horas:
```python
from functools import lru_cache

@lru_cache(maxsize=1, ttl=86400)
async def get_cached_tipos_cbte():
    ...
```

---

#### 3. Generación de PDF
**Ubicación**: `backend/app/services/pdf_service.py`  
**Observación**: WeasyPrint es relativamente lento.

**Mejora a Futuro**: Para alto volumen, considerar:
- Pre-generar PDFs cuando se emite el comprobante
- Usar worker en background (Celery/RQ)
- Cachear PDFs generados

---

### Mantenibilidad

#### 1. Falta de Tests de Frontend
**Estado Actual**: 0 tests unitarios  
**Recomendación**: Agregar tests para:
- Componentes UI básicos
- Stores (auth, comprobantes)
- Servicios de API

---

#### 2. Falta de Tests de Integración
**Recomendación**: Agregar tests que verifiquen:
- Flujo completo de emisión de factura (mock de ARCA)
- Autenticación end-to-end
- Generación de PDF

---

#### 3. Documentación de API Incompleta
**Problema**: Los endpoints tienen docstrings pero faltan ejemplos de uso.

**Mejora**: Agregar examples en los schemas de Pydantic:
```python
class EmitirComprobanteRequest(BaseModel):
    class Config:
        json_schema_extra = {
            "example": {
                "empresa_id": 1,
                "tipo_comprobante": 6,
                ...
            }
        }
```

---

#### 4. Inconsistencia en Nomenclatura AFIP vs ARCA
**Observación**: El código mezcla nomenclatura:
- Variables de entorno: `AFIP_*`
- Código nuevo: `ARCA_*`
- Comentarios: mezcla

**Recomendación**: Seguir la guía en `AGENTS.md`:
- ARCA para textos públicos y código nuevo
- AFIP solo para variables legacy

---

## 📊 Resumen de Acciones Requeridas

### Antes de Producción (BLOQUEANTES)
| # | Acción | Prioridad | Esfuerzo |
|---|--------|-----------|----------|
| 1 | Configurar logging centralizado | 🔴 Alta | 2h |
| 2 | Corregir modelo Cliente en facturación | 🔴 Alta | 1h |
| 3 | Implementar autenticación en endpoint PDF | 🔴 Alta | 30m |
| 4 | Corregir ambiente hardcodeado en facturación | 🔴 Alta | 15m |
| 5 | Actualizar dependencias frontend (npm audit fix) | 🔴 Alta | 1h |

### Después del Primer Deploy (IMPORTANTES)
| # | Acción | Prioridad | Esfuerzo |
|---|--------|-----------|----------|
| 6 | Validar CUIT con dígito verificador | 🟠 Media | 2h |
| 7 | Implementar rate limiting en login | 🟠 Media | 2h |
| 8 | Cargar puntos de venta reales en frontend | 🟠 Media | 4h |
| 9 | Mejorar mensajes de error en UI | 🟠 Media | 4h |
| 10 | Agregar tests de frontend | 🟠 Media | 8h |

### Mejoras Continuas (DESEABLES)
| # | Acción | Prioridad | Esfuerzo |
|---|--------|-----------|----------|
| 11 | Corregir errores de mypy | 🟡 Baja | 4h |
| 12 | Limpiar imports no usados | 🟡 Baja | 1h |
| 13 | Agregar tooltips de ayuda en UI | 🟡 Baja | 4h |
| 14 | Cachear tipos de ARCA | 🟡 Baja | 2h |
| 15 | Deprecar datetime.utcnow() | 🟡 Baja | 2h |

---

## ✅ Aspectos Positivos del Proyecto

1. **Arquitectura Clara**: Separación adecuada entre API, servicios y modelos
2. **Tests Backend Completos**: 84 tests cubriendo funcionalidad core
3. **Manejo de Errores ARCA**: Excepciones personalizadas y bien estructuradas
4. **Seguridad Base**: JWT, bcrypt, permisos en archivos de certificados
5. **Documentación**: Buenos docstrings y estructura de carpetas clara
6. **Vulnerabilidades Backend Corregidas**: Pillow y WeasyPrint actualizados

---

## 🎯 Conclusión

El proyecto FactuFlow tiene una base sólida pero requiere **correcciones críticas** antes de entrar en producción, especialmente:

1. **Logging**: Indispensable para auditoría fiscal
2. **Bug en creación de clientes**: Impedirá funcionamiento básico
3. **Autenticación en PDFs**: Riesgo de exposición de datos
4. **Ambiente de producción**: Actualmente todo va a homologación

Con las correcciones indicadas como "BLOQUEANTES", el sistema estaría en condiciones de iniciar pruebas de producción con usuarios reales.

---

*Documento generado automáticamente. Última actualización: 4 de Febrero de 2026*
