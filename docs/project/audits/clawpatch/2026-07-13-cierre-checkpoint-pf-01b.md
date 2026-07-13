# Cierre del checkpoint Clawpatch PF-01B — 2026-07-13

## Objetivo y alcance

Este checkpoint cerró las dos fuentes backend de PF-01B después de publicar los
cortes de modelo, migración y validación PostgreSQL. No relanzó una auditoría
masiva, no ejecutó `clawpatch fix`, no llamó a ARCA y no modificó código.

Base verificada:

- rama `main` limpia y sincronizada;
- commit `6625254`;
- CI `29270728104` verde en Security Audit, Backend Tests, Frontend Build y
  E2E Tests;
- Clawpatch `0.7.0`, Codex CLI `0.144.0`;
- slice backend con su `root`, `state-dir` y `config` vigentes;
- cero locks antes y después de las revalidaciones.

## Procedimiento

Se ejecutó `show` sobre B10 y B17, se contrastaron sus premisas con modelos,
migración y pruebas actuales, y luego se revalidó un finding por vez con
`gpt-5.6-sol` y razonamiento `high`.

La evidencia enfocada incluyó:

- `27` pruebas de persistencia SQLite y Alembic aprobadas;
- harness PostgreSQL reproducible publicado, con `4` pruebas aprobadas contra
  PostgreSQL 16 efímero;
- suite backend completa previa de `531` aprobadas y `4` omitidas;
- CI completa del commit publicado.

## Resultado

- **B10 — reserva por estados no restringidos:** `fixed`. El vocabulario
  canónico, el check de dominio, el predicado compartido y el preflight legacy
  impiden que un estado desconocido eluda la reserva.
- **B17 — estado/CAE incoherente:** `fixed`. Los checks persistidos rechazan
  estados desconocidos, autorizados sin CAE completo y no autorizados con CAE.

El ledger backend pasó de 98 a 96 findings abiertos y terminó sin locks.

## Incidencia operativa aprendida

La primera revalidación de B10 agotó el límite interno de 300 segundos después
de que el agente intentara invocar otra revalidación de Clawpatch dentro de su
propia sesión. La salida parcial no se tomó como cierre. Se verificaron
worktree, locks y estado del finding, y se realizó un único reintento razonable
con el mismo modelo; ese reintento concluyó `fixed`. B17 concluyó `fixed` en
su primera ejecución.

El runbook incorpora esta regla: una corrida truncada o con timeout no permite
cerrar manualmente el finding; primero se verifica el estado, se reintenta una
vez y luego se usa el fallback documentado si el problema persiste.

## Cierre y continuidad

PF-01 quedó cerrado. El siguiente corte recomendado es preparar el candidato
provisional `v0.2.2`, siguiendo las puertas flexibles del roadmap y del flujo
productivo, antes de mezclar el cambio funcional PF-02. Crear un tag y desplegar
siguen requiriendo decisiones explícitas.

Los IDs completos, prompts y evidencia cruda permanecen en el ledger y en rutas
locales ignoradas. Este documento conserva solo el cierre sanitizado y
versionable.
