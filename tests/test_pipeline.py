from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from spspec.core import build_offline_samples, canonicalize_sample, run_pipeline, search_counterexample


class PipelineTests(unittest.TestCase):
    def test_offline_samples_cover_all_tasks(self) -> None:
        samples = build_offline_samples()
        self.assertEqual(len(samples), 18)
        self.assertEqual({sample.task_id for sample in samples}, {"sortedness", "rate_limiter", "token_expiry"})

    def test_counterexample_exists_for_each_task_pair(self) -> None:
        samples = build_offline_samples()
        by_task = {}
        for sample in samples:
            by_task.setdefault(sample.task_id, []).append(sample)

        for task_id, task_samples in by_task.items():
            left = next(sample for sample in task_samples if sample.model == "gpt-4o")
            right = next(sample for sample in task_samples if sample.model == "gpt-3.5-turbo")
            witness = search_counterexample(left, right)
            self.assertIsNotNone(witness, task_id)

    def test_end_to_end_pipeline_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            report = run_pipeline(output_dir=output_dir, live=False)

            html_path = output_dir / "report.html"
            pdf_path = output_dir / "report.pdf"
            results_path = output_dir / "results.json"
            raw_path = output_dir / "spec_samples.json"
            normalized_path = output_dir / "normalized_samples.json"

            self.assertTrue(html_path.exists())
            self.assertTrue(pdf_path.exists())
            self.assertTrue(results_path.exists())
            self.assertTrue(raw_path.exists())
            self.assertTrue(normalized_path.exists())

            html = html_path.read_text(encoding="utf-8")
            self.assertIn("Cross-Model Spec Comparison", html)
            self.assertIn("Sortedness Property", html)
            self.assertIn("Token-Bucket Rate Limiter", html)
            self.assertIn("Token Expiry Semantics", html)

            pdf_header = pdf_path.read_bytes()[:8]
            self.assertEqual(pdf_header, b"%PDF-1.4")

            self.assertEqual(report["sample_count"], 18)
            self.assertEqual(len(report["tasks"]), 3)

            results = json.loads(results_path.read_text(encoding="utf-8"))
            self.assertEqual(results["sample_count"], 18)


if __name__ == "__main__":
    unittest.main()
