# Portafolio integrado de desarrollo

Última actualización: 2026-07-12

Estado: PRIORIZADO; PRIMER CORTE PF-01A DISEÑADO.

## Propósito y autoridad

Este documento integra el trabajo pendiente de `ROADMAP.md` con el backlog
abierto de Clawpatch. Evita reparar hallazgos aislados sin considerar producto,
dependencias, operación y visión.

La autoridad se mantiene así:

1. `VISION.md` define qué producto se construye y qué queda fuera de alcance.
2. `ROADMAP.md` conserva prioridades y fases macro.
3. Este portafolio agrupa el trabajo operativo por causa raíz y dependencia.
4. `docs/agents/current-status.md` indica el punto exacto para retomar.
5. Los ledgers y reportes locales de Clawpatch conservan la evidencia técnica.

La adjudicación manual de los 36 findings `high` no confirmó ningún P0. La
severidad de una herramienta no reemplaza la validación manual ni una decisión
de prioridad.

## Filtro obligatorio de visión

Todo corte debe preservar:

- facturación electrónica ARCA individual y masiva como núcleo;
- fecha fiscal explícita y confirmación irreversible antes de CAE;
- un emisor activo por vez y aislamiento estricto entre emisores;
- evidencia fiscal y operación auditables;
- experiencia clara para usuarios administrativos no técnicos;
- consumo razonable para instalaciones locales o VPS pequeños;
- persistencia mínima de artefactos descargables en VPS.

Quedan fuera de este portafolio, salvo cambio explícito de `VISION.md`, stock,
cuentas corrientes, CRM, gestión contable integral, reportes globales mezclando
emisores y una plataforma multiempresa compleja.

## Inventario de origen

| Fuente | Estado observado | Uso dentro del portafolio |
|---|---:|---|
| Clawpatch `repo` | 16 abiertos: 5 `high`, 4 `medium`, 7 `low` | Riesgos end-to-end y contratos entre capas |
| Clawpatch `backend` | 101 abiertos: 25 `high`, 52 `medium`, 24 `low` | Dominio, persistencia, API, ARCA y operación |
| Clawpatch `frontend` | 29 abiertos: 5 `high`, 20 `medium`, 4 `low` | Estado de UI, contratos, concurrencia y UX |
| `ROADMAP.md` | 83 ítems no cerrados: 53 pendientes, 30 en curso | Producto, plataforma, operación y evolución |

Los 146 hallazgos abiertos actuales y los 83 ítems no representan 229 tareas independientes.
Existen duplicados entre slices, repeticiones del mismo objetivo en distintas
fases del roadmap y hallazgos que son síntomas de una misma causa raíz.

## Adjudicación de findings `high`

La revisión manual contra código, tests, configuración productiva y contratos
externos dejó este resultado:

- 36 registros revisados;
- 33 problemas únicos después de deduplicar entre slices;
- 20 problemas únicos aceptados como P1;
- 12 riesgos reales diferidos como P2;
- 3 registros duplicados que conservan evidencia en su slice;
- 1 finding rechazado porque ya existe la suite de componente que su premisa
  declaraba ausente;
- 0 P0 y 0 P3 dentro de los `high`.

La distribución principal es:

| Línea | P1 | P2 | Resultado |
|---|---:|---:|---|
| PF-01 | 6 | 0 | Primer corte PF-01A diseñado; PF-01B requiere migración separada. |
| PF-03 | 2 | 0 | Contratos fiscales estrictos e importes válidos. |
| PF-04 | 0 | 4 | Evidencia histórica, moneda, redondeo y tests PDF. |
| PF-06 | 2 | 0 | Invariantes multiemisor backend. |
| PF-07 | 4 | 0 | Cambio de emisor y respuestas tardías frontend. |
| PF-08 | 3 | 0 | Bootstrap, sesión y revalidación administrativa. |
| PF-09 | 3 | 2 | Certificados, ambientes, WSAA y constancias. |
| PF-10 | 0 | 2 | Posesión de exportaciones y liberación concurrente. |
| PF-11 | 0 | 2 | Instantánea y rollback de recuperación. |
| PF-13 | 0 | 1 | Replay corregible pre-ARCA en lotes. |
| PF-16 | 0 | 1 | Default productivo seguro; además queda un gap residual de tests no contado como finding aceptado. |

El detalle con IDs y evidencia queda solo en `.tmp/clawpatch/2026-07-12/`,
ignorado por Git. El diseño sanitizado del primer corte está en
`docs/agents/pf-01-authorization-integrity-design.md`.

## Bandas de investigación del backlog restante

Estas bandas siguen ordenando los `medium`/`low` y las líneas todavía no
desglosadas. Los `high` ya tienen prioridad manual P1/P2.

