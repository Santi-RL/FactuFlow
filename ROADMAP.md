# Roadmap de FactuFlow

Última revisión: 05/09/2026

Estado: VIGENTE.

Este documento muestra hacia dónde avanza FactuFlow y en qué orden. La visión
canónica vive en [`VISION.md`](VISION.md), el inventario completo de trabajo en
[`docs/agents/development-portfolio.md`](docs/agents/development-portfolio.md) y
la historia en [`CHANGELOG.md`](CHANGELOG.md).

## Cómo leerlo

- **Ahora:** unidades aceptadas y ordenadas para los próximos cortes.
- **Después:** trabajo aceptado cuya ejecución depende de cerrar «Ahora».
- **Más adelante:** líneas válidas sin compromiso inmediato ni orden interno.

Las prioridades expresan impacto, no tamaño:

- **P0:** incidente activo, autorización fiscal incorrecta, pérdida o exposición
  de datos. Interrumpe el orden normal.
- **P1:** seguridad fiscal, continuidad operativa o bloqueo real de facturación.
- **P2:** robustez, recuperación y mejora importante del trabajo administrativo.
- **P3:** evolución opcional de UX, UI, distribución o conveniencia.

Una mejora visual puede ascender si bloquea la operación. Una herramienta no
decide prioridades por su severidad automática. Las fechas y versiones se fijan
solo cuando el usuario aprueba un corte concreto.

Cada PF identifica una línea, no una tarea indivisible. Sus cortes pueden tener
prioridades y horizontes distintos. Una dependencia compartida exige la
capacidad necesaria, no terminar toda la línea relacionada. La prioridad mide
impacto; el orden de ejecución lo fijan «Ahora» y «Después».

## Ahora

### 1. PF-13/PF-17 — prevención de duplicados en emisión masiva

**Prioridad:** P1 fiscal y operativa, por decisión del usuario ante el caso real
de doble emisión.

Silenciar repeticiones anónimas internas y detectar coincidencias de contenido
con lotes anteriores, incluso anónimos. Mostrar lote, archivo, cantidad,
importe, fecha/hora y usuario de emisión anterior; dar mayor énfasis a
«Volver a revisar». La excepción «Emitir como operaciones nuevas» exige un
checkbox específico. Revalidar antes de emitir y coordinar solicitudes
simultáneas, conservando las guardas fiscales. Decisiones, compatibilidad y
aceptación en el
[diseño de prevención de duplicados](docs/agents/pf-13-duplicados-lotes-design.md).

Comparte autoría PF-15 y garantías PF-01/PF-03; no depende del rediseño visual
ni de completar todo el constructor. Se conservan los requisitos de respaldo
y recuperación aplicables a cada operación, aunque el corte de mejora
operativa siguiente se implemente después.

### 2. PF-11/PF-15 — recuperación y trazabilidad operativa

**Prioridad:** P1 para recuperación; P2 para señales y soporte.

Vincular cada backup previo a una operación con propósito, fecha/hora y
escrituras intermedias; mostrar señales administrativas útiles; completar
registros operativos y soporte
sin exponer evidencia privada. El estado concreto de una instalación permanece
en `VPS Hostinger` / `vps-admin`.
El [diseño de recuperación y trazabilidad](docs/agents/pf-11-15-recuperacion-trazabilidad-design.md)
separa este corte de la automatización de backups de «Más adelante».

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
  almacenamiento. **P2**; depende de preservación histórica PF-04 y recuperación
  PF-11. Alcance en el [portafolio](docs/agents/development-portfolio.md).
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
- **PF-13 — procesos largos y eficiencia, P2:** límites de recursos y tareas
  reanudables, conservando invariantes fiscales. Alcance en el
  [portafolio](docs/agents/development-portfolio.md).
- **PF-17 — períodos rápidos, P3:** facilitar el Reporte de ventas con
  «Mes actual», «Mes anterior» y selección
  personalizada, completando Desde/Hasta y mostrando el rango calendario.
  Alcance y aceptación en el
  [diseño de períodos rápidos](docs/agents/pf-17-reportes-periodos-design.md).
- **PF-17/PF-15 — actividad de lotes, P2:** mostrar en cada lote el nombre del
  usuario de la última emisión confirmada y desplegar la actividad histórica al
  seleccionarlo, conservando la vista compacta. Ubicación, atribución y aceptación en el
  [diseño de actividad de lotes](docs/agents/pf-17-actividad-lotes-design.md).
- **PF-17 — UI de emisión masiva, P2:** compactar la preparación,
  mantener a la vista el resumen de requisitos y distinguir el archivo nuevo
  del historial. Coordinar con plantillas y duplicados PF-13, actividad PF-15 y
  almacenamiento PF-10. El diseño se revisará con el usuario en la aplicación
  local y podrá ajustarse antes de subir la implementación al repositorio
  remoto. Alcance y aceptación en el
  [diseño de UI de emisión masiva](docs/agents/pf-17-lotes-ui-design.md).
- **PF-18/PF-17 — dashboard mensual, P2:** mostrar cantidad y total en pesos del
  mes actual y anterior según fecha del comprobante, con mes/año y alcance
  explícitos; descontar notas de crédito del importe. El último comprobante
  debe reflejar la emisión más
  reciente e incluir fecha del comprobante y fecha/hora de emisión acreditada.
  Complementa la prevención de duplicados PF-13, con UX PF-17 y trazabilidad
  PF-15. Contrato, límites históricos y aceptación en el
  [diseño de resumen mensual](docs/agents/pf-18-dashboard-mensual-design.md).
- **PF-18/PF-17 — estado del certificado, P3:** «Válido» debe mostrar un
  tilde de éxito; ícono y color deben acompañar cada estado, sin advertencia
  fija para un certificado válido. Es independiente de los nuevos agregados
  mensuales; comparte el [diseño del dashboard](docs/agents/pf-18-dashboard-mensual-design.md).
- **PF-11/PF-15 — automatización de backups, P2:** cifrado, retención, alertas y
  recuperación ensayada hacia un VPS nuevo, después de definir la evidencia
  recuperable del corte operativo. El [diseño de recuperación](docs/agents/pf-11-15-recuperacion-trazabilidad-design.md)
  delimita su alcance; la instalación se documenta en el plano de control.
- **PF-16/PF-17 — calidad y uso administrativo, P2/P3:** cobertura dirigida por
  riesgo y portabilidad de herramientas; accesibilidad, conectividad visible y
  ayudas contextuales. Los cortes se priorizan por riesgo concreto en el
  [portafolio](docs/agents/development-portfolio.md), sin refactor global.
- **PF-18 — distribución e integraciones, P3:** ZIP de PDFs, soporte, correo e
  integraciones; instalación simplificada y demo controlada para terceros tras
  estabilizar operación y cumplir la puerta de calidad PF-16. Preservar
  almacenamiento seguro PF-10. Alcance en el [portafolio](docs/agents/development-portfolio.md).
- **PF-17 — consulta opcional de numeración, P3:** dentro del editor de punto de
  venta y bajo demanda, consultar el
  último comprobante autorizado y el próximo número mediante
  `FECompUltimoAutorizado`. No será columna permanente ni requisito para emitir.
  Preserva PF-02/PF-19; delimitar el corte en el
  [portafolio](docs/agents/development-portfolio.md).

El detalle, dependencias y adjudicación de estos temas viven en el
[`portafolio de desarrollo`](docs/agents/development-portfolio.md).

Los cortes completados, releases y su evidencia se consultan en
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
