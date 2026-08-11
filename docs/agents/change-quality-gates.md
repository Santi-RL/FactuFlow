# Puertas de calidad y evidencia de cambios

Última actualización: 2026-08-09

Estado: VIGENTE para todo cambio nuevo después de `v0.2.2`.

## Objetivo

FactuFlow debe poder ser evaluado por una persona contadora sin exigirle leer
código. La calidad se demuestra con requisitos funcionales claros, pruebas,
evidencia de fallos ensayados, riesgos residuales y una recuperación definida.

La autoridad se divide así:

- la persona contadora valida la corrección funcional, fiscal y operativa;
- los tests, CI y revisiones validan la implementación técnica;
- ninguna cantidad de tests reemplaza un requisito contable mal definido;
- ningún criterio funcional reemplaza las pruebas de errores, concurrencia y
  recuperación necesarias.

## Clasificación por riesgo

| Nivel | Alcance típico | Control durante el trabajo | Puerta de integración |
|---|---|---|---|
| 0 — editorial | Markdown, textos o `.gitignore`, sin runtime | Revisión del diff, idioma y privacidad | CI liviana, PR y merge |
| 1 — funcional no crítico | UX, CRUD o reportes sin emisión, permisos ni pérdida irreversible | Tests enfocados y controles del área | Suite completa del área, CI y smoke visible |
| 2 — sensible o fiscal | ARCA, CAE, fechas, numeración, importes, idempotencia, multiemisor, autenticación, certificados, migraciones, borrados o backups | Diseño de invariantes y tests antes o junto al código | Checklist aplicable, errores/concurrencia, CI completa, revisión y QA |

Una duda entre niveles se resuelve usando el nivel superior hasta documentar por
qué corresponde reducirlo. El tamaño del diff no reduce el riesgo.

El detector automático de CI solo reconoce como Nivel 0 los archivos Markdown y
`.gitignore`. Cualquier otro archivo activa la matriz completa. Esta decisión es
intencionalmente conservadora: workflows, scripts, configuración, lockfiles y
assets pueden cambiar el comportamiento aunque no sean código de aplicación.

## Ciclo único de ramas

`main` es la única rama permanente y la fuente canónica del código aceptado.

Para cada unidad de trabajo:

1. sincronizar `main` con `origin/main` y exigir un árbol limpio;
2. crear una única rama temporal con un objetivo concreto;
3. implementar y probar solamente esa unidad;
4. completar la puerta documental y la revisión sensible que corresponda;
5. preparar el commit y publicar la rama;
6. abrir un pull request hacia `main` con la matriz documental completa;
7. revisar el rango completo antes de marcarlo como listo;
8. esperar todos los checks obligatorios y corregir en la misma rama si falla
   alguno;
9. hacer merge únicamente con CI verde y riesgos aceptados;
10. verificar el commit resultante y la documentación en `main`;
11. eliminar la rama temporal en GitHub y localmente.

Por defecto no se mantienen varias ramas internas activas en paralelo. Una rama
temporal no es una versión del producto, no se despliega y no se conserva como
línea alternativa. Las versiones se identifican únicamente mediante tags y
releases inmutables sobre commits aceptados de `main`.

Los cambios Nivel 0 usan el mismo ciclo pero recorren una CI liviana. Pueden
agruparse cuando formen una unidad documental coherente; no requieren suites de
runtime ni `autoreview`.

## Puerta de alineación documental

La documentación forma parte de la unidad y debe quedar estabilizada antes de
`autoreview`, staging y commit. La revisión ocurre en dos momentos:

1. **Antes del commit:** releer las secciones aplicables después de estabilizar
   comportamiento y tests. Contrastar el diff con el estado objetivo de `main`,
   la release publicada y el tag realmente desplegado.
2. **Antes de marcar el PR como listo:** revisar el rango completo contra la
   base, completar la matriz documental del PR y buscar referencias transitorias
   o contradicciones que un diff archivo por archivo puede ocultar.

Matriz mínima por impacto:

| Impacto | Documentación que debe revisarse |
|---|---|
| Todo cambio funcional aceptado | `CHANGELOG.md > Unreleased`, `ROADMAP.md`, `docs/agents/current-status.md` y `docs/agents/manual-qa.md` |
| Estado de `main`, capacidades o próximo paso | `README.md`, `docs/agents/overview.md`, `ROADMAP.md` y `docs/agents/development-portfolio.md` |
| Pantallas o pasos visibles | `docs/user-guide/README.md` y manuales del flujo |
| Conducta de un endpoint o servicio | `docs/api/README.md` y documentación de dominio, aunque rutas, schemas y status HTTP no cambien |
| ARCA, CAE, numeración, lotes o reconciliación | diseño fiscal, `docs/agents/arca.md`, `docs/arca-ws/NOTAS.md` y matriz de QA |
| Tests, CI o evidencia de validación | `docs/agents/testing.md`, aunque los comandos de ejecución no cambien |
| Arquitectura o tooling | `docs/agents/overview.md`, `CONTRIBUTING.md` e índices aplicables |
| Release, despliegue o instalación | README, changelog, estado, manual, setup, dossier e índices de releases |
| Avance de una línea PF | `docs/agents/development-portfolio.md` y estado del documento de diseño |

