# Portafolio activo de desarrollo

Última revisión: 04/09/2026

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

| Línea | Estado | Prioridad | Resultado buscado | Dependencias / detalle |
|---|---|---|---|---|
| PF-11/PF-15 | Ahora 1 | P1/P2 | Backups trazables, recuperación, logs y soporte comprensible | Plano de control externo; observabilidad vigente |
| PF-04 | Después 1 | P2 fiscal | Evidencia histórica inmutable en comprobantes, PDFs e informes | Contratos de moneda, IVA, emisor y paginado |
| PF-05 | Después 1 | P2 fiscal | Reconstrucción histórica opcional, reanudable y con procedencia desde ARCA | PF-04 y PF-02 cerrado |
| PF-09 | Después 2 | P2 elevable | Propiedad y rotación de certificados, WSAA, caché y ambientes | Seguridad, ARCA y migraciones |
| PF-12 | Después 2 | P2 elevable | Constraints y migraciones reversibles para invariantes críticas | Acompaña cortes de dominio; no es migración masiva aislada |
| PF-14 | Después 2 | P2 | Contratos HTTP, errores y concurrencia CRUD coherentes | Consumido por UI, soporte y procesos largos |
| PF-10 | Más adelante | P2 | Resguardo confirmado, exportaciones y liberación segura de almacenamiento | PF-04, PF-11 y propiedad de artefactos |
| PF-13 | Más adelante | P2 fiscal/operativa | Plantillas contables con tipo y letra separados, receptor por fila, interpretación verificable y lotes eficientes | PF-01/PF-03, PF-12/PF-14, UX compartida con PF-17; [detalle](pf-13-plantillas-contables-design.md) |
| PF-16 | Más adelante | P2/P3 | Calidad dirigida por riesgo y puerta para distribución a terceros | CI actual y documentación viva |
| PF-17 | Más adelante | P2/P3 | UX administrativa, accesibilidad y recuperación de errores | PF-03, PF-07, PF-14 y PF-15 |
| PF-18 | Más adelante | P3 | PDFs masivos, distribución, soporte, correo, integraciones y dashboard | Madurez operativa y almacenamiento seguro |

## Trabajo agrupado por línea

### PF-11/PF-15

- Identidad inequívoca de backups preoperación y escrituras intermedias.
- Automatización cifrada, retención, alertas y restauración hacia un VPS nuevo.
- Señales visibles de backup, salud y trazabilidad sin datos privados.
- QA controlada de almacenamiento, compactación y limpieza segura.

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
- PF-13/PF-17: advertencias de duplicación con receptor identificable, evitando
  avisos por igual fecha e importe entre consumidores finales anónimos. La
  regla aceptada y los límites pendientes viven en el mismo
  [diseño PF-13](pf-13-plantillas-contables-design.md#decisión-de-producto-duplicados-y-receptor-identificable);
  conservar las garantías fiscales de PF-01.
- ZIP de PDFs, selección múltiple y limpieza de temporales.
- Jobs reanudables, trazabilidad de tareas masivas y límites de recursos.
- Cobertura de reportes/PDF, smoke local y portabilidad de herramientas.
- Conectividad visible, ayuda contextual, estados vacíos, microcopy y
  accesibilidad.
- Instalación simplificada, demo, compatibilidad, correo e integraciones
  posteriores.

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
