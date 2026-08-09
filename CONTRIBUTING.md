# 🤝 Guía de Contribución - FactuFlow

¡Gracias por tu interés en contribuir a FactuFlow! Este documento te guiará en el proceso.

---

## 📜 Código de Conducta

### Nuestra Promesa

Nos comprometemos a hacer de la participación en este proyecto una experiencia libre de acoso para todos, independientemente de edad, tamaño corporal, discapacidad, etnia, identidad y expresión de género, nivel de experiencia, nacionalidad, apariencia personal, raza, religión o identidad y orientación sexual.

### Nuestros Estándares

**Ejemplos de comportamiento que contribuyen a crear un ambiente positivo:**
- Usar lenguaje acogedor e inclusivo
- Respetar diferentes puntos de vista y experiencias
- Aceptar críticas constructivas de buena manera
- Enfocarse en lo que es mejor para la comunidad
- Mostrar empatía hacia otros miembros de la comunidad

**Ejemplos de comportamiento inaceptable:**
- Uso de lenguaje o imágenes sexualizadas y atención sexual no deseada
- Comentarios insultantes/despectivos y ataques personales o políticos
- Acoso público o privado
- Publicar información privada de otros sin permiso explícito
- Otras conductas que puedan considerarse inapropiadas en un entorno profesional

### Aplicación

Los casos de comportamiento abusivo, acosador o inaceptable pueden reportarse contactando al equipo del proyecto en GitHub Issues. Todas las quejas serán revisadas e investigadas y resultarán en una respuesta apropiada a las circunstancias.

---

## 🐛 Cómo Reportar Bugs

¿Encontraste un bug? ¡Ayudanos a mejorarlo!

### Antes de Reportar

