# PF-03/PF-04/PF-14 — asociación administrativa del receptor

Fecha: 03/10/2026.

Estado: contrato implementado. Evidencia en el
[dossier](../project/analysis/asociacion-cliente-post-cae-2026-10.md).

## Problema y autoridad

La auditoría A-02 comprobó que varios clientes administrativos del mismo emisor
y documento provocaban una excepción al guardar un comprobante después de CAE.
El esquema permite esas coincidencias; no son prueba de un receptor fiscal
distinto. El pedido de estabilizar contratos autoriza corregir esa dependencia.

El receptor fiscal de la solicitud y su snapshot son la autoridad del
comprobante. Su vínculo con una ficha administrativa es opcional y no debe
elegirse arbitrariamente cuando existen varias coincidencias.

## Contrato compartido

`FacturacionService._guardar_comprobante` resuelve el vínculo mediante un único
helper compartido:

| Situación | Resultado |
|---|---|
| Cliente elegido explícitamente | Conservar el ID bajo la validación de pertenencia previa a CAE, sin agregar otra consulta posterior |
| Sin ID y sin alta solicitada | Conservar ausencia de vínculo |
| Alta implícita, ninguna coincidencia exacta | Crear como antes |
| Alta implícita, una coincidencia exacta | Reutilizar su ID como antes |
| Alta implícita, dos o más coincidencias exactas | Conservar `cliente_id=NULL` y snapshot fiscal íntegro |

La coincidencia exige emisor, tipo y número de documento iguales. No fusiona,
elimina, reactiva ni actualiza fichas; no incorpora un constraint de unicidad
ni una migración. La ambigüedad se registra sin documento ni datos del receptor.

`cliente_id=0` ya es rechazado por el preflight fiscal vigente. No se modifica
su representación en solicitudes históricas ni la semántica previa del guardado.

## Invariantes y frontera irreversible

Nivel 2: el helper participa en persistencia posterior a autorización. Se
aplicó el [checklist fiscal](fiscal-change-checklist.md) antes y junto al código.

- Preservar DTO, hashes, payload congelado, receptor, ítems, total, CAE,
  fecha fiscal explícita, punto, numeración y origen.
- Preservar confirmación irreversible, idempotencia, locks, reservas y guardas.
- No agregar un commit, savepoint o captura general de errores. El caller
  conserva la transacción del comprobante, intento y resultado durable.
- Un error real de base después de ARCA mantiene rollback e incertidumbre
  reconciliable; nunca se interpreta como éxito ni como rechazo fiscal.
- Replay sigue precediendo validaciones mutables conforme al flujo existente
  y no pide otro CAE.

Los cuatro consumidores son emisión individual, procesamiento masivo,
reconstrucción autorizada de un intento stale y registro externo desde un lote.
Comparten `commit=False`; la API, worker y reconciliador consumen esa misma
frontera. No se altera la secuencia previa de autorización ni los métodos WSFE.

La desactivación administrativa concurrente conserva un ID explícito ya
validado, sin nueva lectura posterior. Una eliminación física ajena al flujo
normal conserva el error de FK y rollback existentes. El DELETE público de
clientes es una desactivación; no se convierte en borrado físico.

## Aceptación y recuperación

Cubrir cero, una y varias coincidencias; aislamiento por emisor y tipo; ID
explícito entre duplicados; ID ajeno y cero bloqueados antes de CAE; ausencia
de alta; snapshot, ítems y payload intactos; duplicado aparecido después del
preflight; desactivación, errores de base y rollback; los cuatro consumidores;
fallo post-CAE y replay sin segunda solicitud.

Las pruebas usan dobles fiscales y datos sintéticos sin conexión externa.
Concurrencia de reserva y numeración mantiene su matriz existente; este corte
no modifica los locks ni impone exclusividad administrativa.

No pretende desacoplar toda creación administrativa: otras fallas reales del
alta siguen conservando reconciliación. La capacidad de persistencia A-01 es
una unidad pendiente distinta; no se considera resuelta por este cambio.

Rollback: revertir la unidad y reconstruir. No requiere migración ni cambios
de historia. Comprobantes existentes sin vínculo administrativo permanecen
legibles por su snapshot; nunca reemitir para crear una ficha.
