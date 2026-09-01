# PF-19D — autoridad WSFE y uso operativo de puntos de venta

Fecha de decisión: 29/08/2026

Estado: CERRADO; PUBLICADO EN `v0.3.4`.

Prioridad: P1 fiscal-operativa, Nivel 2. Se implementa después de PF-03B y antes
de PF-06/PF-07/PF-08.

## Problema

PF-19B respondió a fallos productivos haciendo obligatoria una constancia PDF
para acreditar RECE. Esa contención protegió la emisión, pero convirtió datos
descriptivos y una declaración administrativa en una barrera operativa que no es
necesaria para descubrir los puntos CAE informados por ARCA.

El usuario objetivo sólo necesita saber qué puntos puede usar y cuáles decidió
usar en FactuFlow. No debe comprender Web Services, revisiones fiscales,
atestaciones ni procedencia criptográfica para operar normalmente.

## Decisión

`FEParamGetPtosVenta`, consultado con credenciales del emisor activo, será la
fuente técnica de verdad para descubrir y validar puntos asignados a facturación
electrónica compatibles con el flujo CAE implementado por FactuFlow.

La constancia PDF será opcional y aportará datos descriptivos: domicilio, nombre
de fantasía y puntos pertenecientes a otros sistemas. No participará en
elegibilidad, numeración ni payload fiscal.

Una preferencia durable por emisor, `Usar en FactuFlow`, expresará la decisión
operativa de sus usuarios. Estará separada del estado técnico ARCA.

## Invariantes

1. ARCA gobierna número, tipo de emisión, presencia, bloqueo y baja.
2. FactuFlow no permite editar manualmente esos campos.
3. La preferencia local nunca supera una señal técnica negativa.
4. Un usuario puede deshabilitar un punto disponible; ARCA no revierte esa
   decisión.
5. Un desbloqueo posterior de ARCA restaura disponibilidad técnica, pero no
   habilita un punto deshabilitado expresamente.
6. Ningún cambio alcanza CAE sin las guardas, revisión fiscal, locks y
   compare-and-swap existentes.
7. Si ARCA pudo autorizar, se conserva incertidumbre y reconciliación.
8. No se crean permisos diferenciados por punto o usuario en esta unidad.
9. Los datos descriptivos no alteran la validez fiscal del punto.
10. Una respuesta vacía, duplicada, inconsistente o fallida no modifica ningún
    estado.

## Modelo y contratos

Agregar una preferencia durable compartida por emisor, conceptualmente
`usar_en_factuflow`, independiente de `activo`, bloqueo, baja, presencia y
frescura técnica.

Los selectores sólo ofrecerán un punto cuando se cumplan simultáneamente:

- ARCA lo informa como compatible con CAE;
- está presente y activo;
- no está bloqueado ni dado de baja;
- su comprobación está fresca según la política vigente;
- `Usar en FactuFlow` está habilitado.

Los contratos existentes se evolucionarán de forma aditiva. La implementación
deberá definir nombres definitivos, migración y compatibilidad en su checklist
Nivel 2 sin eliminar campos legacy en el mismo corte.

## Comprobación con ARCA

- La primera comprobación exitosa de cada emisor será iniciada manualmente por
  el usuario con `Comprobar con ARCA`.
- La respuesta completa y consistente descubrirá puntos nuevos y actualizará
  todos los existentes del emisor con una marca temporal común.
- Sólo valores `EmisionTipo` compatibles con el flujo CAE se considerarán
  utilizables.
- Puntos nuevos compatibles quedarán `Usar en FactuFlow = sí` por defecto,
  incluso si un bloqueo o baja temporal impide seleccionarlos en ese momento.
- Puntos de otros sistemas se conservarán como información y quedarán fuera del
  uso local.
- Después se mantiene la frescura técnica de 90 días y el preflight final antes
  de cualquier camino capaz de llegar a `FECAESolicitar`.
- Una consulta fallida no crea operaciones, intentos, reservas ni solicitudes
  de CAE.

