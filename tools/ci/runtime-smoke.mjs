import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const DATABASE_URL =
  "postgresql+asyncpg://factuflow_test:synthetic_test_password@127.0.0.1:5432/factuflow_integration_test";
const API_URL = "http://127.0.0.1:18000";
const FRONTEND_URL = "http://127.0.0.1:18080";
const RETRY_DELAY_MS = 500;
const SERVICE_TIMEOUT_MS = 30_000;
const PROCESS_STOP_TIMEOUT_MS = 5_000;
const LOG_TAIL_LENGTH = 12_000;
const SYSTEM_ENVIRONMENT_KEYS = [
  "PATH",
  "PATHEXT",
  "SYSTEMROOT",
  "WINDIR",
  "COMSPEC",
  "HOME",
  "USERPROFILE",
  "APPDATA",
  "LOCALAPPDATA",
  "TEMP",
  "TMP",
  "TMPDIR",
  "LANG",
  "LC_ALL",
  "CI",
];
const SENSITIVE_KEY_FRAGMENT =
  "[A-Z0-9_.-]*(?:ARCA|JWT|TOKEN|API[_-]?KEY|PASSWORD|SECRET|CERT(?:S|IFICATE)?|PRIVATE[_-]?KEY)[A-Z0-9_.-]*";
const SENSITIVE_ASSIGNMENT_PATTERN = new RegExp(
  `(["']?${SENSITIVE_KEY_FRAGMENT}["']?\\s*(?:=|:)\\s*)(?:"[^"\\r\\n]*"|'[^'\\r\\n]*'|[^\\s,;&\\]}]+)`,
  "giu",
);
const SENSITIVE_ARGUMENT_PATTERN = new RegExp(
  `(--${SENSITIVE_KEY_FRAGMENT.toLowerCase()}\\s+)(?:"[^"]*"|'[^']*'|[^\\s]+)`,
  "giu",
);

/** Devuelve el ejecutable npm portable sin habilitar un shell para el proceso. */
export function resolveNpmCommand(platform = process.platform) {
  return platform === "win32" ? "npm.cmd" : "npm";
}

/** Usa el entorno virtual del backend cuando está disponible. */
export function resolveBackendPython(
  backendDirectory,
  { platform = process.platform, pathExists = existsSync } = {},
) {
  const virtualenvPython = resolve(
    backendDirectory,
    platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python",
  );
  return pathExists(virtualenvPython) ? virtualenvPython : "python";
}

/** Construye la invocación npm sin activar `shell:true`. */
export function buildNpmInvocation(
  args,
  { platform = process.platform, environment = process.env } = {},
) {
  const npmCommand = resolveNpmCommand(platform);
  if (platform !== "win32") {
    return { command: npmCommand, args };
  }
  return {
    command: environment.COMSPEC || "cmd.exe",
    args: ["/d", "/s", "/c", npmCommand, ...args],
  };
}

/** Construye el preview directo de Vite mediante el Node actual. */
export function buildVitePreviewInvocation(
  frontendDirectory,
  nodeExecutable = process.execPath,
) {
  return {
    command: nodeExecutable,
    args: [
      resolve(frontendDirectory, "node_modules/vite/bin/vite.js"),
      "preview",
      "--host",
      "127.0.0.1",
      "--port",
      "18080",
      "--strictPort",
    ],
  };
}

/** Define un spawn directo, con pipes acotados y sin interpretación de shell. */
export function buildSpawnOptions(cwd, env) {
  return {
    cwd,
    env,
    shell: false,
    stdio: ["ignore", "pipe", "pipe"],
  };
}

function pickSystemEnvironment(baseEnvironment) {
  const entries = new Map(
    Object.entries(baseEnvironment).map(([key, value]) => [
      key.toUpperCase(),
      value,
    ]),
  );
  return Object.fromEntries(
    SYSTEM_ENVIRONMENT_KEYS.flatMap((key) => {
      const value = entries.get(key);
      return value === undefined ? [] : [[key, value]];
    }),
  );
}

