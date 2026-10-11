# PF-03/PF-04/PF-13 — importes y previsualización fiscal común

Última revisión: 09/10/2026.

Estado: admisibilidad y revisión P1 implementadas; categorías y reutilización
en plantillas P2 pendientes. Preserva el contrato decimal cerrado PF-03B.
Este documento no autoriza emisiones ni acredita un despliegue.

## Problema, evidencia y prioridad

Los ensayos que motivaron el corte comprobaron dos problemas acotados:

- El schema y la validación de negocio admitían alícuotas positivas que el
  calculador no implementa. Con 2,5 %, 5 % y un valor desconocido, el pedido
  preparado tiene IVA cero: no debe reinterpretarse una tasa como otra.
- La revisión de la interfaz usaba aritmética y presentación propias. Un subtotal
  de 1,005 se muestra como 1,01, mientras el cálculo decimal vigente devuelve
  1,00. El objetivo es respetar el cálculo aceptado, no cambiar su redondeo.

La [validación de planificación](../project/analysis/confiabilidad-arca-roadmap.md)
delimita los ensayos y sus límites; no acredita un incidente productivo.

| Corte | Prioridad / horizonte | Resultado |
|---|---|---|
| Admisibilidad y revisión de importes | P1 fiscal, cerrado en código | Impedir conversiones silenciosas a IVA cero y mostrar los importes fiscales que realmente se confirmarán |
| Categorías fiscales completas | P2 fiscal, Más adelante | Separar tasa cero, exento, no gravado y otros tributos; ampliar alícuotas con soporte completo |
| Reutilización en plantillas | P2, junto con PF-13 | Una muestra contable y la emisión usan la misma preparación fiscal |

## Autoridad y responsabilidades

`backend/app/core/comprobante_totales.py` conserva la autoridad decimal y el
orden de operaciones de PF-03B. Una preparación fiscal común produce importes,
desglose, datos efectivos y errores accionables. El frontend puede calcular una
estimación inmediata; la revisión confirmable consume el resultado del backend.

La función de cálculo/preparación no autentica en WSAA, consulta padrón, reserva
numeración ni solicita CAE. El adaptador HTTP conserva autenticación, permisos,
emisor activo y pertenencia de entidades. Reutiliza la revisión existente, sin
agregar un paso o confirmación rutinarios ni llamadas por cada pulsación.

La previsualización no garantiza autorización posterior ni reserva un número.
La emisión revalida lo necesario en su frontera irreversible. Cambios fiscales
posteriores a revisar invalidan la confirmación aplicable; una actualización de
metadatos sin cambio fiscal no invalida por sí sola una operación.

## Primer corte P1

1. Inventariar schemas, validación de negocio, importación, UI, lote, worker,
   reintentos y armado WSFE. Definir un conjunto explícito de tasas efectivamente
   soportadas; distinguirlo del catálogo de tasas admitidas por ARCA.
2. Validar antes de cualquier CAE. Una tasa desconocida o sin implementación
   completa no cae en `base_0`. El error identifica ítem/fila y tasa.
3. La revisión obtiene neto, IVA y total del cálculo decimal común. Mantener
   descuentos, precisión de entrada y redondeo vigentes; no redondear primero
   precios o cantidades para ocultar la diferencia.
4. Delimitar el significado fiscal real del actual «Exento / 0 %». Corregir su
   presentación y validación conforme al contrato efectivo, sin prometer una
   categoría que el backend no representa.
5. Conservar payloads, hashes y autorizados históricos. Un lote preparado con
   datos no soportados se trata explícitamente antes de una nueva emisión;
   intentos activos o inciertos mantienen su evidencia congelada.

La [auditoría integral A-01/A-03](../project/analysis/auditoria-integral-2026-10.md)
separa persistencia de lecturas fiscales. A-01 está implementado en el
[contrato de persistencia fiel](pf-03-04-14-persistencia-fiel-design.md): esta
preparación consume su representación y validación de encodabilidad, conserva
precisión de cantidades/precios y totales y no vuelve a imponer los límites
del esquema anterior ni diseña otra migración de almacenamiento.
A-03 está implementado en el [contrato de lecturas fiscales](a03-lecturas-fiscales-design.md):
las bases y agrupaciones de moneda en informes deben
usar hechos conservados, sin reconstruir netos desde IVA redondeado. La
admisibilidad y revisión de este corte mantienen sus propios criterios de
aceptación; no esperan categorías P2 ni modifican redondeos aceptados.

Si aparece un uso operativo válido de una tasa todavía no implementada, evaluar
su soporte acotado y el efecto de rechazarla antes de imponer una restricción
permanente. El intercambio que requiera bloquear una operatoria válida conserva
la decisión explícita prevista por `VISION.md`; no se resuelve cambiando la tasa.

## Contrato técnico del corte P1

El 09/10/2026 Santi aceptó conservar 0 %, 10,5 %, 21 % y 27 % y exigir
corrección de tasas sin soporte antes de una nueva emisión. El catálogo de ARCA
no implica soporte implementado. Los pendientes incompatibles necesitan
corrección; autorizados, hashes y operaciones activas o inciertas conservan
su evidencia. No se modifica `VISION.md` ni se agregan categorías P2.

`preparar_importes` valida las tasas y consume `calcular_totales`, sin IO.
El calculador y los schemas históricos conservan su lectura y redondeo PF-03B.
API individual nueva, normalización nueva, servicio unitario/batch, columnas y
constantes de Excel usan el mismo conjunto. Worker y reintentos pasan por la
frontera del servicio antes de solicitar otro CAE. El resumen de pendientes
suma importes fiscales por comprobante, incluye IVA 27 % y cuenta los payloads
incompatibles como inválidos; no usa estimados almacenados como autoridad.

