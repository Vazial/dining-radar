import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MUTATION_GATE_PATH = PROJECT_ROOT / "tools" / "check_mutation_score.py"
MUTATION_WORKFLOW_PATH = PROJECT_ROOT.parents[1] / ".github" / "workflows" / "ci-dining-radar.yml"


def load_mutation_gate_module():
    spec = importlib.util.spec_from_file_location("mutation_score_gate", MUTATION_GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MutationScoreGateTests(SimpleTestCase):
    def _assert_pull_request_mutation_command_is_supported(
        self, workflow: str, pytest_help: str
    ) -> None:
        self.assertNotIn("--diff", workflow)
        self.assertIn('--gremlin-targets="$MUTATION_TARGETS"', workflow)
        self.assertIn("s#^projects/dining-radar/##p", workflow)
        self.assertIn("grep -E '^src/.*\\.py$'", workflow)
        self.assertIn("--gremlin-targets=GREMLIN_TARGETS", pytest_help)

    def test_machine_report_score_is_loaded_as_a_number(self):
        gate = load_mutation_gate_module()
        report_path = PROJECT_ROOT / ".runtime" / "synthetic-mutation-report.json"
        report_path.parent.mkdir(exist_ok=True)
        self.addCleanup(report_path.unlink, missing_ok=True)
        report_path.write_text(json.dumps({"summary": {"percentage": 87.5}}), encoding="utf-8")

        self.assertEqual(gate.mutation_score(report_path), 87.5)

    def test_boolean_is_not_accepted_as_a_numeric_score(self):
        gate = load_mutation_gate_module()
        report_path = PROJECT_ROOT / ".runtime" / "synthetic-mutation-report.json"
        report_path.parent.mkdir(exist_ok=True)
        self.addCleanup(report_path.unlink, missing_ok=True)
        report_path.write_text(json.dumps({"summary": {"percentage": True}}), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "must be numeric"):
            gate.mutation_score(report_path)

    def test_pull_request_mutation_uses_a_supported_target_option(self):
        workflow = MUTATION_WORKFLOW_PATH.read_text(encoding="utf-8")
        help_result = subprocess.run(
            [sys.executable, "-m", "pytest", "--help"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        self._assert_pull_request_mutation_command_is_supported(workflow, help_result.stdout)

        # Fault injection: putting the removed --diff option back in the
        # workflow must fail this test before CI can accept the change.
        injected_workflow = workflow.replace(
            '--gremlin-targets="$MUTATION_TARGETS"', '--diff "$MUTATION_DIFF"'
        )
        with self.assertRaises(AssertionError):
            self._assert_pull_request_mutation_command_is_supported(
                injected_workflow, help_result.stdout
            )
