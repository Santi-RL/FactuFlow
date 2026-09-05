# Portafolio activo de desarrollo

Última revisión: 05/09/2026

Estado: VIGENTE.

Este documento conserva el inventario completo del trabajo aceptado y sus
dependencias. `ROADMAP.md` selecciona y ordena sólo las próximas iniciativas.
La severidad de una herramienta no sustituye la validación ni la prioridad de
producto.

## Estados

- **Ahora:** próximo trabajo ordenado en el roadmap.
- **Después:** aceptado y dependiente de «Ahora».
- **Más adelante:** válido, sin compromiso inmediato.
- **Cerrado:** se consulta en changelog, diseño o archivo; no se desarrolla de
  nuevo sin evidencia.

## Líneas activas

Un PF puede contener cortes distintos: la prioridad corresponde al resultado
concreto, y el horizonte no convierte toda la línea en una dependencia previa.
La secuencia de ejecución se toma del roadmap, no del orden de estas filas.

| Línea | Estado | Prioridad | Resultado buscado | Dependencias / detalle |
|---|---|---|---|---|
| PF-11/PF-15, recuperación operativa | Ahora 1 | P1/P2 | Backups trazables, escrituras posteriores y soporte comprensible | [Contrato acotado](pf-11-15-recuperacion-trazabilidad-design.md); plano de control externo |
| PF-04 | Después 1 | P2 fiscal | Evidencia histórica inmutable en comprobantes, PDFs e informes | Contratos de moneda, IVA, emisor y paginado |
| PF-05 | Después 1 | P2 fiscal | Reconstrucción histórica opcional, reanudable y con procedencia desde ARCA | PF-04 y PF-02 cerrado |
| PF-09 | Después 2 | P2 elevable | Propiedad y rotación de certificados, WSAA, caché y ambientes | Seguridad, ARCA y migraciones |
| PF-12 | Después 2 | P2 elevable | Constraints y migraciones reversibles para invariantes críticas | Acompaña cortes de dominio; no es migración masiva aislada |
| PF-14 | Después 2 | P2 | Contratos HTTP, errores y concurrencia CRUD coherentes | Consumido por UI, soporte y procesos largos |
| PF-10 | Más adelante | P2 | Resguardo confirmado, exportaciones y liberación segura de almacenamiento | PF-04, PF-11 y propiedad de artefactos |
| PF-11/PF-15, automatización posterior | Más adelante | P2 | Backups cifrados automatizados, retención, alertas y recuperación hacia un VPS nuevo | Recuperación operativa; diseño específico al abrir el corte e instalación en el plano de control |
| PF-13, plantillas y procesos largos | Más adelante | P2 fiscal/operativa | Interpretación contable verificable y lotes eficientes | PF-01/PF-03, garantías PF-12/PF-14 y UX PF-17; [plantillas](pf-13-plantillas-contables-design.md) |
| PF-13/PF-17, duplicados | Más adelante | P2 | Prevención de doble emisión con evidencia y excepción consciente | Autoría mínima PF-15 y garantías PF-01/PF-03; [duplicados](pf-13-duplicados-lotes-design.md) |
| PF-16 | Más adelante | P2/P3 | Calidad dirigida por riesgo y puerta para distribución a terceros | CI actual y documentación viva |
| PF-17 | Más adelante | P2/P3 | UX administrativa, accesibilidad y recuperación de errores | PF-03, PF-07, PF-14 y PF-15 |
| PF-18 | Más adelante | P2/P3 | P2: resumen mensual y cronología; P3: ícono de certificado, distribución e integraciones | PF-04/PF-15 para moneda e historia y PF-17 para UX; [dashboard](pf-18-dashboard-mensual-design.md); PF-10/PF-16 para distribución |

## Trabajo agrupado por línea

### PF-11/PF-15

- **Ahora:** identidad de backups preoperación y escrituras intermedias;
  señales de recuperación y trazabilidad, sin datos privados, con aceptación
  en el [diseño operativo](pf-11-15-recuperacion-trazabilidad-design.md).
- **Más adelante:** automatización cifrada, retención, alertas y recuperación
  hacia un VPS nuevo. No es un requisito de automatización completo para cerrar
  el corte actual; sí conserva las exigencias de respaldo de cada operación.
- La QA de almacenamiento/compactación se coordina con PF-10 y los controles
  vigentes; no crea una tercera política de limpieza.

### PF-04/PF-05

- Instantáneas del emisor, moneda, IVA y datos históricos necesarios.
- Exactitud de PDFs, reportes, paginado y aislamiento.
- Importación histórica opcional con alcance, límites, journal y cobertura.

### PF-09/PF-12/PF-14

