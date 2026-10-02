# RG 5616 — diseño fiscal y validación del parche

## Autoridad y alcance

Unidad Nivel 2 definida en el [contrato aceptado](../../agents/rg-5616-condicion-iva-receptor-parche.md).
El manual oficial WSFEv1 v4.7, revisión del 01/09/2026, anexo final
«Condición IVA Receptor», fue contrastado antes de implementar:
[manual de ARCA](https://www.afip.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf).

| Condición soportada | ID | A (1/2/3) | B (6/7/8) | C (11/12/13) |
|---|---|---|---|---|
| Responsable Inscripto | 1 | Sí | No | Sí |
| Monotributo | 6 | Sí | No | Sí |
| Exento | 4 | No | Sí | Sí |
| Consumidor Final | 5 | No | Sí | Sí |

No se incorporan otras categorías del catálogo, clases ni regímenes. RNI no
tiene una equivalencia inequívoca entre las cuatro categorías soportadas.

## Checklist previo a implementación

- **Consumidores:** formulario individual y clientes seleccionados; API de
  emisión; normalización, validación y armado del servicio de facturación;
  importación y formatos con condición fija; lote batch y unitario; worker y
  reintentos manuales/background. El cliente WSFE valida todo detalle antes de
  construir `FECAESolicitar`. Los helpers usados para leer historia y reconstruir
  evidencia siguen siendo no estrictos.
- **Hash histórico:** la recuperación de rechazos globales reconstruye el hash
  normalizado anterior (incluidas sus equivalencias legacy) y el actual. La
  evidencia durable debe coincidir con una de esas dos representaciones;
  ownership, material fiscal y constraints se mantienen. Ese cálculo privado
  no habilita emisión ni modifica clientes o comprobantes. Las nuevas solicitudes
  no usan esa compatibilidad.
- **Datos afectados:** exclusivamente condición IVA del receptor y su
  compatibilidad con el tipo de comprobante existente. Sin migraciones, cambios
  de fecha, punto de venta, importes, numeración, certificados o aislamiento.
- **Riesgo:** omisión del campo o reclasificación silenciosa; también bloquear
  una reconciliación si se aplicara la regla a payloads históricos.
- **Invariantes:** fecha explícita y confirmación irreversible vigentes;
  idempotency key y hash sin normalizaciones nuevas; pertenencia al emisor;
  locks y constraints vigentes; CAE incierto reconciliable; ninguna liberación
  ni repetición por errores ambiguos. Cambiar la condición implica cambiar el
  payload fiscal y renovar confirmación y clave por el flujo existente.
- **Orden individual:** lookup idempotente y conflicto primero; replay conserva
  su resultado. Para una operación nueva se valida IVA antes de crear estado
  fiscal. La normalización estricta precede reservas e intentos; el armado y
  serializer vuelven a exigir ID compatible antes de CAE.
- **Orden lote/reintento:** importación valida sin emitir; recuperación y
  reconciliación mantienen su precedencia. Sólo las solicitudes nuevas pasan
  por la normalización estricta. Worker conserva ownership, locks, confirmación
  y cierre pre-ARCA existentes.
- **Estados:** no se añaden transiciones. Un dato inválido nuevo usa el rechazo
  pre-CAE vigente; los grupos pendientes conservan el flujo de corrección. Los
  terminales, autorizados o inciertos no se reclasifican. Un corte post-CAE sigue
  inmovilizado/reconciliable mediante la evidencia durable existente.
- **Concurrencia:** la validación pura no toma decisiones de numeración ni
  reemplaza compare-and-swap. Mismo hash mantiene replay; otro hash con la misma
  clave mantiene conflicto. PostgreSQL y SQLite conservan sus constraints.
- **Fallos:** blanco, desconocido, RNI e incompatibilidad deben ser accionables
  y producir cero llamadas CAE. Todo el batch se serializa antes de enviar, por
  lo que un detalle inválido impide la solicitud completa. Fallos pre/post-CAE,
  accesos revocados y workers interrumpidos conservan la recuperación vigente.
- **Contratos externos:** `FECAESolicitar`, validaciones 10242/10243/10246.
  `FECompConsultar` y las consultas de numeración no reciben esta compuerta.
  No hay lookup de padrón por factura ni llamadas reales en tests.

## Matriz de pruebas prevista

- Las nueve variantes A/B/C con las cuatro condiciones; ID siempre presente.
- Aliases inequívocos, espacios y mayúsculas; vacío, desconocido y RNI sin
  conversión a RI ni CF, incluso con documento 99.
- API: rechazo antes de crear operación/intento; replay terminal legacy y
  conflicto idempotente antes de validación mutable.
- SOAP individual/batch: falta, ID desconocido e incompatible sin llamar CAE.
- Importación: mensajes por comprobante y condiciones fijas válidas sin columnas
  adicionales; lote/reintento/worker con payload previo inválido.
- Suites existentes de confirmación, multiemisor, carreras, fallos pre/post-CAE,
  autorizados e incertidumbre/reconciliación como regresión del flujo compartido.
- UI: opciones válidas, dato histórico visible sin sustitución; corrección del
  receptor conserva reset de claves y confirmación vigente.

No se solicita CAE real en homologación en esta unidad. La matriz documental y
los dobles SOAP prueban el contrato; cualquier ensayo de emisión real requiere
un objetivo y autorización específicos. La verificación de producción sigue el
plano de control y requiere autorización separada.

## Recuperación y cierre

Santi autorizó incorporar la actualización mínima `pypdf 6.16.1 → 6.19.0`
para resolver ocho alertas de la auditoría de dependencias. La corrección está
publicada en la [release del mantenedor](https://github.com/py-pdf/pypdf/releases/tag/6.19.0).
Se valida lectura de constancias y PDFs y se repite la auditoría completa.

Sin migración de datos: el rollback es el commit aceptado anterior por el flujo
de producción. Nunca borrar evidencia fiscal ni repetir una solicitud incierta.
La revisión final utiliza la configuración canónica del checklist fiscal.
El resultado de la suite completa, la revisión y la CI se adjunta al candidato
antes de autorizar su despliegue.

## Validación del candidato

- Área fiscal: 554 pruebas aprobadas, incluidos replay legacy, incertidumbre y
  rechazo global con hashes de ambas representaciones.
- Frontend: 235 pruebas aprobadas y 36 pruebas E2E aprobadas. La captura sintética
  de vista previa conserva fecha explícita y condición Exento para clase B.
- Auditorías de dependencias backend y frontend: cero vulnerabilidades conocidas
  después de actualizar únicamente pypdf a 6.19.0.
- Lectura de constancias y generación/lectura de PDFs incluidas en las suites
  backend; formato, lint, type-check, build y estructura documental aprobados.
- Integración PostgreSQL: la ejecución local omite los escenarios que requieren
  su servidor. La CI con su servicio PostgreSQL debe aprobar antes de avanzar;
  no se modifican schemas, constraints ni migraciones.

Documentación alineada: contrato y dossier fiscal, estado y portfolio, roadmap,
changelog, integración ARCA, API y guía de usuario/QA. No cambian arquitectura,
comandos de instalación, visión ni runbooks de producción. El estado operativo
del despliegue permanece en el plano de control.
