# PF-11/PF-15 — recuperación y trazabilidad operativa

Fecha: 05/09/2026. Estado: alcance futuro delimitado; implementación pendiente.

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

## Delimitación y pendientes técnicos

Antes de codificar, inventariar la evidencia existente y definir su productor,
consumidor, formato mínimo, permisos, precisión temporal, conservación y manejo
de escrituras intermedias. Cerrar el alcance de las señales de Sistema y las
pruebas con el contrato real de respaldo; no inventar cobertura retrospectiva.

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
