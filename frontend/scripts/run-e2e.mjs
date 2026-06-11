import { spawn } from "node:child_process";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const port = Number(process.env.E2E_PORT || 18080);
const host = "127.0.0.1";
const url = `http://${host}:${port}`;

if (!Number.isInteger(port) || port <= 0 || port > 65535) {
  console.error(`Invalid E2E_PORT: ${process.env.E2E_PORT}`);
  process.exit(1);
}

const serverIsReachable = async () =>
  new Promise((resolve) => {
    const req = http.get(url, (res) => {
      res.resume();
      resolve(res.statusCode && res.statusCode < 500);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(1_000, () => {
      req.destroy();
      resolve(false);
    });
  });

if (await serverIsReachable()) {
  console.error(
    `E2E port ${port} is already serving ${url}. Stop that process or set E2E_PORT.`,
  );
  process.exit(1);
}

const waitForServer = async (timeoutMs = 60_000) => {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const ready = await serverIsReachable();
    if (ready) return;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`E2E server did not start at ${url}`);
};

const stopProcess = async (child) => {
  if (!child || child.killed || child.exitCode !== null) return;
  child.kill();
  await new Promise((resolve) => {
    const timeout = setTimeout(resolve, 2_000);
    child.once("exit", () => {
      clearTimeout(timeout);
      resolve();
    });
  });
};

const server = spawn(
  process.execPath,
  [
    "./node_modules/vite/bin/vite.js",
    "--host",
    host,
    "--port",
    String(port),
    "--strictPort",
  ],
  {
    cwd: root,
    stdio: ["ignore", "inherit", "inherit"],
  },
);

const shutdown = async (code = 1) => {
  await stopProcess(server);
  process.exit(code);
};

process.on("SIGINT", () => {
  void shutdown(130);
});
process.on("SIGTERM", () => {
  void shutdown(143);
});

try {
  await waitForServer();
} catch (error) {
  console.error(error);
  await shutdown(1);
}

const playwright = spawn(
  process.execPath,
  ["./node_modules/@playwright/test/cli.js", "test", ...process.argv.slice(2)],
  {
    cwd: root,
    env: {
      ...process.env,
      E2E_EXTERNAL_SERVER: "1",
    },
    stdio: "inherit",
  },
);

playwright.on("exit", (code, signal) => {
  const exitCode = code ?? (signal ? 1 : 0);
  void shutdown(exitCode);
});
