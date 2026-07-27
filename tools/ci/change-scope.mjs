import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

/**
 * Normaliza una ruta recibida desde Git para evaluarla de forma portable.
 *
 * @param {string} value Ruta informada por Git.
 * @returns {string} Ruta relativa normalizada con separadores POSIX.
 */
export function normalizePath(value) {
  return value.trim().replaceAll("\\", "/").replace(/^\.\//, "");
}

/**
 * Determina si un archivo pertenece al recorrido liviano de Nivel 0.
 *
 * La clasificación es deliberadamente conservadora: solo Markdown y
 * `.gitignore` quedan exentos de la matriz completa. Todo archivo ejecutable,
 * configuración, lockfile, workflow o asset activa los controles de runtime.
 *
 * @param {string} value Ruta relativa del archivo.
 * @returns {boolean} `true` cuando el archivo es exclusivamente documental.
 */
export function isLevelZeroPath(value) {
  const path = normalizePath(value);
  return path === ".gitignore" || path.toLowerCase().endsWith(".md");
}

/**
 * Clasifica un conjunto de archivos con una política fail-safe.
 *
 * @param {string[]} values Rutas modificadas.
 * @returns {{ changedCount: number, level0: boolean, runtime: boolean }} Alcance.
 */
export function classifyChangedPaths(values) {
  const paths = values.map(normalizePath).filter(Boolean);
  if (paths.length === 0) {
    return { changedCount: 0, level0: false, runtime: true };
  }

  const level0 = paths.every(isLevelZeroPath);
  return {
    changedCount: paths.length,
    level0,
    runtime: !level0,
  };
}

/** Lee rutas separadas por NUL o por salto de línea desde stdin. */
function readChangedPaths() {
  const input = readFileSync(0, "utf8");
  return input.includes("\0") ? input.split("\0") : input.split(/\r?\n/);
}

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : "";
if (invokedPath === fileURLToPath(import.meta.url)) {
  const result = classifyChangedPaths(readChangedPaths());
  process.stdout.write(`level0=${result.level0}\n`);
  process.stdout.write(`runtime=${result.runtime}\n`);
  process.stdout.write(`changed_count=${result.changedCount}\n`);
}