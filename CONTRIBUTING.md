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

## 🔧 Proceso de Pull Requests

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

#### CI local (mismo alcance que GitHub Actions)

Antes de commitear, ejecutá el **CI local** que replica los mismos pasos del workflow de GitHub Actions:

```bash
powershell -ExecutionPolicy Bypass -File scripts/ci-local.ps1
```

El log queda en `.tmp/ci-local.log` y **se sobrescribe en cada ejecución**. El script **no se detiene** ante un fallo: ejecuta todas las etapas y muestra un **resumen final** con OK/WARN/FAIL. El exit code será distinto de 0 si hubo fallas.

**Regla de sincronía obligatoria:** si agregás/modificás tests o pasos en `.github/workflows/ci.yml`, **tenés que** reflejar lo mismo en `scripts/ci-local.ps1` (y viceversa). El CI de GitHub y el CI local deben ejecutar **exactamente las mismas pruebas**.

**Backend:**
```bash
cd backend
pytest tests/ -v --cov=app
```

**Frontend:**
```bash
cd frontend
npm run test
npm run type-check  # Si usás TypeScript
```

### 5. Lint y Formato

**Backend:**
```bash
cd backend
black app/ tests/
pylint app/
```

**Frontend:**
```bash
cd frontend
npm run lint
npm run format
```

### 6. Commit

Seguí la convención de [Conventional Commits](#conventional-commits) en español.

```bash
git add .
git commit -m "feat: agregar wizard de certificados AFIP"
```

### 7. Push

```bash
git push origin feat/wizard-certificados
```

### 8. Abrir Pull Request

1. Andá a tu fork en GitHub
2. Click en "Compare & pull request"
3. Completá el template del PR:

```markdown
## Descripción
¿Qué hace este PR?

## Tipo de Cambio
- [ ] Bug fix (cambio que corrige un issue)
- [ ] Nueva feature (cambio que agrega funcionalidad)
- [ ] Breaking change (cambio que rompe compatibilidad)
- [ ] Documentación

## Checklist
- [ ] Mi código sigue el estilo del proyecto
- [ ] Revisé mi propio código
- [ ] Comenté el código en partes complicadas
- [ ] Actualicé la documentación
- [ ] Mis cambios no generan nuevas advertencias
- [ ] Agregué tests que prueban mi fix/feature
- [ ] Tests nuevos y existentes pasan localmente
- [ ] Cambios dependientes ya fueron mergeados

## Issue Relacionado
Closes #123
Fixes #456

## Screenshots (si aplica)
[Agregar capturas de pantalla de cambios visuales]

## Notas Adicionales
Información extra que los reviewers deberían saber.
```

4. Click en "Create pull request"

### 9. Code Review

- Respondé a comentarios de reviewers
- Hacé los cambios solicitados
- Pushea los cambios (se actualizarán automáticamente en el PR)

### 10. Merge

Una vez aprobado, un mantenedor hará merge de tu PR. ¡Gracias por tu contribución! 🎉

---

## 📋 Estándares de Código

### Python (Backend)

#### Estilo
- **PEP8** obligatorio
- Formatear con **black** (línea de 88 caracteres)
- Lint con **pylint** o **ruff**

#### Type Hints
Obligatorios en todas las funciones:

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
En español, estilo Google o NumPy:

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

### Verificar Antes de Commit

```bash
# Revisar qué se va a commitear
git status
git diff --cached

# Verificar que no haya archivos sensibles
grep -r "password\|secret\|key" --include="*.py" --include="*.js"
```

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
