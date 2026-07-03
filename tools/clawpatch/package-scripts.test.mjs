import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const EXPECTED = {
  backend: {
    stateDir: "../.clawpatch/backend",
    config: "../.clawpatch/backend/config.json",
  },
  frontend: {
    stateDir: "../.clawpatch/frontend",
    config: "../.clawpatch/frontend/config.json",
  },
  repo: {
    stateDir: ".clawpatch/repo",
    config: ".clawpatch/repo/config.json",
  },
};

test("package Clawpatch scripts pass documented state and config paths", async () => {
  const packageJson = JSON.parse(await readFile(new URL("../../package.json", import.meta.url), "utf8"));

  for (const [name, command] of Object.entries(packageJson.scripts)) {
    if (!command.includes("tools/clawpatch/run-clawpatch.mjs")) {
      continue;
    }

    const area = name.includes(":backend:")
      ? "backend"
      : name.includes(":frontend:")
        ? "frontend"
        : name.includes(":repo:")
          ? "repo"
          : null;

    assert.notEqual(area, null, `${name} must identify a Clawpatch area`);
    assert.equal(command.includes("clawpatch@"), false, `${name} must not pin a Clawpatch package version`);
    assert.ok(command.includes(`--state-dir ${EXPECTED[area].stateDir}`), `${name} must pass the documented state dir`);
    assert.ok(command.includes(`--config ${EXPECTED[area].config}`), `${name} must pass the documented config path`);
  }
});
