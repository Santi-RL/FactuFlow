# Resumen privado de evidencia de recuperación

Este contrato permite a `Sistema > Estado` mostrar hechos comprobados por el
responsable de la instalación. No crea backups, verifica artefactos ni autoriza
restaurar datos. Procedimientos y originales pertenecen al plano de control.

## Productor y fuentes

El responsable operativo normaliza manifiesto e índice de integridad, informes
de restauración y cotejos posteriores. Comprueba vínculos al mismo respaldo,
componentes y operación. No altera originales sellados: la copia externa puede
tener evidencia posterior e independiente del manifiesto inicial.

Las identidades opacas de respaldo y operación se conservan en el índice privado
con los hashes de las fuentes. No deducir el instante del snapshot desde el nombre
del directorio, creación del archivo o fecha fiscal; si es desconocido usar
`captured_at: null`. Un cotejo de estados no reconstruye todas las escrituras.
Cambios en tablas fiscales no equivalen automáticamente a nuevos CAEs.

La aplicación no comprueba que los hashes declarados correspondan a los informes
originales: valida estructura, consistencia y pertenencia de la proyección. Un
archivo modificado por el responsable puede declarar hechos falsos; por eso
debe tener los mismos controles de acceso que la configuración operativa.

## Formato y validación

El esquema exacto es
[`RecoveryEvidence`](../../backend/app/schemas/recovery.py). Desde `backend/`:

```bash
python -c "import json; from app.schemas.recovery import RecoveryEvidence; print(json.dumps(RecoveryEvidence.model_json_schema(), indent=2))"
```

| Campo | Contrato |
|---|---|
| `version` | `1`. Campos adicionales o claves JSON repetidas se rechazan. |
| `installation_id`, `backup_id`, `operation_id` | UUID; instalación coincidente con configuración. Referencias enlazadas al índice privado, sin datos personales. |
| `purpose` | `pre_update`, `pre_maintenance`, `pre_resolution` o `manual`. |
| `source_code_sha` | SHA Git completo de 40 caracteres, comprobado en el origen; no inferir desde el candidato o runtime actual. |
| `created_at`, `captured_at` | ISO 8601 con zona o `null`. Creación del respaldo e instante exacto del snapshot son hechos diferentes. |
| `manifest_sha256` | SHA-256 del manifiesto original, 64 caracteres hexadecimales minúsculos. |
| `components` | Hasta cuatro elementos únicos: `database`, `certificates`, `configuration`, `runtime`; `present`, `missing` o `unknown`; SHA-256 sólo si está presente. Certificados incluye claves. |
| `integrity`, `restore`, `external_copy` | `verified`, `failed` o `not_verified`. Para resultados conocidos: `checked_at` con zona, `report_sha256`, `manifest_sha256` del mismo respaldo y `components` comprobados. `time_precision`: `instant`, `minute` o `unknown`. |
| `comparison` | Opcional. `observed_at`, `report_sha256`, `manifest_sha256`; `changed`, `not_detected` o `unknown` para `database`, `managed_files`, `configuration`, `fiscal_writes` y `administrative_writes`. |
| `comparison.database_scope` | `all_tables`, `partial` o `unknown`. Sólo todas las tablas cotejadas consistentemente permiten `database: not_detected`; conteos iguales no acreditan igualdad. |

`not_verified` no declara fecha, informe ni componentes probados. Un ensayo que
acredita sólo base de datos no es una recuperación completa de certificados,
configuración o ejecutables. El cotejo de archivos incluye faltantes y nuevos;
no comparar sólo nombres presentes en el respaldo. No acreditar ausencia de
actividad desde un journal parcial. Los resultados de base y actividad requieren
`database` presente; archivos gestionados compara certificados/claves y requiere
`certificates` presente; configuración requiere `configuration` presente. Para
componentes ausentes, desconocidos u omitidos, esos resultados deben ser
`unknown`. Los hashes privados no se exponen por HTTP.

Validar antes de publicar la proyección:

```bash
python -m app.scripts.recovery_evidence --input ./data/recovery-evidence.json --installation-id 00000000-0000-4000-8000-000000000001
```

El UUID es sintético. La consola devuelve sólo estado/motivo y código distinto
de cero para entradas inválidas; no conecta a la base ni cambia archivos. Un
resultado válido acredita el contrato, no veracidad ni recuperabilidad.

## Consumo opcional de la instalación

```dotenv
RECOVERY_INSTALLATION_ID=00000000-0000-4000-8000-000000000001
RECOVERY_EVIDENCE_PATH=./data/recovery-evidence.json
```

Crear una identidad propia por instalación; no es una credencial. Conservar la
proyección en ruta privada ignorada y publicar con reemplazo atómico. Runtime
con lectura únicamente; en contenedores usar un mount privado de sólo lectura
o mecanismo equivalente. No montar todo el almacén de respaldos ni copiarlo a
una imagen, contexto de build o Git. Límite de documento: 64 KiB.

Variables opcionales: sin ellas aparece «No verificado», sin bloquear login o
facturación. Endpoint exclusivo de administradores, de alcance instalación, sin
actores, emisores, clientes, CAEs, nombres de archivos, rutas o mensajes libres.
La web no comprueba respaldos ni consulta ARCA al cargarlo.

Cada comprobación conserva su fecha histórica. Cobertura actual siempre
desconocida: puede haber escrituras posteriores. Sin TTL artificial ni estado
«Apto para restaurar». Un archivo ausente, ilegible, excesivo, ajeno o incoherente
descarta éxitos anteriores. Tras restaurar/clonar, retirar el resumen o cambiar
la identidad hasta revalidar las evidencias.

## Recuperación de una operación concreta

Aplicar [`production-workflow.md`](../agents/production-workflow.md) y el runbook
privado antes de actualizar o recuperar:

1. Identificar operación, código/esquema de origen, propósito y componentes.
   Crear respaldo preoperación consistente y registrar el punto o intervalo
   comprobado; uno antiguo íntegro no reemplaza este resguardo.
2. Probar recuperación aislada con runtime/esquema exactos; contrastar datos y
   componentes, registrando lo comprobado y lo desconocido.
3. Antes de recuperar, cotejar base y archivos. Conservar referencias existentes
   de operación, actor, emisor, recurso y resultado para cambios relevantes. Si
   falta historial o zona confiable, declarar el límite de atribución.
4. Si hubo escrituras posteriores, identificar lo que se perdería y preservar
   evidencia fiscal/reservas. Conteos iguales no prueban ausencia de cambios;
   un restore no revierte autorizaciones de ARCA. No restaurar destructivamente
   ni reemitir para suplir historia desconocida.
5. Resolver recuperación específica y autorización antes de actuar. Registrar
   resultado real, incertidumbre y próximo paso seguro; no convertir incertidumbre
   en rechazo ni crear eventos por cada consulta de Sistema.

Son pasos de mantenimiento/soporte, no acciones por factura. Automatización,
cifrado, retención y alertas permanecen en el corte posterior del roadmap.
