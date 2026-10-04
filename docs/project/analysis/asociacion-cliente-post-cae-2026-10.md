# Validación A-02 — asociación administrativa posterior a CAE

Fecha: 03/10/2026.

El [contrato](../../agents/pf-03-04-14-asociacion-cliente.md) corrige la excepción
por clientes administrativos duplicados en el guardado compartido. Nivel 2;
autoridad funcional: conservar el receptor fiscal y una autorización sin
elegir una ficha ambigua. No modifica los contratos ARCA.

## Evidencia enfocada

181 pruebas aprobadas: 27 nuevas y 154 existentes de facturación y API.
Black, Ruff y revisión del diff de los dos archivos aprobados.

Los casos nuevos verifican coincidencias, aislamiento, ID explícito y su
desactivación sin lectura adicional, pertenencia previa a CAE, ausencia de alta,
snapshot/ítems/payload, duplicados aparecidos después del preflight, atomicidad,
FK y rollback, timeout y errores de base. Los dobles cubren autorización
individual y masiva, fallo post-CAE, replay sin segundo CAE, reconstrucción stale
y origen externo `arca_web`.

El ensayo de borrado físico verifica conservación de FK/rollback; no afirma
que la UI permita borrar físicamente un cliente. El DELETE público desactiva.

La suite completa conjunta con el contrato temporal aprueba 1542 pruebas,
incluida integración PostgreSQL, con cobertura del 73,54 %. Los controles de
frontend, construcción, smoke y tooling se registran en la
[validación del conjunto](contrato-tiempo-operativo-2026-10.md#controles-de-cierre).

## Límites

Docker local sin salida externa; datos y CAEs exclusivamente sintéticos. Sin
producción, migraciones, emisión real ni fusión de fichas. El snapshot conserva
legibilidad cuando no existe asociación administrativa.

Otras fallas reales del alta mantienen incertidumbre y reconciliación. A-01
permanece pendiente de capacidad. Recuperación: revertir la unidad sin tocar
historia ni reemitir comprobantes. La revisión obligatoria del conjunto con
GPT-5.6 Sol, razonamiento medio y alcance P0/P1 completó 21 pasadas sin hallazgos
aceptados de esas prioridades; incluye esta unidad y el contrato temporal.