- Rotación y propiedad durable de certificados, TRA y caché WSAA.
- Diferencias de homologación y producción sin asumir equivalencias.
- Constraints, carreras, errores posteriores al commit y unicidad.
- Mensajes HTTP previsibles y sanitizados.

### PF-10/PF-13/PF-16/PF-17/PF-18

- PF-13, con PF-17: constructor de plantillas e importación contable con
  `FC`/`NC`/`ND`, letra, CUIT y condición IVA por fila; requisitos condicionales,
  vista de interpretación y mensajes que identifiquen fila y columna. El
  [diseño de plantillas contables](pf-13-plantillas-contables-design.md)
  adjudica los hallazgos de la auditoría y conserva versiones, perfiles,
  importes, confirmación fiscal e idempotencia. No reabre el rediseño cerrado de
  lotes ni incorpora una segunda línea de constructor.
- PF-13/PF-17: prevención de duplicados con receptor identificable dentro del
  lote y comparación de contenido contra lotes anteriores, incluso anónimos.
  Advertencia con evidencia y usuario de emisión anterior, retorno como acción
  principal y excepción con checkbox. Revalidación y coordinación simultánea,
  con trazabilidad PF-15 y garantías PF-01. El
  [diseño de duplicados](pf-13-duplicados-lotes-design.md) concentra el contrato,
  las decisiones aceptadas y la matriz para implementar.
- PF-18/PF-17, P2: cantidad y total en pesos del mes actual y anterior por fecha
  del comprobante, períodos explícitos y último comprobante con sus dos fechas.
  Las notas de crédito restan del importe, no de la cantidad. El
  [diseño del dashboard mensual](pf-18-dashboard-mensual-design.md) define
  cálculo, moneda, cronología, estados de consulta y pruebas; complementa
  PF-13 sin sustituir su control previo a emitir ni abrir otro motor de duplicados.
  El ajuste P3 del certificado es independiente: tilde de éxito para «Válido» e
  ícono/color coherentes para los demás estados; no espera nuevos agregados.
- PF-18, P3: ZIP de PDFs y selección múltiple; coordinar limpieza de temporales
  y resguardo con PF-10, sin duplicar políticas de almacenamiento.
- PF-13, P2: tareas reanudables, trazabilidad masiva y límites de recursos.
- PF-16: cobertura de reportes/PDF y pruebas por riesgo (P2), verificación local
  y portabilidad de herramientas (P3 salvo bloqueo comprobado).
- PF-17: conectividad visible y recuperación/accesibilidad que afecten operación
  (P2); ayuda contextual y ajustes de texto/presentación opcionales (P3).
  [Observabilidad](operational-observability.md) conserva la señal de conexión.
- PF-17, P3: períodos rápidos en Reporte de ventas, con «Mes actual», «Mes anterior»
  y rango personalizado. Conservar fechas visibles, generación explícita y
  aislamiento por emisor; [contrato y aceptación](pf-17-reportes-periodos-design.md).
- PF-17, P2, con trazabilidad PF-15: usuario de la última emisión confirmada visible
  en la tarjeta y cabecera del lote; actividad histórica desplegada únicamente
  al consultar ese lote. El [diseño de actividad](pf-17-actividad-lotes-design.md)
  distingue carga, emisión y acciones posteriores, comparte procedencia con
  PF-13 y conserva el historial compacto. No altera el corte «Ahora» de PF-15.
- PF-17: preparación compacta de lotes, resumen de requisitos persistente y
  separación entre archivo en preparación, resultado e historial. **P2 de
  usabilidad operativa, Más adelante**; coordina con PF-13, PF-15 y PF-10 sin
  desplazar el orden vigente. El [diseño de UI de lotes](pf-17-lotes-ui-design.md)
  define una evolución nueva, conserva los cortes anteriores cerrados y exige
  revisión del diseño con el usuario en la aplicación local antes de publicar
  la implementación en el repositorio remoto.
- PF-17, P3: consulta opcional de último comprobante y próximo número dentro del
  editor de punto de venta. Preservar PF-02/PF-19; definir tipos consultables,
  estado de carga/error y alcance de `FECompUltimoAutorizado` antes de codificar.
  Una consulta no reserva número ni garantiza el próximo frente a otra emisión;
  no será una columna permanente ni un requisito previo a emitir.
- PF-18, P3: instalación simplificada, demo, compatibilidad, correo e
  integraciones, después de estabilidad operativa y la puerta para terceros
  de PF-16. No ampliar funcionalidades del producto por la vía de packaging.

## Preparación para abrir cada corte

Los diseños específicos contienen decisiones de producto e invariantes, con
matrices de aceptación. Sus apartados pendientes son trabajo previo a codificar,
no capacidades ya implementadas. Las líneas generales necesitan delimitar una
unidad antes de convertirse en una tarea ejecutable.

