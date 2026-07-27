# Puertas de calidad y evidencia de cambios

Última actualización: 2026-07-27

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
4. publicar la rama y abrir un pull request hacia `main`;
5. esperar todos los checks obligatorios;
6. corregir en la misma rama si algún control falla;
7. hacer merge únicamente con CI verde y riesgos aceptados;
8. verificar el commit resultante en `main`;
9. eliminar la rama temporal en GitHub y localmente.

Por defecto no se mantienen varias ramas internas activas en paralelo. Una rama
temporal no es una versión del producto, no se despliega y no se conserva como
línea alternativa. Las versiones se identifican únicamente mediante tags y
releases inmutables sobre commits aceptados de `main`.

Los cambios Nivel 0 usan el mismo ciclo pero recorren una CI liviana. Pueden
agruparse cuando formen una unidad documental coherente; no requieren suites de
runtime ni `autoreview`.

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

Los siguientes jobs deben terminar correctamente antes del merge:

- `Change Scope`;
- `Repository Checks`;
- `Backend Tests`;
- `Frontend Build`;
- `E2E Tests`;
- `Security Audit`.

En Nivel 0 todos los jobs se informan y terminan correctamente, pero los cinco
jobs de runtime omiten sus tareas costosas. Si cambia cualquier archivo no
documental, la matriz completa se ejecuta.

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