`POST /api/comprobantes/previsualizar` acepta el request existente sin exigir
confirmación ni clave. Usa los permisos y emisor activo de emisión; valida
pertenencia de empresa, punto y cliente y reglas locales de preparación.
Devuelve totales y subtotales de ítems como strings decimales, moneda,
cotización y receptor efectivo. Errores locales responden 400; errores de
contrato, 422. No guarda clientes/operaciones/intentos, autentica en WSAA,
consulta RECE/padrón/numeración ni solicita CAE. No reserva número ni promete
autorización. La UI consulta sólo al revisar y presenta ese resultado en el
modal existente; una respuesta vieja nunca rehabilita una revisión invalidada.

Checklist fiscal previo: riesgo de conversión a IVA cero y confirmación de un
total distinto; consumidores identificados arriba. Se mantienen fecha explícita,
confirmación irreversible, aislamiento, hashes, claves, locks, reservas,
intentos durables y reconciliación. La operación existente se busca antes de
las validaciones mutables de una operación nueva. Una reanudación que enviaría
otro CAE revalida tasas; la recuperación autorizada usa la lectura histórica.
No cambia la máquina de estados fiscal, DDL ni constraints. La revisión UI
pasa de vacía a consultando y revisada/error; edición fiscal o cambio de emisor
invalida solicitud/confirmación. La operación incierta conserva su snapshot.

Matriz de aceptación: tasas admitidas/sin soporte, constantes/columnas, errores
por ítem/fila, descuentos 0/100 %, fracciones, mitad de centavo, IVA 27 %,
acumulación inválida y monedas; API sin efectos externos/escrituras y aislamiento;
servicio unitario/batch antes de CAE; pendientes legacy y hashes históricos;
UI con edición fiscal, respuesta tardía, error HTTP, cambio de emisor, doble
acción y snapshot incierto. Las regresiones existentes cubren concurrencia,
replay/conflicto, fallos pre/post-CAE y reconciliación; no se introducen locks.

Rollback técnico por commit, sin reescritura de datos. Revertir runtime
reintroduce el riesgo: preferir corrección hacia adelante. No restaurar ni
reemitir autorizados. Suites completas, QA y revisión final `autoreview`
`gpt-5.6-sol medium` preceden al cierre; release y despliegue tienen puertas
propias. El adaptador WSFE y sus tolerancias mantienen su contrato vigente.

## Ampliación P2 del dominio

- Representar por separado gravado a tasa cero, exento, no gravado y tributos,
  según el contrato oficial aplicable. Una etiqueta o una tasa numérica no bastan
  para distinguirlos. Definir base, alícuota, importe y compatibilidad A/B/C.
- Incorporar 2,5 % y 5 % cuando su contrato completo esté implementado. Mantener
  `Decimal`; no copiar tolerancias o ajustes de IVA del proyecto de referencia.
- Cubrir entrada individual y Excel, preparación, pedido ARCA, snapshot,
  reconciliación, persistencia, PDF, reportes y dashboard. Definir la suma de
  componentes y su presentación; no agregar un módulo contable general.
- Mantener la lectura histórica sin convertir todos los valores antiguos de
  cero en «exento». Una clasificación desconocida se conserva como cobertura
  histórica limitada; no se inventa su significado.
- Versionar la nueva representación, con migraciones reversibles PF-12 y
  compatibilidad de lectores PF-04. PF-13 consume este dominio, sin otro motor.

## Coordinación

| Consumidor | Contrato |
|---|---|
| [Receptor P1](pf-13-receptores-importacion-design.md) | Identificación y condición independientes; su cierre no espera la ampliación de importes |
| [Plantillas PF-13](pf-13-plantillas-contables-design.md) | Consume preparación común y distingue neto/IVA/total, sin recalcular reglas fiscales en UI |
| [UI de lotes](pf-17-lotes-ui-design.md) | Presenta resultado y procedencia; no requiere un rediseño completo para corregir importes |
| [Reconciliación](pf-02-04-reconciliacion-integral-design.md) | Compara la misma representación fiscal versionada y conserva incertidumbre |
| [Notas guiadas](pf-04-17-notas-guiadas-design.md) | Reutiliza cálculo y revisión para notas parciales o totales |

## Aceptación y preparación técnica

- Tasas soportadas, desconocidas, 2,5 % y 5 % sin soporte; diferencias entre
  constantes de plantilla, columnas y API. Ningún valor se transforma en cero.
- Casos de mitad de centavo, cantidades fraccionarias, descuentos, varios ítems
  y monedas: resultado visible igual al fiscal, preservando PF-03B.
- Cambio después de revisar, respuesta tardía, cambio de emisor, repetición de
  revisión y error HTTP; cero solicitudes de CAE en preparación.
- Para P2: categorías mixtas, notas, impuestos separados, historial incompleto,
  lectura de versiones antiguas y agregados sin doble conteo.
- Antes de codificar: cerrar contrato HTTP/preparación, consumidores, política
  legacy y rollback del corte; completar `fiscal-change-checklist.md`.

Fuente fiscal: [manual WSFE oficial](https://www.arca.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf),
v4.7, revisión del 01/09/2026, consultado el 09/10/2026. Verificar versión,
campos y catálogos antes de implementar la ampliación P2.
