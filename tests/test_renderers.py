"""Tests for the pure renderer helpers in mcp_server.server.

stdlib unittest only (matches tests/test_plan_formatters.py). Run with:

    python -m unittest discover -s tests
"""

from __future__ import annotations

import unittest

from mcp_server.server import _format_check_survey


class FormatCheckSurveyStandaloneTests(unittest.TestCase):
    def _status(self, **overrides) -> dict:
        base = {
            "job_id": "job_abc",
            "name": "logo-pref",
            "status": "active",
            "task_type": "comparison",
            "total_datapoints": 10,
            "processing_datapoints": 0,
            "ready_datapoints": 8,
            "completed_datapoints": 4,
            "failed_datapoints": 0,
            "total_responses": 42,
            "max_responses_per_datapoint": 10,
            "cost_usd": 1.23,
            "errors": [],
        }
        base.update(overrides)
        return base

    def _comparison_results(self) -> dict:
        return {
            "task_type": "comparison",
            "results": [
                {
                    "datapoint_index": 0,
                    "context": None,
                    "consensus": "A",
                    "confidence": 0.7,
                    "votes": {"A": 7, "B": 3},
                    "total_responses": 10,
                }
            ],
        }

    def test_renders_status_header(self):
        out = _format_check_survey(self._status(), None)
        self.assertIn("Survey: logo-pref", out)
        self.assertIn("Status: active", out)
        self.assertIn("Progress: 42/100 responses", out)
        self.assertIn("Cost so far: $1.23", out)

    def test_renders_comparison_results(self):
        out = _format_check_survey(self._status(), self._comparison_results())
        self.assertIn("Datapoint 0", out)
        self.assertIn("Consensus: A", out)
        self.assertIn("70%", out)
        self.assertIn("'A': 7", out)


if __name__ == "__main__":
    unittest.main()
