# Rediseño UX de carga masiva

Última actualización: 2026-06-26

## Alcance

Este documento define el diagnóstico y las instrucciones de rediseño de
`/comprobantes/lotes`, sin implementar todavía cambios de UI ni de
comportamiento fiscal.

La sección de carga masiva es central para FactuFlow y debe tratarse como flujo
sensible. Cualquier cambio posterior que toque emisión, reintentos,
reconciliación, descarte, fechas fiscales, puntos de venta, totales o
solicitudes de CAE debe pasar por `docs/agents/fiscal-change-checklist.md`.

## Evidencia del diagnóstico

- Auditoría visual ejecutada con Playwright local el 2026-06-26.
- Frontend real en `http://127.0.0.1:8080/comprobantes/lotes`.
- API mockeada con datos ficticios y sanitizados.
- Criterio aplicado: Product Design para auditar el flujo y Creative Production
  para ordenar jerarquía visual y dirección de interfaz, sin generar assets ni
  propuestas estéticas desconectadas del producto.
- No se usaron credenciales reales, datos reales, CAEs, CUITs reales, Exceles
  privados ni llamadas ARCA.
- Capturas privadas guardadas en
  `private/brand-lab/exports/lotes-ux-audit-2026-06-26/`.

El visor local no pudo abrir imágenes bajo `private/` por ACLs del entorno, pero
las capturas fueron verificadas por dimensiones, tamaño y prueba de no estar en
blanco.

## Diagnóstico resumido

La pantalla acumula varias capas de responsabilidad en una sola vista:

- onboarding inicial para usuarios nuevos
- carga de archivo
- selección de perfil
- confirmación de formato
- decisiones fiscales obligatorias
- validación del lote
- resumen operativo del lote
- emisión
- resolución de fallidos
- reconciliación externa
- descarte de pendientes
- compactación o eliminación
- listado de lotes recientes

Esa acumulación genera ruido visual y obliga al usuario a recorrer una página
larga con decisiones fiscales críticas mezcladas con ayuda introductoria y
acciones excepcionales.

## Problemas principales

1. **El onboarding permanente ocupa demasiado espacio.**
   Los bloques `Descarga la plantilla`, `Completa el archivo` y
   `Valida y confirma` son útiles la primera vez, pero después compiten con la
   tarea frecuente: subir, configurar, validar y revisar un lote.

2. **La acción principal pierde proximidad.**
   El botón `Validar lote` está arriba, junto al selector de archivo, mientras
   varias decisiones obligatorias se completan hacia abajo. El usuario termina
   completando campos y volviendo a buscar la acción principal.

3. **Las decisiones fiscales están correctas, pero dispersas.**
   Punto de venta, concepto fiscal ARCA, descripción facturada y fechas fiscales
   aparecen como bloques separados y extensos. La seguridad fiscal es necesaria,
   pero la forma actual no ayuda a ver de un vistazo qué falta.

4. **Reconciliación y resolución aparecen con peso de caso frecuente.**
   `Reintentar fallidos`, `Descartar visibles` y `Reconciliar ARCA Web` son
   críticas, pero excepcionales. Cuando están visibles ocupan mucho espacio y
   generan sensación de complejidad incluso para usuarios que solo quieren
   validar o revisar.

5. **La pantalla mezcla modos de trabajo.**
   El mismo plano visual intenta servir para preparación del archivo, revisión
   del lote, emisión y soporte post-incidente. Cada modo necesita una jerarquía
   distinta.

6. **La lista de lotes recientes compite con el flujo activo.**
   Es útil para navegación, pero en desktop queda al lado del flujo principal y
   suma información numérica repetida mientras el usuario toma decisiones sobre
   el lote actual.

## Principios de rediseño

- Mantener todos los controles fiscales obligatorios visibles antes de validar,
  pero agruparlos como un checklist operativo con estado `Completo` /
  `Pendiente`.
- Reducir texto persistente. La ayuda larga debe pasar a detalles desplegables,
  tooltips, estados vacíos o una guía inicial colapsable.
