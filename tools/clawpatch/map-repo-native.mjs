#!/usr/bin/env node
import { copyFile, lstat, mkdir, mkdtemp, realpath, rm } from "node:fs/promises";
import { spawn } from "node:child_process";
import path from "node:path";

const repoRoot = process.cwd();
const tempParent = path.join(repoRoot, ".tmp");
const snapshotPrefix = path.join(tempParent, "clawpatch-repo-map-");

await mkdir(tempParent, { recursive: true });
const tempRoot = await mkdtemp(snapshotPrefix);

try {
  const files = await listVersionableFiles();
  await copyFilesToSnapshot(files, tempRoot);
  await runNativeMap(tempRoot);
} finally {
  await assertInside(tempParent, tempRoot, "temporary Clawpatch map root");
  await rm(tempRoot, { recursive: true, force: true });
}

async function listVersionableFiles() {
  const output = await runGit([
    "ls-files",
    "-z",
    "--cached",
    "--others",
    "--exclude-standard",
  ]);

  return output
    .split("\0")
    .filter(Boolean)
    .filter((filePath) => !filePath.startsWith(".clawpatch/"))
    .filter((filePath) => !filePath.startsWith(".tmp/"));
}

async function copyFilesToSnapshot(files, destinationRoot) {
  for (const filePath of files) {
    const source = path.join(repoRoot, filePath);
    const destination = path.join(destinationRoot, filePath);

    await assertInside(repoRoot, source, "source file");
    await assertInside(destinationRoot, destination, "snapshot destination");

    let sourceStats;
    try {
      sourceStats = await lstat(source);
    } catch (error) {
      if (isMissingPathError(error)) {
        continue;
      }
      throw error;
    }

    if (sourceStats.isSymbolicLink() || !sourceStats.isFile()) {
      continue;
    }

    const resolvedSource = await realpath(source);
    await assertInside(repoRoot, resolvedSource, "resolved source file");
    await mkdir(path.dirname(destination), { recursive: true });
    await copyFile(resolvedSource, destination);
  }
}

async function runNativeMap(root) {
  const args = [
    path.join(repoRoot, "tools", "clawpatch", "run-clawpatch.mjs"),
    "--root",
    toForwardSlashes(root),
    "--state-dir",
    toForwardSlashes(path.join(repoRoot, ".clawpatch", "repo")),
    "--config",
    toForwardSlashes(path.join(repoRoot, ".clawpatch", "repo", "config.json")),
    "map",
    "--skip-git-repo-check",
  ];

  await runProcess(process.execPath, args, { cwd: repoRoot, stdio: "inherit" });
}

async function runGit(args) {
  const chunks = [];
  await runProcess("git", args, {
    cwd: repoRoot,
    stdio: ["ignore", "pipe", "inherit"],
    onStdout: (chunk) => chunks.push(chunk),
  });
  return Buffer.concat(chunks).toString("utf8");
}

function runProcess(command, args, options) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      shell: false,
      stdio: options.stdio,
    });

    if (options.onStdout) {
      child.stdout?.on("data", options.onStdout);
    }

    child.on("error", reject);
    child.on("close", (code, signal) => {
      if (signal) {
        reject(new Error(`${command} exited with signal ${signal}`));
        return;
      }
      if (code !== 0) {
        reject(new Error(`${command} exited with code ${code}`));
        return;
      }
      resolve();
    });
  });
}

async function assertInside(parent, child, label) {
  const relative = path.relative(path.resolve(parent), path.resolve(child));

  if (
    relative === "" ||
    (!relative.startsWith("..") && !path.isAbsolute(relative))
  ) {
    return;
  }

  throw new Error(`${label} must stay inside ${parent}: ${child}`);
}

function isMissingPathError(error) {
  return (
    error instanceof Error &&
    "code" in error &&
    error.code === "ENOENT"
  );
}

function toForwardSlashes(value) {
  return value.replaceAll(path.sep, "/");
}
