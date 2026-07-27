import assert from "node:assert/strict";
import test from "node:test";

import {
  classifyChangedPaths,
  isLevelZeroPath,
  normalizePath,
} from "./change-scope.mjs";

test("normaliza rutas de Windows y prefijos relativos", () => {
  assert.equal(normalizePath(".\\docs\\agents\\testing.md"), "docs/agents/testing.md");
});

test("clasifica Markdown y .gitignore como Nivel 0", () => {
  assert.equal(isLevelZeroPath("README.md"), true);
  assert.equal(isLevelZeroPath("docs/Guía de uso.MD"), true);
  assert.equal(isLevelZeroPath(".gitignore"), true);
  assert.deepEqual(classifyChangedPaths(["README.md", "docs/agents/testing.md"]), {
    changedCount: 2,
    level0: true,
    runtime: false,
  });
});

test("activa la matriz completa ante código o configuración", () => {
  for (const path of [
    "backend/app/main.py",
    "frontend/src/main.ts",
    ".github/workflows/ci.yml",
    "package-lock.json",
    "docs/diagrama.png",
  ]) {
    assert.equal(classifyChangedPaths(["README.md", path]).runtime, true, path);
  }
});

test("usa una clasificación conservadora cuando no recibe archivos", () => {
  assert.deepEqual(classifyChangedPaths([]), {
    changedCount: 0,
    level0: false,
    runtime: true,
  });
});