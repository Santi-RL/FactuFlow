# Validación del contrato temporal operativo

Fecha: 03/10/2026.

El [contrato](../../agents/pf-12-15-17-tiempo-operativo.md) corrige instantes
ambiguos en la API y presentación dependiente del navegador. Nivel 2
proporcional a las respuestas de lotes: no modifica la transición fiscal.
Autoridad: pedido explícito del usuario de registrar y mostrar hora argentina.

## Evidencia enfocada

- Cinco pruebas del serializer y HTTP verifican offsets equivalentes, precisión,
  calendario, nulos, metadata desconocida y persistencia original sin cambios.
- Dos casos de replay terminal verifican respuestas actuales y UTC anterior sin
  zona, cero llamadas WSFE y registro idempotente intacto.
- 110 casos de componentes y utilidades pasan con procesos en Argentina, UTC
  y Tokio. Incluyen días bisiestos, cambio de día, calendario e inputs imposibles.
- Chromium recorre preparación y validación en UTC y Tokio con mocks completos;
  el instante de carga se muestra en Argentina. No pulsa emisión y registra
  cero solicitudes de emisión, procesamiento o reintento durante el recorrido.
- Revisión independiente de fuentes y consumidores: sin hallazgos de runtime;
  fortalecida la observación de ausencia de emisión en E2E.
- La primera suite completa detectó una comparación naive/aware en el
  verificador v4 que rechazaba replays con UTC explícito. Se corrigió únicamente
  la comparación de creación del lote, sin modificar JSON ni relajar identidad,
  estados o evidencia fiscal. Doce casos nuevos cubren representaciones
  equivalentes, microsegundos, otro instante, metadata y manipulación de evidencia.
- Las 313 pruebas del archivo de migración pasan después de esa corrección,
  incluidos controles fiscales hermanos. El helper es puro y no solicita CAE;
  concurrencia y reserva conservan su matriz en la suite integral.

## Controles de cierre

- Suite completa del backend, incluida integración PostgreSQL: 1542 pruebas
  aprobadas en 1187,81 segundos, cobertura de ramas incluida del 73,54 % frente
  al mínimo del 69 %. Ejecutada en el árbol de trabajo conjunto con A-02.
- 273 pruebas unitarias del frontend y 38 E2E de Chromium aprobadas; cobertura
  por encima de los umbrales vigentes. Tipos, lint y construcción aprobados.
- Black comprueba los 153 archivos Python sin cambios; Ruff aprueba aplicación
  y tests. Los 28 tests del tooling y el control documental también pasan.
- Smoke local con base PostgreSQL sintética migrada a head: salud de FastAPI y
  DB, Nginx, HTML, assets compilados y proxy API correctos. No hubo puertos
  publicados, datos privados ni solicitudes de emisión.
- Revisión final obligatoria con GPT-5.6 Sol, razonamiento medio y alcance
  P0/P1: 21 pasadas, sin hallazgos aceptados de esas prioridades. Incluye el
  verificador v4 corregido y la asociación A-02 del mismo árbol de trabajo;
  no sustituye los tests ni acredita ausencia de defectos de cualquier prioridad.

## Límites y recuperación

La base y los relojes internos conservan UTC. Se comunican zonas sólo en campos
con procedencia comprobada; JSON arbitrario y evidencia con hora desconocida
no se reinterpretan. El frontend usa precisión de milisegundos para presentación
y duración; la respuesta conserva microsegundos.

No se consultó producción, no se solicitó CAE y no hubo migraciones de aplicación.
Revertir la presentación/serialización recupera el comportamiento anterior sin
restaurar ni desplazar datos; conservar el verificador compatible para paquetes
que contengan replays UTC explícitos.
La auditoría npm del frontend vigente conserva cinco avisos altos de una misma
cadena de construcción. La migración Tailwind candidata está aislada y pendiente
de decidir compatibilidad de navegadores; estos controles no declaran CI integral
verde ni integración en `main`. El build Docker emitió un aviso informativo de
tiempos de plugins bajo carga; la construcción local y los smoke checks pasaron.
