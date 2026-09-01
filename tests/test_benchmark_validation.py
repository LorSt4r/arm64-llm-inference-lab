import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


inference = load_module("benchmark_inference", "scripts/benchmark_inference.py")
quality = load_module("benchmark_llm", "scripts/benchmark_llm.py")


class InferenceHelpersTest(unittest.TestCase):
    def test_prefill_payload_changes_nonce(self):
        first = inference.prefill_payload("model", 16)
        second = inference.prefill_payload("model", 16)
        self.assertNotEqual(first["messages"][0]["content"], second["messages"][0]["content"])

    def test_memory_summary_reports_range_and_deltas(self):
        samples = [
            {"rss_kb": 10, "process_major_faults": 2},
            {"rss_kb": 15, "process_major_faults": 5},
        ]
        summary = inference.summarize_samples(samples)
        self.assertEqual(summary["rss_kb_min"], 10)
        self.assertEqual(summary["rss_kb_max"], 15)
        self.assertEqual(summary["process_major_faults_delta"], 3)


class QualityValidationTest(unittest.TestCase):
    def test_structured_extraction_requires_exact_json_keys(self):
        case = next(case for case in quality.CASES if case["id"] == "structured_extraction")
        valid = '{"data":"12 agosto 2026","decisione":"mantenere","azione":"tre test"}'
        invalid = '```json\n' + valid + '\n```'
        self.assertTrue(all(quality.validate_response(case, valid).values()))
        self.assertFalse(quality.validate_response(case, invalid)["valid_json_only"])


if __name__ == "__main__":
    unittest.main()
