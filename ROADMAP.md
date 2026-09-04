# Roadmap de FactuFlow

Última revisión: 04/09/2026

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

### 1. PF-11/PF-15 — recuperación y trazabilidad operativa

**Prioridad:** P1/P2 operativa.

Vincular cada backup preoperación con propósito, timestamp y escrituras
intermedias; mostrar señales administrativas útiles; completar logs y soporte
sin exponer evidencia privada. El estado concreto de una instalación permanece
en `VPS Hostinger` / `vps-admin`.

## Después

El orden de esta sección también es vinculante salvo nueva evidencia o decisión
explícita del usuario.

### 1. PF-04/PF-05 — evidencia e historia fiscal externa

**Prioridad:** P2 fiscal.

Primero preservar instantáneas históricas correctas en comprobantes, PDFs e
informes. Después diseñar una reconstrucción opcional, reanudable y con
procedencia desde ARCA. La historia externa nunca será requisito para emitir.

### 2. PF-09/PF-12/PF-14 — contratos e invariantes de plataforma

**Prioridad:** P2, elevable por evidencia.

Endurecer certificados, WSAA y ambientes; trasladar garantías críticas a
constraints y migraciones reversibles; uniformar contratos HTTP, errores y
concurrencia CRUD sin mezclar estos cortes con funcionalidades nuevas.

## Más adelante

Estas líneas están aceptadas, pero no deben desplazar problemas fiscales u
operativos confirmados:

- **PF-10:** exportaciones, resguardo confirmado y liberación segura de
  almacenamiento.
- **PF-13 — plantillas contables e importación fiscal:** permitir una misma
  plantilla con tipo (`FC`, `NC`, `ND`) y letra (`A`, `B`, `C`) en columnas
  separadas, CUIT y condición IVA del receptor por fila. Anticipar requisitos
  condicionales en el constructor y validarlos en el lote: los comprobantes A
  requieren CUIT válido y condición compatible; las notas requieren su asociado.
  Mostrar cómo se interpretará el Excel, con neto, IVA y total diferenciados,
  sin exigir códigos técnicos. **P2 fiscal y de usabilidad**, sin desplazar el
  orden vigente. Depende de conservar PF-01/PF-03 y el aislamiento multiemisor;
  comparte claridad de uso con PF-17 y contratos con PF-14. Alcance, auditoría,
  compatibilidad y aceptación en el
  [diseño de plantillas contables](docs/agents/pf-13-plantillas-contables-design.md).
  **Con PF-17, prevenir duplicados en emisión masiva:** silenciar repeticiones
  anónimas internas y detectar coincidencias de contenido con lotes anteriores,
  incluso anónimos. Mostrar lote, archivo, cantidad, importe, fecha/hora y usuario
  de emisión anterior; dar mayor énfasis a «Volver a revisar». La excepción
  «Emitir como operaciones nuevas» exige un checkbox específico. Revalidar antes
  de emitir y coordinar solicitudes simultáneas, conservando las guardas
  fiscales. Decisiones, compatibilidad y aceptación en el
  [diseño de prevención de duplicados](docs/agents/pf-13-duplicados-lotes-design.md).
  PF-13 conserva además su línea de procesos largos y eficiencia de lotes.
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

- **v0.3.5 / PF-06/PF-07/PF-08:** asignaciones explícitas multiemisor,
  capacidad delegada para crear y editar y cambio de contexto seguro. La
  release está publicada; el despliegue permanece pendiente.
- **v0.3.4 / PF-19D:** WSFE como autoridad de puntos CAE, preferencia compartida
  de uso y constancia descriptiva opcional, con guardas y migración conservadas.
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
