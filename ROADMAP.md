# Roadmap de FactuFlow

Última revisión: 04/10/2026

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

### Puerta previa — estabilización del estado actual

**Prioridad:** P1, antes de nuevas capacidades. La
[auditoría integral](docs/project/analysis/auditoria-integral-2026-10.md)
delimita los problemas de persistencia y lecturas fiscales. Cerrar en unidades
separadas:

- **PF-03/PF-04/PF-14:** capacidad de persistencia fiscal fiel en todos sus
  consumidores, incluidos importación, duplicados y recuperación.
  Conservar precisión PF-03B, snapshots y estados inciertos; no fusionar historia
  ni imponer límites silenciosos.
- **PF-03/PF-04/PF-17:** corregir bases de IVA y presentación/agregación de
  monedas desde hechos conservados. Cerrar autoridad funcional de agrupación o
  conversión histórica; no depende de PF-05 ni del dashboard futuro.

El [portafolio](docs/agents/development-portfolio.md) adjudica responsables y
aceptación. Esta puerta no es un refactor global ni una única implementación
mezclada. Los cortes P1 siguientes conservan sus dueños; coordinar su preparación
común para no crear validaciones o máquinas fiscales paralelas.
Cada integración de runtime exige auditoría verde. Las
reparaciones fiscales de la puerta se coordinan con los cortes 1–3: cada unidad
puede integrarse al cumplir su contrato y sus checks, sin esperar una reparación
conjunta de todo el proyecto. Las capacidades nuevas esperan el cierre de los
P1 que afectan sus consumidores.

### 1. PF-13 — fidelidad del receptor en importación fiscal

**Prioridad:** P1 fiscal.

Conservar documento y nombre suministrados y resolver condición IVA desde el
archivo o una configuración explícita. Admitir consumidor final identificado
con CUIT/CUIL: identificación y condición fiscal son datos independientes.
Corregir conjuntamente la pérdida del documento bajo el umbral y el rechazo
general de CUIT con consumidor final; señalar diferencias reales entre archivo
y plantilla antes de emitir, sin inferir una inscripción ni cambiar datos
silenciosamente. El riesgo demostrado de emitir sin la identificación esperada
o bloquear una combinación válida justifica adelantar este corte acotado.
Preservar los casos anónimos permitidos, la compatibilidad RG 5616, duplicados,
historia e idempotencia. No espera el rediseño P2 del constructor o de la UI.
Motivo, fuentes, transición legacy y aceptación en el
[diseño de fidelidad del receptor](docs/agents/pf-13-receptores-importacion-design.md).

### 2. PF-03/PF-13 — admisibilidad y revisión de importes

**Prioridad:** P1 fiscal. Evitar que alícuotas sin soporte se conviertan en IVA
cero y que la revisión muestre un total distinto del cálculo decimal vigente.
Usar preparación fiscal común sin cambiar redondeos PF-03B ni agregar pasos.
La ampliación de categorías permanece P2. Alcance, compatibilidad y aceptación
en el [diseño de importes y previsualización](docs/agents/pf-03-04-importes-previsualizacion-design.md).

### 3. PF-02/PF-04 — comparación fiscal en recuperación legacy

**Prioridad:** P1 fiscal. Comparar componentes fiscales disponibles antes de
reconstruir/vincular un autorizado; conservar CAE e incertidumbre ante diferencias.
Preservar guardas modernas y evidencia antigua. La recuperación integral moderna
es otro corte P2; alcance y aceptación en el
[diseño de reconciliación](docs/agents/pf-02-04-reconciliacion-integral-design.md).

### 4. PF-11/PF-15 — recuperación y trazabilidad operativa

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

### 1. PF-04/PF-02 — evidencia y reconciliación integral

**Prioridad:** P2 fiscal.

Preservar instantáneas históricas correctas en comprobantes, PDFs e informes,
y la solicitud fiscal mínima necesaria para recuperar intentos unitarios y
masivos con seguridad. Extender la comparación y las transiciones modernas sin
saltar guardas ni reemitir; comparte el [diseño de reconciliación](docs/agents/pf-02-04-reconciliacion-integral-design.md).
PF-05 externo es opcional y no bloquea padrón, notas ni emisión.

### 2. PF-09/PF-12/PF-14 — contratos e invariantes de plataforma

**Prioridad:** P2, elevable por evidencia.

Priorizar coordinación WSAA entre consumidores/procesos y tickets cifrados,
con identidad, renovación y recuperación seguras. Contrato en el
[diseño WSAA](docs/agents/pf-09-wsaa-coordinacion-cache-design.md).
Endurecer certificados/ambientes, constraints reversibles y contratos HTTP por
cortes de dominio; no exigir terminar toda la plataforma para un consumidor.

### 3. PF-18/PF-09 — padrón de clientes y alta de emisores

**Prioridad:** P2 fiscal y administrativa. Consultar ARCA para completar datos
por CUIT y detectar cambios de régimen; conservar fuente y fecha de verificación.
Anticipar y agrupar consultas, reutilizar caché y renovar fuera del tramo de CAE.
Mantener alternativas manual/PDF y resolver credenciales del primer emisor;
no convertir ausencia de respuesta en CF ni alterar solicitudes congeladas.
Depende de la capacidad WSAA necesaria, receptor P1 y preparación común.
Política de actualización, límites y aceptación en el
[diseño de padrón](docs/agents/pf-18-09-padron-clientes-emisores-design.md).

