## Resultado esperado

<!-- Explicar la conducta en lenguaje funcional o contable. -->

## Nivel de riesgo

- [ ] Nivel 0 — editorial o visual aislado
- [ ] Nivel 1 — funcional no crítico
- [ ] Nivel 2 — sensible o fiscal crítico

**Justificación del nivel:**

## Autoridad funcional e invariantes

- Regla contable, fiscal u operativa:
- Conductas que nunca deben ocurrir:
- Alcance expresamente excluido:

## Evidencia

- Pruebas enfocadas:
- Suites y controles completos:
- QA manual:
- CI:

## Alineación documental

<!--
Completar cada fila con archivos concretos o "No aplica" y una justificación.
La documentación debe describir el estado objetivo de main, no la rama actual.
-->

| Área revisada | Archivos actualizados o motivo de `No aplica` |
|---|---|
| Estado, roadmap y portafolio | |
| `CHANGELOG.md > Unreleased` | |
| README y manual de usuario | |
| QA, testing y diseño del corte | |
| ARCA/API, si corresponde | |
| Versión publicada, producción, setup y releases | |
| Índices y fechas/estados documentales | |

- [ ] Releí las secciones afectadas completas; no solo confirmé que el archivo
      aparezca en el diff.
- [ ] Diferencié código en `main`, release publicada y versión desplegada.
- [ ] No quedan nombres de ramas temporales ni estados efímeros en documentos
      canónicos.
- [ ] Revisé todos los consumidores de servicios o contratos compartidos.

## Seguridad y privacidad

- [ ] Revisé que no haya secretos, datos privados, CUITs, CAEs, certificados,
      bases, logs, capturas ni archivos de clientes.
- [ ] El cambio no solicita CAE real durante tests o QA automatizada.
- [ ] Completé el checklist fiscal o de seguridad cuando corresponde.

## Riesgo residual y recuperación

- Riesgo conocido que permanece:
- Rollback, reconciliación o recuperación:

## Cierre

- [ ] El diff mantiene una única unidad lógica.
- [ ] La matriz documental quedó completa antes de marcar el PR como listo.
- [ ] Todos los checks obligatorios están verdes.
- [ ] Los hallazgos fueron aceptados, rechazados o diferidos explícitamente.
- [ ] Después del merge se verificará `main`, incluida la documentación, antes
      de eliminar la rama temporal local y remota.