No se exige editar todos esos archivos indiscriminadamente. Se exige revisarlos
y registrar en el PR cuáles cambiaron y por qué los restantes no aplican. Una
casilla genérica o la mera presencia del archivo en el diff no constituyen
evidencia.

Un contrato HTTP sin cambios no vuelve irrelevante la guía API si cambió la
semántica del endpoint. Del mismo modo, comandos de test estables no justifican
omitir `docs/agents/testing.md` cuando el PR agrega una matriz, nuevos conteos o
un checkpoint de CI. Si cambia qué contiene `main` o cuál es el siguiente paso,
`docs/agents/overview.md` debe revisarse aunque la arquitectura no cambie.

Los documentos canónicos incluidos en el PR describen cómo quedará `main` al
integrarse; no deben contener nombres de ramas temporales ni estados como
"implementación local" o "publicado para revisión". El cuerpo del PR conserva
el estado transitorio. Los hechos posteriores al merge —en especial una
publicación o despliegue— requieren un cierre documental explícito separado.

Todo cambio sobre un servicio o helper compartido debe revisar sus consumidores
reales, no solo el flujo sugerido por su nombre. La matriz documental y la de
tests deben incluir API, UI, worker, lotes, reintentos y reconciliación que usen
ese contrato.

## Evidencia mínima de una unidad

El pull request debe poder responder en lenguaje simple:

- **Resultado esperado:** qué conducta cambia y por qué.
- **Nivel y justificación:** 0, 1 o 2, con el riesgo concreto.
- **Autoridad funcional:** regla contable, fiscal u operativa que define lo
  correcto.
- **Invariantes preservadas:** qué nunca debe ocurrir.
- **Alcance excluido:** qué no se cambió.
- **Pruebas enfocadas:** casos felices, errores y bordes cubiertos.
- **Controles completos:** suites, lint, formato, tipos, build, E2E y seguridad
  que correspondan.
- **QA manual:** escenario y resultado, o motivo explícito por el cual no aplica.
- **Riesgo residual:** riesgo conocido que permanece y su tratamiento.
- **Recuperación:** rollback, reconciliación o procedimiento seguro si falla.

No se acepta como evidencia suficiente “la IA dijo que funciona”, “hay muchos
tests” o “compiló”. Cada evidencia debe vincularse con una conducta o riesgo.

## Checks obligatorios de GitHub

Los siete checks remotos del workflow de Nivel 2 deben terminar correctamente
y la protección remota debe verificarlos antes del merge:

- `Change Scope`;
- `Repository Checks`;
- `Backend Tests`;
- `Frontend Build`;
- `Runtime Smoke`;
- `E2E Tests`;
- `Security Audit`.

En Nivel 0 todos los checks se informan, pero los jobs de runtime omiten sus
tareas costosas. Si cambia cualquier archivo no documental, la matriz completa
se ejecuta. Esta regla describe la puerta requerida; no afirma que la CI de un
SHA concreto ya haya ocurrido.

Los checks decorativos que ignoran su código de salida no cuentan como puertas.
Ruff, Black, tests, build, auditorías y scripts deben fallar de forma visible
cuando detectan un problema.

## Alcance de la auditoría de dependencias

En cada cambio de runtime, `Security Audit` bloquea vulnerabilidades conocidas
de las dependencias que se instalan en producción. El árbol exclusivo de
compilación y tests también se revisa, pero sus migraciones mayores se realizan
en un corte técnico propio para no introducir incompatibilidades de forma
automática. Hasta completar ese corte, las herramientas de desarrollo no se
exponen como servicios públicos y sus alertas conocidas se registran como riesgo
residual; nunca se usa `--force` para silenciarlas.

## Puerta adicional de release

Una CI verde permite integrar una unidad, pero no convierte automáticamente el
commit en release. Una versión candidata destinada a producción o a terceros
debe completar además las puertas de `ROADMAP.md > PF-16`, el checklist fiscal
cuando corresponda, el dossier de release, backup/restauración, migraciones y QA
contable del rango completo.
