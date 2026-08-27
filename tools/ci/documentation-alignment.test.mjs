import assert from "node:assert/strict";
import test from "node:test";

import {
  isLiveDocumentationPath,
  normalizePath,
  validateDocumentation,
} from "./documentation-alignment.mjs";

const DEPLOYMENT_AUTHORITY =
  "El estado desplegado autoritativo vive en el plano de control `VPS Hostinger` / `vps-admin`.";

function alignedFiles(overrides = {}) {
  return new Map(
    Object.entries({
      "README.md": [
        "# FactuFlow",
        "",
        "Versión publicada más reciente: `v0.3.0`",
        "",
        DEPLOYMENT_AUTHORITY,
      ].join("\n"),
      "CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n",
      "docs/README.md": `# Documentación\n\n${DEPLOYMENT_AUTHORITY}\n`,
      "docs/agents/current-status.md":
        `# Estado actual\n\n${DEPLOYMENT_AUTHORITY}\n`,
      "docs/agents/overview.md": [
        "# Resumen",
        "",
        "## Estado actual",
        "",
        DEPLOYMENT_AUTHORITY,
      ].join("\n"),
      "docs/user-guide/README.md": [
        "# Manual de usuario",
        "",
        DEPLOYMENT_AUTHORITY,
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

test("acepta una release publicada sin fijar una versión productiva", () => {
  assert.deepEqual(validateDocumentation(alignedFiles()), []);
});

test("permite conservar referencias históricas sin volverlas estado desplegado", () => {
  const files = alignedFiles({
    "docs/user-guide/README.md": [
      "# Manual de usuario",
      "",
      DEPLOYMENT_AUTHORITY,
      "La versión `v0.2.2` tuvo un despliegue histórico documentado.",
      "",
      "## Contenido",
    ].join("\n"),
  });

  assert.deepEqual(validateDocumentation(files), []);
});

test("exige el puntero autoritativo en cada documento operativo", () => {
  const paths = [
    "README.md",
    "docs/README.md",
    "docs/agents/current-status.md",
    "docs/agents/overview.md",
    "docs/user-guide/README.md",
  ];

  for (const path of paths) {
    const content = alignedFiles().get(path).replace(
      DEPLOYMENT_AUTHORITY,
      "Sin puntero operativo.",
    );
    const errors = validateDocumentation(alignedFiles({ [path]: content }));

    assert.equal(errors.length, 1);
    assert.equal(errors[0].path, path);
    assert.match(errors[0].message, /VPS Hostinger.*vps-admin/u);
  }
});

test("sigue exigiendo la versión publicada", () => {
  const files = alignedFiles({
    "README.md": `# FactuFlow\n\n${DEPLOYMENT_AUTHORITY}\n`,
  });

  assert.match(
    validateDocumentation(files)[0].message,
    /Versión publicada más reciente/u,
  );
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
      DEPLOYMENT_AUTHORITY,
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
