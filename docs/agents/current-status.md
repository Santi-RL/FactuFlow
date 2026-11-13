# Estado aceptado del repositorio

Última revisión: 13/11/2026.

Estado: VIGENTE.

Handoff breve del código aceptado y del punto de continuación. La historia,
evidencia de pruebas y cierres de release viven en changelog, contratos y dossiers.
El estado desplegado autoritativo vive en el plano de control `VPS Hostinger` /
`vps-admin`. No se infiere desde este documento, `main`, una release ni un tag.

## Línea base aceptada

- La release publicada más reciente es `v0.3.12`. Incluye descarga directa de PDF
  y ZIP de selección
  PF-18/PF-17, conservando permisos, historia y bloqueos, sin nuevas migraciones
  ni dependencias. El [dossier del corte](../project/releases/v0.3.12-candidate.md)
  conserva alcance, publicación, compatibilidad, CI, ensayo y recuperación.
  La publicación no determina ni modifica el estado desplegado.
- La preparación de `v0.3.13` alinea los productores técnicos y visibles en
  `0.3.13` para el corte NC/ND aceptado. El
  [dossier](../project/releases/v0.3.13-candidate.md) conserva las puertas de
  publicación y recuperación; esta preparación no acredita un despliegue.
- FastAPI, Vue 3 y persistencia SQLAlchemy; Alembic es el camino canónico de
  esquema fuera de tests controlados. Topología y salud de cada instalación se
  consultan en el plano de control.
- Emisión individual y masiva, clientes, comprobantes, PDF, reportes,
  certificados, puntos, perfiles y formatos se aíslan por emisor activo explícito.
- Los operadores tienen cero, uno o varios accesos por emisor. La capacidad de
  crear/editar fichas no concede administración global ni borrado; contrato en
  [PF-06/PF-07/PF-08](pf-06-08-permisos-multiemisor-design.md).
- Fecha fiscal explícita, confirmación irreversible, idempotencia, reservas
  durables y reconciliación ante posible autorización son invariantes vigentes.

## Contratos implementados que deben conservarse

