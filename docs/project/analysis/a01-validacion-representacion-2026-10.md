# A-01 — validación preparatoria de representación

Fecha: 05/10/2026.

Estado: ENSAYOS PREPARATORIOS; SIN CAMBIOS DE RUNTIME.

El usuario informó que su revisión manual de v0.3.7 fue satisfactoria y pidió
continuar. Se preparó el [contrato de persistencia](../../agents/pf-03-04-14-persistencia-fiel-design.md).
Esta evidencia no cierra A-01 ni acredita una implementación futura.

## Entorno y resultados

SQLite en memoria y PostgreSQL 16 desechable sólo en loopback. Datos sintéticos,
tablas propias, sin certificados, datos operativos, producción ni llamadas ARCA.
Los harness/resultados quedan en rutas ignoradas y el contenedor propio se retira.

| Ensayo | Resultado |
|---|---|
| Cantidad `1.00005`, tipo antiguo | Ambos motores leen `1.0001` |
| PostgreSQL `NUMERIC` sin typmod | Conserva `0.1234567890123456789012345678` y `10000000000000000000000000.01`; suma SQL exacta |
| SQLite `Numeric()` | Devuelve diez decimales y pierde precisión/centavos en esos casos |
| Texto decimal compacto | Los valores probados vuelven exactamente a `Decimal` |
| SQLite `SUM(TEXT)` | Vuelve a flotante; no satisface el contrato |
| Agregado SQLite exacto sintético | Igual al oráculo de fracciones; equivalencia de ceros/escalas aprobada |
| Codec sin contexto | Conserva 28 decimales con contexto de precisión 8 y el exponente compacto `1E+200000` |
| Traslado SQLite | Conserva lectura antigua `1.0001`, sin reconstruir `1.00005` |
| Ampliación PostgreSQL sintética | Fila antigua equivalente; centavos fuera de int64, código de 51 caracteres y exponente compacto como texto |
| Downgrade PostgreSQL compatible | Tras retirar sólo la fila sintética incompatible, el esquema antiguo devuelve la fila inicial exacta |
| Guarda de incompatibilidad | Detecta importe/centavos/código fuera de capacidad antes de reducir tipos; la implementación debe cubrir todos los campos |

Son tablas simples, no la migración Alembic del grafo real. Las fracciones son
un oráculo de exactitud, no el algoritmo de producción. El adapter definitivo
debe acreditar coste y funcionamiento síncrono/asíncrono.

Un primer harness intentó `SUM(TEXT)` en PostgreSQL, que lo rechazó; se corrigió
para agregar `NUMERIC`. Otro reutilizó un prepared statement tras cambiar sus
tipos y `asyncpg` rechazó el descriptor anterior. Se repitió sin reutilización;
el contrato exige conexiones nuevas al migrar, sin desactivar la caché productiva.

## Invariantes y revisión

PF-03B y asociación A-02 aprobaron **36 pruebas enfocadas** en la imagen Linux
local de v0.3.7 con red deshabilitada. Incluyen hashes canónicos, round-trip JSON,
cálculo/redondeos y guardado/asociación sintéticos. Demuestran el contrato vigente,
no su integración con un codec nuevo.

La carga inicial de pytest en Windows falló por HarfBuzz-Subset de WeasyPrint.
No se silenció ni se declaró aprobada; la comprobación enfocada se hizo en Linux.

La revisión independiente confirmó centavos, cotización/índices, procesadores
legacy y compatibilidad de paquetes como consumidores obligatorios. No encontró
una decisión funcional que impida esta preparación ni autoriza topes nuevos.

La revisión del documento detectó que un borrador atribuía el redondeo del
subtotal de ítem a la base. El servicio lo cuantiza explícitamente a centavos;
se corrigió el contrato para preservar ese cálculo antes de continuar.

## Límites

No se ejecutaron Alembic nuevo, llamadas fiscales, QA productiva A-01 ni pruebas
integradas del futuro codec. No cambiaron modelos, DTO, API, worker, PDF, índices
o versiones. El siguiente corte implementa el contrato y completa su matriz de
errores, concurrencia, recuperación y compatibilidad antes de cerrar el hallazgo.
