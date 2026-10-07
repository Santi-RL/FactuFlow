import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  realpathSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontend = fileURLToPath(new URL("../", import.meta.url));
const configPath = join(frontend, "vite.config.ts");
const temporaryRoot = join(frontend, ".tmp");
const cliPath = join(frontend, "node_modules/vitest/vitest.mjs");
const metrics = { statements: 56, branches: 50, functions: 43, lines: 57 };

function runCoverageFixture(covered) {
  mkdirSync(temporaryRoot, { recursive: true });
  const directory = mkdtempSync(join(temporaryRoot, "coverage-gate-"));
  const configBefore = readFileSync(configPath, "utf8");
  try {
    const configImport = relative(directory, configPath).split(sep).join("/");
    writeFileSync(
      join(directory, "vitest.config.ts"),
      `import config from ${JSON.stringify(configImport)};
export default {
  ...config,
  test: {
    ...config.test,
    environment: 'node',
    include: ['fixture.test.ts'],
    exclude: [],
    coverage: {
      ...config.test.coverage,
      include: ['fixture*.ts'],
      exclude: ['**/*.test.ts'],
      reporter: ['json-summary'],
      reportsDirectory: './coverage',
    },
  },
};
`,
    );
    writeFileSync(
      join(directory, "fixture.ts"),
      `export function label(active: boolean) {
  if (active) {
    return 'active';
  }
  return 'inactive';
}
`,
    );
    writeFileSync(
      join(directory, "fixture.test.ts"),
      covered
        ? `import { expect, test } from 'vitest';
import { label } from './fixture';
test('synthetic branches', () => {
  expect(label(true)).toBe('active');
  expect(label(false)).toBe('inactive');
});
`
        : `import { expect, test } from 'vitest';
test('synthetic test without source coverage', () => expect(true).toBe(true));
`,
    );

    const result = spawnSync(
      process.execPath,
      [cliPath, "run", "--root", directory, "--config", "vitest.config.ts", "--coverage"],
      { cwd: directory, encoding: "utf8", timeout: 60_000 },
    );
    assert.ifError(result.error);
    assert.equal(result.signal, null);
    assert.equal(readFileSync(configPath, "utf8"), configBefore);
    const report = JSON.parse(
      readFileSync(join(directory, "coverage/coverage-summary.json"), "utf8"),
    );
    return { ...result, report };
  } finally {
    assert.equal(dirname(realpathSync(directory)), realpathSync(temporaryRoot));
    rmSync(directory, { recursive: true });
  }
}

test("la puerta real rechaza cobertura insuficiente en las cuatro métricas", () => {
  const result = runCoverageFixture(false);
  const output = `${result.stdout}\n${result.stderr}`;
  assert.equal(result.status, 1, output);
  for (const [metric, threshold] of Object.entries(metrics)) {
    assert.equal(result.report.total[metric].pct, 0, metric);
    assert.ok(
      output.includes(`Coverage for ${metric} (0%) does not meet global threshold (${threshold}%)`),
      output,
    );
  }
});

test("la puerta real acepta cobertura suficiente sin modificar la configuración", () => {
  const result = runCoverageFixture(true);
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  for (const metric of Object.keys(metrics)) {
    assert.equal(result.report.total[metric].pct, 100, metric);
  }
});
