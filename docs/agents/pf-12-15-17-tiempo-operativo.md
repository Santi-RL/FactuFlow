# PF-12/PF-15/PF-17 — instantes operativos y hora argentina

Fecha: 03/10/2026.

Estado: contrato implementado; evidencia de validación en el
[dossier](../project/analysis/contrato-tiempo-operativo-2026-10.md).

## Problema y autoridad

El usuario confirmó que los horarios de lotes se muestran en otra región y
pidió registrar y mostrar la hora argentina. La aplicación genera sus marcas
operativas actuales en UTC, pero algunas respuestas omiten la zona y distintas
vistas las interpretan con el reloj local del navegador. Un mismo instante puede
verse tres horas desplazado o en otro día.

Esta unidad corrige el contrato temporal compartido. No modifica las fechas de
emisión, servicio, pago o vencimiento fiscal, ni la lista futura de actividad.

## Contrato común

- Registrar un instante inequívoco. Conservar UTC en almacenamiento y en los
  relojes internos existentes, y comunicar la zona explícita en la API.
  La misma operación corresponde a una hora argentina concreta; no se suman o
  restan tres horas a los datos guardados para cambiar su significado.
- Mostrar los instantes conocidos en `America/Argentina/Buenos_Aires`, con
  fecha `DD/MM/AAAA` y hora de 24 horas. La configuración regional del servidor
  o del navegador no decide la presentación.
- Las respuestas de campos producidos en UTC pueden interpretar sus valores
  históricos sin zona conforme a esa procedencia acreditada. El fallback de
  cliente debe ser explícito para esos campos, compatible con API anteriores.
- Un timestamp con `Z` u offset conserva su instante. No aplicar dos veces una
  conversión ni asumir que todo valor sin zona es argentino o UTC.
- Los antecedentes fiscales con `hora_confiable` y los documentos externos
  conservan su cobertura. Una hora desconocida no recibe una zona inventada.
- Las fechas de calendario se formatean sin conversión de zona. Un string de
  fecha no se convierte en un instante a medianoche.
- Entradas ambiguas o imposibles no se normalizan a otro día. La UI presenta
  ausencia de un valor válido; no usa la hora actual como sustituto.

## Fronteras e invariantes

La serialización de respuestas añade información de zona sólo a campos cuya
fuente UTC fue comprobada. No altera objetos Python, modelos de almacenamiento,
comparaciones de antigüedad, reservas, hashes ni contenido congelado de intentos.
No migra bases ni reescribe JSON históricos o respuestas idempotentes guardadas.

Frontend comparte el parser de instantes entre presentación y cálculo de
duraciones de lotes. Las vistas no mantienen variantes locales de parsing. Los
antecedentes de duplicados mantienen su política de procedencia.

El cotejo puro de creación en paquetes v4 se utiliza al exportar, validar un
manifiesto y verificar/importar el destino durable. Sólo compara los dos
`created_at` conocidos como UTC; conserva identidad, estados, precisión y
evidencia fiscal. No cambia barreras, digests, locks ni conversiones físicas.
El parser v3 valida timestamps sin comparar esos instantes; el cierre legacy
PF-19 compara ambos lados mediante el mismo DTO, ya compatible con UTC explícito.

La corrección no agrega consultas ARCA, confirmaciones, vencimientos o pasos.
Fecha fiscal explícita, confirmación irreversible, emisor activo, idempotencia,
ownership y recuperación de incertidumbre conservan su comportamiento.

## Consumidores y aceptación

| Consumidor | Comprobación |
|---|---|
| Lotes, resumen y seguimiento | Carga/inicio/fin/compactación y avance describen el mismo instante; respuestas con zona y compatibilidad UTC anterior |
| Usuarios y emisores | Último ingreso y actualización muestran Argentina independientemente de la zona del navegador |
| Sistema y almacenamiento | Instantes conocidos con zona; vencimiento del certificado conserva fecha de calendario |
| Antecedentes de duplicados | Hora confiable convertida a Argentina; cobertura desconocida visible y sin inferencias |
| CRUD y metadatos de respuesta | Fuente UTC acreditada y serialización JSON explícita, sin modificar valores Python o fechas `date` |
| Replay de lote | Respuesta antigua con instantes UTC sin zona sigue interpretable; registro y payload guardados intactos y cero llamadas externas |
| Migración y recuperación v3/v4 | Creación del lote compara el mismo instante UTC entre replay y fila durable; acepta representación anterior y zona explícita, conservando precisión, identidad y controles fiscales |

Probar cambio de día/mes/año, offsets equivalentes, milisegundos, calendario
bisiesto, nulos, formatos ambiguos e imposibles, y ejecución en zonas de
navegador distintas de Argentina. La evidencia de la corrida pertenece al
dossier, no a este contrato.

Rollback de aplicación: revertir la presentación/serialización y reconstruir,
conservando el verificador compatible de paquetes anteriores y UTC explícito.
La lectura de paquetes con replay nuevo requiere ese cotejo compatible, también
durante una recuperación. No hay migración ni escritura histórica que revertir. Aplican las
[puertas de calidad](change-quality-gates.md) y el
[checklist fiscal](fiscal-change-checklist.md) de forma proporcional a las
respuestas de lotes y metadatos; no cambia una transición fiscal.

La [dirección de arquitectura](architecture-direction.md) conserva esta frontera
para futuros consumidores HTTP/MCP: un instante inequívoco y su presentación no
dependen del canal. La evolución de actores y eventos permanece en el
[diseño de actividad](pf-17-actividad-lotes-design.md).
