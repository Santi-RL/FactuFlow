# Release v0.3.6 — prevención de duplicados PF-13/PF-17

Fecha de corte de evidencia: 08/09/2026.

Estado: **v0.3.6 publicada el 08/09/2026**. Este dossier conserva la evidencia del código y de su publicación. No acredita despliegue. El estado de cualquier instalación se consulta únicamente en el plano de control operativo.

## Identificación del rango

- Base de `main`: `80ac122052761ffe94184f5eb6cfbbce43ead6e1`.
- Commit de código evaluado: `8f733772417938810ee477e716739722da5d5ea5`. El PR que integra este dossier conserva los ajustes documentales y los resultados de integración posteriores a ese corte.
- Última release publicada al preparar este dossier: `v0.3.5`, cuyo tag apunta a `ba8b7d0e5d9a2fd1c0a68a714e02f6a5aab0a655`. El corte de publicación posterior corresponde a `v0.3.6`.
- El rango entre ese tag y la base `80ac122` contiene sólo cambios Markdown; los cambios funcionales de este candidato están íntegramente en `8f73377`. El versionado posterior no altera ese comportamiento.

## Resultado incluido

PF-13 incorpora el contrato `duplicados_lotes/v2` al flujo de emisión masiva. Distingue coincidencias internas por receptor identificable, igualdad completa de contenido entre lotes delimitados y el predicado histórico individual ya vigente. La advertencia conserva resumen y detalle paginado, vuelve a revisar ante evidencia nueva y sólo habilita la excepción después de una decisión explícita vinculada a la evidencia exacta.

Repetir fecha e importe en ventas anónimas dentro del lote no genera por sí solo un aviso. La comparación de contenido entre lotes sí incluye receptores anónimos; archivo, cantidad e importe total no bastan para afirmar duplicación. «Volver a revisar» conserva el mayor énfasis y el foco inicial.

La evidencia y la aceptación quedan asociadas a la operación y a su selección original. La coordinación por emisor y ambiente protege lotes concurrentes; el worker, el envío unitario o agrupado del lote, los reintentos y la recuperación stale consumen la misma decisión validada. Un resultado parcial conserva lo ya autorizado y permite reintentar únicamente los grupos fallidos demostrables.

El cierre de reparación incluido en el candidato admite operaciones batch terminales `fallido` o `rechazado_arca`, además de `finalizado`, sólo cuando siguen acreditados comprobante, CAE, grupo, guarda RECE, generación y replay; la operación individual conserva el requisito `finalizado`. El caso positivo ensayado contiene una autorización válida y un rechazo verificable `10005`. También preserva identidad de entrada legacy sólo desde payload y contexto válidos, acota la hidratación histórica y la paginación viva, valida integridad antes del GET durable y presenta un único checkbox para todas las clases de coincidencia presentes.

También se actualiza `pypdf` a `6.16.1` para resolver avisos de seguridad en la lectura de constancias, conservando los lectores de inscripción y puntos de venta.

## Alcance excluido

- No cambia la política, el DTO ni el predicado de duplicados de la emisión individual.
- No modifica fecha fiscal, receptor fiscal, importes, tipo de comprobante, punto de venta, numeración, solicitud SOAP ni significado de los hashes idempotentes existentes.
- No convierte similitud en prueba de autorización de ARCA y el comparador no realiza llamadas externas.
- No reduce la protección de misma importación, idempotencia, aislamiento por emisor/ambiente, confirmación irreversible, reservas, estados inciertos o reconciliación.
- No incorpora las mejoras menores H6/H8 clasificadas como P3.
- El alcance funcional no incluye migración de una instalación real, despliegue ni acceso a producción. El versionado, tag y GitHub Release se cierran por separado de esa operación productiva.

## Invariantes fiscales preservadas

- La fecha de emisión continúa siendo explícita y la confirmación fiscal irreversible conserva fecha y punto de venta cuando corresponde.
- Una misma clave y payload conserva replay sin otro CAE; la misma clave con payload distinto mantiene conflicto.
- Ninguna excepción por duplicados reemite un comprobante autorizado ni habilita un resultado incierto. Todo resultado que pudo cruzar ARCA permanece reconciliable.
- La selección original completa no se reduce después de una autorización parcial. Los grupos ya autorizados quedan fuera del retry y no se vuelven a emitir.
- Una aceptación cubre sólo la misma operación o raíz, material, selección y evidencia. Un cambio relevante invalida la decisión anterior y termina antes de `FECAESolicitar`.
- Operaciones, lotes, grupos, puntos de venta, certificados, actores y evidencia permanecen aislados por emisor y ambiente.