## Más adelante

Estas líneas están aceptadas, pero no deben desplazar problemas fiscales u
operativos confirmados:

- **PF-05, P2 fiscal:** reconstrucción histórica externa opcional, reanudable y
  con procedencia desde ARCA, después del snapshot PF-04. No es requisito para
  emitir ni para reconciliar intentos locales. Alcance en el portafolio.
- **PF-03/PF-04/PF-13, P2 fiscal:** separar tasa cero, exento, no gravado y
  tributos, y ampliar alícuotas con soporte completo hasta PDF/informes.
  Preservar interpretación histórica y consumir el
  [dominio común de importes](docs/agents/pf-03-04-importes-previsualizacion-design.md).
- **PF-04/PF-17/PF-13, P2:** preparar NC/ND desde un comprobante autorizado,
  con asociado, alcance e importes explícitos; usar evidencia histórica y
  revisión común. Contrato en el [diseño de notas guiadas](docs/agents/pf-04-17-notas-guiadas-design.md).
- **PF-10:** exportaciones, resguardo confirmado y liberación segura de
  almacenamiento. **P2**; depende de preservación histórica PF-04 y recuperación
  PF-11. Alcance en el [portafolio](docs/agents/development-portfolio.md).
- **PF-13 — plantillas contables e importación fiscal:** permitir una misma
  plantilla con tipo (`FC`, `NC`, `ND`) y letra (`A`, `B`, `C`) en columnas
  separadas, CUIT y condición IVA del receptor por fila. Anticipar requisitos
  condicionales en el constructor y validarlos en el lote: los comprobantes A
  requieren CUIT válido y condición compatible; las notas requieren su asociado.
  Mostrar cómo se interpretará el Excel, con neto, IVA y total diferenciados,
  sin exigir códigos técnicos. Aceptar alias inequívocos como «Monotributista»
  para «Monotributo», evitando correcciones manuales de significado equivalente;
  distinguir documento y condición, con procedencia visible y fechas de emisión,
  servicio desde/hasta y vencimiento. **P2 fiscal y de usabilidad**, sin desplazar
  el corte P1 de fidelidad del receptor ni repetirlo. Depende de conservar
  PF-01/PF-03 y el aislamiento multiemisor;
  comparte claridad de uso con PF-17 y contratos con PF-14. Alcance, auditoría,
  compatibilidad y aceptación en el
  [diseño de plantillas contables](docs/agents/pf-13-plantillas-contables-design.md).
  Consume preparación fiscal común y padrón anticipado cuando esté disponible;
  no agrega otro cálculo ni una consulta obligatoria por fila o al emitir.
- **PF-13 — procesos largos y eficiencia, P2:** límites de recursos y tareas
  reanudables generales, conservando invariantes fiscales. El reintento de lotes
  parciales, su progreso y la recuperación de reservas terminales están cubiertos
  por el [contrato del parche cerrado](docs/agents/pf-13-17-reintentos-seguros-parche.md). Alcance restante en el
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
  del historial. Hacer evidentes el tipo FC/NC/ND del perfil y los datos efectivos
  del receptor y las fechas, diferenciando Excel, constantes y perfil; evitar
  seleccionar una configuración de notas al preparar facturas sin advertirlo.
  Coordinar con plantillas y duplicados PF-13, actividad PF-15 y
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
  Después del primer release de prevención de duplicados, completar la
  verificación adicional de zoom real al 200 % y lector de pantalla del diálogo,
  junto con ajustes visuales menores que no bloqueen la operación (**P3**).
  Aclarar también el resumen y la atribución visibles cuando una coincidencia
  corresponde a una emisión todavía en curso, conservando su bloqueo.
  Unificar el estado informado de esos avisos bloqueados y limitar las
  advertencias de filas a los grupos realmente afectados, sin modificar la
  evidencia ni las restricciones de emisión del control de duplicados.
  Este seguimiento no retrasa el control fiscal; cualquier defecto que impida
  revisar, cancelar o confirmar conscientemente conserva prioridad de bloqueo.
- **PF-18 — distribución e integraciones, P3:** ZIP de PDFs del lote para evitar
  descargas individuales repetidas, soporte, correo e integraciones;
  instalación simplificada y demo controlada para terceros tras
  estabilizar operación y cumplir la puerta de calidad PF-16. Preservar
  almacenamiento seguro PF-10. Alcance en el [portafolio](docs/agents/development-portfolio.md).
- **PF-18 — operación asistida mediante MCP, horizonte futuro:** permitir que
  un agente consulte, revise un Excel y prepare facturas o lotes sobre los mismos
  casos de uso de la web. La emisión conserva autorización humana verificable
  sobre los datos exactos, permisos por emisor, idempotencia y reconciliación.
  La [dirección de arquitectura](docs/agents/architecture-direction.md) orienta
  las piezas previas; sin calendario ni plan de implementación detallado y tras
  estabilizar el núcleo. No introduce otro motor fiscal ni administración ajena
  a la facturación.
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
