#!/usr/bin/env node
import { spawn } from "node:child_process";
import path from "node:path";

const repoRoot = process.cwd();
const localBin = path.join(repoRoot, "tools", "clawpatch", "bin");
const env = buildChildEnv(localBin);
const args = process.argv.slice(2);

// FactuFlow usa la CLI instalada de Clawpatch; la version se actualiza fuera del repo.
const child =
  process.platform === "win32"
    ? spawn(process.env.ComSpec ?? "cmd.exe", ["/d", "/c", buildWindowsCommand(args)], {
        cwd: repoRoot,
        env,
        shell: false,
        stdio: "inherit",
      })
    : spawn("clawpatch", args, {
        cwd: repoRoot,
        env,
        shell: false,
        stdio: "inherit",
      });

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exitCode = code ?? 1;
});

child.on("error", (error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});

function buildChildEnv(localBinPath) {
  const childEnv = { ...process.env };
  const pathKey = resolvePathKey(childEnv);
  const currentPath = childEnv[pathKey] ?? "";

  if (process.platform === "win32") {
    for (const key of Object.keys(childEnv)) {
      if (key !== pathKey && key.toLowerCase() === "path") {
        delete childEnv[key];
      }
    }
  }

  childEnv[pathKey] = `${localBinPath}${path.delimiter}${currentPath}`;
  return childEnv;
}

function resolvePathKey(env) {
  if (process.platform !== "win32") {
    return "PATH";
  }
  return Object.keys(env).find((key) => key.toLowerCase() === "path") ?? "Path";
}

function buildWindowsCommand(values) {
  return ["clawpatch", ...values.map(quoteWindowsArgument)].join(" ");
}

function quoteWindowsArgument(value) {
  const text = String(value);
  if (/^[A-Za-z0-9_@%+=:,./-]+$/.test(text)) {
    return text;
  }
  return `"${text.replace(/[\\"%]/g, (character) => `^${character}`)}"`;
}