## Preferencia de uso

- Cualquier usuario autorizado para el emisor podrá habilitar o deshabilitar un
  punto.
- La acción estará dentro del editor y exigirá una confirmación clara; no será
  un switch accidental en la tabla.
- La preferencia es compartida por todos los usuarios del emisor.
- Deshabilitar incrementará la revisión fiscal usada por guardas y bloqueará
  emisiones nuevas o continuaciones pre-ARCA.
- No se sustituirá silenciosamente el punto ni se borrará trabajo.
- Formularios, perfiles y lotes conservarán datos recuperables y explicarán que
  se debe elegir otro punto habilitado o habilitarlo desde `Puntos de venta`.

## Constancia y datos descriptivos

- `Importar constancia` será opcional.
- Los usuarios podrán cargar manualmente domicilio y nombre de fantasía.
- Una constancia posterior sobrescribirá los datos manuales coincidentes.
- La UI distinguirá discretamente `Informado por ARCA`, `Ingresado manualmente`
  y `Sin información`.
- Si existe un nombre interno de FactuFlow, permanecerá separado del nombre de
  fantasía informado por ARCA.
- El PDF no se almacenará; se conservarán únicamente metadatos mínimos cuando
  sean necesarios para trazabilidad descriptiva.

## Interfaz

- Mantener una sola tabla.
- La vista habitual mostrará los puntos usados en FactuFlow; un filtro simple
  permitirá mostrar todos.
- El contador reflejará el filtro.
- Estados normales breves: `Listo para emitir`, `Web Services activo`,
  `No disponible en FactuFlow` y `Otro sistema`.
- Sólo errores, bloqueos o acciones necesarias tendrán explicación adicional.
- Toda acción necesaria indicará exactamente qué debe hacer el usuario.
- No mostrar revisión fiscal, ambiente, atestación ni terminología técnica en
  estados normales.

Reordenamiento visual, microcopy general y accesibilidad no bloqueantes se
mantendrán en PF-17 y no ampliarán esta unidad.

## Migración y rollback

- Migración aditiva y conservadora.
- Puntos Web Services existentes quedarán inicialmente marcados para uso,
  aunque estén bloqueados o dados de baja temporalmente.
- Puntos de otros sistemas quedarán fuera.
- Conservar acreditaciones, revisiones, fechas de comprobación, historia y
  ledger PF-19B.
- No borrar tablas, contratos ni evidencia legacy en el mismo corte.
- Ensayar upgrade y rollback en SQLite y PostgreSQL.
- Validar conteos y snapshots antes de promover el cambio en una instalación.
- Producción manda: datos existentes y flujos válidos no deben dejar de
  funcionar por la migración.

## Emisión y carreras

- Individual, lotes nuevos, perfiles, worker, reintentos y continuaciones
  consumirán el mismo contrato seleccionable.
- Un estado desactualizado se comprueba antes de habilitar opciones según la
  política vigente.
- La revisión fiscal detectará cambios ocurridos después de la selección y antes
  de CAE.
- Replays terminales devolverán su respuesta durable sin reevaluar condiciones
  mutables.
- Una falla preflight devuelve un error claro antes de crear estado fiscal.

## Matriz mínima de aceptación

- primera comprobación manual;
- CAE compatible y tipo no compatible;
- punto nuevo, existente, ausente, bloqueado y dado de baja;
- desbloqueo posterior con preferencia habilitada o deshabilitada;
- respuesta vacía, duplicada, inconsistente y timeout;
- constancia ausente, válida y posterior a datos manuales;
- procedencia de cada campo descriptivo;
- usuarios comunes y administradores;
- aislamiento multiemisor;
- individual, perfiles, lotes, worker, reintentos, stale y carreras;
- cero operaciones, intentos, reservas y FECAE en abortos previos;
- upgrade y rollback SQLite/PostgreSQL;
- mensajes con datos sintéticos y sin jerga técnica.

## Fuera de alcance

