import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const WORKFLOW_URL = new URL("../../.github/workflows/ci.yml", import.meta.url);
const workflow = readFileSync(WORKFLOW_URL, "utf8").replaceAll("\r\n", "\n");

function extractJob(jobId) {
  const marker = `  ${jobId}:\n`;
  const start = workflow.indexOf(marker);
  assert.notEqual(start, -1, `No se encontró el job ${jobId}`);

  const contentStart = start + marker.length;
  const nextJobOffset = workflow
    .slice(contentStart)
    .search(/\n  [a-z0-9-]+:\n/u);
  const end =
    nextJobOffset === -1 ? workflow.length : contentStart + nextJobOffset;
  return workflow.slice(contentStart, end);
}

function extractSetupNode(jobId) {
  const job = extractJob(jobId);
  const marker = "        uses: actions/setup-node@v6\n";
  const start = job.indexOf(marker);
  assert.notEqual(start, -1, `No se encontró setup-node en ${jobId}`);

  const contentStart = start + marker.length;
  const nextStepOffset = job.slice(contentStart).search(/\n      - name:/u);
  const end =
    nextStepOffset === -1 ? job.length : contentStart + nextStepOffset;
  return job.slice(start, end);
}

test("configura explícitamente la caché de cada setup-node", () => {
  assert.equal(
    workflow.match(/uses: actions\/setup-node@v6/gu)?.length,
    6,
    "Todo setup-node nuevo debe incorporarse a este contrato",
  );

  for (const jobId of ["scope", "repository", "security"]) {
    const setup = extractSetupNode(jobId);
    assert.match(setup, /node-version: "24\.15\.0"/u, jobId);
    assert.match(setup, /package-manager-cache: false/u, jobId);
    assert.doesNotMatch(setup, /^\s+cache:\s/mu, jobId);
  }

  for (const jobId of ["frontend", "runtime-smoke", "e2e"]) {
    const setup = extractSetupNode(jobId);
    assert.match(setup, /^\s+cache: npm$/mu, jobId);
    assert.match(
      setup,
      /^\s+cache-dependency-path: frontend\/package-lock\.json$/mu,
      jobId,
    );
    assert.doesNotMatch(setup, /package-manager-cache: false/u, jobId);
  }

  assert.doesNotMatch(
    workflow,
    /cache-dependency-path:\s+(?:\.\/)?package-lock\.json/u,
    "La raíz no tiene lockfile de dependencias y no debe usarse como caché",
  );
});
