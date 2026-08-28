import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const PRODUCT_VERSION = "0.3.1";

async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

test("alinea los productores técnicos y visibles de la versión candidata", async () => {
  const [rootPackage, frontendPackage, frontendLock, backendPackage, pyproject, appInit, config, sidebar] =
    await Promise.all([
      readJson("package.json"),
      readJson("frontend/package.json"),
      readJson("frontend/package-lock.json"),
      readJson("backend/package.json"),
      readFile("backend/pyproject.toml", "utf8"),
      readFile("backend/app/__init__.py", "utf8"),
      readFile("backend/app/core/config.py", "utf8"),
      readFile("frontend/src/components/layout/Sidebar.vue", "utf8"),
    ]);

  assert.equal(rootPackage.version, PRODUCT_VERSION);
  assert.equal(frontendPackage.version, PRODUCT_VERSION);
  assert.equal(frontendLock.version, PRODUCT_VERSION);
  assert.equal(frontendLock.packages[""].version, PRODUCT_VERSION);
  assert.equal(backendPackage.version, PRODUCT_VERSION);
  assert.match(pyproject, /^version = "0\.3\.1"$/mu);
  assert.match(appInit, /^__version__ = "0\.3\.1"$/mu);
  assert.match(config, /^    app_version: str = "0\.3\.1"$/mu);
  assert.match(sidebar, /FactuFlow v0\.3\.1/u);
});
