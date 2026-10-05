# Portafolio activo de desarrollo

Última revisión: 05/10/2026

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
| PF-03/PF-04/PF-14, capacidad de persistencia | Puerta previa | P1 fiscal | Datos admitidos persistibles fielmente sin límites silenciosos ni pérdida de precisión | [Contrato A-01](pf-03-04-14-persistencia-fiel-design.md); implementación pendiente; preservar historia y recuperación; asociación A-02 cerrada por su contrato |
| PF-03/PF-04/PF-17, lecturas actuales | Puerta previa | P1 | Bases de IVA correctas y moneda explícita en detalle, ventas, IVA y ranking | [Auditoría A-03](../project/analysis/auditoria-integral-2026-10.md); autoridad de agrupación/conversión por cerrar; sin dependencia PF-05 |
| PF-13, fidelidad del receptor | Ahora 1 | P1 fiscal | Conservar identificación y condición explícitas; admitir CF identificado con CUIT/CUIL | [Contrato acotado](pf-13-receptores-importacion-design.md); preserva RG 5616, duplicados, historia e idempotencia |
| PF-03/PF-13, admisibilidad y revisión | Ahora 2 | P1 fiscal | Tasas efectivamente soportadas y revisión igual al cálculo decimal | [Importes/previsualización](pf-03-04-importes-previsualizacion-design.md); preserva PF-03B |
| PF-02/PF-04, recuperación legacy | Ahora 3 | P1 fiscal | Comparación fiscal suficiente antes de atribuir/reconstruir un autorizado | [Reconciliación](pf-02-04-reconciliacion-integral-design.md); guardas modernas intactas |
| PF-11/PF-15, recuperación operativa | Ahora 4 | P1/P2 | Backups trazables, escrituras posteriores y soporte comprensible | [Contrato acotado](pf-11-15-recuperacion-trazabilidad-design.md); plano de control externo |
| PF-04/PF-02, evidencia y recuperación integral | Después 1 | P2 fiscal | Historia inmutable y solicitud mínima para recuperar intentos modernos, unitarios y masivos | [Reconciliación](pf-02-04-reconciliacion-integral-design.md); contratos de moneda, IVA, emisor y paginado |
| PF-05 | Más adelante | P2 fiscal | Reconstrucción histórica externa opcional, reanudable y con procedencia desde ARCA | PF-04; no bloquea emisión, padrón, notas ni reconciliación local |
| PF-09 | Después 2 | P2 elevable | WSAA coordinado y tickets cifrados; propiedad/rotación de certificados y ambientes | [Contrato WSAA](pf-09-wsaa-coordinacion-cache-design.md); seguridad y migraciones |
| PF-12 | Después 2 | P2 elevable | Constraints y migraciones reversibles para invariantes críticas | Acompaña cortes de dominio; no es migración masiva aislada |
| PF-14 | Después 2 | P2 | Contratos HTTP, errores y concurrencia CRUD coherentes | Consumido por UI, soporte y procesos largos |
| PF-18/PF-09, padrón | Después 3 | P2 fiscal/administrativa | Situación registral desde ARCA, actualización de clientes y alta de emisores por CUIT | [Padrón](pf-18-09-padron-clientes-emisores-design.md); WSAA necesario y receptor/preparación comunes |
| PF-03/PF-04/PF-13, categorías de importes | Más adelante | P2 fiscal | Tasa cero, exento, no gravado, tributos y alícuotas con soporte completo | [Importes/previsualización](pf-03-04-importes-previsualizacion-design.md); PF-04/PF-12 |
| PF-04/PF-17/PF-13, notas guiadas | Más adelante | P2 fiscal/administrativa | NC/ND desde original autorizado, con asociado y revisión coherentes | [Notas](pf-04-17-notas-guiadas-design.md); snapshot mínimo y preparación común |
| PF-10 | Más adelante | P2 | Resguardo confirmado, exportaciones y liberación segura de almacenamiento | PF-04, PF-11 y propiedad de artefactos |
| PF-11/PF-15, automatización posterior | Más adelante | P2 | Backups cifrados automatizados, retención, alertas y recuperación hacia un VPS nuevo | Recuperación operativa; diseño específico al abrir el corte e instalación en el plano de control |
| PF-13, plantillas y procesos largos | Más adelante | P2 fiscal/operativa | Interpretación contable verificable y lotes eficientes | PF-01/PF-03, garantías PF-12/PF-14 y UX PF-17; [plantillas](pf-13-plantillas-contables-design.md) |
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
- PF-02/PF-04: comparación legacy P1 y recuperación integral P2 en cortes
  separados; usar solicitud congelada, conservar incertidumbre y coordinar
  grafo RECE. [Contrato de reconciliación](pf-02-04-reconciliacion-integral-design.md).
