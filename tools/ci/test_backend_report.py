"""Contratos de evidencia con pytest y cobertura reales sobre código sintético."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("backend_report.py")
SPEC = importlib.util.spec_from_file_location("backend_report", SCRIPT)
backend_report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend_report)


class BackendReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="factuflow-backend-report-")
        cls.root = Path(cls.temporary.name).resolve()
        cls.project = cls.root / "project"
        (cls.project / "app").mkdir(parents=True)
        (cls.project / "tests").mkdir()
        (cls.project / "app/__init__.py").write_text("", encoding="utf-8")
        (cls.project / "tests/__init__.py").write_text("", encoding="utf-8")
        (cls.project / "app/calc.py").write_text(
            "def sign(value):\n"
            "    if value:\n"
            "        return 1\n"
            "    return 0\n",
            encoding="utf-8",
        )
        (cls.project / "tests/test_probe.py").write_text(
            "import pytest\n"
            "from app.calc import sign\n"
            "@pytest.mark.parametrize('value', [True, False])\n"
            "def test_sign(value):\n"
            "    assert sign(value) == int(value)\n",
            encoding="utf-8",
        )
        (cls.project / "pytest.ini").write_text(
            "[pytest]\n"
            "addopts = --cov=app --cov-branch --cov-report=term --cov-fail-under=69\n"
            "filterwarnings = error\n"
            "asyncio_default_fixture_loop_scope = session\n"
            "asyncio_default_test_loop_scope = session\n",
            encoding="utf-8",
        )
        cls.reference = cls.root / "reference"
        result = cls.run_cli("run", "--output-dir", str(cls.reference))
        if result.returncode:
            cls.temporary.cleanup()
            raise AssertionError(result.stdout + result.stderr)
        cls.execution = json.loads(
            (cls.reference / "execution.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    @classmethod
    def run_cli(cls, *arguments):
        command = [sys.executable, str(SCRIPT), *arguments]
        if arguments[0] == "run":
            command.extend(["--source-sha", "a" * 40, "--run-id", "synthetic"])
        env = os.environ.copy()
        env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        env.pop("PYTEST_ADDOPTS", None)
        return subprocess.run(
            command,
            cwd=cls.project,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )

    def candidate(self):
        directory = Path(tempfile.mkdtemp(dir=self.root, prefix="candidate-"))
        shutil.copytree(self.reference, directory, dirs_exist_ok=True)
        return directory

    def test_real_run_records_every_case_phase_and_artifact(self):
        self.assertEqual(len(self.execution["collected"]), 2)
        self.assertEqual(len(self.execution["results"]), 6)
        self.assertEqual(self.execution["source_sha"], "a" * 40)
        self.assertTrue(self.execution["collector_sha256"])
        backend_report.validate_execution(self.execution)
        backend_report.validate_artifacts(self.reference)
        data = json.loads((self.reference / "coverage.json").read_text())
        self.assertTrue(data["meta"]["branch_coverage"])
        self.assertEqual(data["totals"]["percent_covered"], 100)

    def test_missing_duplicate_failed_cancelled_or_skipped_results_are_rejected(self):
        for mutation in (
            "missing_phase",
            "duplicate_phase",
            "duplicate_case",
            "empty",
            "failed",
            "cancelled",
            "skipped",
            "xfail",
        ):
            with self.subTest(mutation=mutation):
                report = copy.deepcopy(self.execution)
                if mutation == "missing_phase":
                    report["results"].pop()
                elif mutation == "duplicate_phase":
                    report["results"].append(report["results"][0])
                elif mutation == "duplicate_case":
                    report["collected"].append(report["collected"][0])
                elif mutation == "empty":
                    report["collected"] = []
                    report["results"] = []
                elif mutation == "cancelled":
                    report["exit_code"] = 2
                elif mutation == "xfail":
                    report["results"][1]["was_xfail"] = True
                else:
                    report["results"][1]["outcome"] = mutation
                with self.assertRaises(ValueError):
                    backend_report.validate_execution(report)

    def test_identical_evidence_accepts_different_commit_with_same_application(self):
        candidate = self.candidate()
        report = copy.deepcopy(self.execution)
        report["source_sha"] = "b" * 40
        (candidate / "execution.json").write_text(json.dumps(report))
        result = backend_report.compare_reports(self.reference, candidate)
        self.assertEqual(result["cases_preserved"], 2)
        self.assertEqual(result["lost_branches"], 0)

    def test_lost_line_or_branch_fails_even_with_unchanged_percentages(self):
        for key in ("executed_lines", "executed_branches"):
            with self.subTest(key=key):
                candidate = self.candidate()
                path = candidate / "coverage.json"
                data = json.loads(path.read_text())
                data["files"]["app/calc.py"][key].pop()
                path.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, "Se perdió cobertura"):
                    backend_report.compare_reports(self.reference, candidate)

    def test_missing_native_report_or_changed_environment_fails(self):
        for mutation in (
            "missing_native",
            "environment",
            "application",
            "inventory",
            "configuration",
        ):
            with self.subTest(mutation=mutation):
                candidate = self.candidate()
                if mutation == "missing_native":
                    (candidate / "coverage.raw").unlink()
                else:
                    report = copy.deepcopy(self.execution)
                    if mutation == "environment":
                        report["environment"]["python"] = "different"
                    elif mutation == "application":
                        report["application_fingerprint"] = "different"
                    elif mutation == "configuration":
                        report["coverage_config_sha256"] = "different"
                    else:
                        removed = report["collected"].pop()
                        report["results"] = [
                            r for r in report["results"] if r["nodeid"] != removed
                        ]
                    (candidate / "execution.json").write_text(json.dumps(report))
                with self.assertRaises(ValueError):
                    backend_report.compare_reports(self.reference, candidate)

    def test_cli_refuses_to_reuse_stale_output(self):
        result = self.run_cli("run", "--output-dir", str(self.reference))
        self.assertNotEqual(result.returncode, 0)

    def test_new_file_is_collected_and_failed_assertion_remains_a_failure(self):
        extra = self.project / "tests/test_added.py"
        extra.write_text("def test_added():\n    assert False\n", encoding="utf-8")
        try:
            output = self.root / "failed"
            result = self.run_cli("run", "--output-dir", str(output))
            self.assertNotEqual(result.returncode, 0)
            report = json.loads((output / "execution.json").read_text())
            self.assertIn("tests/test_added.py::test_added", report["collected"])
            self.assertEqual(report["exit_code"], 1)
            self.assertTrue(any(r["outcome"] == "failed" for r in report["results"]))
        finally:
            extra.unlink()

    def test_coverage_gate_is_preserved_with_real_pytest(self):
        extra = self.project / "app/uncovered.py"
        extra.write_text(
            "def uncovered():\n" + "".join(f"    x{i} = {i}\n" for i in range(20)),
            encoding="utf-8",
        )
        try:
            output = self.root / "insufficient-coverage"
            result = self.run_cli("run", "--output-dir", str(output))
            self.assertNotEqual(result.returncode, 0)
            report = json.loads((output / "execution.json").read_text())
            self.assertTrue(all(r["outcome"] == "passed" for r in report["results"]))
            self.assertEqual(report["exit_code"], 1)
        finally:
            extra.unlink()


if __name__ == "__main__":
    unittest.main()
