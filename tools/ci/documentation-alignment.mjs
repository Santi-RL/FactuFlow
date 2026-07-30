import { readFile, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, relative, resolve } from "node:path";

const VERSION_PATTERN = "v\\d+\\.\\d+\\.\\d+";
const REQUIRED_DOCUMENTS = [
  "README.md",
  "CHANGELOG.md",
  "docs/agents/overview.md",
  "docs/user-guide/README.md",
];
const LIVE_DOCUMENT_PREFIXES = [
  "docs/agents/",
  "docs/api/",
  "docs/arca-ws/",
  "docs/certificates/",
  "docs/setup/",
  "docs/user-guide/",
];
const LIVE_DOCUMENT_DIRECTORIES = LIVE_DOCUMENT_PREFIXES.map((prefix) =>
  prefix.slice(0, -1),
);
const LIVE_DOCUMENT_FILES = new Set([
  "README.md",
  "ROADMAP.md",
  "CHANGELOG.md",
  "docs/README.md",
  "docs/certificados-wizard.md",
]);
const TRANSIENT_MARKERS = [
  {
    pattern: /^#{1,6}\s+implementaci[oó]n local en curso\b/iu,
    description: "encabezado de implementación local en curso",
  },
  {
    pattern:
      /^Estado:\s*[^\n]*(?:validado localmente|en implementaci[oó]n local)\b/iu,
    description: "estado local transitorio",
  },
  {
    pattern: /^\s*-\s*\[[ x~]\]\s*primer corte local:/iu,
    description: "corte del roadmap descrito como local",
  },
  {
    pattern: /\bpublicado para revisi[oó]n mediante el PR\b/iu,
    description: "estado transitorio de revisión de PR",
  },
  {
    pattern: /\bpendiente de integraci[oó]n (?:en|a) `?main`?\b/iu,
    description: "estado transitorio pendiente de integración",
  },
];

