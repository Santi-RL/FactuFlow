# PF-11/PF-15 — recuperación y trazabilidad operativa

Fecha: 10/10/2026. Estado: contrato del corte operativo; automatización posterior pendiente.

## Objetivo y horizonte

Permitir identificar qué estado puede recuperarse con un backup preoperación
y explicar qué escrituras u operaciones ocurrieron después. Distinguir evidencia
comprobada, incompleta y desconocida sin presentar un respaldo como recuperable
sólo porque existe un archivo con fecha reciente.

El corte operativo pertenece a «Ahora»: P1 para recuperación y P2 para señales
y soporte. Su posición exacta vive en [ROADMAP.md](../../ROADMAP.md). La
automatización cifrada, retención, alertas y recuperación hacia un VPS nuevo
permanece como un corte posterior P2 en «Más adelante».

## Responsabilidades

| Dueño | Alcance |
|---|---|
| FactuFlow, PF-11/PF-15 | Contrato de evidencia mínima, vínculo con operaciones, señales administrativas y diagnóstico de aplicación. |
| Plano de control `VPS Hostinger` / `vps-admin` | Estado de la instalación, acceso, comandos, backups privados, restauración y evidencia operativa concreta. No duplicarlos en este repositorio. |
| [Observabilidad](operational-observability.md) y [soporte](support-runbook.md) | Reutilizar estados, correlación y recorridos existentes; extender sólo los faltantes comprobados. |
| PF-13 y [actividad de lotes](pf-17-actividad-lotes-design.md) | Consumir procedencia compartida de operaciones; no esperar la lista visual completa para registrar autoría o excepciones. |

## Resultado requerido

- Identificar respaldo, propósito, instante inequívoco, componentes incluidos y
  operación para la que se tomó. Conservar referencia privada e integridad según
  el contrato de backup vigente, sin exponer secretos ni rutas de acceso en UI.
- Relacionar el punto respaldado con las escrituras posteriores relevantes.
  Explicar qué quedaría fuera de una restauración y cuándo esa cobertura no se
  puede acreditar. No afirmar automáticamente que un backup sigue siendo apto
  para un rollback después de nuevas autorizaciones fiscales.
- Mantener resultado de la comprobación o ensayo y su momento, sin confundir
  archivo creado, backup íntegro y restauración comprobada. La ausencia de
  evidencia debe verse como «No verificado», no como éxito ni como pérdida
  demostrada de datos.
- Mostrar a administración/soporte sólo estado, alcance y próximo paso útil.
  Reutilizar la sección Sistema y los permisos vigentes; no añadir confirmaciones
  por factura, recordatorios obligatorios ni requisitos manuales a cada operador.
- Correlacionar operación, actor, emisor y resultado con los registros existentes.
  No registrar que alguien leyó una advertencia ni sustituir incertidumbre fiscal
  por un fallo genérico. Evitar duplicar eventos por cada consulta de estado.
- Mantener el material sensible en el plano de control o rutas privadas. El
  resumen de aplicación no es un nuevo repositorio de backups ni un mecanismo
  de restauración automática.

## Inventario y contrato del corte operativo

La instalación revisada produce un manifiesto, índice de checksums, huellas de
tablas del mismo snapshot que el dump, validación de restauración aislada y
cotejos posteriores. Son evidencia privada del plano de control, no entradas
para importar datos en FactuFlow. Sus formatos históricos no son una API estable.
La aplicación ya conserva operaciones idempotentes con actor/emisor/resultado,
intentos fiscales, eventos de lotes y eventos administrativos. Se reutilizan esas
referencias en el diagnóstico privado; no se crea otro journal ni se reconstruye
autoría a partir de timestamps antiguos.

No añade autoría retrospectiva a escrituras que no la conservan ni convierte
huellas de estado en un historial completo. Ante esa limitación, el diagnóstico
privado declara atribución desconocida y preserva los estados cotejados. La
ampliación histórica/visual conserva su corte futuro PF-17/PF-15.

El productor del resumen es el responsable de la instalación, después de
comprobar esa evidencia. Debe enlazar el respaldo, la operación que motivó su
creación, los informes y el último cotejo por sus identidades y hashes. La
aplicación consume sólo ese resumen privado, versionado y acotado; no ejecuta
comandos del manifiesto, descarga material ni restaura datos.

- Configuración opcional: `RECOVERY_INSTALLATION_ID` (UUID no secreto de la
  instalación) y `RECOVERY_EVIDENCE_PATH` (archivo JSON privado de sólo lectura).
  Ambos ausentes mantienen la señal «No verificado», sin bloquear la aplicación.
- Identidad: UUID de respaldo y operación; propósito enumerado; instante del
  snapshot con zona, o `null` cuando sea desconocido; creación separada, SHA
  exacto de código de origen y hash del manifiesto.
- Componentes: base de datos, certificados/claves, configuración y, si existe,
  runtime. Estado presente/ausente/desconocido y hash cuando está presente.
- Integridad y ensayo: resultado, instante, hash del informe y hash del
  manifiesto al que pertenecen. El ensayo declara los componentes comprobados;
  un ensayo parcial no acredita recuperación completa.
- Copia externa: evidencia independiente, fechada y con precisión declarada.
  No hereda un booleano histórico del manifiesto inicial.