/** Construye el entorno aislado y sin capacidades fiscales para el smoke. */
export function buildRuntimeEnvironment(baseEnvironment = process.env) {
  return {
    ...pickSystemEnvironment(baseEnvironment),
    DATABASE_URL,
    APP_ENV: "ci",
    APP_DEBUG: "false",
    APP_SECRET_KEY: "runtime-smoke-ci-secret-key-0123456789abcdef",
    CORS_ORIGINS: FRONTEND_URL,
    ARCA_ENV: "homologacion",
    BATCH_WORKER_ENABLED: "false",
    ARCA_FECAESOLICITAR_BATCH_ENABLED: "false",
  };
}

function collectSensitiveValues(environment) {
  return Object.entries(environment)
    .filter(
      ([key, value]) =>
        (key === "DATABASE_URL" || new RegExp(`^${SENSITIVE_KEY_FRAGMENT}$`, "iu").test(key)) &&
        typeof value === "string" &&
        value.length >= 6,
    )
    .map(([, value]) => value)
    .sort((left, right) => right.length - left.length);
}

/** Oculta credenciales y secretos antes de publicar evidencia de un fallo. */
export function sanitizeLog(value, sensitiveValues = []) {
  let sanitized = String(value);
  for (const sensitiveValue of sensitiveValues) {
    sanitized = sanitized.split(sensitiveValue).join("[redacted]");
  }
  return sanitized
    .replace(
      /\b([a-z][a-z0-9+.-]*:\/\/)[^\s/@]+:[^\s/@]+@/giu,
      "$1[redacted]@",
    )
    .replace(SENSITIVE_ASSIGNMENT_PATTERN, "$1[redacted]")
    .replace(SENSITIVE_ARGUMENT_PATTERN, "$1[redacted]");
}

/** Conserva solo una cola acotada de logs para diagnóstico tras un fallo. */
export function createLogCapture(
  maxLength = LOG_TAIL_LENGTH,
  sensitiveValues = [],
) {
  let content = "";

  return {
    append(label, chunk) {
      content += `[${label}] ${chunk.toString()}`;
      if (content.length > maxLength) {
        content = content.slice(-maxLength);
      }
    },
    tail() {
      return sanitizeLog(content, sensitiveValues);
    },
  };
}

/** Extrae revisiones que Alembic marca explícitamente como head. */
export function extractAlembicHeadRevisions(output) {
  return new Set(
    [...output.matchAll(/^\s*([a-z0-9]+)\s+\(head\)\s*$/gimu)].map(
      (match) => match[1],
    ),
  );
}

/** Verifica que la base migrada y el árbol de Alembic compartan exactamente heads. */
export function assertAlembicAtHeads(currentOutput, headsOutput) {
  const current = [...extractAlembicHeadRevisions(currentOutput)].sort();
  const heads = [...extractAlembicHeadRevisions(headsOutput)].sort();
  if (heads.length === 0 || current.length === 0 || current.join(",") !== heads.join(",")) {
    throw new Error(
      "Alembic current no coincide con alembic heads después de aplicar migraciones.",
    );
  }
}

/** Valida el contrato mínimo de los endpoints públicos de salud. */
export function assertHealthyResponse(response, body, endpoint) {
  if (!response.ok || body?.status !== "healthy") {
    throw new Error(
      `${endpoint} no respondió con estado healthy (HTTP ${response.status}).`,
    );
  }
}

