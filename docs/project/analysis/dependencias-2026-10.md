# Mantenimiento de dependencias y cierre de PR

Fecha: 14/10/2026.

Alcance: mantenimiento autorizado antes de retomar el roadmap. No modifica
producción, no publica una release y no implementa PF-04/PF-02. El estado
desplegado se acredita exclusivamente en `VPS Hostinger` / `vps-admin`.

## Unidades y autoridad

| PR | Resultado del mantenimiento |
|---|---|
| [#77](https://github.com/Santi-RL/FactuFlow/pull/77) | psycopg2-binary 2.9.13 para herramientas síncronas y traslado; asyncpg conservado |
| [#79](https://github.com/Santi-RL/FactuFlow/pull/79) | Vitest/coverage-v8 5.0.3 con puerta real y umbrales globales intactos |
| [#103](https://github.com/Santi-RL/FactuFlow/pull/103) | FastAPI 0.143.0; mismos contratos HTTP, validaciones, permisos y mensajes |
| [#102](https://github.com/Santi-RL/FactuFlow/pull/102) | ESLint 10.12.0 y @eslint/js 10.0.1 juntos; incorpora la propuesta de #101 |
| [#104](https://github.com/Santi-RL/FactuFlow/pull/104) | SQLAlchemy 2.1.4 con compatibilidad SQLite explícita y protección PF-19 preservada |

#78 y #81 fueron sustituidos por #104 y #102. El cierre de #101 requiere la
integración y comprobación del contenido completo en #102. Las integraciones
requieren los siete checks obligatorios del head revisado y una base vigente;
la autorización de mantenimiento no permite omitirlos para vaciar la lista.

## Diseño previo y checklist de SQLAlchemy

Nivel 2 por su frontera de persistencia fiscal. Consumidores: constructor de
engines, API, worker, CLI PF-19, sesiones y seguimiento transaccional, Alembic,
traslado y almacenamiento decimal. La actualización no solicita CAE por sí
misma; los caminos de emisión conservan confirmación explícita, fecha elegida,
idempotencia, reservas, aislamiento y reconciliación sin reemisión automática.

SQLite de archivo conserva `NullPool`; memoria, URL vacía y URI `mode=memory`
conservan `StaticPool`, al igual que `file::memory:` con URI habilitada y su
forma codificada. Las pruebas crean datos desde API y los leen después desde
worker. API y worker comparten engine SQLite; PostgreSQL mantiene
sus dos pools y capacidades. La selección explícita evita tanto el cambio de
default como el warning de selección por URI de SQLAlchemy 2.1. No cambia DDL,
locks, constraints, transiciones, CAS, autorización de trabajos ni orden fiscal.

La prueba PF-19 agregaba un listener `connect` después de sembrar datos. Un pool
reutilizable devolvía una conexión previa, sin ejecutar ese listener; por eso
no se cumplía la precondición de solo lectura que la prueba quería restaurar.
Se renueva la conexión de prueba, se acredita `query_only=1` antes y después,
y se conserva la aserción de restauración. Se ensayan `NullPool` y
`AsyncAdaptedQueuePool`, en éxito y fallo. No se modifica el inventario para
forzar el resultado ni se elimina la comprobación; el servicio sigue activando
solo lectura, haciendo rollback y restaurando el valor previo.

Matriz: archivo/memoria/URI, doble consumidor, fallo dentro de inventario y
restauración, rechazo de escrituras, PostgreSQL desechable con locks y
constraints reales, codecs decimales, migraciones y traslado v3/v4/v5. Las
regresiones fiscales existentes cubren replay, concurrencia, respuesta tardía,
rechazo e incertidumbre. No hay cambio de UI, confirmaciones, fecha, numeración,
hashes, snapshots ni llamadas ARCA que requiera otro contrato de usuario.

## Evidencia local y límites

- Driver: 357 pruebas de traslado, almacenamiento y harness aprobadas; roundtrip
  v5 adicional aprobado contra PostgreSQL desechable. El harness sólo admite
  loopback y la base exacta `factuflow_integration_test` con opt-in explícito.
- Vitest: 291 pruebas y los dos ensayos de cobertura aprobados; lint, tipos y
  build correctos. Umbrales conservados: statements 56 %, branches 50 %,
  functions 43 % y lines 57 %, con `autoUpdate: false`.
- FastAPI: 94 pruebas de autenticación, health y comprobantes simulados aprobadas.
- ESLint conjunto: 295 pruebas aprobadas, cobertura sobre los mismos umbrales,
  lint con cero warnings, tipos y build correctos; auditoría npm completa sin
  vulnerabilidades. Se preserva la causa interna de los errores sin ampliar sus
  mensajes públicos. `ES2022.Error` agrega tipos; el target sigue siendo ES2020.
- SQLAlchemy: 80 pruebas enfocadas de pools, inventario, almacenamiento y
  Alembic aprobadas; 8 pruebas PostgreSQL de precisión, solo lectura, capacidad
  y traslado también aprobadas. Ruff y Black correctos. La evidencia de CI
  corresponde al SHA de cada PR, no a otro candidato.

La revisión con `gpt-6.1-sol low`, elegida y autorizada por Santi, detectó un P2
aceptado: faltaba clasificar la URI anónima `file::memory:` como memoria.
Se reprodujo el fallo, se cubrieron también sus caracteres codificados y se
agregó la conservación real de una tabla entre conexiones API/worker. Las 40
pruebas de pools e inventario pasaron tras la corrección; el cierre exige repetir
la revisión con la misma configuración y la CI completa.

Windows carecía de HarfBuzz-Subset, por lo que backend se comprobó en un
contenedor desechable con bibliotecas compatibles y red externa bloqueada para
las pruebas. Un primer fallo de harness fue la ausencia del workflow en la
copia de fuente; se agregó ese archivo y sus 24 pruebas pasaron. Vitest encontró
temporales inaccesibles dentro del sandbox Windows y pasó al ejecutarlo con
acceso normal; no se cambiaron aserciones, warnings ni controles de cobertura.
Los fallos previos HTTP 429 del registro de imágenes no acreditaban defectos
de FastAPI o ESLint; se mantienen visibles y se repite CI sin omitir jobs.

## Recuperación y exclusiones

Revertir la unidad de dependencia y su adaptación de código, sin restaurar
datos. No hay esquema nuevo ni migraciones destructivas. Una falla o resultado
fiscal incierto conserva la recuperación vigente; este mantenimiento nunca
borra reservas ni vuelve a enviar una solicitud para probar compatibilidad.
No hay QA con CAEs reales, acceso al VPS, cambios de credenciales o limpieza de
datos. Las prioridades del roadmap, la visión y el diseño PF-04/PF-02 siguen
siendo independientes. Una CI verde permite integrar, no desplegar.
