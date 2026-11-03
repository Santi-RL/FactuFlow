"""Cuatro grupos secuenciales y una puerta completa de casos y cobertura."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import backend_report as evidence

GROUP_COUNT = 4
DIRECTORY = Path(__file__).resolve().parent
WEIGHTS = DIRECTORY / "backend-file-durations.json"
COVERAGE_CONFIG = DIRECTORY.parents[1] / "backend" / ".coveragerc"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_file(nodeid: str) -> str:
    path = nodeid.split("::", 1)[0]
    if (
        not path.startswith("tests/")
        or not path.endswith(".py")
        or ".." in path.split("/")
    ):
        raise ValueError(f"Ruta de prueba inesperada: {path}")
    return path


def partition(cases: list[str], weights: dict[str, float]) -> list[dict]:
    """Mayor duración primero; desempates por ruta y número de grupo."""
    if not cases or len(set(cases)) != len(cases):
        raise ValueError("El inventario está vacío o contiene casos duplicados")
    if any(not math.isfinite(value) or value <= 0 for value in weights.values()):
        raise ValueError("Los tiempos de referencia deben ser positivos y finitos")
    files = set(map(test_file, cases))
    groups = [
        dict(group_id=index, files=[], estimated_seconds=0.0)
        for index in range(1, GROUP_COUNT + 1)
    ]
    for path in sorted(files, key=lambda name: (-weights.get(name, 1.0), name)):
        group = min(
            groups, key=lambda item: (item["estimated_seconds"], item["group_id"])
        )
        group["files"].append(path)
        group["estimated_seconds"] += weights.get(path, 1.0)
    for group in groups:
        group["files"].sort()
    return groups


def load_weights(path: Path) -> dict[str, float]:
    report = read_json(path)
    if report["schema_version"] != 1 or not re.fullmatch(
        r"[0-9a-f]{40}", report["source_sha"]
    ):
        raise ValueError("Referencia de tiempos no soportada")
    return report["file_seconds"]


def identity(source_sha: str, run_id: str, weights_path: Path) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha) or not run_id.strip():
        raise ValueError("Se requieren el SHA completo y la identidad de ejecución")
    return {
        "source_sha": source_sha,
        "run_id": run_id,
        "collector_sha256": file_digest(Path(__file__)),
        "evidence_collector_sha256": file_digest(Path(evidence.__file__)),
        "weights_sha256": file_digest(weights_path),
        "coverage_config_sha256": file_digest(COVERAGE_CONFIG),
        "application_fingerprint": evidence.application_fingerprint(Path.cwd()),
        "coverage_version": importlib.metadata.version("coverage"),
        "environment": evidence.environment(),
    }


class Selection(evidence.ExecutionReport):
    def __init__(self, weights: dict, group_id: int | None = None) -> None:
        super().__init__()
        self.weights = weights
        self.group_id = group_id
        self.discovered: list[str] = []
        self.groups: list[dict] = []

    def pytest_collection_modifyitems(self, session, config, items) -> None:
        self.discovered = [item.nodeid for item in items]
        if not items:
            return
        self.groups = partition(self.discovered, self.weights)
        if self.group_id is not None:
            files = self.groups[self.group_id - 1]["files"]
            selected, deselected = [], []
            for item in items:
                (selected if test_file(item.nodeid) in files else deselected).append(
                    item
                )
            items[:] = selected
            config.hook.pytest_deselected(items=deselected)


def run_group(
    output: Path, source_sha: str, run_id: str, group_id: int, weights_path: Path
) -> int:
    import pytest

    output = output.resolve()
    report = identity(source_sha, run_id, weights_path)
    output.mkdir(parents=True, exist_ok=False)
    observer = Selection(load_weights(weights_path), group_id)
    started = time.perf_counter()
    report.update(
        schema_version=evidence.SCHEMA_VERSION,
        group_id=group_id,
        group_count=GROUP_COUNT,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    previous = os.environ.get("COVERAGE_FILE")
    os.environ["COVERAGE_FILE"] = str(output / "coverage.raw")
    try:
        exit_code = int(
            pytest.main(
                [
                    "tests/",
                    "-q",
                    "--durations=25",
                    f"--junitxml={output / 'junit.xml'}",
                    "-o",
                    "junit_duration_report=total",
                    f"--cov-config={COVERAGE_CONFIG}",
                    "--cov-fail-under=0",
                    f"--cov-report=xml:{output / 'coverage.xml'}",
                    f"--cov-report=json:{output / 'coverage.json'}",
                ],
                plugins=[observer],
            )
        )
    finally:
        if previous is None:
            os.environ.pop("COVERAGE_FILE", None)
        else:
            os.environ["COVERAGE_FILE"] = previous
    report.update(
        exit_code=exit_code,
        elapsed_seconds=time.perf_counter() - started,
        finished_at=datetime.now(timezone.utc).isoformat(),
        discovered=observer.discovered,
        groups=observer.groups,
        collected=observer.collected,
        results=observer.results,
        artifact_sha256={
            name: file_digest(output / name)
            for name in evidence.ARTIFACTS
            if (output / name).is_file()
        },
    )
    write_json(output / "execution.json", report)
    if exit_code:
        return exit_code
    evidence.validate_execution(report)
    evidence.validate_artifacts(output)
    evidence.validate_native_coverage(output, Path.cwd(), relative_only=True)
    return 0


def collect_inventory(output: Path, weights_path: Path) -> None:
    """Colección independiente: no ejecuta fixtures ni mide cobertura ficticia."""
    import pytest

    observer = Selection(load_weights(weights_path))
    exit_code = int(
        pytest.main(["tests/", "--collect-only", "--no-cov", "-q"], plugins=[observer])
    )
    if exit_code:
        raise ValueError(f"No se pudo descubrir la suite completa: {exit_code}")
    write_json(output, {"discovered": observer.discovered, "groups": observer.groups})


def validate_groups(
    inputs: Path,
    inventory: dict,
    expected_identity: dict,
    source_root: Path | None = None,
) -> list[tuple[Path, dict]]:
    """Cada caso descubierto debe aparecer exactamente una vez, sin excepciones."""
    paths = sorted(inputs.glob("*/execution.json"))
    if len(paths) != GROUP_COUNT:
        raise ValueError("Falta un grupo o hay informes adicionales")
    groups = []
    ids = []
    executed: list[str] = []
    for path in paths:
        report = read_json(path)
        evidence.validate_execution(report)
        evidence.validate_artifacts(path.parent)
        if any(report.get(key) != value for key, value in expected_identity.items()):
            raise ValueError(
                "Los grupos no pertenecen al mismo código, ejecución o entorno"
            )
        group_id = report["group_id"]
        if (
            group_id not in range(1, GROUP_COUNT + 1)
            or report["group_count"] != GROUP_COUNT
        ):
            raise ValueError("Número de grupo inválido")
        if (
            report["discovered"] != inventory["discovered"]
            or report["groups"] != inventory["groups"]
        ):
            raise ValueError(
                "El inventario o la distribución no coincide con la colección independiente"
            )
        files = inventory["groups"][group_id - 1]["files"]
        selected = [
            case for case in inventory["discovered"] if test_file(case) in files
        ]
        if report["collected"] != selected:
            raise ValueError(
                "Faltan casos seleccionados o se ejecutó un archivo de otro grupo"
            )
        for name in evidence.ARTIFACTS:
            if report["artifact_sha256"].get(name) != file_digest(path.parent / name):
                raise ValueError(f"El artefacto cambió después de la ejecución: {name}")
        coverage = read_json(path.parent / "coverage.json")
        if coverage["meta"]["version"] != expected_identity["coverage_version"]:
            raise ValueError("La versión nativa de cobertura no coincide")
        evidence.covered_statements(path.parent)
        evidence.validate_native_coverage(
            path.parent, source_root or Path.cwd(), relative_only=True
        )
        junit = ET.parse(path.parent / "junit.xml")
        if len(junit.findall(".//testcase")) != len(selected) or any(
            junit.findall(f".//{kind}") for kind in ("failure", "error", "skipped")
        ):
            raise ValueError("JUnit no acredita todos los casos aprobados del grupo")
        ids.append(group_id)
        executed.extend(report["collected"])
        groups.append((path.parent, report))
    if sorted(ids) != list(range(1, GROUP_COUNT + 1)):
        raise ValueError("Falta un grupo o hay grupos duplicados")
    if Counter(executed) != Counter(inventory["discovered"]):
        raise ValueError("La suite tiene casos faltantes o duplicados")
    return sorted(groups, key=lambda item: item[1]["group_id"])


def aggregate(
    inputs: Path, output: Path, source_sha: str, run_id: str, weights_path: Path
) -> None:
    expected_identity = identity(source_sha, run_id, weights_path)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "inventory",
            "--output",
            str(output / "inventory.json"),
            "--weights",
            str(weights_path.resolve()),
        ],
        check=True,
    )
    inventory = read_json(output / "inventory.json")
    groups = validate_groups(inputs.resolve(), inventory, expected_identity)
    env = dict(os.environ, COVERAGE_FILE=str(output / "coverage.raw"))
    command = [sys.executable, "-m", "coverage"]
    subprocess.run(
        [
            *command,
            "combine",
            f"--rcfile={COVERAGE_CONFIG}",
            "--keep",
            *(str(path / "coverage.raw") for path, _ in groups),
        ],
        env=env,
        check=True,
    )
    subprocess.run(
        [
            *command,
            "json",
            f"--rcfile={COVERAGE_CONFIG}",
            "-o",
            str(output / "coverage.json"),
        ],
        env=env,
        check=True,
    )
    subprocess.run(
        [
            *command,
            "xml",
            f"--rcfile={COVERAGE_CONFIG}",
            "-o",
            str(output / "coverage.xml"),
        ],
        env=env,
        check=True,
    )
    # El umbral procede del contrato habitual de pytest, no de cada parcial.
    import configparser

    config = configparser.ConfigParser()
    config.read("pytest.ini", encoding="utf-8")
    thresholds = re.findall(
        r"--cov-fail-under[=\s]+([0-9]+(?:\.[0-9]+)?)", config["pytest"]["addopts"]
    )
    if len(thresholds) != 1 or float(thresholds[0]) != 69:
        raise ValueError("No se reconoce el umbral backend vigente del 69 %")
    subprocess.run(
        [
            *command,
            "report",
            f"--rcfile={COVERAGE_CONFIG}",
            f"--fail-under={thresholds[0]}",
        ],
        env=env,
        check=True,
    )
    junit = ET.Element("testsuites")
    for path, _ in groups:
        junit.extend(ET.parse(path / "junit.xml").getroot())
    ET.ElementTree(junit).write(
        output / "junit.xml", encoding="utf-8", xml_declaration=True
    )
    reports = [report for _, report in groups]
    started = min(datetime.fromisoformat(report["started_at"]) for report in reports)
    finished = max(datetime.fromisoformat(report["finished_at"]) for report in reports)
    combined = dict(
        expected_identity,
        schema_version=evidence.SCHEMA_VERSION,
        exit_code=0,
        collected=inventory["discovered"],
        results=[result for report in reports for result in report["results"]],
        elapsed_seconds=(finished - started).total_seconds(),
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        groups=inventory["groups"],
        group_seconds={
            report["group_id"]: report["elapsed_seconds"] for report in reports
        },
        total_group_seconds=sum(report["elapsed_seconds"] for report in reports),
    )
    evidence.validate_execution(combined)
    evidence.validate_artifacts(output)
    evidence.validate_native_coverage(output, Path.cwd(), relative_only=True)
    write_json(output / "execution.json", combined)
    print(
        json.dumps(
            {
                "cases_passed": len(combined["collected"]),
                "groups": GROUP_COUNT,
                "coverage_percent": read_json(output / "coverage.json")["totals"][
                    "percent_covered"
                ],
                "elapsed_seconds": combined["elapsed_seconds"],
                "total_group_seconds": combined["total_group_seconds"],
            },
            indent=2,
        )
    )


def validate_gate(
    scope_result: str, runtime: str, level0: str, groups_result: str
) -> None:
    if scope_result != "success":
        raise ValueError("Change Scope no terminó correctamente")
    if runtime == "true" and level0 == "false" and groups_result == "success":
        return
    if runtime == "false" and level0 == "true" and groups_result == "skipped":
        return
    raise ValueError(
        "Los cuatro grupos deben aprobarse; solo Nivel 0 permite omitirlos"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "aggregate", "inventory"):
        command = commands.add_parser(name)
        command.add_argument("--weights", type=Path, default=WEIGHTS)
        if name == "inventory":
            command.add_argument("--output", type=Path, required=True)
        else:
            command.add_argument("--output-dir", type=Path, required=True)
            command.add_argument("--source-sha", required=True)
            command.add_argument("--run-id", required=True)
            if name == "run":
                command.add_argument(
                    "--group",
                    type=int,
                    choices=range(1, GROUP_COUNT + 1),
                    required=True,
                )
            else:
                command.add_argument("--inputs", type=Path, required=True)
    gate = commands.add_parser("gate")
    for name in ("scope-result", "runtime", "level0", "groups-result"):
        gate.add_argument(f"--{name}", required=True)
    args = parser.parse_args()
    try:
        if args.command == "gate":
            validate_gate(
                args.scope_result, args.runtime, args.level0, args.groups_result
            )
        elif args.command == "inventory":
            collect_inventory(args.output, args.weights)
        elif args.command == "run":
            return run_group(
                args.output_dir, args.source_sha, args.run_id, args.group, args.weights
            )
        else:
            aggregate(
                args.inputs, args.output_dir, args.source_sha, args.run_id, args.weights
            )
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Error en los grupos backend: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