/** Normaliza rutas para que las validaciones sean idénticas en Windows y Linux. */
export function normalizePath(value) {
  return value.replaceAll("\\", "/").replace(/^\.\//, "");
}

/** Indica si un Markdown pertenece al corpus operativo vivo del repositorio. */
export function isLiveDocumentationPath(value) {
  const path = normalizePath(value);
  if (!path.toLowerCase().endsWith(".md") || path.startsWith("docs/project/")) {
    return false;
  }
  if (path.startsWith("docs/arca-ws/_extracted/")) {
    return false;
  }
  return (
    LIVE_DOCUMENT_FILES.has(path) ||
    LIVE_DOCUMENT_PREFIXES.some((prefix) => path.startsWith(prefix))
  );
}

function lineNumberAt(content, index) {
  return content.slice(0, index).split(/\r?\n/u).length;
}

function findLabeledVersion(content, pattern) {
  const match = content.match(pattern);
  return match?.groups?.version ?? null;
}

function compareVersions(left, right) {
  const leftParts = left.slice(1).split(".").map(Number);
  const rightParts = right.slice(1).split(".").map(Number);
  for (let index = 0; index < 3; index += 1) {
    if (leftParts[index] !== rightParts[index]) {
      return leftParts[index] - rightParts[index];
    }
  }
  return 0;
}

function error(path, message, line = null) {
  return { path, line, message };
}

/**
 * Valida invariantes documentales estructurales sobre un conjunto de archivos.
 *
 * Este control no intenta comprender toda la documentación ni reemplaza su
 * revisión semántica. Solo detecta divergencias objetivas de versión y estados
 * transitorios inequívocos.
 */
export function validateDocumentation(files) {
  const normalizedFiles = new Map(
    [...files.entries()].map(([path, content]) => [
      normalizePath(path),
      content,
    ]),
  );
  const errors = [];

  for (const path of REQUIRED_DOCUMENTS) {
    if (!normalizedFiles.has(path)) {
      errors.push(error(path, "falta el documento requerido"));
    }
  }
  if (errors.length > 0) {
    return errors;
  }

  const readme = normalizedFiles.get("README.md");
  const publishedPattern = new RegExp(
    `^Versi[oó]n publicada m[aá]s reciente:\\s*(?:\\x60)?(?<version>${VERSION_PATTERN})(?:\\x60)?\\s*$`,
    "imu",
  );
  const productionPattern = new RegExp(
    `^Versi[oó]n productiva vigente:\\s*(?:\\x60)?(?<version>${VERSION_PATTERN})(?:\\x60)?\\s*$`,
    "imu",
  );
  const publishedVersion = findLabeledVersion(readme, publishedPattern);
  const productionVersion = findLabeledVersion(readme, productionPattern);

  if (!publishedVersion) {
    errors.push(
      error(
        "README.md",
        "no declara «Versión publicada más reciente» con formato vX.Y.Z",
      ),
    );
  }
  if (!productionVersion) {
    errors.push(
      error(
        "README.md",
        "no declara «Versión productiva vigente» con formato vX.Y.Z",
      ),
    );
  }
  if (
    publishedVersion &&
    productionVersion &&
    compareVersions(productionVersion, publishedVersion) > 0
  ) {
    errors.push(
      error(
        "README.md",
        `la versión productiva ${productionVersion} supera la publicada ${publishedVersion}`,
      ),
    );
  }

  if (productionVersion) {
    const overview = normalizedFiles.get("docs/agents/overview.md");
    const overviewPattern = new RegExp(
      `^\\s*-\\s*(?:Release|Versi[oó]n) productiva vigente:\\s*(?:\\x60)?(?<version>${VERSION_PATTERN})(?:\\x60)?`,
      "imu",
    );
    const overviewVersion = findLabeledVersion(overview, overviewPattern);
    if (!overviewVersion) {
      errors.push(
        error(
          "docs/agents/overview.md",
          "no declara una versión productiva vigente con formato vX.Y.Z",
        ),
      );
    } else if (overviewVersion !== productionVersion) {
      errors.push(
        error(
          "docs/agents/overview.md",
          `declara ${overviewVersion}, pero README.md define ${productionVersion} como productiva`,
        ),
      );
    }

    const userGuide = normalizedFiles.get("docs/user-guide/README.md");
    const firstSectionIndex = userGuide.search(/^##\s+/mu);
    const userGuideHeader = userGuide.slice(
      0,
      firstSectionIndex === -1 ? userGuide.length : firstSectionIndex,
    );
    const userGuidePatterns = [
      new RegExp(
        `Este manual describe\\s+(?:\\x60)?(?<version>${VERSION_PATTERN})(?:\\x60)?`,
        "iu",
      ),
      new RegExp(
        `Versi[oó]n productiva(?: vigente)?[^\\n:]*:\\s*(?:\\x60)?(?<version>${VERSION_PATTERN})(?:\\x60)?`,
        "iu",
      ),
    ];
    const userGuideVersion = userGuidePatterns
      .map((pattern) => findLabeledVersion(userGuideHeader, pattern))
      .find(Boolean);
    if (!userGuideVersion) {
      errors.push(
        error(
          "docs/user-guide/README.md",
          "el encabezado no identifica la versión productiva cubierta",
        ),
      );
    } else if (userGuideVersion !== productionVersion) {
      errors.push(
        error(
          "docs/user-guide/README.md",
          `el encabezado referencia ${userGuideVersion}, pero README.md define ${productionVersion} como productiva`,
        ),
      );
    }
  }

  const changelog = normalizedFiles.get("CHANGELOG.md");
  if (!/^##\s+\[Unreleased\]\s*$/mu.test(changelog)) {
    errors.push(
      error(
        "CHANGELOG.md",
        "falta la sección de trabajo vigente «## [Unreleased]»",
      ),
    );
  }

  const branchPattern = /\bcodex\/[a-z0-9][a-z0-9._/-]*/gu;
  for (const [path, content] of normalizedFiles) {
    if (!isLiveDocumentationPath(path)) {
      continue;
    }

    for (const match of content.matchAll(branchPattern)) {
      errors.push(
        error(
          path,
          `contiene la rama temporal «${match[0]}»`,
          lineNumberAt(content, match.index),
        ),
      );
    }

    const lines = content.split(/\r?\n/u);
    lines.forEach((line, index) => {
      for (const marker of TRANSIENT_MARKERS) {
        if (marker.pattern.test(line)) {
          errors.push(error(path, marker.description, index + 1));
        }
      }
    });
  }

  return errors;
}

async function collectMarkdownFiles(root) {
  const files = new Map();

  async function walk(directory) {
    let entries;
    try {
      entries = await readdir(directory, { withFileTypes: true });
    } catch (caughtError) {
      if (caughtError.code === "ENOENT") {
        return;
      }
      throw caughtError;
    }
    for (const entry of entries) {
      const absolutePath = resolve(directory, entry.name);
      const relativePath = normalizePath(relative(root, absolutePath));
      if (entry.isDirectory()) {
        if (relativePath.startsWith("docs/arca-ws/_extracted/")) {
          continue;
        }
        await walk(absolutePath);
      } else if (isLiveDocumentationPath(relativePath)) {
        files.set(relativePath, await readFile(absolutePath, "utf8"));
      }
    }
  }

  for (const directory of LIVE_DOCUMENT_DIRECTORIES) {
    await walk(resolve(root, directory));
  }
  for (const path of LIVE_DOCUMENT_FILES) {
    if (!files.has(path)) {
      try {
        files.set(path, await readFile(resolve(root, path), "utf8"));
      } catch {
        // La validación pura informa después el documento faltante.
      }
    }
  }
  return files;
}

async function main() {
  const scriptDirectory = dirname(fileURLToPath(import.meta.url));
  const root = resolve(scriptDirectory, "../..");
  const files = await collectMarkdownFiles(root);
  const errors = validateDocumentation(files);

  console.log(
    "Documentation alignment comprueba versiones y marcadores estructurales; " +
      "no reemplaza la revisión semántica de la documentación.",
  );
  if (errors.length === 0) {
    console.log("Documentación estructuralmente alineada.");
    return;
  }

  console.error(`Se encontraron ${errors.length} problema(s) documental(es):`);
  for (const item of errors) {
    const location = item.line ? `${item.path}:${item.line}` : item.path;
    console.error(`- ${location}: ${item.message}`);
  }
  process.exitCode = 1;
}

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : "";
if (invokedPath === fileURLToPath(import.meta.url)) {
  await main();
}