- Importación histórica externa PF-05 opcional, Más adelante, con alcance,
  límites, journal y cobertura; no retrasa la recuperación local ni nuevos consumidores.

### PF-09/PF-12/PF-14

- Rotación y propiedad durable de certificados, TRA y caché WSAA.
- Corte prioritario: [coordinación y cifrado WSAA](pf-09-wsaa-coordinacion-cache-design.md),
  incluyendo API/worker, reinicio, corrupción y material de recuperación.
- Diferencias de homologación y producción sin asumir equivalencias.
- Constraints, carreras, errores posteriores al commit y unicidad.
- Mensajes HTTP previsibles y sanitizados.

### PF-10/PF-13/PF-16/PF-17/PF-18

- PF-03/PF-13: [importes y previsualización común](pf-03-04-importes-previsualizacion-design.md).
  El corte P1 corrige tasas convertidas a cero y diferencias de revisión sin
  cambiar redondeos; la ampliación P2 cubre categorías hasta PDF e informes.
  Preparación individual y muestra Excel comparten autoridad decimal.
- PF-18/PF-09, P2, Después 3: [padrón para clientes y emisores](pf-18-09-padron-clientes-emisores-design.md).
  ARCA acredita situación registral en una consulta fechada; deduplicar/agrupar,
  renovar anticipadamente y emitir con snapshot. Mantener bootstrap manual/PDF,
  permisos, evidencia histórica y CF identificado válido; no fallback fiscal a CF.
- PF-04/PF-17/PF-13, P2, Más adelante: [notas guiadas](pf-04-17-notas-guiadas-design.md),
  con asociado y alcance explícitos desde original autorizado. Reutiliza
  validación de notas y revisión común; no implementa cuentas corrientes.
- PF-13, **P1 fiscal, Ahora 1**: preservar documento/nombre y condición fiscal
  explícitos, admitiendo consumidor final identificado con CUIT/CUIL. Corregir
  la pérdida del documento y el rechazo general de CUIT con CF como una unidad;
  señalar diferencias reales entre archivo y configuración. El riesgo demostrado
  justifica adelantarlo sin elevar toda PF-13. El
  [diseño de fidelidad del receptor](pf-13-receptores-importacion-design.md)
  concentra motivo, fuentes, transición legacy y aceptación; no modifica el
  contrato cerrado de duplicados ni reinterpreta el parche RG 5616.
- PF-13, con PF-17: constructor de plantillas e importación contable con
  `FC`/`NC`/`ND`, letra, CUIT y condición IVA por fila; requisitos condicionales,
  vista de interpretación y mensajes que identifiquen fila y columna. **P2,
  Más adelante**: alias inequívocos, como «Monotributista» a «Monotributo», y
  procedencia visible del receptor y fechas reducen correcciones manuales y
  configuraciones equivocadas. Consume la regla P1, sin implementarla de nuevo. El
  [diseño de plantillas contables](pf-13-plantillas-contables-design.md)
  adjudica los hallazgos de la auditoría y conserva versiones, perfiles,
  importes, confirmación fiscal e idempotencia. No reabre el rediseño cerrado de
  lotes ni incorpora una segunda línea de constructor.
  Consume preparación común y consultas registrales anticipadas cuando estén
  disponibles; no exige terminar el rediseño UI ni consultar ARCA por cada fila.
- PF-18/PF-17, P2: cantidad y total en pesos del mes actual y anterior por fecha
  del comprobante, períodos explícitos y último comprobante con sus dos fechas.
  Las notas de crédito restan del importe, no de la cantidad. El
  [diseño del dashboard mensual](pf-18-dashboard-mensual-design.md) define
  cálculo, moneda, cronología, estados de consulta y pruebas; complementa
  PF-13 sin sustituir su control previo a emitir ni abrir otro motor de duplicados.
  El ajuste P3 del certificado es independiente: tilde de éxito para «Válido» e
  ícono/color coherentes para los demás estados; no espera nuevos agregados.
