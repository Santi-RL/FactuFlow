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
  const packageJson = JSON.parse(
    await readFile(new URL("../../package.json", import.meta.url), "utf8"),
  );

  for (const [name, command] of Object.entries(packageJson.scripts)) {
    if (name.startsWith("clawpatch:")) {
      assert.equal(
        command.includes("clawpatch@"),
        false,
        `${name} must not pin a Clawpatch package version`,
      );
    }

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
    assert.ok(
      command.includes(`--state-dir ${EXPECTED[area].stateDir}`),
      `${name} must pass the documented state dir`,
    );
    assert.ok(
      command.includes(`--config ${EXPECTED[area].config}`),
      `${name} must pass the documented config path`,
    );
  }
});

test("repo Clawpatch map runs native mapper before manual seeding", async () => {
  const packageJson = JSON.parse(
    await readFile(new URL("../../package.json", import.meta.url), "utf8"),
  );
  const scripts = packageJson.scripts;
  const repoMapScript = await readFile(
    new URL("map-repo-native.mjs", import.meta.url),
    "utf8",
  );

  assert.equal(
    scripts["clawpatch:repo:map:native"],
    "node tools/clawpatch/map-repo-native.mjs",
  );
  assert.equal(
    scripts["clawpatch:repo:map"],
    "npm run clawpatch:repo:map:native && npm run clawpatch:repo:seed",
  );
  assert.ok(
    scripts["clawpatch:map-all"].includes("npm run clawpatch:repo:map"),
    "map-all must invoke the full repo map chain",
  );
  assert.ok(
    repoMapScript.includes("git") && repoMapScript.includes("ls-files"),
    "repo native map must build a versionable snapshot",
  );
  assert.ok(
    repoMapScript.includes("run-clawpatch.mjs"),
    "repo native map must invoke the Clawpatch runner",
  );
  assert.ok(
    repoMapScript.includes("--skip-git-repo-check"),
    "repo native map snapshot must skip the git root check",
  );
  assert.ok(
    repoMapScript.includes("lstat") &&
      repoMapScript.includes("realpath") &&
      repoMapScript.includes("isSymbolicLink"),
    "repo native map must avoid copying symlink targets into the snapshot",
  );
  assert.ok(
    repoMapScript.includes("ENOENT"),
    "repo native map must skip tracked files deleted from the worktree",
  );
  assert.ok(
    repoMapScript.includes('child.on("close"'),
    "repo native map must wait for child stdio to close",
  );
});