- Verificá que estés usando la última versión de FactuFlow
- Buscá en [Issues existentes](https://github.com/Santi-RL/FactuFlow/issues) para ver si ya fue reportado
- Recopilá información sobre el bug (pasos para reproducir, logs, screenshots)

### Template para Reportar Bugs

```markdown
## Descripción del Bug
Una descripción clara y concisa del problema.

## Pasos para Reproducir
1. Ir a '...'
2. Hacer click en '...'
3. Scrollear hasta '...'
4. Ver error

## Comportamiento Esperado
Descripción clara de lo que esperabas que sucediera.

## Comportamiento Actual
Descripción clara de lo que está sucediendo.

## Screenshots
Si aplica, agregá capturas de pantalla.

## Entorno
- OS: [ej. Ubuntu 22.04]
- Navegador: [ej. Chrome 120]
- Versión de FactuFlow: [ej. 1.0.0]
- Ambiente ARCA: [homologación / producción]

## Logs
```
Pegá acá los logs relevantes
```

## Información Adicional
Cualquier otra información que pueda ser útil.
```

### Creá el Issue

[Reportar Bug](https://github.com/Santi-RL/FactuFlow/issues/new?labels=bug)

---

## 💡 Cómo Proponer Nuevas Features

¿Tenés una idea para mejorar FactuFlow?

### Antes de Proponer

- Revisá el [ROADMAP.md](ROADMAP.md) para ver si ya está planeada
- Buscá en [Issues existentes](https://github.com/Santi-RL/FactuFlow/issues) por propuestas similares
- Pensá si la feature es útil para la mayoría de usuarios o solo para tu caso particular

### Template para Proponer Features

```markdown
## Resumen de la Feature
Descripción breve de la funcionalidad propuesta.

## Problema que Resuelve
Explicá qué problema o necesidad resuelve esta feature.

## Solución Propuesta
Descripción detallada de cómo implementarías esta funcionalidad.

## Alternativas Consideradas
¿Qué otras soluciones consideraste?

## Mockups / Ejemplos
Si aplica, agregá mockups, diagramas o ejemplos de cómo se vería.

## Beneficios
- ¿Quiénes se beneficiarían?
- ¿Es algo que la mayoría de usuarios usaría?

## Complejidad Estimada
Bajo / Medio / Alto (opcional)
```

### Creá el Issue

[Proponer Feature](https://github.com/Santi-RL/FactuFlow/issues/new?labels=enhancement)

---

## 🔧 Flujo interno de trabajo

`main` es la única rama permanente y representa el código aceptado. El trabajo
interno se realiza en una rama temporal corta por unidad lógica, normalmente una
sola activa a la vez:

1. sincronizar y verificar que `main` esté limpia;
2. crear la rama temporal desde `main`;
3. implementar, probar y documentar una única unidad;
4. ejecutar la puerta de alineación documental antes del commit final;
5. abrir un pull request hacia `main` con la matriz documental completa;
6. revisar nuevamente el rango completo antes de marcarlo como listo;
7. esperar todos los checks obligatorios;
8. hacer merge solo con CI verde y riesgos aceptados;
9. verificar `main`, incluida su documentación, y eliminar la rama remota y
   local.

La rama temporal no es una versión ni se despliega. Las versiones se identifican
únicamente mediante tags/releases sobre commits aceptados de `main`. Los cambios
Nivel 0 usan una CI liviana, pero conservan PR, merge y eliminación para que
`main` nunca reciba cambios sin una verificación previa.

Antes de empezar:

```bash
git status --short --branch
git fetch origin
git rev-list --left-right --count origin/main...HEAD
```

Si hay commits sin publicar, cambios pendientes o una rama anterior abierta,
cerrar ese ciclo antes de acumular otra unidad. No revertir trabajo del usuario
que no pertenezca al alcance.

Después de implementar:

- ejecutar la verificación proporcional definida en
  `docs/agents/change-quality-gates.md`;
- completar la puerta documental después de estabilizar comportamiento y tests,
  antes de `autoreview`, staging y commit. Los documentos deben describir el
  estado objetivo de `main`, distinguirlo de la versión desplegada y no
  conservar nombres o estados de la rama temporal;
- preparar uno o pocos commits con unidad lógica y Conventional Commits;
- revisar que no haya evidencia privada;
- solicitar autorización antes de push, merge o eliminación remota, salvo que el
  usuario ya haya autorizado explícitamente completar todo el ciclo.

## 🔧 Proceso de Pull Requests

El proceso interno usa ramas temporales del repositorio. Las colaboraciones
externas pueden usar un fork, pero deben cumplir las mismas puertas y completar
la plantilla `.github/pull_request_template.md`.
### 1. Fork y Clone

```bash
# Hacé fork del repo en GitHub, luego:
git clone https://github.com/TU-USUARIO/FactuFlow.git
cd FactuFlow

# Agregá el repositorio original como upstream
git remote add upstream https://github.com/Santi-RL/FactuFlow.git
```

### 2. Crear Branch

```bash
# Sincronizá con main
git checkout main
git pull upstream main

# Creá tu branch
git checkout -b tipo/descripcion-breve
```

**Convención de nombres de branches:**
- `feat/nombre-feature` - Nueva funcionalidad
- `fix/descripcion-bug` - Corrección de bug
- `docs/tema` - Documentación
- `refactor/componente` - Refactorización
- `test/componente` - Agregar tests
- `chore/tarea` - Tareas de mantenimiento

**Ejemplos:**
```bash
git checkout -b feat/wizard-certificados
git checkout -b fix/calculo-iva-factura-b
git checkout -b docs/guia-instalacion
```

### 3. Desarrollar

- Escribí código limpio y bien documentado
- Seguí las [convenciones de código](#estándares-de-código)
- Agregá o actualizá tests
- Actualizá documentación si es necesario

### 4. Tests

#### CI local completo

Al cerrar una unidad funcional o sensible, ejecutar la matriz local completa:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/ci-local.ps1
```

El script ejecuta controles de repositorio, Ruff, Black, backend, frontend, E2E
y auditorías de dependencias. Continúa después de un fallo para mostrar el
resumen completo, pero devuelve un código distinto de cero si cualquier puerta
obligatoria falla. El log local queda en `.tmp/ci-local.log`.

GitHub ejecuta la misma matriz para cualquier archivo de runtime o configuración.
Si el cambio contiene únicamente Markdown o `.gitignore`, todos los jobs
informan éxito mediante el recorrido Nivel 0 sin instalar dependencias ni correr
suites costosas.

Si se agregan o modifican pruebas o pasos de `.github/workflows/ci.yml`, mantener
alineados `scripts/ci-local.ps1`, los scripts raíz y
`docs/agents/change-quality-gates.md`.

Controles principales de backend:

```bash
cd backend
ruff check app/ tests/
black --check app/ tests/
pytest tests/ -v --cov=app --cov-report=xml
```

Las integraciones PostgreSQL que recrean el schema usan exclusivamente
`FACTUFLOW_TEST_POSTGRES_URL` con driver `postgresql` o
`postgresql+asyncpg`, host loopback exacto (`localhost`, `127.0.0.1` o `::1`),
base exacta `factuflow_integration_test`, sin query/options, más
`FACTUFLOW_TEST_POSTGRES_ALLOW_SCHEMA_RESET=1`. El harness revalida esas
condiciones en cada punto destructivo. No se acepta una base cuyo nombre solo
“parezca de prueba”. La matriz CI y el uso seguro están documentados en
[`docs/agents/testing.md`](docs/agents/testing.md).

Controles principales de frontend:

```bash
cd frontend
npm run lint:check
npm run type-check
npm run build
npm run test:unit
npm run test:e2e
```
### 5. Lint y formato

Usar checks no destructivos antes de integrar:

```bash
npm run lint
npm run backend:format:check
```

Los comandos con `--fix` o `--write` se reservan para cuando se quiera modificar
archivos y siempre requieren revisar el diff resultante.
### 6. Commit

Seguí la convención de [Conventional Commits](#conventional-commits) en español.

```bash
git add .
git commit -m "feat: agregar wizard de certificados ARCA"
```

### 7. Push

```bash
git push origin feat/wizard-certificados
```

### 8. Abrir Pull Request

1. Andá a tu fork en GitHub
2. Click en "Compare & pull request"
3. Completá `.github/pull_request_template.md` con nivel de riesgo, autoridad
   funcional, invariantes, evidencia, matriz documental, riesgo residual y
   recuperación. Si usás un cuerpo personalizado o una API, conservá las mismas
   secciones y justificá cada `No aplica`.
4. Click en "Create pull request"

### 9. Code Review

- Respondé a comentarios de reviewers
- Hacé los cambios solicitados
- Publicá correcciones en la misma rama temporal; el PR y la CI se actualizarán automáticamente

### 10. Merge

Una vez aprobados todos los checks y aceptados los riesgos, se hace merge a `main`, se verifica el commit resultante y se elimina la rama temporal local y remota.

---

## 📋 Estándares de Código

### Python (Backend)

#### Estilo
- **PEP8** obligatorio
- Formatear con **black** (línea de 88 caracteres)
- Lint con **pylint** o **ruff**

#### Type Hints
Obligatorios en código nuevo o modificado para funciones, clases y helpers
públicos. El código histórico se normaliza cuando se toca o en tareas técnicas
dedicadas.

```python
# ✅ BIEN
def calcular_total(items: list[dict], iva: float = 21.0) -> float:
    """Calcula el total con IVA."""
    subtotal = sum(item['precio'] * item['cantidad'] for item in items)
    return subtotal * (1 + iva / 100)

# ❌ MAL
def calcular_total(items, iva=21):
    subtotal = sum(item['precio'] * item['cantidad'] for item in items)
    return subtotal * (1 + iva / 100)
```

#### Docstrings
En código nuevo o modificado, usar docstrings en español para funciones,
clases y helpers públicos. Preferir estilo Google o NumPy:

```python
def emitir_factura(cliente_id: int, items: list[dict]) -> Comprobante:
    """
    Emite una factura electrónica en ARCA.
    
    Args:
        cliente_id: ID del cliente en la base de datos
        items: Lista de items con precio, cantidad e IVA
        
    Returns:
        Comprobante con CAE asignado
        
    Raises:
        ARCAError: Si ARCA rechaza el comprobante
        ValidationError: Si los datos son inválidos
    """
    pass
```

#### Imports
```python
# Orden: stdlib, third-party, local
import os
from datetime import datetime

from fastapi import FastAPI
from sqlalchemy import Column

from app.models import Cliente
from app.services import FacturaService
```

### Fechas

FactuFlow es una aplicación argentina. En UI, documentación de usuario,
confirmaciones, reportes y PDFs, las fechas visibles deben mostrarse en formato
`DD/MM/AAAA`.

Para código nuevo o modificado:
- Soportar explícitamente `DD/MM/AAAA` cuando se acepten fechas como texto de
  usuario o como texto ya formateado para usuarios argentinos.
- Mantener `YYYY-MM-DD`, ISO datetime o `CbteFch` `YYYYMMDD` solo como formatos
  técnicos de contratos internos, backend, base de datos o ARCA.
- No usar `new Date(string)` ni `Date.parse` para strings ambiguos o de usuario.
  Parsear por formato conocido y validar calendario real.
- No normalizar silenciosamente fechas inválidas como `31/02/2026`: rechazarlas
  o conservarlas sin inventar otra fecha, según el contrato del flujo.
- Agregar tests para `DD/MM/AAAA`, `YYYY-MM-DD`, fechas inválidas, strings
  vacíos y casos de timezone si se aceptan ISO datetime.

### Vue.js (Frontend)

#### Estilo de Componentes
- **Composition API** con `<script setup>`
- TypeScript cuando sea posible
- Props con validación

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
  const c = props.cliente.cuit
  return `${c.slice(0, 2)}-${c.slice(2, 10)}-${c.slice(10)}`
})
</script>

<template>
  <div class="cliente-card">
    <h3>{{ cliente.nombre }}</h3>
    <p>{{ cuitFormateado }}</p>
  </div>
</template>
```

#### Nombrado
- **Componentes**: PascalCase (`BotonPrimario.vue`)
- **Props**: camelCase (`nombreCliente`)
- **Events**: kebab-case (`@cliente-guardado`)
- **CSS classes**: kebab-case (`cliente-card`)

#### Tailwind CSS
- Preferir utilidades sobre CSS custom
- Orden de clases: layout → spacing → colors → typography

```vue
<!-- ✅ BIEN -->
<button class="flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600">
  Click
</button>

<!-- ❌ EVITAR (demasiado CSS custom) -->
<button class="mi-boton-custom">
  Click
</button>
```

---

## 📝 Conventional Commits

Usamos **Conventional Commits** en **español**.

### Formato

```
<tipo>(<scope>): <descripción>

[cuerpo opcional]

[footer opcional]
```

### Tipos

- `feat`: Nueva funcionalidad
- `fix`: Corrección de bug
- `docs`: Documentación
- `style`: Formato (no afecta funcionalidad)
- `refactor`: Refactorización de código
- `test`: Agregar o modificar tests
- `chore`: Tareas de mantenimiento (deps, config, etc.)
- `perf`: Mejora de performance

### Ejemplos

```bash
# Nueva feature
feat: agregar wizard de certificados ARCA
feat(frontend): implementar modal de confirmación
feat(api): endpoint para consultar comprobantes

# Bug fix
fix: corregir cálculo de IVA en facturas tipo B
fix(wsfe): manejar timeout en llamadas a ARCA
fix(ui): alinear botones en formulario de cliente

# Documentación
docs: actualizar guía de instalación con Docker
docs(api): documentar endpoint de facturas
docs: agregar ejemplos de uso en README

# Refactorización
refactor: extraer lógica de WSAA a servicio separado
refactor(models): simplificar relaciones de SQLAlchemy

# Tests
test: agregar tests para modelo Comprobante
test(wsaa): mockear respuesta de ARCA

# Chore
chore: actualizar dependencias de FastAPI
chore: configurar GitHub Actions para CI
```

### Scope (opcional)

El scope puede ser:
- Componente: `frontend`, `backend`, `api`, `ui`
- Módulo: `wsfe`, `wsaa`, `clientes`, `certificados`
- Tipo de archivo: `docs`, `tests`, `config`

### Breaking Changes

Si tu cambio rompe compatibilidad:

```bash
feat!: cambiar estructura de respuesta de API

BREAKING CHANGE: El campo "items" ahora se llama "lineas"
```

---

## 🧪 Testing

### Cobertura Mínima

- Backend: **80%** de coverage
- Frontend: **70%** de coverage (lógica de negocio)

### Backend (pytest)

```python
# tests/test_clientes.py
def test_crear_cliente_valido(client, db):
    """Debe crear un cliente con datos válidos."""
    response = client.post(
        "/api/v1/clientes",
        json={
            "nombre": "Juan Pérez",
            "cuit": "20123456789",
            "email": "juan@example.com"
        }
    )
    assert response.status_code == 201
    assert response.json()["nombre"] == "Juan Pérez"

def test_crear_cliente_cuit_invalido(client, db):
    """No debe crear cliente con CUIT inválido."""
    response = client.post(
        "/api/v1/clientes",
        json={"nombre": "Juan", "cuit": "123"}
    )
    assert response.status_code == 422
```

### Frontend (Vitest)

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
})
```

---

## 🔒 Consideraciones de Seguridad

### ⚠️ NUNCA Commitear

- Certificados (.crt, .key, .pem, .p12, .pfx)
- Claves privadas
- Archivos .env con datos reales
- Credenciales de ARCA
- Tokens o secrets
- CUITs reales, nombres de clientes o emisores reales
- CAEs reales o evidencia fiscal privada
- Bases locales, backups, dumps, logs de producción
- Excel/PDF de clientes, constancias ARCA reales, capturas privadas, trazas o
  videos de QA/debug

### Verificar Antes de Commit

```bash
# Revisar qué se va a commitear
git status --short --untracked-files=all
git diff --cached

# Verificar que no haya archivos sensibles
git grep -n -E "[0-9]{11}|password|secret|token|CAE|BEGIN (RSA |EC |)PRIVATE KEY"
```

Usar datos sintéticos en tests, docs y ejemplos. Si una corrida real deja
evidencia necesaria para continuidad operativa, guardarla fuera del repo en una
carpeta ignorada y documentar solo un resumen redactado.

### Reportar Vulnerabilidades

Si encontrás una vulnerabilidad de seguridad:
1. **NO abras un issue público**
2. Contactá a los mantenedores por privado
3. Describí la vulnerabilidad en detalle
4. Esperá a que se fixee antes de divulgar

---

## 📚 Recursos Útiles

### Documentación
- [FastAPI](https://fastapi.tiangolo.com/)
- [Vue.js 3](https://vuejs.org/)
- [Tailwind CSS](https://tailwindcss.com/)
- [ARCA Webservices](https://www.arca.gob.ar/ws/) (ex-AFIP)

### Herramientas
- [Black Playground](https://black.vercel.app/)
- [Vue Devtools](https://devtools.vuejs.org/)
- [Postman](https://www.postman.com/) (para probar API)

---

## 🌟 Reconocimientos

Todos los contribuidores serán reconocidos en:
- README.md (sección de Contributors)
- Release notes
- Changelog

---

## 📞 Contacto

- **Issues**: [GitHub Issues](https://github.com/Santi-RL/FactuFlow/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Santi-RL/FactuFlow/discussions)

---

## ❓ Preguntas Frecuentes

### ¿Puedo trabajar en un issue que ya está asignado?
No. Si un issue está asignado, alguien ya está trabajando en él. Podés preguntar en el issue si necesita ayuda.

### ¿Puedo trabajar en múltiples features a la vez?
Preferiblemente no. Enfocate en una feature/fix a la vez para facilitar el review.

### ¿Cuánto tiempo toma que revisen mi PR?
Tratamos de revisar PRs en 2-3 días. Si pasó más tiempo, podés pedir review en el PR.

### Mi PR fue rechazado, ¿qué hago?
Leé los comentarios del reviewer, hacé los cambios solicitados y volvé a solicitar review. No te desanimes, es parte del proceso.

### ¿Puedo contribuir si soy principiante?
¡Por supuesto! Buscá issues etiquetados con `good first issue` o `help wanted`.

---

**¡Gracias por contribuir a FactuFlow! 🚀**

Cada contribución, por pequeña que sea, hace la diferencia.
