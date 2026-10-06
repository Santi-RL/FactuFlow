# A-01 — implementación de persistencia fiscal fiel

Fecha del corte: 05/10/2026. Riesgo: Nivel 2, persistencia y migración fiscal.

## Resultado y autoridad

La representación física conserva los decimales finitos admitidos y los
resultados de PF-03B. El [contrato dueño](../../agents/pf-03-04-14-persistencia-fiel-design.md)
define codecs, consumidores y transición. El cálculo y su contexto no cambian;
el subtotal de ítem mantiene su cuantización explícita a centavos. No se imponen
topes comerciales para acomodar datos al esquema antiguo.

Los adaptadores comparten `Decimal` e `int`: campos variables en texto compacto,
importes PostgreSQL en `NUMERIC` sin typmod y agregado SQLite explícito en
centavos. La comparación es numérica. Centavos superan int64; la cotización usa
una clave física fija y se compara después su valor exacto. Código de ítem usa
`TEXT`. Las respuestas consultadas, PDF, lotes y reportes conservan cifras sin
convertir a flotantes. El ranking recibe su total desde el servidor.

Alembic `b2c3d4e5f6a7`, posterior a `a1b2c3d4e5f6`, es la transición real.
SQLite conserva la lectura del procesador `Numeric` anterior; PostgreSQL
conserva la escala que ya aplicó. El paquete v5 identifica el head ampliado y
su representación. Los paquetes v3/v4 mantienen lectores, hashes y barreras
congelados, con adaptación explícita al destino.

## Checklist fiscal y consumidores

| Contrato / consumidor | Evidencia automatizada |
|---|---|
| Codec finito, sin contexto ni expansión de exponentes | `test_fiscal_storage.py`: contexto de precisión 8, exponentes ±200000, ceros equivalentes, centavos fuera de int64 |
| Igualdad, rangos, orden y suma exacta, vacío y conexiones nuevas | `test_fiscal_storage.py` y `integration/test_fiscal_storage_postgresql.py`: SQLite síncrono/aiosqlite y PostgreSQL real |
| Preparación y guardado compartido | `test_fiscal_storage.py`, `test_pf03b_importes.py`: orden técnico y cálculo imposible rechazados antes de emitir; detalle y componentes fieles |
| Emisión individual y por bloques | `test_facturacion_cliente_asociacion.py`: datos ampliados, asociación ambigua, replay y falla real de DB posterior a CAE simulado |
| Worker y reintento parcial | `test_reintentos_background.py`: selección durable, bloques, progreso, replay y datos ampliados; no volver a tocar autorizados |
| Recuperación stale y externa | `test_facturacion_cliente_asociacion.py`: snapshot ampliado y solicitud congelada intactos; `LotesComprobantesView.spec.ts`: total decimal enviado sin conversión |
| Duplicados y aislamiento | Suites de lotes, duplicados y PostgreSQL: emisor/ambiente, reservas, evidencia, carreras y restricciones vigentes |
| Migración histórica y recuperación | Cadena real con comprobantes e ítems en ambos motores; grafo PF-13 completo SQLite, JSON literal, huellas, IDs, relaciones y reservas preservados |
| Atomicidad SQLite | Fallo inyectado durante el segundo `DROP TABLE`: esquema/datos íntegros y `foreign_keys` restaurado en la misma conexión |
| Downgrade | Compatible: downgrade/reupgrade. Incompatible: abortar antes del DDL con precisión y código ampliados, sin truncar ni cambiar el head |
| Transferencia | Suite VPS histórica y round-trip v3/v4/v5 con PostgreSQL desechable; v5 conserva precio, descuento, cantidad, cotización enorme y total ampliado |
| Consulta y presentación | `fiscal-decimal.spec.ts`, vistas y reportes; PDF real con texto extraído y QR numérico exacto; sumas de reportes sin contexto |
| Confirmaciones y estados | Suites fiscales existentes: fecha explícita, clave/confirmación ausentes, conflicto, concurrencia, revocación e incertidumbre |

No se agregan estados ni transiciones fiscales. API, servicio, worker y
reintentos usan la guarda compartida antes de reserva/CAE. Los locks, constraints,
compare-and-swap, aislamiento y asociación A-02 permanecen vigentes.

Una falla previa a CAE no crea una autorización. Una falla de almacenamiento
posterior a una posible autorización conserva intento, reserva e incertidumbre;
no se transforma en rechazo ni en retry automático. Replay terminal conserva su
respuesta durable y no solicita otro CAE. JSON originales, payloads congelados
y hashes históricos no se canonizan con el codec nuevo.

## Validación y límites

