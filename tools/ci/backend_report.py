"""Evidencia de la suite completa sin cambiar su selección ni sus umbrales."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
PHASES = ("setup", "call", "teardown")
ARTIFACTS = ("junit.xml", "coverage.raw", "coverage.xml", "coverage.json")


class ExecutionReport:
    """Observa la colección y las tres fases sin intervenir en las pruebas."""

    def __init__(self) -> None:
        self.collected: list[str] = []
        self.results: list[dict] = []

    def pytest_collection_finish(self, session) -> None:
        self.collected = [item.nodeid for item in session.items]

    def pytest_runtest_logreport(self, report) -> None:
        self.results.append(
            {
                "nodeid": report.nodeid,
                "phase": report.when,
                "outcome": report.outcome,
                "duration_seconds": report.duration,
                "was_xfail": hasattr(report, "wasxfail"),
            }
        )


def application_fingerprint(root: Path) -> str:
    """Identifica los fuentes de aplicación y migraciones comparados."""
    digest = hashlib.sha256()
    paths = sorted(
        path
        for directory in (root / "app", root / "alembic")
        for path in directory.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix in {".py", ".html", ".css", ".j2", ".txt", ".json", ".sql"}
    )
    if not paths:
        raise ValueError("No se encontraron fuentes de aplicación para la referencia")
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def environment() -> dict:
    """Registra versiones sin URLs de instalación, credenciales ni hostname."""
    packages = {
        distribution.metadata["Name"]: distribution.version
        for distribution in importlib.metadata.distributions()
        if distribution.metadata["Name"]
    }
    return {
        "python": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "os_release": (
            platform.freedesktop_os_release().get("PRETTY_NAME", "")
            if platform.system() == "Linux"
            else platform.version()
        ),
        "packages": dict(sorted(packages.items())),
    }


def validate_execution(report: dict) -> None:
    """Rechaza evidencia incompleta, duplicada o con casos no aprobados."""
    if report["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Versión de informe no soportada")
    collected = report["collected"]
    if not collected or len(set(collected)) != len(collected):
        raise ValueError(
            "La colección está vacía o contiene identificadores duplicados"
        )
    if report["exit_code"] != 0:
        raise ValueError("La suite no terminó correctamente")
    expected = Counter((nodeid, phase) for nodeid in collected for phase in PHASES)
    actual = Counter((r["nodeid"], r["phase"]) for r in report["results"])
    if actual != expected:
        raise ValueError("Faltan fases o hay ejecuciones duplicadas o no seleccionadas")
    if any(r["outcome"] != "passed" or r["was_xfail"] for r in report["results"]):
        raise ValueError("Hay casos fallidos, omitidos o con fallo esperado")


def run_suite(output: Path, source_sha: str, run_id: str) -> int:
    """Ejecuta la selección completa habitual y conserva los datos originales."""
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("La referencia requiere un SHA completo")
    root = Path.cwd()
    fingerprint = application_fingerprint(root)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    native_coverage = output / "coverage.raw"
    previous_coverage = os.environ.get("COVERAGE_FILE")
    os.environ["COVERAGE_FILE"] = str(native_coverage)
    observer = ExecutionReport()
    started = time.perf_counter()
    report = {
        "schema_version": SCHEMA_VERSION,
        "source_sha": source_sha,
        "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "application_fingerprint": fingerprint,
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "environment": environment(),
        "coverage_config_sha256": (
            hashlib.sha256((root / ".coveragerc").read_bytes()).hexdigest()
            if (root / ".coveragerc").is_file()
            else None
        ),
    }
    try:
        import pytest

        exit_code = int(
            pytest.main(
                [
                    "tests/",
                    "-q",
                    "--durations=25",
                    f"--junitxml={output / 'junit.xml'}",
                    "-o",
                    "junit_duration_report=total",
                    f"--cov-report=xml:{output / 'coverage.xml'}",
                    f"--cov-report=json:{output / 'coverage.json'}",
                    *(
                        [f"--cov-config={root / '.coveragerc'}"]
                        if (root / ".coveragerc").is_file()
                        else []
                    ),
                ],
                plugins=[observer],
            )
        )
    finally:
        if previous_coverage is None:
            os.environ.pop("COVERAGE_FILE", None)
        else:
            os.environ["COVERAGE_FILE"] = previous_coverage
    report.update(
        exit_code=exit_code,
        elapsed_seconds=time.perf_counter() - started,
        collected=observer.collected,
        results=observer.results,
    )
    (output / "execution.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if exit_code:
        return exit_code
    validate_execution(report)
    validate_artifacts(output)
    validate_native_coverage(output, root)
    return 0


def validate_artifacts(directory: Path) -> None:
    """Exige también los originales usados para contrastar la evidencia."""
    for name in ARTIFACTS:
        if not (directory / name).is_file() or (directory / name).stat().st_size == 0:
            raise ValueError(f"Falta el artefacto obligatorio: {name}")


def validate_native_coverage(
    directory: Path, source_root: Path, *, relative_only: bool = False
) -> None:
    """Detecta trazas incoherentes, incluidas líneas de otro contexto greenlet."""
    from coverage import CoverageData

    native = CoverageData(basename=str(directory / "coverage.raw"))
    native.read()
    if not native.has_arcs() or not native.measured_files():
        raise ValueError("La cobertura nativa no contiene líneas y ramas")
    application = (source_root / "app").resolve()
    for name in native.measured_files():
        if relative_only and (not name.startswith("app/") or ".." in name.split("/")):
            raise ValueError(
                "La cobertura nativa debe usar rutas relativas de aplicación"
            )
        path = (source_root / name).resolve()
        if not path.is_relative_to(application) or not path.is_file():
            raise ValueError(
                f"La cobertura no corresponde a una fuente de aplicación: {name}"
            )
        # Jinja conserva el nombre HTML para código Python generado con otras líneas.
        # Sus datos nativos se conservan; el límite textual aplica a fuentes Python.
        if path.suffix != ".py":
            continue
        last_line = max(1, len(path.read_text(encoding="utf-8").splitlines()))
        if any(
            abs(line) > last_line for arc in native.arcs(name) or [] for line in arc
        ):
            raise ValueError(f"La cobertura contiene arcos fuera del archivo: {name}")


def covered_statements(directory: Path) -> dict[str, dict[str, set]]:
    """Normaliza rutas para comparar líneas y arcos de cobertura, no porcentajes."""
    data = json.loads((directory / "coverage.json").read_text(encoding="utf-8"))
    if data["meta"]["branch_coverage"] is not True or not data["files"]:
        raise ValueError("Falta la medición de líneas y ramas")
    result = {}
    for name, file in data["files"].items():
        normalized = name.replace("\\", "/")
        if "/app/" in normalized:
            normalized = "app/" + normalized.rsplit("/app/", 1)[1]
        if not normalized.startswith("app/") or normalized in result:
            raise ValueError(f"Ruta de cobertura inesperada o duplicada: {name}")
        result[normalized] = {
            "lines": set(file["executed_lines"]),
            "branches": {tuple(branch) for branch in file["executed_branches"]},
        }
    return result


def compare_reports(reference: Path, candidate: Path) -> dict:
    """Exige los mismos casos aprobados y ninguna línea o rama perdida."""
    before = json.loads((reference / "execution.json").read_text(encoding="utf-8"))
    after = json.loads((candidate / "execution.json").read_text(encoding="utf-8"))
    validate_execution(before)
    validate_execution(after)
    validate_artifacts(reference)
    validate_artifacts(candidate)
    if set(before["collected"]) != set(after["collected"]):
        raise ValueError("Cambió el inventario de casos ejecutados")
    if before["application_fingerprint"] != after["application_fingerprint"]:
        raise ValueError("Cambió la aplicación o las migraciones comparadas")
    if before["environment"] != after["environment"]:
        raise ValueError("Los entornos o dependencias de las corridas no coinciden")
    if before.get("coverage_config_sha256") != after.get("coverage_config_sha256"):
        raise ValueError("Cambió la configuración de cobertura comparada")
    old_coverage = covered_statements(reference)
    new_coverage = covered_statements(candidate)
    losses = {}
    for name, old in old_coverage.items():
        new = new_coverage.get(name, {"lines": set(), "branches": set()})
        missing = {
            kind: sorted(old[kind] - new[kind]) for kind in ("lines", "branches")
        }
        if any(missing.values()):
            losses[name] = missing
    if losses:
        raise ValueError("Se perdió cobertura: " + json.dumps(losses, sort_keys=True))
    return {
        "reference_sha": before["source_sha"],
        "candidate_sha": after["source_sha"],
        "cases_preserved": len(before["collected"]),
        "lost_lines": 0,
        "lost_branches": 0,
        "reference_seconds": before["elapsed_seconds"],
        "candidate_seconds": after["elapsed_seconds"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--source-sha", required=True)
    run.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    compare = commands.add_parser("compare")
    compare.add_argument("reference", type=Path)
    compare.add_argument("candidate", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "run":
            return run_suite(args.output_dir, args.source_sha, args.run_id)
        print(
            json.dumps(
                compare_reports(args.reference, args.candidate),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"Error en la evidencia backend: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
