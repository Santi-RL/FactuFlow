# Roadmap de FactuFlow

Última revisión: 29/08/2026

Estado: VIGENTE.

Este documento muestra hacia dónde avanza FactuFlow y en qué orden. La visión
canónica vive en [`VISION.md`](VISION.md), el inventario completo de trabajo en
[`docs/agents/development-portfolio.md`](docs/agents/development-portfolio.md) y
la historia en [`CHANGELOG.md`](CHANGELOG.md).

## Cómo leerlo

- **Ahora:** unidades aceptadas y ordenadas para los próximos cortes.
- **Después:** trabajo aceptado cuya ejecución depende de cerrar «Ahora».
- **Más adelante:** líneas válidas sin compromiso inmediato ni orden interno.
- **Completado recientemente:** contexto mínimo; el detalle no vive aquí.

Las prioridades expresan impacto, no tamaño:

- **P0:** incidente activo, autorización fiscal incorrecta, pérdida o exposición
  de datos. Interrumpe el orden normal.
- **P1:** seguridad fiscal, continuidad operativa o bloqueo real de facturación.
- **P2:** robustez, recuperación y mejora importante del trabajo administrativo.
- **P3:** evolución opcional de UX, UI, distribución o conveniencia.

Una mejora visual puede ascender si bloquea la operación. Una herramienta no
decide prioridades por su severidad automática. Las fechas y versiones se fijan
solo cuando el usuario aprueba un corte concreto.

## Ahora

### 1. PF-03B — validación estricta de ítems e importes

**Prioridad:** P1 fiscal, Nivel 2.

Separar el DTO que la interfaz usa para editar ítems del contrato que recibe el
backend. Rechazar propiedades desconocidas, descuentos inválidos y valores no
finitos antes de crear operaciones, reservas, intentos o solicitudes de CAE.

**Resultado esperado:** emisión individual, lotes, perfiles, worker, reintentos
y recuperación stale comparten un contrato estricto sin romper archivos ni
perfiles válidos existentes.

**Diseño:**
[`docs/agents/pf-03-validacion-fiscal-design.md`](docs/agents/pf-03-validacion-fiscal-design.md).

### 2. PF-19D — autoridad WSFE y uso operativo de puntos de venta

**Prioridad:** P1 fiscal-operativa, Nivel 2. Depende de cerrar PF-03B.

Usar `FEParamGetPtosVenta` como autoridad técnica autenticada para descubrir y
validar puntos compatibles con el flujo CAE. Separar esa disponibilidad de la
preferencia compartida `Usar en FactuFlow` y convertir la constancia PDF en un
complemento descriptivo opcional.

**Resultado esperado:** el usuario puede comenzar con `Comprobar con ARCA`, usar
solo los puntos técnicamente válidos que eligió para FactuFlow y completar
domicilio o nombre de fantasía manualmente o mediante constancia, sin debilitar
preflights, idempotencia ni reconciliación.

**Diseño:**
[`docs/agents/pf-19d-puntos-venta-authority-design.md`](docs/agents/pf-19d-puntos-venta-authority-design.md).

## Después

El orden de esta sección también es vinculante salvo nueva evidencia o decisión
explícita del usuario.

### 1. PF-06/PF-07/PF-08 — permisos operativos multiemisor

**Prioridad:** P1 de aislamiento y autorización, Nivel 2.

Implementar como una sola unidad la relación de operadores con varios emisores,
la creación o edición delegada y el cambio de emisor seguro. No introducir
permisos finos por punto de venta ni administración multiempresa compleja.

**Diseño:**
[`docs/agents/pf-06-08-permisos-multiemisor-design.md`](docs/agents/pf-06-08-permisos-multiemisor-design.md).

### 2. PF-11/PF-15 — recuperación y trazabilidad operativa

**Prioridad:** P1/P2 operativa.

Vincular cada backup preoperación con propósito, timestamp y escrituras
intermedias; mostrar señales administrativas útiles; completar logs y soporte
sin exponer evidencia privada. El estado concreto de una instalación permanece
en `VPS Hostinger` / `vps-admin`.

### 3. PF-04/PF-05 — evidencia e historia fiscal externa

**Prioridad:** P2 fiscal.

Primero preservar instantáneas históricas correctas en comprobantes, PDFs e
informes. Después diseñar una reconstrucción opcional, reanudable y con
procedencia desde ARCA. La historia externa nunca será requisito para emitir.

### 4. PF-09/PF-12/PF-14 — contratos e invariantes de plataforma

**Prioridad:** P2, elevable por evidencia.

Endurecer certificados, WSAA y ambientes; trasladar garantías críticas a
constraints y migraciones reversibles; uniformar contratos HTTP, errores y
concurrencia CRUD sin mezclar estos cortes con funcionalidades nuevas.

## Más adelante

Estas líneas están aceptadas, pero no deben desplazar problemas fiscales u
operativos confirmados:

- **PF-10:** exportaciones, resguardo confirmado y liberación segura de
  almacenamiento.
- **PF-13:** arquitectura de procesos largos, formatos y perfiles de lotes.
- **PF-16:** cobertura dirigida por riesgo, portabilidad de tooling y puerta
  previa a ofrecer FactuFlow a terceros.
- **PF-17:** accesibilidad, conectividad visible, ayudas contextuales y
  recuperación comprensible para usuarios administrativos.
- **PF-18:** ZIP de PDFs, distribución, soporte, correo, integraciones y
  dashboard posterior.
- Backups cifrados automatizados, retención, alertas y recuperación ensayada
  hacia un VPS nuevo.
- Instalación simplificada, demo controlada y política de compatibilidad para
  terceros, después de estabilizar operación y soporte.
- Consulta opcional, dentro del editor de punto de venta y bajo demanda, del
  último comprobante autorizado y el próximo número mediante
  `FECompUltimoAutorizado`. No será columna permanente ni requisito para emitir.

El detalle, dependencias y adjudicación de estos temas viven en el
[`portafolio de desarrollo`](docs/agents/development-portfolio.md).

## Completado recientemente

- **v0.3.2:** selección estricta y UX breve de puntos de venta.
- **v0.3.1:** acreditación durable y compatibilidad con constancias ARCA.
- **v0.3.0:** numeración compatible con historia externa, validación superior y
  cierre PF-19A/PF-19B/PF-19C.

Las notas, SHAs, CI y evidencia de esos cortes se consultan en
[`CHANGELOG.md`](CHANGELOG.md) y
[`docs/project/releases/`](docs/project/releases/README.md). El estado
desplegado no se infiere desde este repositorio.

## Gobierno del roadmap

- Cada iniciativa debe explicar problema, resultado, prioridad, dependencias y
  enlace al detalle; no copiar su plan de implementación.
- Sólo se actualiza cuando cambia una prioridad, entra o sale una iniciativa o
  se acepta un resultado macro.
- El trabajo terminado sale de las secciones prospectivas y pasa al changelog,
  dossier o archivo histórico.
- Un agente no puede agregar fricción operativa ni reducir seguridad por cuenta
  propia. Debe aplicar la regla de simplicidad segura de `VISION.md` y solicitar
  una decisión explícita del usuario.
- El snapshot íntegro anterior a esta estructura está en
  [`docs/project/history/roadmap-through-2026-08-29.md`](docs/project/history/roadmap-through-2026-08-29.md).