- PF-18, P3: ZIP de PDFs del lote y selección múltiple para evitar descargas
  individuales repetidas; generar bajo demanda y coordinar limpieza de temporales
  y resguardo con PF-10, sin duplicar políticas de almacenamiento. La comodidad
  de descarga no desplaza correcciones fiscales ni implica controlar el diálogo
  de guardado del sistema operativo.
- PF-13, P2: tareas reanudables, trazabilidad masiva y límites de recursos.
- PF-16: cobertura de reportes/PDF y pruebas por riesgo (P2), verificación local
  y portabilidad de herramientas (P3 salvo bloqueo comprobado).
- PF-17: conectividad visible y recuperación/accesibilidad que afecten operación
  (P2); ayuda contextual y ajustes de texto/presentación opcionales (P3).
  [Observabilidad](operational-observability.md) conserva la señal de conexión.
- PF-16/PF-17, P3, después del primer release de duplicados: completar las
  comprobaciones adicionales de zoom real al 200 % y lector de pantalla del
  diálogo, y corregir detalles visuales menores sin impacto operativo o fiscal.
  Incluye aclarar el resumen y la atribución de emisiones coincidentes todavía
  en curso, preservando su bloqueo.
  También unificar el estado del DTO cuando coexisten una coincidencia
  autorizada y una reserva ajena, sin alterar el bloqueo efectivo de API y UI;
  corregir las advertencias de filas de la proyección anterior para que sólo
  señalen grupos afectados, conservando el conteo y la evidencia v2 correctos.
  La falta de esas comprobaciones no se presenta como una aprobación de
  accesibilidad. Se conservan como puertas de salida la evidencia comprensible,
  el retorno seguro, el checkbox específico y los controles fiscales del
  [diseño de duplicados](pf-13-duplicados-lotes-design.md). Un defecto comprobado
  que impida utilizar esos controles se atiende antes de publicar.
- PF-17, P3: períodos rápidos en Reporte de ventas, con «Mes actual», «Mes anterior»
  y rango personalizado. Conservar fechas visibles, generación explícita y
  aislamiento por emisor; [contrato y aceptación](pf-17-reportes-periodos-design.md).
- PF-17, P2, con trazabilidad PF-15: usuario de la última emisión confirmada visible
  en la tarjeta y cabecera del lote; actividad histórica desplegada únicamente
  al consultar ese lote. El [diseño de actividad](pf-17-actividad-lotes-design.md)
  distingue carga, emisión y acciones posteriores, comparte procedencia con
  PF-13 y conserva el historial compacto. No altera el corte «Ahora» de PF-15.
- PF-17: preparación compacta de lotes, resumen de requisitos persistente y
  separación entre archivo en preparación, resultado e historial. Hacer explícito
  el tipo de comprobante del perfil y la procedencia efectiva de documento,
  condición IVA y fechas evita preparar FC con una configuración de NC o aceptar
  valores fijos sin advertirlos. **P2 de
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

## Hallazgos candidatos a delimitar

Estos hallazgos no modifican el orden aceptado ni autorizan por sí solos una
implementación. La corrección necesita una unidad y un alcance explícitos.

| Candidato | Evidencia y alcance propuesto |
|---|---|
| Mensajes de validación al iniciar sesión | Una respuesta estructurada `422` puede mostrarse como `Error: [object Object]`. Delimitar un mensaje comprensible y pruebas con entradas inválidas, preservando la validación del servidor. |
| Frontera de errores técnicos, PF-09/PF-12 | PDF está sanitizado; revisar respuestas ARCA/certificados y diagnóstico SQL sin parámetros sensibles. Conservar errores fiscales públicos controlados. [Auditoría](../project/analysis/auditoria-integral-2026-10.md). |
| Updates con `null`, PF-12/PF-14 | Validar campos obligatorios de clientes/emisores antes de persistir, conservando restricciones y rollback; no confundir ausencia con `null`. |
| Guía del wizard por ambiente, PF-09/PF-17 | Homologación necesita WSASS también en el paso de portal; propagar ambiente y comprobar ambas experiencias. |

