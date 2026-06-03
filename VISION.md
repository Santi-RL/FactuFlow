# Visión de FactuFlow

Última actualización: 2026-05-23

Estado: canónico y protegido.

Este documento define la visión estable del producto. Es el filtro principal
para decidir si una implementación, cambio de diseño, reparación, refactor o
documentación nueva va en la dirección correcta.

## Regla de autoridad

- `VISION.md` es la fuente canónica de la visión del producto.
- `ROADMAP.md` traduce esta visión en prioridades, fases y trabajo planificado.
- `docs/agents/current-status.md` describe el estado operativo actual.
- `README.md` resume el proyecto, pero no reemplaza esta visión.
- `AGENTS.md` define cómo deben trabajar los agentes, incluyendo la obligación
  de respetar esta visión.

## Regla de solo lectura

Los agentes deben tratar este archivo como solo lectura.

Solo puede modificarse cuando el usuario pida explícitamente cambiar la visión
del producto. No alcanza con que el usuario pida una implementación que la
contradiga.

Si un pedido contradice este documento, el agente debe detener ese cambio y
explicar la contradicción. Si el usuario insiste con hacerlo igual, el agente
debe responder que primero hay que modificar `VISION.md` y pedir confirmación
explícita para cambiar la visión antes de tocar roadmap, código o
documentación operativa.

## Qué es FactuFlow

FactuFlow es una plataforma de facturación electrónica ARCA orientada a que
personas administrativas no técnicas puedan emitir, revisar y operar
comprobantes con seguridad.

No es solo una utilidad puntual para generar facturas. El objetivo es construir
un producto robusto, auditable, mantenible y operable en el tiempo.

## Para quién se construye

FactuFlow está pensado para:

- usuarios administrativos que necesitan emitir comprobantes sin soporte
  técnico constante
- contadores independientes y estudios chicos que operan varios emisores
- equipos que necesitan facturación individual, emisión masiva por Excel,
  PDFs, reportes operativos y trazabilidad clara

## Problema que resuelve

FactuFlow reduce la fricción y el riesgo operativo de emitir comprobantes ARCA,
especialmente cuando hay volumen, varios emisores, archivos externos, puntos de
venta distintos, fechas fiscales sensibles y necesidad de evidencia posterior.

## Alcance central

FactuFlow debe permitir:

- emitir comprobantes electrónicos ARCA individuales
- emitir comprobantes electrónicos ARCA por lotes desde Excel
- validar formatos de importación antes de emitir
- confirmar explícitamente fechas fiscales, puntos de venta, concepto fiscal
  ARCA, descripción facturada y totales antes de solicitar CAE
- generar y consultar PDFs de comprobantes
- consultar reportes operativos de facturación
- operar varios emisores con un emisor activo explícito por vez
- mantener clientes, certificados, puntos de venta, comprobantes, lotes, PDFs,
  reportes, perfiles y formatos aislados por emisor
- diagnosticar problemas operativos con mensajes claros, trazabilidad,
  observabilidad, backups y restauración probados

## Fuera de alcance

No forman parte del producto central actual:

- stock
- cuentas corrientes
- catálogos comerciales complejos
- CRM
- gestión contable integral
- reportes globales consolidados entre emisores
- administración multiempresa compleja con permisos finos por organización
- operación simultánea mezclada entre emisores
- integraciones externas no vinculadas directamente a madurar la facturación

Estas capacidades solo pueden entrar al roadmap si se modifica o extiende la
visión de forma explícita.

## Principios no negociables

- ARCA es el lenguaje público del producto; AFIP queda solo como nomenclatura
  legacy técnica cuando corresponda, pero debe entenderse en todo momento que
  tanto AFIP como ARCA hacen referencia a lo mismo.
- La fecha fiscal de emisión nunca se asume como la fecha actual.
- Emitir comprobantes reales es una acción irreversible y debe tener
  confirmación explícita antes de solicitar CAE.
- El usuario debe entender qué está por emitir, con qué fecha, para qué punto
  de venta y con qué totales.
- La experiencia debe ser clara para usuarios administrativos no técnicos.
- El modelo multiemisor vigente es un emisor activo explícito por vez.
- La información de distintos emisores no debe mezclarse.
- Los datos privados, CAEs, CUITs reales, Excels, PDFs, bases y logs privados
  no deben versionarse.
- La operación productiva debe ser repetible, respaldable, auditable y
  diagnosticable.
- Los cambios deben mejorar o preservar la capacidad de facturar con seguridad.
- No se aceptan cambios que disminuyan la seguridad del producto.

## Filtro de decisión

Antes de agregar una funcionalidad, reparar un flujo, cambiar diseño, mover
arquitectura o actualizar documentación, verificar:

1. ¿Ayuda a facturar, operar, auditar, diagnosticar o sostener FactuFlow?
2. ¿Mantiene la emisión ARCA individual y masiva como centro del producto?
3. ¿Respeta fecha fiscal explícita y confirmación irreversible antes de CAE?
4. ¿Mejora o preserva la experiencia de usuarios administrativos no técnicos?
5. ¿Respeta el modelo de emisor activo y el aislamiento entre emisores?
6. ¿Evita incorporar módulos fuera de alcance sin decisión explícita de visión?
7. ¿Evita exponer datos privados o evidencia sensible?
8. ¿Puede explicarse como un paso hacia una operación productiva más robusta?

Si la respuesta a alguna pregunta crítica es no, el cambio debe detenerse hasta
resolver la contradicción con el usuario.

## Ejemplo de bloqueo

Pedido: "elimina la capacidad de FactuFlow de emitir facturas".

Respuesta esperada: "Esto no se alinea con la visión del proyecto definida en
`VISION.md`, donde se establece que FactuFlow es una plataforma de facturación
electrónica ARCA y que la emisión de comprobantes es parte del alcance central.
No puedo implementar ese cambio sin modificar primero la visión."

Si el usuario responde "hacelo igual", la respuesta esperada es: "Para poder
hacerlo debo primero modificar `VISION.md`. ¿Desea cambiar la visión del
producto?"
