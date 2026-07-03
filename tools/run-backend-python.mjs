#!/usr/bin/env node
import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import path from "node:path";

const repoRoot = process.cwd();
const backendRoot = path.join(repoRoot, "backend");
const venvPython =
  process.platform === "win32"
    ? path.join(backendRoot, ".venv", "Scripts", "python.exe")
    : path.join(backendRoot, ".venv", "bin", "python");
const python = existsSync(venvPython) ? venvPython : "python";

const child = spawn(python, process.argv.slice(2), {
  cwd: backendRoot,
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
