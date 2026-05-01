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


from mcp_server.server import _render_aggregation


class RenderAggregationTests(unittest.TestCase):
    def test_comparison_renders_consensus_votes_confidence(self):
        agg = {
            "consensus": "A",
            "confidence": 0.7,
            "votes": {"A": 7, "B": 3},
            "total_responses": 10,
        }
        out = "\n".join(_render_aggregation(agg, "comparison"))
        self.assertIn("Consensus: A", out)
        self.assertIn("70%", out)
        self.assertIn("'A': 7", out)
        self.assertIn("Responses: 10", out)

    def test_multiple_choice_renders_like_comparison(self):
        agg = {
            "consensus": "smooth",
            "confidence": 0.6,
            "votes": {"smooth": 6, "jittery": 4},
            "total_responses": 10,
        }
        out = "\n".join(_render_aggregation(agg, "multiple_choice"))
        self.assertIn("Consensus: smooth", out)
        self.assertIn("'smooth': 6", out)

    def test_rating_renders_mean_median_distribution(self):
        agg = {
            "mean": 3.7,
            "median": 4,
            "distribution": {"3": 4, "4": 3, "5": 1},
            "total_responses": 8,
        }
        out = "\n".join(_render_aggregation(agg, "rating"))
        self.assertIn("Mean: 3.70", out)
        self.assertIn("Median: 4", out)
        self.assertIn("'3': 4", out)
        self.assertIn("Responses: 8", out)

    def test_ranking_renders_order_and_average_ranks(self):
        agg = {
            "ranking_order": ["video_2", "video_1", "video_3"],
            "average_ranks": {"video_1": 2.0, "video_2": 1.2, "video_3": 2.8},
            "total_responses": 5,
        }
        out = "\n".join(_render_aggregation(agg, "ranking"))
        self.assertIn("Ranking: ['video_2', 'video_1', 'video_3']", out)
        self.assertIn("'video_2': 1.2", out)
        self.assertIn("Responses: 5", out)

    def test_falls_back_to_field_detection_when_task_type_absent(self):
        agg = {"mean": 4.1, "median": 4, "total_responses": 7}
        out = "\n".join(_render_aggregation(agg, None))
        self.assertIn("Mean: 4.10", out)
        self.assertIn("Responses: 7", out)

    def test_missing_optional_fields_does_not_crash(self):
        agg = {"consensus": "A", "total_responses": 3}
        out = "\n".join(_render_aggregation(agg, "comparison"))
        self.assertIn("Consensus: A", out)
        self.assertIn("Responses: 3", out)

    def test_indent_is_applied_to_every_line(self):
        agg = {"consensus": "A", "votes": {"A": 1}, "total_responses": 1}
        lines = _render_aggregation(agg, "comparison", indent="    ")
        for line in lines:
            self.assertTrue(line.startswith("    "), f"line missing indent: {line!r}")


class FormatCheckSurveyChainTests(unittest.TestCase):
    def _status(self) -> dict:
        return {
            "job_id": "job_chain",
            "name": "vid-quality-chain",
            "status": "active",
            "task_type": "chain",
            "total_datapoints": 1,
            "processing_datapoints": 0,
            "ready_datapoints": 1,
            "completed_datapoints": 1,
            "failed_datapoints": 0,
            "total_responses": 18,
            "max_responses_per_datapoint": 10,
            "cost_usd": 0.36,
            "errors": [],
        }

    def _chain_results(self) -> dict:
        return {
            "task_type": "chain",
            "results": [
                {
                    "datapoint_index": 0,
                    "context": None,
                    "steps": [
                        {
                            "step_index": 0,
                            "task_type": "multiple_choice",
                            "votes": {"yes": 8, "no": 2},
                            "total_responses": 10,
                            "consensus": "yes",
                            "confidence": 0.8,
                        },
                        {
                            "step_index": 1,
                            "task_type": "rating",
                            "mean": 3.7,
                            "median": 4,
                            "distribution": {"3": 4, "4": 3, "5": 1},
                            "total_responses": 8,
                        },
                    ],
                }
            ],
        }

    def test_chain_results_render_per_step_with_indent(self):
        out = _format_check_survey(self._status(), self._chain_results())
        self.assertIn("Datapoint 0", out)
        self.assertIn("Step 0 [multiple_choice]", out)
        self.assertIn("Step 1 [rating]", out)
        # Per-step aggregation deeper indent (six spaces)
        self.assertIn("      Consensus: yes", out)
        self.assertIn("      Mean: 3.70", out)
        # Drop-off across steps is visible (10 -> 8)
        self.assertIn("      Responses: 10", out)
        self.assertIn("      Responses: 8", out)


class FormatCheckSurveyStatusBlockTests(unittest.TestCase):
    def _status(self, **overrides) -> dict:
        base = {
            "job_id": "job_x",
            "name": "n",
            "status": "active",
            "task_type": "comparison",
            "total_datapoints": 12,
            "processing_datapoints": 3,
            "ready_datapoints": 9,
            "completed_datapoints": 4,
            "failed_datapoints": 0,
            "total_responses": 0,
            "max_responses_per_datapoint": 10,
            "cost_usd": 0.0,
            "errors": [],
        }
        base.update(overrides)
        return base

    def test_paused_flag_appended_to_status_line(self):
        out = _format_check_survey(self._status(is_paused=True), None)
        self.assertIn("Status: active (paused)", out)

    def test_paused_absent_does_not_modify_status_line(self):
        out = _format_check_survey(self._status(), None)
        self.assertIn("Status: active", out)
        self.assertNotIn("(paused)", out)

    def test_active_count_excludes_completed(self):
        # ready=9, completed=4, so active should be 5
        out = _format_check_survey(self._status(), None)
        self.assertIn("active: 5", out)
        self.assertIn("completed: 4", out)

    def test_queued_count_surfaces_processing_datapoints(self):
        out = _format_check_survey(self._status(), None)
        self.assertIn("queued: 3", out)


if __name__ == "__main__":
    unittest.main()
