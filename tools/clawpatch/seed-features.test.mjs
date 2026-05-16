import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";
import { FEATURE_AREAS } from "./factuflow-features.mjs";
import { parseArgs, seedFeatures, validateAllFeatures } from "./seed-features.mjs";

test("manual feature map references files that exist in FactuFlow", async () => {
  const results = await validateAllFeatures(process.cwd());
  const invalid = results.filter((result) => !result.valid);

  assert.deepEqual(
    invalid.map((result) => ({
      area: result.area,
      featureId: result.featureId,
      warnings: result.warnings,
    })),
    [],
  );
});

test("parseArgs requires explicit area, root and state directory", () => {
  assert.deepEqual(
    parseArgs(["--area", "backend", "--root", "backend", "--state-dir", ".clawpatch/backend", "--dry-run"]),
    {
      area: "backend",
      root: "backend",
      stateDir: ".clawpatch/backend",
      dryRun: true,
      strict: false,
    },
  );

  assert.throws(() => parseArgs(["--area", "backend"]), /Missing --root/u);
  assert.throws(() => parseArgs(["--area", "unknown", "--root", ".", "--state-dir", ".clawpatch/repo"]), /Unknown area/u);
});

test("seedFeatures writes Clawpatch records and preserves existing finding state", async () => {
  const tmp = await mkdtemp(path.join(tmpdir(), "factuflow-clawpatch-test-"));
  try {
    await mkdir(path.join(tmp, "backend", "app", "api"), { recursive: true });
    await mkdir(path.join(tmp, ".clawpatch", "backend", "features"), { recursive: true });
    await writeFile(path.join(tmp, ".clawpatch", "backend", "project.json"), "{}\n", "utf8");

    for (const filePath of filesForArea("backend")) {
      const full = path.join(tmp, "backend", filePath);
      if (path.extname(full) === "") {
        await mkdir(full, { recursive: true });
      } else {
        await mkdir(path.dirname(full), { recursive: true });
        await writeFile(full, "# test fixture\n", "utf8");
      }
    }

    const existingPath = path.join(
      tmp,
      ".clawpatch",
      "backend",
      "features",
      "feat_factuflow_backend_facturacion_fiscal.json",
    );
    await writeFile(
      existingPath,
      `${JSON.stringify({
        schemaVersion: 1,
        featureId: "feat_factuflow_backend_facturacion_fiscal",
        title: "Backend fiscal issuance and CAE barrier",
        summary: "old summary",
        kind: "service",
        source: "factuflow-manual-feature-map",
        confidence: "high",
        entrypoints: [],
        ownedFiles: [],
        contextFiles: [],
        tests: [],
        tags: [],
        trustBoundaries: [],
        status: "reviewed",
        lock: null,
        findingIds: ["finding_1"],
        patchAttemptIds: ["patch_1"],
        analysisHistory: [{ runId: "run_1", kind: "review", summary: "done", provider: "codex", model: null, createdAt: "2026-05-16T00:00:00.000Z" }],
        createdAt: "2026-05-16T00:00:00.000Z",
        updatedAt: "2026-05-16T00:00:00.000Z",
      })}\n`,
      "utf8",
    );

    const result = await seedFeatures(
      {
        area: "backend",
        root: "backend",
        stateDir: ".clawpatch/backend",
        dryRun: false,
        strict: true,
      },
      tmp,
    );

    assert.equal(result.features, FEATURE_AREAS.backend.length);
    const updated = JSON.parse(await readFile(existingPath, "utf8"));
    assert.equal(updated.status, "pending");
    assert.deepEqual(updated.findingIds, ["finding_1"]);
    assert.deepEqual(updated.patchAttemptIds, ["patch_1"]);
    assert.equal(updated.createdAt, "2026-05-16T00:00:00.000Z");
    assert.equal(updated.ownedFiles.length > 0, true);
  } finally {
    await rm(tmp, { recursive: true, force: true });
  }
});

function filesForArea(area) {
  const files = new Set();
  for (const feature of FEATURE_AREAS[area]) {
    for (const ref of [...feature.entrypoints, ...feature.ownedFiles, ...feature.contextFiles, ...feature.tests]) {
      files.add(ref.path);
    }
  }
  return files;
}