| Corte | Fuente y preparación restante |
|---|---|
| Recuperación/trazabilidad | [Diseño operativo](pf-11-15-recuperacion-trazabilidad-design.md): productor y cobertura de evidencia, escrituras posteriores y permisos; evidencia de instalación en el plano de control. |
| Duplicados | [Diseño](pf-13-duplicados-lotes-design.md): normalización, alcance comparable, aceptación vinculada, coordinación atómica, historia compactada y transición. No espera toda la UI ni todo el constructor. |
| Plantillas contables | [Diseño](pf-13-plantillas-contables-design.md): política de documento B/CF, requisitos legacy, controles de importes y casos sintéticos. Sus reglas fiscales se verifican con fuentes oficiales antes de codificar. |
| Actividad de lotes | [Diseño](pf-17-actividad-lotes-design.md): fuente/orden de actor, cobertura histórica y consulta paginada. Reutiliza la procedencia mínima de duplicados, sin dependencia circular. |
| Dashboard mensual | [Diseño](pf-18-dashboard-mensual-design.md): fuente temporal, moneda histórica, agregados y cobertura; el ícono tiene aceptación independiente. |
| Reportes con períodos rápidos | [Diseño](pf-17-reportes-periodos-design.md): calendario e interacción definidos; verificar helper y consumidores al implementar. |
| UI de lotes | [Diseño](pf-17-lotes-ui-design.md): distribución final y totales disponibles; revisión del usuario en la aplicación local antes del primer push de implementación. |
| PF-04/PF-05 | Delimitar instantáneas, cobertura histórica y contratos de informes; después, diseño de importación externa opcional con procedencia, reanudación y aceptación. |
| PF-09/PF-12/PF-14 | Delimitar por dominio certificados/ambiente, garantía de persistencia o contrato HTTP; migración, consumidores, error, concurrencia y rollback según el corte. No exigir completar una plataforma entera. |
| Otras líneas generales | Automatización, distribución, eficiencia y consulta opcional: conservar alcance del inventario y cerrar diseño acotado, dependencias y aceptación antes de codificar. |

## Decisión de prioridad pendiente

La revisión del caso real de doble emisión justifica proponer que el corte de
duplicados pase a P1 y a «Ahora». Queda pendiente la decisión del usuario sobre
su posición respecto de recuperación/trazabilidad. Hasta esa decisión, el
roadmap conserva su P2 y horizonte actuales; la recomendación no reordena por
sí sola el trabajo ni incorpora el rediseño visual al corte urgente.

## Dependencias que no deben romperse

1. PF-04 precede a PF-05.
2. PF-06/PF-07/PF-08 se implementan como una unidad end-to-end.
3. PF-12 acompaña los cortes que necesitan persistencia; no absorbe dominios.
4. PF-13 no optimiza volumen sacrificando PF-01 o PF-03.
5. PF-17 consume errores y señales de PF-14/PF-15; no crea colas fiscales
   offline ni reintentos automáticos.
6. PF-19D no reabre numeración PF-02 ni debilita las guardas PF-19 existentes.
7. Un hallazgo nuevo P0/P1 puede alterar el orden sólo después de validación y
   decisión explícita.
8. Duplicados, actividad y dashboard comparten autoría/cronología cuando aplique;
   implementar la evidencia mínima con el primer consumidor, sin exigir que las
   tres interfaces estén terminadas. El ícono y los atajos de fechas son cortes
   independientes de los nuevos agregados.

## Líneas cerradas

PF-01, PF-02, PF-03A/PF-03B, PF-06/PF-07/PF-08 y
PF-19A/PF-19B/PF-19C/PF-19D están cerrados. El contrato
de PF-03B vive en [`pf-03b-items-importes-design.md`](pf-03b-items-importes-design.md).
El cierre multiemisor vive en
[`pf-06-08-permisos-multiemisor-design.md`](pf-06-08-permisos-multiemisor-design.md).
El cierre de PF-19D vive en
[`pf-19d-puntos-venta-authority-design.md`](pf-19d-puntos-venta-authority-design.md).
Su evidencia vive
en sus diseños, `CHANGELOG.md`, dossiers y auditorías. No se incluyen aquí sus
conteos de pruebas, SHAs ni cronología.

## Trazabilidad de la migración

Los 61 ítems pendientes y 30 en curso del roadmap anterior fueron adjudicados a
estas líneas o identificados como duplicados/históricos en
[`docs/project/history/documentation-audit-2026-08-29.md`](../project/history/documentation-audit-2026-08-29.md).
El snapshot completo permanece en
[`roadmap-through-2026-08-29.md`](../project/history/roadmap-through-2026-08-29.md).