| Área | Conducta aceptada y fuente dueña |
|---|---|
| Numeración e integridad | Cortes originales PF-01/PF-02 y PF-19A/B/C/D cerrados; la recuperación integral moderna sigue pendiente. [Índice de contratos cerrados](README.md#diseños-cerrados-de-consulta) |
| Puntos de venta | WSFE acredita puntos CAE por emisor/ambiente; preferencia compartida de uso y constancia descriptiva opcional separadas. Revisión fiscal y preflight vigentes. [PF-19D](pf-19d-puntos-venta-authority-design.md) |
| Importes e historia | PF-03B calcula; A-01 conserva decimales exactos; A-03 lee bases contrastadas y separa monedas sin conversión. No inferir categorías desde IVA cero o letra C. [Persistencia](pf-03-04-14-persistencia-fiel-design.md), [lecturas](a03-lecturas-fiscales-design.md) |
| Receptor y asociación | Condición IVA explícita y compatible; PF-13 conserva documento/nombre y CF identificado, sin inferir por documento ni reemplazar inválidos por CF. A-02 no elige al azar entre fichas coincidentes. [RG 5616](rg-5616-condicion-iva-receptor-parche.md), [PF-13](pf-13-receptores-importacion-design.md), [A-02](pf-03-04-14-asociacion-cliente.md) |
| Admisibilidad y revisión | P1 cerrado: tasas soportadas explícitas, vista previa decimal del backend y revisión masiva coherente con IVA 27 %. Categorías completas siguen P2. [Contrato](pf-03-04-importes-previsualizacion-design.md) |
| Duplicados y retries | Aceptación específica y revalidación; autorizados anteriores intactos y retry sólo de fallidos seleccionados por cola durable. Replay, ownership y reservas conservados. [Duplicados](pf-13-duplicados-lotes-design.md), [reintentos](pf-13-17-reintentos-seguros-parche.md) |
| Respuestas y recuperación legacy | SC-09 conserva correlación e incertidumbre. El P1 legacy exige comparación suficiente; diferencias o cobertura insuficiente conservan CAE atribuible y reserva. No abrir guardas modernas. [SC-09](sc-09-respuestas-wsfe-design.md), [reconciliación](pf-02-04-reconciliacion-integral-design.md) |
| PDF y tiempo | IVA guardado en A/B y detalle legible, sin recalcular; el PDF en pesos omite el bloque visible de moneda/cotización y conserva los datos y el QR. Instantes UTC explícitos y presentación argentina, sin desplazar fechas fiscales. [PDF](pf-04-pdf-representacion-fiscal-design.md), [moneda](a03-lecturas-fiscales-design.md#monedas-y-compatibilidad-http), [tiempo](pf-12-15-17-tiempo-operativo.md) |
| Acceso y recuperación | Presupuesto de login previo a bcrypt, recuperación asistida y sesiones nuevas vinculadas a la credencial verificada, con compatibilidad legacy. [SC-08](sc-08-login-recuperacion-design.md), [SC-11](sc-11-login-reset-design.md) |
| Respaldo | PF-11/PF-15 conserva evidencia externa y señal administrativa de Sistema; cobertura actual desconocida. No garantiza un respaldo actual ni crea otro journal. [Contrato](pf-11-15-recuperacion-trazabilidad-design.md) |

El mantenimiento publicado se resume en la sección `v0.3.9` del
[`CHANGELOG.md`](../../CHANGELOG.md), con antecedentes en el
[análisis](../project/analysis/dependencias-2026-10.md). No acredita una instalación.
Versiones, comandos y políticas de pruebas se consultan en sus archivos dueños y
en [testing](testing.md).

## Siguiente unidad: notas de crédito y débito individuales

El usuario adelanta las notas individuales como máxima prioridad de ejecución,
Ahora 1 y P1 por bloqueo operativo. El
[diseño de notas](pf-04-17-notas-guiadas-design.md) define acceso desde factura
autorizada y desde «Nuevo comprobante», reemplazando «Nueva factura», con una
misma preparación y revisión fiscal. El flujo incluye originales externos
consultables por WSFE en pesos y con importes soportados, sin importar historia.
El asociado se conserva en la evidencia previa y se presenta en revisión,
detalle y PDF. Los consumidores técnicos sin alcance declarado mantienen su
contrato y los hashes existentes.

La implementación se aceptó mediante el PR #145 con CI completa verde y revisión
independiente `scoped-clean` P0–P2. Retomar cerrando las puertas de release y la
operación autorizada por SHA exacto. El checklist vive en el diseño. Preservar
evidencia, aislamiento, fecha explícita, confirmación, numeración, idempotencia e
incertidumbre. Preparar la salida productiva por SHA exacto con sus controles;
este handoff no acredita una instalación ni autoriza emisiones reales.

## Descargas: continuación conservada después de las notas

El [corte PF-18/PF-17](pf-18-17-descargas-pdf-design.md) implementa
PDF por fila junto al ojo, selección individual y de todos
los resultados filtrados entre páginas, y ZIP sólo si contiene todos los PDF
seleccionados. Conserva historia, permisos, bloqueos por evidencia inválida y
generación bajo demanda sin archivos permanentes. Este corte P3 conserva su
salida productiva pendiente como Ahora 2, después de las notas individuales;
no agrega correo, resguardo ni rediseño de Lotes.

La release está publicada y verificada. El siguiente paso requiere autorización
separada para preflight y despliegue de su SHA inmutable, con origen real,
respaldo fresco, copia externa cifrada verificada, rollback y controles finales
sin emisiones reales. La publicación no acredita el estado de la instalación.
Las evidencias del corte viven en el dossier. Consultar los
cierres operativos existentes en el plano de control; no repetir el preflight
anterior por una instrucción de handoff que ya fue reemplazada.

## PF-04/PF-02: continuación conservada después de las descargas

El [primer corte PF-04/PF-02](pf-02-04-reconciliacion-integral-design.md#primer-corte-p2-evidencia-previa-compartida)
incorpora evidencia previa versionada e inmutable para intentos nuevos,
verificación durable antes de CAE, lector/comparador puros y traslado v6 con
compatibilidad v3/v4/v5. No habilita recuperación moderna ni corrige todavía
las lecturas históricas del emisor; ambas continuaciones conservan su alcance.
El [segundo corte](pf-04-lecturas-historicas-design.md) implementa la lectura
de emisor y punto originales en PDF/QR, comprobantes e informes,
cobertura antigua en los metadatos internos y la contención aceptada de PDF/QR
ante evidencia presente no verificable. La interfaz habitual y el PDF omiten
leyendas técnicas; el bloqueo conserva un mensaje accionable. Reutiliza el
vínculo del intento y no abre recuperación moderna ni cambia la compactación
o el traslado vigentes. La continuación de
Ahora 3 requiere preparar primero el cierre moderno individual, antes del masivo.
Se retoma después del corte de descargas y su salida autorizada; sus invariantes
y el orden relativo de las demás líneas permanecen intactos.

El orden y alcance macro se toman exclusivamente de
[`ROADMAP.md`](../../ROADMAP.md); el inventario y dependencias están en el
[portafolio](development-portfolio.md). Los diseños futuros no describen
capacidades implementadas. La preparación no autoriza por sí sola implementar,
publicar o desplegar; cada operación conserva su alcance autorizado.

## Condiciones de continuidad

- Antes de usar un formato antiguo para una nueva importación, revisar tipo
  documental y condición IVA explícitos según PF-13. La adaptación del formato
  seleccionado sigue pendiente y no modifica lotes anteriores.
- El análisis de alícuotas por fila está anotado para la próxima versión,
  sin prioridad de implementación ni cambios de configuración autorizados.
- La revisión visual local acordada para la [UI de lotes](pf-17-lotes-ui-design.md)
  precede a publicar esa implementación; no queda cerrada por otros controles.
- El cierre operativo aceptado de v0.3.8 tiene su evidencia en el plano de
  control. No repetir aquel preflight o ensayo sin una nueva operación o
  evidencia que lo justifique; una operación nueva exige su respaldo y controles
  aplicables. No inferir la cobertura actual desde una aceptación histórica.

## Cómo retomar

1. Revisar estado de Git y sincronía con `origin/main`, preservando cambios ajenos.
2. Leer `VISION.md`, Ahora 1 del roadmap y el diseño de notas individuales;
   cerrar la aceptación y preparar la salida del corte fiscal. Las descargas
   y PF-04/PF-02 conservan su continuación posterior.
3. Usar el [índice de agentes](README.md) para abrir sólo contratos/runbooks
   aplicables; completar el checklist fiscal antes de implementar si corresponde.
4. No consultar ni modificar producción sin autorización explícita y el
   enrutamiento hacia `vps-admin`.

El [archivo histórico](../project/history/README.md) preserva el handoff anterior.
No es necesario leer auditorías o diseños cerrados para reconstruir el siguiente
paso; sólo se consultan para rastrear una decisión o proteger un contrato afectado.