Toda la evidencia usa emisores, certificados, fechas y CAEs sintéticos, con
ARCA simulado. No hubo llamadas fiscales reales ni acceso a producción.
PostgreSQL usa el harness con base descartable exacta, loopback y opt-in de
reset; el smoke usa otro contenedor aislado de la suite.

Las pruebas Linux usan el runtime PDF nativo de la imagen de validación, sin
desactivar warnings. Los controles locales cubren backend con cobertura y
PostgreSQL, frontend, scripts, formato, lint, tipos, build, E2E y smoke.
Resultados de esta validación:

- Suite completa backend con PostgreSQL: 1570 casos aprobados, sin fallos ni
  omisiones; cobertura global 72,31 %, sobre el mínimo vigente de 69 %.
- Las últimas correcciones se comprobaron después de esa captura: 54 casos de
  persistencia, PDF y worker/reintentos; 40 casos de persistencia, reportes y
  duplicados; y la prueba integrada PostgreSQL de migración, orden y downgrade.
  La regresión de agregados SQLite pasó además por separado. La selección de
  40 casos se repitió con `--no-cov` y terminó con código 0; la cobertura global
  se comprueba con la suite completa, no con esa selección parcial.
- Frontend: 277 casos aprobados en 40 archivos; tipos, lint, build nativo y
  Docker aprobados. E2E Chromium: 38 casos aprobados. Scripts: 30 casos
  aprobados; herramientas de revisión: 5 casos aprobados.
- Ruff, Black, alineación documental y `git diff --check` aprobados. Smoke:
  salud API y PostgreSQL HTTP 200; frontend HTTP 200, assets presentes y
  configuración nginx válida.
- Auditoría Python completa sin vulnerabilidades. Las cuatro alertas npm
  detectadas inicialmente se corrigieron con la actualización autorizada el
  06/10/2026: Vue y sus paquetes internos 3.5.42, `postcss-selector-parser`
  7.1.6 y `source-map-js` 1.2.2. Se conservan los demás paquetes previamente
  fijados. `npm ci` y `npm audit --audit-level=low` aprobaron con cero
  vulnerabilidades. Después de actualizar volvieron a aprobar 277 pruebas
  unitarias, 38 E2E Chromium, lint, tipos y compilación nativa. La reconstrucción
  Docker también aprobó `npm ci`, auditoría y build Linux. Se autorizó iniciar
  Docker Desktop para ese ensayo; el contenedor desechable sirvió HTTP 200,
  raíz Vue, cinco assets JS/CSS y fallback SPA de `/comprobantes`, con
  `nginx -t` aprobado. El contenedor se retiró al terminar.

La revisión sensible usa Codex `gpt-5.6-sol medium`. Su primera pasada encontró
dos P2 aceptados y corregidos: versión del manifiesto según el head de origen y
comparador numérico de agregados SQLite, conservando NUMERIC nativo PostgreSQL.
Se agregaron pruebas de orden ascendente/descendente y filtros `HAVING` con
valores positivos y negativos. La segunda pasada no encontró nuevos defectos
de código; se aceptó su P2 documental para explicitar la actualización hasta un
head de paquete admitido antes del preflight. La tercera pasada sobre el diff
completo terminó con código 0, sin hallazgos accionables P0–P2 y dictamen
`patch is correct`; se conservó `gpt-5.6-sol medium` en todas las pasadas.
La auditoría de seguridad local está limpia. La revisión posterior a la
actualización autorizada de dependencias también terminó con código 0,
dictamen `patch is correct` y ningún hallazgo accionable P0–P2 sobre el diff
completo, con `gpt-5.6-sol medium`. Estos controles no acreditan CI remota,
integración ni despliegue.

## Recuperación y exclusiones

Detener API/worker y recrear conexiones durante una actualización autorizada;
retirar prepared statements de `asyncpg` con tipos antiguos. El downgrade
demuestra round-trip completo antes del DDL y aborta ante pérdida. Preferir
corrección hacia adelante. Restaurar datos exige autorización y revisar
escrituras posteriores.

A-03 conserva bases IVA y la autoridad funcional de moneda: este corte sólo
evita pérdidas de representación y suma. La previsualización y alícuotas P1,
categorías P2, reconciliación integral y padrón tienen contratos separados.
No se cambia la visión, la versión publicada ni el estado de una instalación.

Revisados testing, gobierno documental, arquitectura, API, manual de usuario,
QA y procedimiento de traslado. Los comandos y políticas de pruebas no cambian;
no se añaden conteos a esos runbooks. `README.md`, `CONTRIBUTING.md` y releases
no requieren cambios porque no hay publicación, nuevas instrucciones de
contribución ni despliegue. La evidencia preparatoria anterior conserva su
alcance histórico.