La limpieza de guías, marcado PostgreSQL y código sin consumidores salió del
inventario activo; su evidencia está en el
[dossier de auditoría](../project/analysis/auditoria-integral-2026-10.md). Las
dependencias reales se consultan en manifests y lockfiles; nuevos usos del lector
PDF requieren reevaluar los avisos aplicables, sin mantener aquí una versión de
release como estado de instalación.

## Horizonte de operación asistida

PF-18 contempla un MCP futuro para consultar y preparar comprobantes o lotes
desde agentes. Reutilizar el caso de uso completo, incluidos controles que hoy
viven en routers, con autorización humana verificable del contenido exacto.
La [dirección de arquitectura](architecture-direction.md) conecta este horizonte
con los cortes de datos, preparación, persistencia y recuperación. No implica
implementación autorizada, calendario ni un plan detallado nuevo.

## Preparación para abrir cada corte

Los diseños específicos contienen decisiones de producto e invariantes, con
matrices de aceptación. Sus apartados pendientes son trabajo previo a codificar,
no capacidades ya implementadas. Las líneas generales necesitan delimitar una
unidad antes de convertirse en una tarea ejecutable.

| Corte | Fuente y preparación restante |
|---|---|
| Capacidad y precisión de persistencia | [Contrato A-01](pf-03-04-14-persistencia-fiel-design.md): representación y transición definidas con ensayos preparatorios; implementar adaptadores, agregados/índices, migración Alembic y matriz integrada sin alterar historia; conservar el [contrato de asociación A-02](pf-03-04-14-asociacion-cliente.md) ya estabilizado. |
| Lecturas fiscales actuales | [Auditoría A-03](../project/analysis/auditoria-integral-2026-10.md): bases desde evidencia conservada y política funcional de moneda; separar corrección actual de nuevas categorías o importación externa. |
| Fidelidad del receptor | [Diseño P1](pf-13-receptores-importacion-design.md): consumidores y transición legacy de tipo de documento/condición; lotes preparados, snapshots e intentos congelados; fuentes oficiales antes de implementar. |
| Admisibilidad, revisión y categorías | [Importes](pf-03-04-importes-previsualizacion-design.md): separar P1 de ampliación P2, contrato de preparación, tasas efectivas, lectura legacy y precisión inmutable. |
| Reconciliación | [Diseño](pf-02-04-reconciliacion-integral-design.md): comparación legacy P1, cobertura del snapshot y recuperación moderna P2; conservar ownership y guardas RECE. |
| WSAA coordinado/cifrado | [Diseño](pf-09-wsaa-coordinacion-cache-design.md): mecanismo multiproceso, claves, renovación, transición y recuperación; no requiere otro servicio. |
| Padrón de clientes/emisores | [Diseño](pf-18-09-padron-clientes-emisores-design.md): mapeo oficial, permisos del servicio, datos actuales frente a operación, caché/renovación y bootstrap del primer emisor. |
| Notas guiadas | [Diseño](pf-04-17-notas-guiadas-design.md): evidencia mínima del original, asociados y alcance parcial/total; reutiliza preparación y controles vigentes. |
| Recuperación/trazabilidad | [Diseño operativo](pf-11-15-recuperacion-trazabilidad-design.md): productor y cobertura de evidencia, escrituras posteriores y permisos; evidencia de instalación en el plano de control. |
| Plantillas contables | [Diseño](pf-13-plantillas-contables-design.md): consumir la regla P1 de receptor; alias inequívocos, requisitos legacy, controles de importes y casos sintéticos. Sus reglas fiscales se verifican con fuentes oficiales antes de codificar. |
| Actividad de lotes | [Diseño](pf-17-actividad-lotes-design.md): fuente/orden de actor, cobertura histórica y consulta paginada. Reutiliza la procedencia mínima de duplicados, sin dependencia circular. |
| Dashboard mensual | [Diseño](pf-18-dashboard-mensual-design.md): fuente temporal, moneda histórica, agregados y cobertura; el ícono tiene aceptación independiente. |
| Reportes con períodos rápidos | [Diseño](pf-17-reportes-periodos-design.md): calendario e interacción definidos; verificar helper y consumidores al implementar. |
| UI de lotes | [Diseño](pf-17-lotes-ui-design.md): distribución final y totales disponibles; revisión del usuario en la aplicación local antes del primer push de implementación. |
| PF-04/PF-05 | Delimitar instantáneas, cobertura histórica y contratos de informes; después, diseño de importación externa opcional con procedencia, reanudación y aceptación. |
| PF-09/PF-12/PF-14 | Delimitar por dominio certificados/ambiente, garantía de persistencia o contrato HTTP; migración, consumidores, error, concurrencia y rollback según el corte. No exigir completar una plataforma entera. |
| Otras líneas generales | Automatización, distribución, eficiencia y consulta opcional: conservar alcance del inventario y cerrar diseño acotado, dependencias y aceptación antes de codificar. |