- permisos por usuario y punto de venta;
- edición manual de señales técnicas ARCA;
- reconstrucción histórica de comprobantes;
- consulta automática de numeración por cada punto y tipo;
- cambios de fecha fiscal, numeración, CAE o reconciliación;
- release o despliegue dentro de la misma decisión de diseño.

## Contrato implementado

La implementación usa estos nombres persistentes y públicos:

- `puntos_venta.usar_en_factuflow`: preferencia compartida por emisor;
- `domicilio_fuente` y `nombre_fantasia_fuente`: `manual`,
  `constancia_arca` o ausencia de información;
- evidencia `wsfe_param_get_ptos_venta_v1` y clasificador
  `wsfe_emision_tipo_cae_v1` en el ledger PF-19B;
- `seleccionable_para_emision`: continúa siendo el contrato único de los
  selectores y ahora incluye la preferencia.

El clasificador acepta únicamente un `EmisionTipo` explícito con forma
`CAE - …`. Una respuesta completa crea una revisión WSFE para el ambiente
consultado. Los puntos compatibles nuevos quedan habilitados para uso aun si
están bloqueados o dados de baja; los de otras modalidades quedan informativos
y deshabilitados. Una ausencia invalida la disponibilidad técnica sin borrar la
preferencia.

`PUT /api/puntos-venta/{id}` admite nombre interno, domicilio, nombre de
fantasía y `usar_en_factuflow` para cualquier usuario del emisor. Rechaza número,
sistema, bloqueo, baja, presencia y demás campos técnicos aun para un
administrador. El `POST` legacy se conserva como ruta, pero responde conflicto
porque el alta técnica debe provenir de ARCA. El `DELETE` legacy equivale a
deshabilitar el uso, sin borrar ni falsear el estado técnico.

La constancia no llama a WSFE, no crea acreditaciones ni invalida ausentes.
Sobrescribe sólo los datos descriptivos presentes y puede crear filas
informativas de otros sistemas con uso deshabilitado. No conserva el PDF.

La migración `e3f4a5b6c7d8` habilita inicialmente los puntos Web Services legacy,
mantiene fuera los demás y conserva ledger, revisiones y comprobaciones. El
rollback es exacto mientras no exista evidencia WSFE nueva; después bloquea el
downgrade y exige conservar el esquema o restaurar un backup anterior.

## Cierre del checklist fiscal

- **Alcance:** API, UI, sincronización WSFE, migración, emisión individual,
  perfiles, lotes, worker, reintentos y continuaciones consumen la misma
  elegibilidad. No cambian fecha, numeración, payload FECAE ni reconciliación.
- **Orden:** autenticar emisor y ambiente, leer y validar el snapshot completo,
  tomar locks por punto, aplicar cambios con compare-and-swap, mover heads WSFE
  y confirmar una única transacción. Un fallo revierte altas y cambios.
- **Concurrencia:** los cambios técnicos o de preferencia rechazan guardas
  `pre_arca`, `arca_iniciada` o `requiere_reconciliacion`. Una actualización
  puramente descriptiva no cambia la revisión fiscal.
- **Fallos:** vacío, duplicado, `EmisionTipo` ausente, timeout o respuesta
  inconsistente producen `503`, sin operaciones, intentos, reservas ni CAE.
- **Replays:** las respuestas terminales y estados inciertos conservan sus
  snapshots inmutables; no se reevalúan contra una preferencia posterior.
- **Aislamiento:** toda lectura, escritura y preferencia está limitada por
  `empresa_id`; se cubren usuario común, administrador y dos emisores.
- **Migración:** upgrade, rollback sin evidencia y bloqueo fail-closed con
  evidencia se prueban en SQLite; el recorrido PostgreSQL desechable cubre
  upgrade, rollback y reupgrade.
- **Pruebas externas:** todas las respuestas ARCA son sintéticas. Ninguna prueba
  automatizada usa certificados reales ni solicita CAE.

El despliegue productivo permanece fuera de este cierre y requiere el flujo
separado mediante `vps-admin`.
