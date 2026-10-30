import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluator
from evaluator import normalize_rows, normalize_sql, parse_model_json


class ParseModelJsonTests(unittest.TestCase):
    def test_parses_fenced_json_and_fills_optional_fields(self):
        parsed = parse_model_json('```json\n{"fixed_sql": "SELECT 1"}\n```')

        self.assertFalse(parsed["_parse_error"])
        self.assertEqual(parsed["fixed_sql"], "SELECT 1")
        self.assertEqual(parsed["explanation"], "")

    def test_malformed_json_is_not_executable(self):
        parsed = parse_model_json("not json")

        self.assertTrue(parsed["_parse_error"])
        self.assertEqual(parsed["fixed_sql"], "")
        self.assertEqual(parsed["explanation"], "not json")

    def test_non_string_sql_is_rejected(self):
        parsed = parse_model_json('{"fixed_sql": 123}')

        self.assertTrue(parsed["_parse_error"])
        self.assertEqual(parsed["fixed_sql"], "")

    def test_empty_response_is_rejected(self):
        self.assertTrue(parse_model_json(" ")["_parse_error"])


class NormalizationTests(unittest.TestCase):
    def test_sql_normalization_ignores_case_whitespace_and_trailing_semicolon(self):
        self.assertEqual(normalize_sql(" SELECT 1; "), normalize_sql("select 1"))

    def test_row_normalization_ignores_row_order_only(self):
        self.assertEqual(
            normalize_rows([[2, "b"], [1, "a"]]), [(1, "a"), (2, "b")]
        )
        self.assertNotEqual(normalize_rows([[1, 2]]), normalize_rows([[2, 1]]))


class BenchmarkRunTests(unittest.TestCase):
    def test_run_uses_project_paths_and_preserves_input_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_dir = root / "project"
            results_dir = project_dir / "results"
            work_dir = root / "different-working-directory"
            project_dir.mkdir()
            work_dir.mkdir()

            cases_path = project_dir / "test_cases.json"
            cases_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "T01",
                            "category": "syntax",
                            "broken_sql": "SELEC name FROM Students",
                            "reference_sql": "SELECT name FROM Students",
                            "expected_rows": [["Asha"], ["Ravi"], ["Meera"]],
                            "explanation_keywords": ["syntax"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            sample_db = project_dir / "benchmark.db"
            sample_db.write_bytes(b"keep this source database")

            def fake_generate_fix(_broken_sql, _schema):
                return {
                    "model": "offline-test",
                    "latency_seconds": 0.01,
                    "raw_response": json.dumps(
                        {
                            "error_type": "syntax",
                            "explanation": "A syntax error needs correction.",
                            "fixed_sql": "SELECT name FROM Students",
                            "assumptions": "",
                        }
                    ),
                }

            original_cwd = Path.cwd()
            try:
                os.chdir(work_dir)
                with (
                    patch.object(evaluator, "PROJECT_DIR", project_dir),
                    patch.object(evaluator, "RESULTS_DIR", results_dir),
                    patch.object(evaluator, "generate_fix", side_effect=fake_generate_fix),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    evaluator.run_benchmark()
            finally:
                os.chdir(original_cwd)

            self.assertEqual(sample_db.read_bytes(), b"keep this source database")
            self.assertTrue(cases_path.exists())
            self.assertTrue((results_dir / "detailed_results.csv").exists())
            self.assertTrue((results_dir / "summary_metrics.csv").exists())
            self.assertTrue((results_dir / "category_metrics.csv").exists())
            self.assertTrue((results_dir / "benchmark.db").exists())


if __name__ == "__main__":
    unittest.main()
