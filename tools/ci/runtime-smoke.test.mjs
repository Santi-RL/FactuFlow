import assert from "node:assert/strict";
import { isAbsolute, resolve } from "node:path";
import test from "node:test";

import {
  assertAlembicAtHeads,
  assertFrontendMountHtml,
  assertHealthyResponse,
  buildNpmInvocation,
  buildSpawnOptions,
  buildRuntimeEnvironment,
  buildVitePreviewInvocation,
  cleanupProcesses,
  createLogCapture,
  resolveBackendPython,
  resolveNpmCommand,
  sanitizeLog,
  stopProcess,
} from "./runtime-smoke.mjs";

test("prefiere el Python del entorno virtual del backend", () => {
  const backendDirectory = resolve("fixtures", "backend");
  const windowsPython = resolve(backendDirectory, ".venv/Scripts/python.exe");

  assert.equal(
    resolveBackendPython(backendDirectory, {
      platform: "win32",
      pathExists: (path) => path === windowsPython,
    }),
    windowsPython,
  );
  assert.equal(
    resolveBackendPython(backendDirectory, {
      platform: "linux",
      pathExists: () => false,
    }),
    "python",
  );
});

test("elige un launcher npm portable sin shell", () => {
  assert.equal(resolveNpmCommand("win32"), "npm.cmd");
  assert.equal(resolveNpmCommand("linux"), "npm");
  assert.equal(resolveNpmCommand("darwin"), "npm");
  assert.deepEqual(
    buildNpmInvocation(["run", "build"], {
      platform: "win32",
      environment: { COMSPEC: "C:\\Windows\\System32\\cmd.exe" },
    }),
    {
      command: "C:\\Windows\\System32\\cmd.exe",
      args: ["/d", "/s", "/c", "npm.cmd", "run", "build"],
    },
  );
  assert.deepEqual(
    buildNpmInvocation(["run", "build"], {
      platform: "linux",
      environment: {},
    }),
    { command: "npm", args: ["run", "build"] },
  );
  assert.equal(buildSpawnOptions("cwd", { PATH: "path" }).shell, false);
});

test("construye el preview Vite directo con una ruta absoluta portable", () => {
  const frontendDirectory = resolve("fixtures", "frontend");
  const invocation = buildVitePreviewInvocation(
    frontendDirectory,
    "C:\\runtime\\node.exe",
  );

  assert.equal(invocation.command, "C:\\runtime\\node.exe");
  assert.equal(invocation.args[0], resolve(frontendDirectory, "node_modules/vite/bin/vite.js"));
  assert.equal(isAbsolute(invocation.args[0]), true);
  assert.deepEqual(invocation.args.slice(1), [
    "preview",
    "--host",
    "127.0.0.1",
    "--port",
    "18080",
    "--strictPort",
  ]);
});

test("fija un entorno CI sintético mediante una allowlist mínima", () => {
  const environment = buildRuntimeEnvironment({
    Path: "system-path",
    HOME: "/home/runner",
    TEMP: "/tmp",
    KEEP: "must-not-pass",
    APP_ENV: "production",
    ARCA_TOKEN: "must-not-pass",
    NODE_OPTIONS: "--require injected.js",
  });

  assert.equal(environment.PATH, "system-path");
  assert.equal(environment.HOME, "/home/runner");
  assert.equal(environment.TEMP, "/tmp");
  assert.equal(environment.KEEP, undefined);
  assert.equal(environment.ARCA_TOKEN, undefined);
  assert.equal(environment.NODE_OPTIONS, undefined);
  assert.equal(environment.APP_ENV, "ci");
  assert.equal(environment.APP_DEBUG, "false");
  assert.equal(environment.CORS_ORIGINS, "http://127.0.0.1:18080");
  assert.equal(environment.ARCA_ENV, "homologacion");
  assert.equal(environment.BATCH_WORKER_ENABLED, "false");
  assert.equal(environment.ARCA_FECAESOLICITAR_BATCH_ENABLED, "false");
  assert.ok(environment.APP_SECRET_KEY.length >= 32);
  assert.match(environment.DATABASE_URL, /127\.0\.0\.1:5432\/factuflow_integration_test/);
});

test("sanea claves, argumentos y valores sensibles de la cola de logs", () => {
  const logs = createLogCapture(2_000, ["standalone-sensitive-value"]);
  logs.append(
    "api",
    [
      "DATABASE_URL=postgresql+asyncpg://user:very-secret@127.0.0.1/db",
      '"ARCA_TOKEN": "arca-value"',
      "JWT_SECRET='jwt-value'",
      "THIRD_PARTY_API_KEY=api-value",
      "PRIVATE_KEY_PASSWORD=password-value",
      "CERTS_PATH=C:/private/certs",
      "--api-key cli-value",
      "standalone-sensitive-value",
    ].join(" "),
  );

  assert.doesNotMatch(
    logs.tail(),
    /very-secret|arca-value|jwt-value|api-value|password-value|private\/certs|cli-value|standalone-sensitive-value/,
  );
  assert.match(logs.tail(), /\[redacted\]/);
  assert.doesNotMatch(
    sanitizeLog("POSTGRES_PASSWORD=secret-value"),
    /secret-value/,
  );
});

test("stopProcess escala de SIGTERM a SIGKILL sin procesos reales", async () => {
  const signals = [];
  const child = {
    exitCode: null,
    signalCode: null,
    kill(signal) {
      signals.push(signal);
    },
  };
  const waitResults = [false, true];

  await stopProcess(
    { child, label: "fake" },
    {
      timeoutMs: 0,
      waitForExitImpl: async () => waitResults.shift(),
    },
  );

  assert.deepEqual(signals, ["SIGTERM", "SIGKILL"]);
});

test("cleanup apaga todos los servicios en el orden solicitado", async () => {
  const stopped = [];
  const frontend = { label: "frontend" };
  const api = { label: "api" };

  await cleanupProcesses(
    [frontend, undefined, api],
    async (processInfo) => stopped.push(processInfo?.label ?? "empty"),
  );

  assert.deepEqual(stopped, ["frontend", "empty", "api"]);
});

test("exige que Alembic current sea exactamente igual a heads", () => {
  assert.doesNotThrow(() =>
    assertAlembicAtHeads("abc123 (head)\n", "abc123 (head)\n"),
  );
  assert.throws(
    () => assertAlembicAtHeads("old000 (head)\n", "new000 (head)\n"),
    /no coincide/,
  );
});

test("valida salud HTTP y el HTML compilado de Vite", () => {
  assert.doesNotThrow(() =>
    assertHealthyResponse({ ok: true, status: 200 }, { status: "healthy" }, "/api/health"),
  );
  assert.throws(
    () => assertHealthyResponse({ ok: false, status: 503 }, { status: "degraded" }, "/api/health/db"),
    /healthy/,
  );
  assert.doesNotThrow(() =>
    assertFrontendMountHtml(
      '<div id="app"></div><script type="module" src="/assets/index-abc.js"></script>',
    ),
  );
  assert.throws(() => assertFrontendMountHtml('<div id="app"></div>'), /módulo/);
});
