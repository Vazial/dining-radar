import importlib.util
import json
from pathlib import Path

from django.test import SimpleTestCase

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MUTATION_GATE_PATH = PROJECT_ROOT / "tools" / "check_mutation_score.py"


def load_mutation_gate_module():
    spec = importlib.util.spec_from_file_location("mutation_score_gate", MUTATION_GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MutationScoreGateTests(SimpleTestCase):
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