- **A — adjudicación inmediata:** puede contener un P0 o una precondición del
  P1. Requiere verificar alcanzabilidad, impacto actual y guardas existentes.
- **B — siguiente corte estructural:** trabajo importante alineado con el
  producto, normalmente candidato a P1 o P2 después de resolver A.
- **C — continuo y operativo:** calidad, UX, observabilidad, soporte y
  mantenimiento que deben entrar en cortes coherentes sin desplazar seguridad.
- **D — evolución posterior:** trabajo válido pero dependiente de mayor madurez
  productiva. No debe adelantarse a las garantías fiscales y operativas.

## Matriz integrada

| ID | Línea de trabajo y resultado buscado | Fuentes consolidadas | Riesgo o valor | Dependencias principales | Banda |
|---|---|---|---|---|---|
| PF-01 | Integridad de autorización fiscal: CAE válido, estados coherentes, idempotencia y reconciliación segura | Hallazgos ARCA/CAE, emisión individual y lotes; P1 fiscal | Evitar reintentos inseguros, autorizaciones incompletas y estados ambiguos | Checklist fiscal, tabla de estados y tests de fallos post-ARCA | A |
| PF-02 | Numeración compatible con historia previa y otros sistemas | P1 explícito del roadmap y hallazgos de reservas/numeración | Permitir emisiones legítimas sin debilitar intentos propios inciertos | PF-01; ARCA como fuente global y FactuFlow como fuente de intentos propios | B |
| PF-03 | Validación fiscal de entradas, fechas, importes, moneda y totales | Hallazgos de esquemas, analizadores, descuentos, perfiles, constancias y plantillas | Evitar payloads no elegidos, fechas inválidas y montos incoherentes | Contratos UI/API y matriz individual/masiva | A |
| PF-04 | Evidencia fiscal histórica correcta en PDFs y reportes | Hallazgos de instantánea del emisor, moneda, IVA, paginado, ranking y aislamiento PDF | Evitar documentos históricos mutables o informes impositivos incorrectos | Modelo de instantáneas, migración de datos heredados y pruebas de evidencia | A |
| PF-05 | Reconstrucción histórica opcional desde ARCA | P2 explícito del roadmap | Completar informes sin convertir historia externa en requisito de emisión | PF-02, PF-04, procedencia, cobertura y registro reanudable | B |
| PF-06 | Aislamiento multiemisor backend y modelo de datos | Roadmap multiemisor; hallazgos de pertenencia, enumeración y asociaciones cruzadas | Evitar mezcla o revelación de datos entre emisores | Invariantes DB, filtros uniformes y tests multiemisor | A |
| PF-07 | Cambio de emisor seguro en frontend | Hallazgos del estado Pinia, respuestas tardías, asistente y selector de clientes | Evitar aplicar o mostrar respuestas del emisor anterior | PF-06; versión/cancelación común de solicitudes y contratos de stores | A |
| PF-08 | Autenticación, sesiones, bootstrap y administración de usuarios | Hallazgos de inicio de sesión, 401 tardíos, setup, bloqueos y permisos; cambio de contraseña propio | Evitar apropiación inicial, sesión obsoleta y acciones administrativas tardías | Política de bootstrap y revalidación de autorización | A |
| PF-09 | Certificados, claves, WSAA, caché y ambientes | Hallazgos de archivos concurrentes, TRA, caché, CSR, ambiente y estado de servidores; roadmap WSAA | Evitar material huérfano, autenticación inválida y uso accidental de producción | Propiedad durable de archivos, zona horaria y contratos de ambiente | A |
| PF-10 | Exportaciones y liberación segura de almacenamiento | Hallazgos de confirmación de descarga, concurrencia, caché HTTP y ZIP huérfanos | Evitar borrar datos antes de verificar un resguardo completo | Protocolo de posesión, idempotencia y limpieza durable | A |
| PF-11 | Respaldos, migración y recuperación operativa | Roadmap de respaldos/VPS; hallazgos de instantánea SQLite, restauración y verificación de paquetes | Garantizar recuperación coherente y repetible | PF-09, PF-10, secretos y ensayo en entorno aislado | A/B |
| PF-12 | Base de datos, migraciones e invariantes transaccionales | Roadmap de convivencia entre datos heredados y Alembic; hallazgos de restricciones, carreras y confirmaciones ambiguas | Mover garantías críticas del flujo feliz a invariantes verificables | Diseño por dominio, migraciones reversibles y datos heredados | A/B |
| PF-13 | Emisión masiva, formatos, perfiles y arquitectura de procesos | Roadmap de lotes/procesos; hallazgos de worker, formatos, perfiles, Excel y bucle de eventos | Mantener volumen y UX sin perder garantías fiscales ni recursos | PF-01, PF-03, PF-12 y límites de VPS pequeño | B |
| PF-14 | Contratos API, errores y concurrencia CRUD coherentes | Hallazgos de 400/404/500, errores posteriores al commit, paginación y unicidad | Respuestas previsibles, sanitizadas e idempotentes | Convención API, manejo uniforme de IntegrityError y tests contractuales | B/C |
| PF-15 | Observabilidad, salud, trazabilidad y soporte | Roadmap de estado del sistema/logs/runbooks; hallazgos de salud y diagnósticos engañosos | Diagnosticar sin exponer secretos ni presentar falsos OK | Taxonomía de estados, IDs de correlación y retención | B/C |
| PF-16 | Calidad, CI y cadena de herramientas portable | Roadmap Node 24/testing; hallazgos de scripts Windows, Playwright, fechas dinámicas y vacíos de cobertura en suites | Evitar regresiones y mantener Windows/Linux reproducibles | Matriz de entornos y suites por línea de trabajo | C |
| PF-17 | UX administrativa, accesibilidad y recuperación de errores | Roadmap UX; hallazgos de navegación, notificaciones, fechas visibles y estado persistido corrupto | Reducir errores operativos de usuarios no técnicos | Contratos estables de PF-03, PF-07, PF-08 y PF-14 | C |
| PF-18 | Salidas masivas, distribución y evolución posterior | ZIP de PDFs, paquetes, actualizaciones, soporte, correo electrónico, integraciones y dashboard | Mejorar adopción sin desviar recursos del núcleo fiscal | PF-04, PF-10, PF-11 y madurez productiva | D |