- Último cotejo: instante, informe enlazado al mismo manifiesto y estado de base,
  archivos, configuración y escrituras fiscales/administrativas (cambios, sin cambios detectados
  o desconocido). Debe usar comparación consistente de todas las tablas para
  declarar igualdad de base; conteos iguales o falta de eventos no bastan. Base
  y actividad requieren el componente de base presente; archivos gestionados
  compara certificados/claves y requiere ese componente presente; configuración
  requiere su componente presente. Si falta el componente, el resultado es
  desconocido, sin acreditar un cotejo contra material ausente.
- Los registros privados de soporte conservan los actores, emisores, recursos,
  resultados y referencias de las operaciones afectadas. El resumen de Sistema
  es de instalación: no contiene identidades de clientes/emisores, CAEs, rutas,
  mensajes libres, payloads ni eventos de otros emisores.
- Los informes conservan su fecha histórica. **La cobertura actual siempre es
  desconocida**: una lectura del resumen no comprueba que desde el cotejo no hubo
  escrituras. No se inventa un vencimiento, ni se presenta aptitud automática
  para rollback, aunque el último cotejo no haya detectado cambios.
- Un archivo ausente, inválido, excesivo, ajeno a la instalación o con fechas
  futuras/contradictorias devuelve diagnóstico sanitizado; no reutiliza un
  éxito anterior. Se lee fuera del loop de eventos, con un límite de 64 KiB.
- El productor publica mediante reemplazo atómico, con permisos de instalación
  y fuera de Git. Se conserva el original privado según el runbook aplicable,
  sin introducir una política nueva de retención. Tras restaurar/clonar una
  instalación se retira el resumen o se cambia la identidad hasta revalidarlo.

`GET /api/health/recovery` es exclusivo de administradores y devuelve una
allowlist. `Sistema > Estado` muestra componentes, fechas de integridad/ensayo,
último cotejo y próximo paso; no añade polling, confirmaciones ni obligaciones
a cada operador. Las respuestas atrasadas se descartan.
El [contrato de instalación](../setup/recovery-evidence.md) define el formato y
la validación por consola. La aplicación valida una proyección de un productor
confiable; no verifica el contenido de los informes ni concede permiso de restore.

## Invariantes y revisión previa al código

Nivel 2 por diagnóstico de recuperación. Checklist fiscal aplicado al alcance:
consumidores nuevos API administrativa, Sistema y soporte; sin cambios en los
servicios fiscales, modelos, migraciones, worker, reintentos o reconciliación.
La lectura no llama a ARCA ni escribe en base, modifica reservas, vincula CAEs,
emite, libera almacenamiento o ejecuta restauración. Una operación incierta
conserva íntegramente su estado y procedencia. Los locks fiscales, fechas,
confirmaciones e idempotencia no se modifican, por lo que sus carreras se cubren
por las suites existentes, no mediante una segunda implementación.

Matriz antes de implementar: autenticación/admin; archivo ausente/ilegible/JSON
inválido/excesivo; identidad ajena; componentes faltantes; fechas sin zona,
desconocidas, futuras o contradictorias; integridad/ensayo fallidos o parciales;
cotejo con escrituras fiscales y administrativas; igualdad histórica sin promesa
actual; ausencia de datos privados; consultas repetidas sin mutaciones; UI con
hora argentina y respuesta atrasada descartada. La restauración real se prueba
únicamente en la preparación autorizada de release, en entorno aislado.

## Delimitación y pendientes técnicos

La traducción concreta de los informes privados al resumen pertenece al plano
de control. No inferir cobertura retrospectiva, nueva autorización fiscal o
ausencia de actividad desde una pantalla o desde la fecha de un archivo.

Automatizar planificación, retención, cifrado y alertas requiere el corte
posterior y su diseño específico. PF-10 conserva resguardo y liberación de
almacenamiento; esta unidad no habilita borrados ni modifica su política.

Toda comprobación productiva o ensayo de recuperación sigue la autorización
vigente y el [flujo de producción](production-workflow.md). Documentar este
alcance no autoriza acceder al VPS, restaurar datos, rotar claves ni desplegar.

## Aceptación mínima

| Caso sintético | Evidencia esperada |
|---|---|
| Backup preoperación completo | Identidad, propósito, instante y alcance inequívocos; resultado de verificación separado de creación. |
| Escrituras posteriores, incluidas autorizaciones | Cobertura de recuperación y límites explícitos; no prometer un rollback que borre evidencia fiscal nueva. |
| Componentes ausentes, archivo ilegible o verificación fallida | Estado accionable y honesto; nunca éxito por la sola existencia del archivo. |
| Registro histórico incompleto o convención horaria desconocida | Límite visible, sin reconstrucción inventada. |
| Permisos, otro emisor y respuesta atrasada | Evidencia y señales aisladas; sin secretos ni datos ajenos. |
| Operación incierta o reconciliada | Se conserva su resultado real y procedencia; consultar estado no reintenta emisión. |
| Ensayo controlado de restauración autorizado | Evidencia privada de inicio y consulta correcta; sin CAE real y sin afectar producción. |

La revisión documental es Nivel 0. Al implementar aplicar
[puertas de calidad](change-quality-gates.md), [testing](testing.md) y
[QA manual](manual-qa.md); backups, restauración o persistencia sensible requieren
Nivel 2 y el [checklist fiscal](fiscal-change-checklist.md) cuando exista alcance fiscal.
El cierre conserva evidencia privada y actualiza los runbooks afectados.