/** Confirma que el preview servido conserva el punto de montaje y un módulo compilado. */
export function assertFrontendMountHtml(html) {
  if (!/id=["']app["']/iu.test(html)) {
    throw new Error("El HTML del preview no contiene el punto de montaje #app.");
  }
  if (!/<script\b[^>]*type=["']module["'][^>]*src=["']\/assets\/[^"']+\.js["']/iu.test(html)) {
    throw new Error("El HTML del preview no referencia un módulo compilado en /assets.");
  }
}

function wait(milliseconds) {
  return new Promise((resolveWait) => setTimeout(resolveWait, milliseconds));
}

function waitForExit(child, timeoutMs) {
  return new Promise((resolveExit) => {
    if (hasProcessExited(child)) {
      resolveExit(true);
      return;
    }
    const timeout = setTimeout(() => {
      child.off("exit", onExit);
      resolveExit(false);
    }, timeoutMs);
    const onExit = () => {
      clearTimeout(timeout);
      resolveExit(true);
    };
    child.once("exit", onExit);
  });
}

function hasProcessExited(child) {
  return child.exitCode !== null || child.signalCode !== null;
}

export async function stopProcess(
  processInfo,
  {
    waitForExitImpl = waitForExit,
    timeoutMs = PROCESS_STOP_TIMEOUT_MS,
  } = {},
) {
  if (!processInfo || hasProcessExited(processInfo.child)) {
    return;
  }
  processInfo.child.kill("SIGTERM");
  if (!(await waitForExitImpl(processInfo.child, timeoutMs))) {
    processInfo.child.kill("SIGKILL");
    await waitForExitImpl(processInfo.child, timeoutMs);
  }
}

/** Apaga servicios en el orden recibido y permite probar el cleanup sin procesos. */
export async function cleanupProcesses(
  processInfos,
  stopProcessImpl = stopProcess,
) {
  for (const processInfo of processInfos) {
    await stopProcessImpl(processInfo);
  }
}

function startProcess({ label, command, args, cwd, env, logs }) {
  const child = spawn(command, args, buildSpawnOptions(cwd, env));
  child.stdout.on("data", (chunk) => logs.append(label, chunk));
  child.stderr.on("data", (chunk) => logs.append(label, chunk));
  child.on("error", (error) => logs.append(label, `No se pudo iniciar: ${error.message}\n`));
  return { child, label };
}

function runCommand({ label, command, args, cwd, env, logs }) {
  return new Promise((resolveCommand, rejectCommand) => {
    const processInfo = startProcess({ label, command, args, cwd, env, logs });
    let stdout = "";
    let stderr = "";
    processInfo.child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    processInfo.child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    processInfo.child.once("error", () => {
      rejectCommand(new Error(`No se pudo ejecutar ${command}.`));
    });
    processInfo.child.once("exit", (code, signal) => {
      if (code === 0) {
        resolveCommand({ stdout, stderr });
        return;
      }
      rejectCommand(
        new Error(
          `${label} terminó con código ${code ?? "nulo"}${signal ? ` (${signal})` : ""}.`,
        ),
      );
    });
  });
}

async function waitForHttp(url, validate, processInfo, fetchImpl = fetch) {
  const deadline = Date.now() + SERVICE_TIMEOUT_MS;
  let lastError = null;
  while (Date.now() < deadline) {
    if (processInfo && hasProcessExited(processInfo.child)) {
      throw new Error(`${processInfo.label} terminó antes de quedar disponible.`);
    }
    try {
      const response = await fetchImpl(url, { signal: AbortSignal.timeout(2_000) });
      await validate(response);
      return;
    } catch (error) {
      lastError = error;
      await wait(RETRY_DELAY_MS);
    }
  }
  throw new Error(
    `Tiempo agotado esperando ${url}: ${lastError instanceof Error ? lastError.message : "sin detalle"}`,
  );
}

async function requestHealthyEndpoint(url, endpoint) {
  const response = await fetch(url, { signal: AbortSignal.timeout(5_000) });
  const body = await response.json().catch(() => null);
  assertHealthyResponse(response, body, endpoint);
}

async function persistFailureLog(root, logs, error, sensitiveValues) {
  const directory = resolve(root, ".tmp/runtime-smoke");
  const content = `${sanitizeLog(error.stack || error.message, sensitiveValues)}\n\n${logs.tail()}`;
  await mkdir(directory, { recursive: true });
  await writeFile(resolve(directory, "runtime-smoke.log"), content, "utf8");
  console.error("Runtime smoke falló. Cola sanitizada de logs:");
  console.error(content);
}

/** Ejecuta migraciones y verifica API, base y preview real de Vue. */
export async function runRuntimeSmoke({
  root,
  environment = process.env,
  platform = process.platform,
  stopProcessImpl = stopProcess,
} = {}) {
  const scriptDirectory = dirname(fileURLToPath(import.meta.url));
  const repositoryRoot = root ?? resolve(scriptDirectory, "../..");
  const backendDirectory = resolve(repositoryRoot, "backend");
  const frontendDirectory = resolve(repositoryRoot, "frontend");
  const env = buildRuntimeEnvironment(environment);
  const pythonCommand = resolveBackendPython(backendDirectory);
  const sensitiveValues = collectSensitiveValues(env);
  const logs = createLogCapture(LOG_TAIL_LENGTH, sensitiveValues);
  let apiProcess;
  let frontendProcess;

  try {
    console.log("Runtime smoke: aplicando migraciones Alembic.");
    await runCommand({
      label: "alembic-upgrade",
      command: pythonCommand,
      args: ["-m", "alembic", "upgrade", "head"],
      cwd: backendDirectory,
      env,
      logs,
    });
    const current = await runCommand({
      label: "alembic-current",
      command: pythonCommand,
      args: ["-m", "alembic", "current"],
      cwd: backendDirectory,
      env,
      logs,
    });
    const heads = await runCommand({
      label: "alembic-heads",
      command: pythonCommand,
      args: ["-m", "alembic", "heads"],
      cwd: backendDirectory,
      env,
      logs,
    });
    assertAlembicAtHeads(current.stdout, heads.stdout);

    console.log("Runtime smoke: iniciando FastAPI y verificando salud real.");
    apiProcess = startProcess({
      label: "fastapi",
      command: pythonCommand,
      args: [
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "18000",
      ],
      cwd: backendDirectory,
      env,
      logs,
    });
    await waitForHttp(
      `${API_URL}/api/health`,
      async (response) => assertHealthyResponse(response, await response.json(), "/api/health"),
      apiProcess,
    );
    await requestHealthyEndpoint(`${API_URL}/api/health/db`, "/api/health/db");

    console.log("Runtime smoke: compilando y previsualizando Vue.");
    const buildInvocation = buildNpmInvocation(["run", "build"], {
      platform,
      environment: env,
    });
    await runCommand({
      label: "frontend-build",
      ...buildInvocation,
      cwd: frontendDirectory,
      env,
      logs,
    });
    const previewInvocation = buildVitePreviewInvocation(frontendDirectory);
    frontendProcess = startProcess({
      label: "vite-preview",
      ...previewInvocation,
      cwd: frontendDirectory,
      env,
      logs,
    });
    await waitForHttp(
      `${FRONTEND_URL}/`,
      async (response) => {
        if (!response.ok) {
          throw new Error(`El preview respondió HTTP ${response.status}.`);
        }
        assertFrontendMountHtml(await response.text());
      },
      frontendProcess,
    );
    console.log("Runtime smoke: API, PostgreSQL y preview Vue verificados.");
  } catch (error) {
    await persistFailureLog(
      repositoryRoot,
      logs,
      error instanceof Error ? error : new Error(String(error)),
      sensitiveValues,
    );
    throw error;
  } finally {
    await cleanupProcesses(
      [frontendProcess, apiProcess],
      stopProcessImpl,
    );
  }
}

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : "";
if (invokedPath === fileURLToPath(import.meta.url)) {
  try {
    await runRuntimeSmoke();
  } catch {
    process.exitCode = 1;
  }
}