## Relaciones que condicionan el orden

1. PF-01 es una precondición de PF-02: no se debe flexibilizar numeración sin
   cerrar primero las fronteras de CAE, idempotencia y reconciliación.
2. PF-04 precede a PF-05: no se debe importar historia que el modelo no pueda
   representar con procedencia y evidencia inmutables.
3. PF-06 y PF-07 forman una sola garantía end-to-end; corregir solo backend o
   solo frontend deja una frontera abierta.
4. PF-09, PF-10 y PF-11 comparten propiedad de archivos, secretos y recuperación.
5. PF-12 debe acompañar los cortes fiscales o multiemisor que necesiten
   invariantes persistentes; no debe convertirse en una migración masiva aparte.
6. PF-13 no puede optimizar concurrencia o volumen sacrificando PF-01 y PF-03.
7. PF-15 y PF-16 son habilitadores transversales, pero no sustituyen una
   reparación funcional confirmada.

## Enrutamiento del roadmap

- P1 fiscal: PF-01 y PF-02.
- P2 histórico: PF-04 y PF-05.
- Multiemisor: PF-06 y PF-07.
- Usuarios y cuenta propia: PF-08 y PF-17.
- Certificados, homologación y producción ARCA: PF-09 y PF-15.
- Almacenamiento, respaldos, migración y recuperación: PF-10, PF-11 y PF-12.
- Lotes, formatos, perfiles y procesos largos: PF-03 y PF-13.
- API, mensajes y documentación contractual: PF-14 y PF-17.
- Observabilidad, soporte y operación: PF-11 y PF-15.
- Testing, Node, CI y portabilidad: PF-16.
- PDFs masivos, distribución e integraciones posteriores: PF-18.

## Reglas para convertir una línea en trabajo implementable

Antes de editar código, cada corte debe tener:

1. causa raíz y fuentes exactas, incluidos IDs de Clawpatch aplicables;
2. estado de cada fuente: confirmada, duplicada, rechazada o diferida;
3. prioridad propuesta con justificación de impacto y alcanzabilidad;
4. invariantes, estados y fallos intermedios cuando sea sensible;
5. dependencias y alcance explícitamente excluido;
6. tests definidos antes o durante el diseño;
7. migración y política legacy si cambia persistencia;
8. validación enfocada, documentación viva y criterio de cierre;
9. `autoreview` solo con confirmación explícita cuando el corte sea importante;
10. commit, push y CI separados según la unidad lógica autorizada.

## Criterio de cierre de este paso

- Las 147 entradas originales de Clawpatch quedaron cubiertas por líneas
  temáticas sin tratarlas como tareas independientes.
- Los 83 ítems abiertos o en curso del roadmap quedaron enrutados a una o más
  líneas del portafolio.
- P1 y P2 conservan su intención original.
- Los 36 hallazgos `high` fueron adjudicados, deduplicados y asignados a PF.
- No se confirmó ningún P0 ni se modificó código de producto.
- PF-01A tiene alcance, invariantes, estados, orden de operaciones, fallos y
  matriz de tests definidos.
- El siguiente paso es revisar este diseño con el usuario y, solo con su
  confirmación, comenzar el primer corte de implementación.