## Compatibilidad legacy exacta

- Durante la transición, el backend conserva los campos planos `confirmacion_duplicado_logico`, `mensaje_confirmacion_duplicado_logico` y `cantidad_duplicados_logicos`; el frontend acepta esa proyección y `control_duplicados`. Un token v1 sólo continúa una operación v1 demostrable y nunca se convierte en autorización v2 mediante un booleano.
- Un replay v1 terminal se conserva exactamente. Una operación no terminal pre-ARCA sin coincidencias actuales puede continuar; una incierta debe reconciliar. Si existen coincidencias actuales y la aceptación anterior no acredita sus testigos, la continuación y el reintento quedan bloqueados sin pedir otra confirmación que invente evidencia.
- El backfill v2 sólo acredita payloads que validan bajo el contrato fiscal estricto y cuyo emisor, ambiente y punto de venta coinciden. Recupera hashes y originales de identidad todavía presentes en el payload para comparación, sin escribir ni cambiar el receptor fiscal. La cobertura incompleta queda `parcial_legacy`; payload o contexto no acreditable queda `no_comprobable`, nunca “sin coincidencias”.
- El paquete del migrador evoluciona a v4 y conserva operaciones, selecciones, lotes, grupos, intentos, guardas y generaciones requeridos por PF-13 y por replays terminales. La lectura de paquetes v3 se limita al schema, partición y head conocidos; deja campos v2 nuevos en `null`, regenera coordinadores y no inventa historia omitida ni transforma tokens v1 en aceptación v2.

## Migración, dependencias y configuración

- Alembic agrega la revisión `a1b2c3d4e5f6`, con padre `f4a5b6c7d8e9`. La expansión es aditiva y nullable; añade material comparable y evidencia durable sin reescribir `payload_json`, `archivo_hash`, `payload_hash`, `huella_logica` ni respuestas idempotentes.
- Productores y workers v1/v2 no pueden convivir. Un corte real debe drenar o detener el worker anterior, clasificar remanentes, aplicar expansión/backfill y recién entonces iniciar todos los procesos v2.
- El downgrade físico sólo es admisible cuando una comprobación sanitizada demuestra cero evidencia, operaciones o reservas v2 y existe un backup verificable; si hay actividad v2, debe abortar sin degradarla a booleanos.
- Dependencia actualizada: `pypdf==6.16.1`. No se agrega una configuración de ARCA ni una capacidad externa nueva.

## Evidencia disponible