- Separar modos:
  - **Preparar archivo**
  - **Validar configuración**
  - **Revisar lote**
  - **Resolver excepciones**
- Mantener la acción primaria cerca del último dato requerido. Si el usuario
  completa decisiones hacia abajo, la acción de validar debe acompañar ese final
  o quedar en una barra de acción persistente.
- Las acciones excepcionales deben ser progresivas: visibles como resumen de
  pendientes, con detalle expandible solo cuando corresponde.
- No ocultar riesgos fiscales detrás de diseño estético. La UI debe reducir
  ruido, no reducir controles.

## Instrucciones de implementación por cortes

### Corte 1 - Reorganizar preparación y validación

Objetivo: mejorar el flujo de carga sin tocar servicios ni contratos.

- Convertir los bloques introductorios en una guía colapsable o secundaria.
- Mantener `Perfil de carga masiva`, archivo y formato en una primera zona.
- Agrupar punto de venta, concepto fiscal ARCA, descripción facturada y fechas
  en un panel `Configuración fiscal del lote`.
- Agregar un resumen compacto de requisitos con estado pendiente/completo.
- Mover o duplicar `Validar lote` junto al cierre de la configuración fiscal.
- No cambiar payload, validaciones, watchers ni llamadas API.

Validación mínima:
- test unitario de `LotesComprobantesView`
- `npm run lint:check`
- `npm run type-check`
- `npm run build`
- smoke visual con API mockeada y sin ARCA

### Corte 2 - Reducir ruido del lote activo

Objetivo: que el resumen del lote sea la vista principal después de validar.

- Priorizar estado, totales, avance y siguiente acción segura.
- Mover detalles extensos a secciones plegables.
- Mantener `Emitir comprobantes válidos` con confirmación fiscal irreversible.
- No tocar reglas de emisión ni confirmaciones.

Validación mínima:
- tests existentes de procesamiento/reintento no deben cambiar de contrato
- captura de lote `validado`, `con_errores` y `procesando`

### Corte 3 - Tratar reconciliación como modo excepcional

Objetivo: bajar el ruido de reconciliación sin esconder acciones críticas.

- Mostrar un resumen claro de pendientes y una acción `Resolver pendientes`.
- Llevar `Reintentar`, `Descartar` y `Reconciliar ARCA Web` a paneles
  desplegables, tabs o un drawer específico.
- Mantener textos de advertencia fiscal dentro del modo de resolución.
- No habilitar reintentos ni reconciliaciones cuando el estado no lo permite.

Validación mínima:
- tests existentes de `requiere_reconciliacion`
- smoke visual de lote incierto con acciones deshabilitadas cuando corresponda

### Corte 4 - Navegación de lotes recientes

Objetivo: que la navegación histórica no compita con la tarea actual.

- Convertir `Lotes recientes` en lista compacta, filtro lateral colapsable o
  panel secundario.
- Resumir cada lote con estado, fecha y métrica principal.
- Evitar repetir seis contadores por lote si no aportan a la decisión inmediata.

Validación mínima:
- carga de lista, selección de lote y refresco
- responsive desktop/mobile

## Límites explícitos

- No modificar backend, ARCA, emisión, reconciliación, numeración, CAE,
  idempotencia ni contratos en los primeros cortes visuales.
- No llamar ARCA en QA visual.
- No usar datos reales ni archivos privados en capturas versionables.
- No eliminar confirmaciones fiscales ni textos irreversibles.
- No mover acciones sensibles sin cubrir tests y QA del estado correspondiente.

## Criterio de éxito

El rediseño será exitoso cuando un usuario administrativo pueda:

- entender en qué etapa está
- ver qué requisito falta antes de validar
- validar sin recorrer la página de ida y vuelta
- revisar el lote validado sin ruido de acciones excepcionales
- encontrar resolución/reconciliación cuando el lote realmente lo requiere
- operar sin perder las garantías fiscales actuales
