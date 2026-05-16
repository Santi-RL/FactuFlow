#!/usr/bin/env node
import { mkdir, readFile, realpath, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FEATURE_AREAS } from "./factuflow-features.mjs";

const VALID_KINDS = new Set([
  "cli-command",
  "route",
  "ui-flow",
  "service",
  "job",
  "agent-tool",
  "library",
  "config",
  "release",
  "test-suite",
  "infra",
  "unknown",
]);

const VALID_CONFIDENCE = new Set(["high", "medium", "low"]);
const VALID_TRUST_BOUNDARIES = new Set([
  "user-input",
  "network",
  "filesystem",
  "secrets",
  "process-exec",
  "database",
  "auth",
  "permissions",
  "concurrency",
  "external-api",
  "serialization",
]);

const RESET_STATUSES = new Set(["reviewed", "revalidated", "fixed", "skipped"]);

export function parseArgs(argv) {
  const options = {
    area: null,
    root: null,
    stateDir: null,
    dryRun: false,
    strict: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--dry-run") {
      options.dryRun = true;
    } else if (arg === "--strict") {
      options.strict = true;
    } else if (arg === "--area" || arg === "--root" || arg === "--state-dir") {
      const value = argv[index + 1];
      if (!value || value.startsWith("--")) {
        throw new Error(`Missing value for ${arg}`);
      }
      options[toCamel(arg.slice(2))] = value;
      index += 1;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (!options.area) {
    throw new Error("Missing --area");
  }
  if (!options.root) {
    throw new Error("Missing --root");
  }
  if (!options.stateDir) {
    throw new Error("Missing --state-dir");
  }
  if (!FEATURE_AREAS[options.area]) {
    throw new Error(`Unknown area '${options.area}'. Expected one of: ${Object.keys(FEATURE_AREAS).join(", ")}`);
  }

  return options;
}

export async function seedFeatures(options, cwd = process.cwd()) {
  const root = path.resolve(cwd, options.root);
  const stateDir = path.resolve(cwd, options.stateDir);
  const featuresDir = path.join(stateDir, "features");
  const projectPath = path.join(stateDir, "project.json");
  const now = new Date().toISOString();
  const seeded = [];
  const warnings = [];

  assertInside(cwd, root, "root");
  assertInside(cwd, stateDir, "state-dir");

  if (!existsSync(projectPath)) {
    throw new Error(`Clawpatch state not initialized for ${options.area}: ${projectPath}`);
  }

  await mkdir(featuresDir, { recursive: true });

  for (const definition of FEATURE_AREAS[options.area]) {
    const validation = await validateDefinition(definition, root);
    warnings.push(...validation.warnings);
    if (options.strict && validation.warnings.length > 0) {
      throw new Error(`Invalid feature ${definition.id}: ${validation.warnings.join("; ")}`);
    }

    const target = path.join(featuresDir, `${definition.id}.json`);
    const previous = await readJsonIfExists(target);
    const record = buildFeatureRecord(definition, previous, now);
    const changed = previous !== null && hasMeaningfulChanges(previous, record);

    if (changed && RESET_STATUSES.has(record.status)) {
      record.status = "pending";
    }
    if (record.status === "skipped") {
      record.status = "pending";
    }

    if (!options.dryRun) {
      await writeFile(target, `${JSON.stringify(record, null, 2)}\n`, "utf8");
    }

    seeded.push({
      featureId: record.featureId,
      title: record.title,
      status: record.status,
      changed,
    });
  }

  return {
    area: options.area,
    root,
    stateDir,
    features: seeded.length,
    seeded,
    warnings,
    dryRun: options.dryRun,
  };
}

export async function validateAllFeatures(cwd = process.cwd()) {
  const results = [];
  for (const [area, definitions] of Object.entries(FEATURE_AREAS)) {
    const root = path.resolve(cwd, area === "repo" ? "." : area);
    for (const definition of definitions) {
      results.push({
        area,
        featureId: definition.id,
        ...(await validateDefinition(definition, root)),
      });
    }
  }
  return results;
}

function buildFeatureRecord(definition, previous, now) {
  return {
    schemaVersion: 1,
    featureId: definition.id,
    title: definition.title,
    summary: definition.summary,
    kind: definition.kind,
    source: "factuflow-manual-feature-map",
    confidence: definition.confidence ?? "high",
    entrypoints: definition.entrypoints,
    ownedFiles: definition.ownedFiles,
    contextFiles: definition.contextFiles,
    tests: definition.tests,
    tags: definition.tags,
    trustBoundaries: definition.trustBoundaries,
    status: previous?.status ?? "pending",
    lock: previous?.lock ?? null,
    findingIds: previous?.findingIds ?? [],
    patchAttemptIds: previous?.patchAttemptIds ?? [],
    analysisHistory: previous?.analysisHistory ?? [],
    createdAt: previous?.createdAt ?? now,
    updatedAt: now,
  };
}

async function validateDefinition(definition, root) {
  const warnings = [];
  const seenFiles = [
    ...definition.entrypoints.map((item) => item.path),
    ...definition.ownedFiles.map((item) => item.path),
    ...definition.contextFiles.map((item) => item.path),
    ...definition.tests.map((item) => item.path),
  ];

  if (!definition.id.startsWith("feat_factuflow_")) {
    warnings.push("feature id must start with feat_factuflow_");
  }
  if (!VALID_KINDS.has(definition.kind)) {
    warnings.push(`invalid kind: ${definition.kind}`);
  }
  if (!VALID_CONFIDENCE.has(definition.confidence ?? "high")) {
    warnings.push(`invalid confidence: ${definition.confidence}`);
  }
  for (const boundary of definition.trustBoundaries) {
    if (!VALID_TRUST_BOUNDARIES.has(boundary)) {
      warnings.push(`invalid trust boundary: ${boundary}`);
    }
  }

  for (const filePath of new Set(seenFiles)) {
    const full = path.resolve(root, filePath);
    if (!isInside(root, full)) {
      warnings.push(`path escapes area root: ${filePath}`);
      continue;
    }
    if (!existsSync(full)) {
      warnings.push(`missing file: ${filePath}`);
      continue;
    }
    const realRoot = await realpath(root).catch(() => root);
    const realFull = await realpath(full).catch(() => full);
    if (!isInside(realRoot, realFull)) {
      warnings.push(`real path escapes area root: ${filePath}`);
    }
  }

  return { valid: warnings.length === 0, warnings };
}

function hasMeaningfulChanges(previous, next) {
  return JSON.stringify(stripVolatile(previous)) !== JSON.stringify(stripVolatile(next));
}

function stripVolatile(feature) {
  const {
    createdAt: _createdAt,
    updatedAt: _updatedAt,
    lock: _lock,
    analysisHistory: _analysisHistory,
    findingIds: _findingIds,
    patchAttemptIds: _patchAttemptIds,
    status: _status,
    ...stable
  } = feature;
  return stable;
}

async function readJsonIfExists(filePath) {
  if (!existsSync(filePath)) {
    return null;
  }
  return JSON.parse(await readFile(filePath, "utf8"));
}

function assertInside(root, candidate, label) {
  if (!isInside(path.resolve(root), path.resolve(candidate))) {
    throw new Error(`${label} must stay inside repository root: ${candidate}`);
  }
}

function isInside(root, candidate) {
  const relative = path.relative(root, candidate);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

function toCamel(value) {
  return value.replace(/-([a-z])/gu, (_, letter) => letter.toUpperCase());
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  try {
    const options = parseArgs(process.argv.slice(2));
    const result = await seedFeatures(options);
    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
