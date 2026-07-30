import assert from "node:assert/strict";
import test from "node:test";

import {
  isLiveDocumentationPath,
  normalizePath,
  validateDocumentation,
} from "./documentation-alignment.mjs";

function alignedFiles(overrides = {}) {
  return new Map(
    Object.entries({
      "README.md": [
        "# FactuFlow",
        "",
        "Versión publicada más reciente: `v0.3.0`",
        "",
        "Versión productiva vigente: `v0.2.2`",
      ].join("\n"),
      "CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n",
      "docs/agents/overview.md": [
        "# Resumen",
        "",
        "## Estado actual",
        "",
        "- Release productiva vigente: `v0.2.2`.",
      ].join("\n"),
      "docs/user-guide/README.md": [
        "# Manual de usuario",
        "",
        "Este manual describe `v0.2.2`, actualmente desplegada.",
        "",
        "## Contenido",
      ].join("\n"),
      ...overrides,
    }),
  );
}

test("normaliza rutas y excluye documentación histórica", () => {
  assert.equal(
    normalizePath(".\\docs\\agents\\current-status.md"),
    "docs/agents/current-status.md",
  );
  assert.equal(isLiveDocumentationPath("docs\\agents\\overview.md"), true);
  assert.equal(
    isLiveDocumentationPath("docs/project/releases/v0.2.2-candidate.md"),
    false,
  );
  assert.equal(
    isLiveDocumentationPath("docs/arca-ws/_extracted/manual.md"),
    false,
  );
});

test("acepta versiones alineadas y una release publicada aún no desplegada", () => {
  assert.deepEqual(validateDocumentation(alignedFiles()), []);
});

test("permite mencionar otra release si el manual etiqueta la productiva correcta", () => {
  const files = alignedFiles({
    "docs/user-guide/README.md": [
      "# Manual de usuario",
      "",
      "Versión productiva cubierta por este manual: `v0.2.2`.",
      "La versión publicada `v0.3.0` todavía no fue desplegada.",
      "",
      "## Contenido",
    ].join("\n"),
  });

  assert.deepEqual(validateDocumentation(files), []);
});

test("detecta divergencias de la versión productiva en overview y manual", () => {
  const files = alignedFiles({
    "docs/agents/overview.md": "- Release productiva vigente: `v0.2.1`.",
    "docs/user-guide/README.md": [
      "# Manual",
      "",
      "Este manual describe `v0.2.1`, actualmente desplegada.",
      "",
      "## Contenido",
    ].join("\n"),
  });

  const errors = validateDocumentation(files);
  assert.equal(errors.length, 2);
  assert.match(errors[0].message, /v0\.2\.1.*v0\.2\.2/u);
  assert.match(errors[1].message, /v0\.2\.1.*v0\.2\.2/u);
});

test("rechaza una versión productiva superior a la publicada", () => {
  const files = alignedFiles({
    "README.md": [
      "Versión publicada más reciente: `v0.2.1`",
      "Versión productiva vigente: `v0.2.2`",
    ].join("\n"),
  });

  assert.match(validateDocumentation(files)[0].message, /supera la publicada/u);
});

test("exige la sección Unreleased del changelog", () => {
  const errors = validateDocumentation(
    alignedFiles({ "CHANGELOG.md": "# Changelog\n\n## [0.2.2]\n" }),
  );

  assert.equal(errors.length, 1);
  assert.match(errors[0].message, /Unreleased/u);
});

test("detecta ramas y estados transitorios solo en documentación viva", () => {
  const files = alignedFiles({
    "docs/agents/current-status.md": [
      "## Implementación local en curso — PF-02B",
      "Rama `codex/pf-02b-numeracion-masiva`.",
    ].join("\n"),
    "docs/agents/design.md":
      "Estado: primer corte implementado y validado localmente.",
    "ROADMAP.md": "- [x] Primer corte local: núcleo batch.",
    "docs/project/history.md": [
      "Rama `codex/historica`.",
      "Estado: validado localmente.",
    ].join("\n"),
  });

  const errors = validateDocumentation(files);
  assert.deepEqual(
    errors.map(({ path, line }) => `${path}:${line}`),
    [
      "docs/agents/current-status.md:2",
      "docs/agents/current-status.md:1",
      "docs/agents/design.md:1",
      "ROADMAP.md:1",
    ],
  );
});

test("no confunde el prefijo de rama ni evidencia local estable con estados transitorios", () => {
  const files = alignedFiles({
    "docs/agents/process.md": [
      "Las ramas usan el prefijo `codex/`.",
      "La revisión histórica usó Codex/GPT-5.5.",
      "La validación local reproducible complementa CI.",
      "El componente fue validado localmente y luego desplegado en v0.2.2.",
    ].join("\n"),
  });

  assert.deepEqual(validateDocumentation(files), []);
});
