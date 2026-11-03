"""Ensayos de orquestación con pytest, JUnit y cobertura nativa reales."""

from __future__ import annotations

import contextlib
import copy
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from coverage.exceptions import CoverageException
from coverage import CoverageData

import backend_report as evidence
import backend_shards as shards

SCRIPT = Path(shards.__file__).resolve()
SOURCE_SHA = "a" * 40
RUN_ID = "synthetic:1"


class BackendShardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="factuflow-backend-groups-")
        cls.root = Path(cls.temporary.name).resolve()
        cls.project = cls.root / "project"
        (cls.project / "app").mkdir(parents=True)
        (cls.project / "tests").mkdir()
        (cls.project / "app/__init__.py").write_text("", encoding="utf-8")
        (cls.project / "tests/__init__.py").write_text("", encoding="utf-8")
        shutil.copyfile(shards.COVERAGE_CONFIG, cls.project / ".coveragerc")
        (cls.project / "app/calc.py").write_text(
            "def evaluate(value):\n"
            "    if value == 0:\n        return 0\n"
            "    if value == 1:\n        return 1\n"
            "    if value == 2:\n        return 2\n"
            "    return 3\n",
            encoding="utf-8",
        )
        for value in range(4):
            (cls.project / f"tests/test_{value}.py").write_text(
                "from app.calc import evaluate\n"
                f"def test_value_{value}():\n    assert evaluate({value}) == {value}\n",
                encoding="utf-8",
            )
        with (cls.project / "tests/test_0.py").open("a", encoding="utf-8") as target:
            target.write("def test_same_file():\n    assert evaluate(0) == 0\n")
        (cls.project / "pytest.ini").write_text(
            "[pytest]\n"
            "addopts = --cov=app --cov-branch --cov-report=term --cov-fail-under=69\n"
            "filterwarnings = error\n"
            "asyncio_default_fixture_loop_scope = session\n"
            "asyncio_default_test_loop_scope = session\n",
            encoding="utf-8",
        )
        cls.weights = cls.root / "weights.json"
        shards.write_json(
            cls.weights,
            {
                "schema_version": 1,
                "source_sha": SOURCE_SHA,
                "file_seconds": {
                    f"tests/test_{value}.py": 4 - value for value in range(4)
                },
            },
        )
        cls.inputs = cls.root / "groups"
        try:
            cls.run_all(cls.inputs)
            cls.inventory = cls.inventory_now()
            with contextlib.chdir(cls.project):
                cls.expected_identity = shards.identity(SOURCE_SHA, RUN_ID, cls.weights)
        except Exception:
            cls.temporary.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    @classmethod
    def cli(cls, *arguments, script=SCRIPT, project=None):
        env = os.environ.copy()
        env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        env.pop("PYTEST_ADDOPTS", None)
        env.pop("COVERAGE_FILE", None)
        return subprocess.run(
            [sys.executable, str(script), *map(str, arguments)],
            cwd=project or cls.project,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )

    @classmethod
    def run_all(cls, output):
        for group in range(1, 5):
            result = cls.cli(
                "run",
                "--weights",
                cls.weights,
                "--group",
                group,
                "--output-dir",
                output / f"group-{group}",
                "--source-sha",
                SOURCE_SHA,
                "--run-id",
                RUN_ID,
            )
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)

    @classmethod
    def inventory_now(cls):
        output = cls.root / "inventory.json"
        result = cls.cli("inventory", "--weights", cls.weights, "--output", output)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return shards.read_json(output)

    def inputs_copy(self):
        directory = Path(tempfile.mkdtemp(dir=self.root, prefix="reports-"))
        shutil.copytree(self.inputs, directory, dirs_exist_ok=True)
        return directory

    def combine(self, inputs, output):
        return self.cli(
            "aggregate",
            "--weights",
            self.weights,
            "--inputs",
            inputs,
            "--output-dir",
            output,
            "--source-sha",
            SOURCE_SHA,
            "--run-id",
            RUN_ID,
        )

    def test_deterministic_balance_keeps_files_whole_and_new_file_weighs_one_second(
        self,
    ):
        cases = [
            f"tests/test_{letter}.py::test_{case}"
            for letter in "abcde"
            for case in (1, 2)
        ]
        weights = {f"tests/test_{letter}.py": 2.0 for letter in "abcd"}
        expected = shards.partition(cases, weights)
        self.assertEqual(
            expected,
            shards.partition(
                list(reversed(cases)), dict(reversed(list(weights.items())))
            ),
        )
        self.assertEqual(expected[0]["files"], ["tests/test_a.py", "tests/test_e.py"])
        self.assertEqual(expected[0]["estimated_seconds"], 3)
        self.assertEqual(
            [group["estimated_seconds"] for group in expected[1:]], [2, 2, 2]
        )
        self.assertEqual(sum(len(group["files"]) for group in expected), 5)
        for bad in ([], cases + [cases[0]], ["../test_bad.py::test_bad"]):
            with self.assertRaises(ValueError):
                shards.partition(bad, weights)
        with self.assertRaises(ValueError):
            shards.partition(cases, {"tests/test_a.py": float("nan")})

    def test_real_groups_contain_all_selected_phases_and_native_artifacts(self):
        groups = shards.validate_groups(
            self.inputs, self.inventory, self.expected_identity, self.project
        )
        self.assertEqual([report["group_id"] for _, report in groups], [1, 2, 3, 4])
        self.assertEqual(sum(len(report["collected"]) for _, report in groups), 5)
        partial = [
            shards.read_json(path / "coverage.json")["totals"]["percent_covered"]
            for path, _ in groups
        ]
        self.assertLess(min(partial), 69)
        for path, report in groups:
            self.assertEqual(len(report["results"]), len(report["collected"]) * 3)
            self.assertEqual(report["run_id"], RUN_ID)
            self.assertEqual(
                report["artifact_sha256"]["coverage.raw"],
                shards.file_digest(path / "coverage.raw"),
            )

    def test_real_combine_matches_the_full_sequential_lines_and_branches(self):
        output = self.root / "combined"
        result = self.combine(self.inputs, output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        sequential = self.root / "sequential"
        result = self.cli(
            "run",
            "--output-dir",
            sequential,
            "--source-sha",
            SOURCE_SHA,
            "--run-id",
            RUN_ID,
            script=Path(evidence.__file__),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        comparison = evidence.compare_reports(sequential, output)
        self.assertEqual(comparison["cases_preserved"], 5)
        self.assertEqual(comparison["lost_lines"], 0)
        self.assertEqual(comparison["lost_branches"], 0)
        self.assertEqual(
            shards.read_json(output / "coverage.json")["totals"]["percent_covered"], 100
        )
        self.assertEqual(len(ET.parse(output / "junit.xml").findall(".//testcase")), 5)
        for group in range(1, 5):
            self.assertTrue((self.inputs / f"group-{group}/coverage.raw").is_file())
        stale = self.combine(self.inputs, output)
        self.assertNotEqual(stale.returncode, 0)

    def test_incomplete_duplicate_skipped_failed_or_foreign_reports_never_pass(self):
        mutations = (
            "missing_case",
            "duplicate_case",
            "wrong_group",
            "missing_phase",
            "failed",
            "cancelled",
            "skipped",
            "xfail",
            "wrong_sha",
            "wrong_run",
            "wrong_attempt",
            "wrong_version",
            "wrong_environment",
            "wrong_collector",
            "wrong_plan",
            "missing_report",
            "missing_native",
            "missing_junit",
            "missing_json",
            "extra_group",
            "changed_artifact",
            "invalid_native",
            "invalid_junit",
            "wrong_native_version",
            "out_of_bounds_arc",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                inputs = self.inputs_copy()
                path = inputs / "group-1/execution.json"
                report = shards.read_json(path)
                if mutation == "missing_case":
                    removed = report["collected"].pop()
                    report["results"] = [
                        row for row in report["results"] if row["nodeid"] != removed
                    ]
                    evidence.validate_execution(report)
                elif mutation == "duplicate_case":
                    report["collected"].append(report["collected"][0])
                elif mutation == "wrong_group":
                    report["group_id"] = 2
                elif mutation == "missing_phase":
                    report["results"].pop()
                elif mutation == "cancelled":
                    report["exit_code"] = 2
                elif mutation in ("failed", "skipped"):
                    report["results"][1]["outcome"] = mutation
                elif mutation == "xfail":
                    report["results"][1]["was_xfail"] = True
                elif mutation == "wrong_sha":
                    report["source_sha"] = "b" * 40
                elif mutation in ("wrong_run", "wrong_attempt"):
                    report["run_id"] = (
                        "different:1" if mutation == "wrong_run" else "synthetic:2"
                    )
                elif mutation == "wrong_version":
                    report["coverage_version"] = "different"
                elif mutation == "wrong_environment":
                    report["environment"]["python"] = "different"
                elif mutation == "wrong_collector":
                    report["collector_sha256"] = "different"
                elif mutation == "wrong_plan":
                    report["groups"][0]["files"] = ["tests/test_other.py"]
                elif mutation == "missing_report":
                    path.unlink()
                elif mutation.startswith("missing_"):
                    name = {
                        "missing_native": "coverage.raw",
                        "missing_junit": "junit.xml",
                        "missing_json": "coverage.json",
                    }[mutation]
                    (path.parent / name).unlink()
                elif mutation == "extra_group":
                    shutil.copytree(path.parent, inputs / "group-5")
                elif mutation in (
                    "changed_artifact",
                    "invalid_native",
                    "invalid_junit",
                ):
                    name = (
                        "junit.xml" if mutation == "invalid_junit" else "coverage.raw"
                    )
                    (path.parent / name).write_bytes(b"invalid")
                    if mutation != "changed_artifact":
                        report["artifact_sha256"][name] = shards.file_digest(
                            path.parent / name
                        )
                elif mutation == "wrong_native_version":
                    coverage = shards.read_json(path.parent / "coverage.json")
                    coverage["meta"]["version"] = "different"
                    shards.write_json(path.parent / "coverage.json", coverage)
                    report["artifact_sha256"]["coverage.json"] = shards.file_digest(
                        path.parent / "coverage.json"
                    )
                elif mutation == "out_of_bounds_arc":
                    native = CoverageData(basename=str(path.parent / "coverage.raw"))
                    native.read()
                    native.add_arcs({"app/calc.py": [(1, 9999)]})
                    native.write()
                    report["artifact_sha256"]["coverage.raw"] = shards.file_digest(
                        path.parent / "coverage.raw"
                    )
                if mutation != "missing_report":
                    shards.write_json(path, report)
                with self.assertRaises((ValueError, CoverageException, ET.ParseError)):
                    shards.validate_groups(
                        inputs, self.inventory, self.expected_identity, self.project
                    )

    def test_self_consistent_missing_case_is_detected_by_independent_collection(self):
        inputs = self.inputs_copy()
        path = inputs / "group-1/execution.json"
        report = shards.read_json(path)
        missing = report["collected"][0]
        inventory = copy.deepcopy(self.inventory)
        # Un informe puede ser internamente válido y aun así omitir un caso real.
        inventory["discovered"].append("tests/test_0.py::test_missing")
        self.assertNotIn("tests/test_0.py::test_missing", report["collected"])
        self.assertTrue(missing)
        with self.assertRaises(ValueError):
            shards.validate_groups(
                inputs, inventory, self.expected_identity, self.project
            )

    def test_new_file_is_automatically_executed_and_old_reports_are_rejected(self):
        extra = self.project / "tests/test_added.py"
        extra.write_text(
            "from app.calc import evaluate\ndef test_added():\n    assert evaluate(0) == 0\n",
            encoding="utf-8",
        )
        try:
            inventory = self.inventory_now()
            self.assertIn("tests/test_added.py::test_added", inventory["discovered"])
            with self.assertRaises(ValueError):
                shards.validate_groups(
                    self.inputs, inventory, self.expected_identity, self.project
                )
            inputs = self.root / "groups-with-new-file"
            self.run_all(inputs)
            result = self.combine(inputs, self.root / "combined-with-new-file")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(
                len(
                    shards.read_json(
                        self.root / "combined-with-new-file/execution.json"
                    )["collected"]
                ),
                6,
            )
        finally:
            extra.unlink()

    def test_combined_coverage_below_threshold_fails_after_all_cases_pass(self):
        extra = self.project / "app/uncovered.py"
        extra.write_text(
            "def uncovered():\n"
            + "".join(f"    x{index} = {index}\n" for index in range(40)),
            encoding="utf-8",
        )
        try:
            inputs = self.root / "groups-insufficient"
            self.run_all(inputs)
            result = self.combine(inputs, self.root / "combined-insufficient")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Coverage failure", result.stdout + result.stderr)
            self.assertFalse(
                (self.root / "combined-insufficient/execution.json").exists()
            )
        finally:
            extra.unlink()

    def test_actual_failed_assertion_is_not_hidden_by_partial_coverage(self):
        path = self.project / "tests/test_0.py"
        original = path.read_text(encoding="utf-8")
        path.write_text(original.replace("== 0", "== 99"), encoding="utf-8")
        try:
            output = self.root / "failed-group"
            result = self.cli(
                "run",
                "--weights",
                self.weights,
                "--group",
                1,
                "--output-dir",
                output,
                "--source-sha",
                SOURCE_SHA,
                "--run-id",
                RUN_ID,
            )
            self.assertNotEqual(result.returncode, 0)
            report = shards.read_json(output / "execution.json")
            self.assertTrue(
                any(row["outcome"] == "failed" for row in report["results"])
            )
            with self.assertRaises(ValueError):
                evidence.validate_execution(report)
        finally:
            path.write_text(original, encoding="utf-8")

    def test_gate_rejects_failed_cancelled_skipped_or_unknown_runtime_groups(self):
        shards.validate_gate("success", "true", "false", "success")
        shards.validate_gate("success", "false", "true", "skipped")
        for scope in ("failure", "cancelled", "skipped", "", "success"):
            for result in ("success", "failure", "cancelled", "skipped", ""):
                if scope == result == "success":
                    continue
                with self.subTest(scope=scope, groups=result), self.assertRaises(
                    ValueError
                ):
                    shards.validate_gate(scope, "true", "false", result)
        for runtime, level0, result in (
            ("", "", "skipped"),
            ("false", "false", "skipped"),
            ("false", "true", "failure"),
            ("true", "true", "success"),
        ):
            with self.assertRaises(ValueError):
                shards.validate_gate("success", runtime, level0, result)
        result = self.cli(
            "gate",
            "--scope-result",
            "success",
            "--runtime",
            "true",
            "--level0",
            "false",
            "--groups-result",
            "cancelled",
        )
        self.assertNotEqual(result.returncode, 0)

    def test_real_async_sqlalchemy_has_no_foreign_greenlet_arcs(self):
        project = self.root / "sqlalchemy-greenlet"
        (project / "app").mkdir(parents=True)
        (project / "tests").mkdir()
        for name in ("app/__init__.py", "tests/__init__.py"):
            (project / name).write_text("", encoding="utf-8")
        shutil.copyfile(shards.COVERAGE_CONFIG, project / ".coveragerc")
        shutil.copyfile(self.project / "pytest.ini", project / "pytest.ini")
        (project / "app/sql_probe.py").write_text(
            "from sqlalchemy import text\n"
            "from sqlalchemy.ext.asyncio import create_async_engine\n"
            "async def query():\n"
            "    engine = create_async_engine('sqlite+aiosqlite:///:memory:')\n"
            "    async with engine.connect() as connection:\n"
            "        result = await connection.execute(text('SELECT 1'))\n"
            "    await engine.dispose()\n"
            "    return result.scalar()\n",
            encoding="utf-8",
        )
        (project / "app/templates").mkdir()
        (project / "app/templates/probe.html").write_text(
            "{{ label }}", encoding="utf-8"
        )
        (project / "app/render_probe.py").write_text(
            "from pathlib import Path\n"
            "from jinja2 import Environment, FileSystemLoader\n"
            "def render():\n"
            "    env = Environment(loader=FileSystemLoader(Path(__file__).parent / 'templates'))\n"
            "    return env.get_template('probe.html').render(label='Synthetic')\n",
            encoding="utf-8",
        )
        (project / "tests/test_sql_probe.py").write_text(
            "import pytest\nfrom app.sql_probe import query\nfrom app.render_probe import render\n"
            + "\n" * 150
            + "@pytest.mark.asyncio\nasync def test_query():\n    assert await query() == 1\n    assert render() == 'Synthetic'\n",
            encoding="utf-8",
        )
        output = self.root / "sqlalchemy-greenlet-report"
        result = self.cli(
            "run",
            "--output-dir",
            output,
            "--source-sha",
            SOURCE_SHA,
            "--run-id",
            RUN_ID,
            script=Path(evidence.__file__),
            project=project,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        evidence.validate_native_coverage(output, project, relative_only=True)
        native = CoverageData(basename=str(output / "coverage.raw"))
        native.read()
        template = "app/templates/probe.html"
        self.assertIn(template, native.measured_files())
        self.assertTrue(
            any(abs(line) > 1 for arc in native.arcs(template) for line in arc)
        )
        coverage = shards.read_json(output / "coverage.json")
        self.assertEqual(coverage["totals"]["percent_covered"], 100)


if __name__ == "__main__":
    unittest.main()