- CI remota del commit candidato: [ejecución `34199954992`](https://github.com/Santi-RL/FactuFlow/actions/runs/34199954992), evento `workflow_dispatch`, siete jobs correctos (`Change Scope`, `Repository Checks`, `Backend Tests`, `Frontend Build`, `Runtime Smoke`, `E2E Tests` y `Security Audit`). Backend: 1.378 pruebas y 73,10 % de cobertura; módulo PostgreSQL PF-13: 20 casos. Frontend: 223 pruebas en 36 archivos. E2E: 36 casos.
- QA integrada con servicios fiscales simulados y datos sintéticos: carga y emisión por actores distintos, operación ajena activa, autorización parcial con retry sólo del fallido y evidencia nueva que invalida una aceptación anterior. Santi aprobó expresamente la revisión visual del 08/09/2026.
- Admisión PostgreSQL previa: suite integrada de 40 casos, incluidos coordinación real entre conexiones, claim/reserva y rollback. La CI del commit candidato vuelve a acreditar el módulo actual; los totales de corridas diferentes no se suman.
- Ensayo operativo local: migración sintética `f4`→`a1`, API y worker sobre PostgreSQL, build/preview del frontend y restauración del estado sintético `f4` anterior al corte. El dump y la comparación fueron verificados de forma privada.
- Revisiones independientes de las seis reparaciones: H1/H9 aprobadas con 12 casos focales; H4/H7/H10 aprobadas con 17 casos focales, medición de memoria, parámetros y adulteración; H11 aprobada con pruebas de UI. No se presenta `autoreview` como evidencia verde: la atribución formal anterior quedó incompleta y el cierre se basó en CI, revisiones independientes y contraste de coordinación.

Toda la evidencia usa identidades, archivos, comprobantes y servicios sintéticos. Los artefactos privados no se copian al repositorio público.

## Recuperación demostrada y límites

El ensayo local demostró respaldo, migración y restauración sobre una base sintética previa a nueva actividad fiscal. También comprobó limpieza de procesos propios y conservación de los artefactos privados del ensayo. No fue una reproducción exacta de una instalación histórica, no acreditó drenaje de una cola v1 real, carga productiva ni restauración después de crear evidencia v2.

Ante una falla de corte real, la recuperación debe detener productores y workers v2. Si ya existe actividad v2, la aplicación anterior no puede arrancar: corresponde conservar el esquema expandido y usar una versión compatible que lea o bloquee esa evidencia. El backup y el rollback concretos de una instalación deberán verificarse en su plano de control; este dossier no afirma que exista un backup productivo.

## Puertas de integración y publicación

- La integración exige matriz documental completa, revisión del rango y los siete checks correctos sobre el PR. El resultado y el SHA se registran en ese PR y en GitHub Actions.
- El cierre de integración exige comprobar el SHA resultante y la CI de `main`; una ejecución documental con runtime omitido no sustituye las pruebas del rango fiscal.
- La versión de publicación elegida es `v0.3.6`. El tag y la release requieren un SHA aceptado de `main` con CI verde; no se crean por el solo resultado de integración.
- Antes de cualquier instalación real: preflight de remanentes v1, procesos, migración, backup/restauración y rollback sobre el entorno correspondiente.
- Producción y despliegue permanecen fuera de esta fase.

## Dictamen al corte de evidencia

No se observó una incoherencia que impida preparar el PR. Los límites reales son explícitos: la recuperación acreditada es sintética y previa a actividad v2; el corte no admite convivencia de workers v1/v2; la publicación, preflight real, backup productivo y despliegue siguen sujetos a sus comprobaciones correspondientes.

## Integración y preparación de v0.3.6

El [PR #53](https://github.com/Santi-RL/FactuFlow/pull/53) integró la unidad en
`7e15821f4d863aa0c9f7288dbb87a17c9192c19a`, con contenido idéntico al HEAD
revisado. Los siete controles completos aprobaron tanto en el
[PR](https://github.com/Santi-RL/FactuFlow/actions/runs/34214852658) como en
[`main`](https://github.com/Santi-RL/FactuFlow/actions/runs/34216867368).

La preparación de `v0.3.6` sólo alinea metadatos de backend/frontend, la versión
visible y las expectativas existentes; no modifica lógica fiscal ni
dependencias. La suite de scripts aprobó 28 casos y el spec del Sidebar, 7.
El SHA de publicación es el commit integrado de ese versionado, comprobado
por CI antes de crear el tag y registrado a continuación.

## Publicación

- El [PR #54](https://github.com/Santi-RL/FactuFlow/pull/54) integró el versionado
  en `629174b188a93abf98fd081bbcad43d65ba54306`, con contenido idéntico al HEAD
  revisado. Los siete controles completos aprobaron en el
  [PR](https://github.com/Santi-RL/FactuFlow/actions/runs/34219314340) y en
  [`main`](https://github.com/Santi-RL/FactuFlow/actions/runs/34220904386).
  Backend: 1.378 pruebas y 73,10 % de cobertura en ambas ejecuciones.
- El tag anotado `v0.3.6` apunta a ese SHA completo; su objeto es
  `aef75a31bbf5aaba98310eb964b9ed3c7469166b`. Se verificaron ambos contra el
  remoto después de publicar el tag.
- La [GitHub Release v0.3.6](https://github.com/Santi-RL/FactuFlow/releases/tag/v0.3.6)
  se publicó el 08/09/2026 a las 11:49:14 UTC, marcada como `Latest`, sin estado
  de borrador ni prerelease. No se adjuntaron artefactos privados.
- El cierre documental posterior puede avanzar `main` sin modificar runtime
  ni mover este tag. Su CI documental no sustituye la CI completa del SHA
  publicado.
- No se accedió a producción ni se desplegó. Preflight, respaldo y recuperación
  de una instalación real requieren la fase autorizada en su plano de control.
