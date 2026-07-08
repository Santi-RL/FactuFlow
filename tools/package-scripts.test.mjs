import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const packageJson = JSON.parse(await readFile("package.json", "utf8"));
const { scripts } = packageJson;

test("root lint and test scripts cover backend and frontend", () => {
  assert.match(scripts.lint, /backend:lint/);
  assert.match(scripts.lint, /frontend:lint/);
  assert.match(scripts.lint, /frontend:type-check/);

  assert.match(scripts.test, /backend:test/);
  assert.match(scripts.test, /frontend:test/);
  assert.match(scripts.test, /test:scripts/);
});

test("backend-only format check is explicitly scoped", () => {
  assert.ok(!Object.hasOwn(scripts, "format"));
  assert.match(scripts["backend:format:check"], /black --check app tests/);
});

test("scoped frontend quality scripts delegate to frontend package", () => {
  assert.match(scripts["frontend:lint"], /npm --prefix frontend run lint:check/);
  assert.match(
    scripts["frontend:type-check"],
    /npm --prefix frontend run type-check/,
  );
  assert.match(scripts["frontend:test"], /npm --prefix frontend run test:unit/);
});