## Orden aceptado

La puerta previa de estabilización precede a capacidades nuevas; sus reparaciones
se delimitan por contrato, sin mezclar un refactor global. Los cortes P1 de
receptor, admisibilidad/revisión y comparación legacy mantienen sus dueños y se
coordinan con esa preparación común antes de recuperación/trazabilidad.
Tooling habilita la integración de runtime con CI verde; cada reparación fiscal
se integra por su propio contrato y checks. No se exige cerrar todos los P1 en
una única unidad ni se bloquea una reparación esperando su propio resultado.
Después: evidencia/reconciliación integral, WSAA y capacidades de plataforma
necesarias, y padrón para clientes/emisores. La historia externa PF-05 pasa a
Más adelante y no bloquea estos consumidores. Constructor, categorías completas
y notas guiadas son P2; ZIP permanece P3. El orden autoritativo está en el roadmap.
El parche RG 5616 cerrado se
consulta en su [contrato](rg-5616-condicion-iva-receptor-parche.md) y
[dossier fiscal](../project/releases/rg5616-condicion-iva.md).
La [validación de planificación](../project/analysis/confiabilidad-arca-roadmap.md)
conserva evidencia, fuentes y límites. Esta decisión de planificación
no implementa capacidades ni autoriza publicación, despliegue o emisiones.
Se conservan los requisitos de respaldo y recuperación de cada operación.
La publicación de duplicados se consulta en su dossier y no autoriza
a iniciar otra unidad ni incorpora el rediseño visual completo o la ampliación
del constructor.

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
9. Preparación, categorías y reconciliación comparten representación fiscal
   mínima versionada; no crean tres cálculos ni cambian hashes históricos.
10. Padrón consulta anticipadamente con identidad autorizada; su estado actual
    no modifica solicitudes congeladas, CAEs ni evidencia histórica. Bootstrap
    del primer emisor no depende circularmente de certificados todavía inexistentes.
11. Notas consumen snapshot mínimo, cálculo y asociados comunes; no exigen
    reconstrucción histórica externa completa ni introducen cuentas corrientes.

## Líneas cerradas

La cadena vulnerable de construcción frontend se retiró con Tailwind 4.3.3.
El [contrato de navegadores](../../frontend/README.md#navegadores-compatibles)
conserva estilos y foco y acepta Firefox 128+. Las herramientas del backend
resuelven sus alertas con pytest 9.0.3, pytest-asyncio 1.3.0 y Black 26.3.1;
la auditoría Python abarca ejecución y desarrollo. Estos cortes no cierran la
evolución de calidad PF-16 ni acreditan una instalación productiva.

La asociación administrativa A-02 tiene un
[contrato compartido](pf-03-04-14-asociacion-cliente.md): ambigüedad conserva
snapshot y autorización sin una ficha arbitraria. No cierra capacidad A-01
ni todas las fallas posibles de creación administrativa.

El contrato de [instantes operativos](pf-12-15-17-tiempo-operativo.md) comunica
UTC explícito y muestra hora argentina con compatibilidad para sus campos
históricos de procedencia UTC. No cierra la evolución de actores y eventos de
PF-15/PF-17 ni atribuye zona a antecedentes desconocidos.

El parche de emisión parcial y reintentos está implementado; su
[contrato](pf-13-17-reintentos-seguros-parche.md) y
[dossier](../project/releases/pf13-17-reintentos-seguros.md) conservan el alcance
y la evidencia. No cierra plantillas, eficiencia general ni el rediseño visual.

El corte de prevención de duplicados PF-13/PF-17 está implementado; su contrato
vive en [duplicados](pf-13-duplicados-lotes-design.md) y su publicación en el
[dossier](../project/releases/pf13-duplicados-candidate.md). Esto no cierra las
otras unidades de PF-13/PF-17 ni acredita el estado de una instalación.

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
