"""Tests for ``plan_survey``'s output formatters.

Uses stdlib unittest so the MCP package can stay pytest-free — run with:

    python -m unittest discover -s tests
"""

from __future__ import annotations

import unittest

from mcp_server.server import (
    _format_audience_targeting,
    _format_chain_plan_output,
    _format_skip_if,
    _format_standalone_plan_output,
)


class StandaloneFormatterTests(unittest.TestCase):
    def test_standalone_shows_task_type_and_cost(self):
        plan = {
            "task_type": "comparison",
            "datapoints": [{}, {}, {}],
            "max_responses_per_datapoint": 10,
        }
        out = "\n".join(_format_standalone_plan_output(plan, "A comparison survey.", 0.09, []))
        self.assertIn("Survey Plan Ready", out)
        self.assertIn("Task type: comparison", out)
        self.assertIn("Datapoints: 3", out)
        self.assertIn("Responses per datapoint: 10", out)
        self.assertIn("Estimated cost: $0.09", out)
        self.assertIn("WAIT for explicit confirmation", out)

    def test_standalone_warnings_rendered(self):
        out = "\n".join(_format_standalone_plan_output({}, "s", 0.0, ["sample too small", "watch for bias"]))
        self.assertIn("Warnings:", out)
        self.assertIn("sample too small", out)
        self.assertIn("watch for bias", out)


def _make_chain_plan(**overrides) -> dict:
    """Two-step chain test fixture: MC screener with skip_if → rating."""
    plan = {
        "steps": [
            {
                "task_type": "multiple_choice",
                "instruction": "Could you understand the speaker?",
                "response_options": {"mode": "single"},
                "skip_if": {"predicate": {"==": [{"var": "choice"}, "opt_no"]}},
            },
            {
                "task_type": "rating",
                "instruction": "Rate the quality.",
                "response_options": {"scale": [1, 2, 3, 4, 5]},
            },
        ],
        "datapoints": [{}, {}],
        "max_responses_per_datapoint": 8,
    }
    plan.update(overrides)
    return plan


class ChainFormatterTests(unittest.TestCase):
    def test_chain_header_shows_length_and_datapoint_count(self):
        out = "\n".join(_format_chain_plan_output(_make_chain_plan(), "Chain summary", 0.48, []))
        self.assertIn("Chain Survey Plan Ready", out)
        self.assertIn("Chain length: 2 step(s) in order", out)
        self.assertIn("Datapoints: 2 (each walked by up to 8 annotators)", out)
        self.assertIn("Estimated cost: $0.48 (upper bound — partial walks cost less)", out)

    def test_chain_structure_renders_steps_in_list_order(self):
        out = "\n".join(_format_chain_plan_output(_make_chain_plan(), "s", 0.1, []))

        q1_pos = out.index("1. [multiple_choice]")
        q2_pos = out.index("2. [rating]")
        self.assertLess(q1_pos, q2_pos, "chain steps must render in list order")

    def test_skip_if_predicate_rendered_inline(self):
        out = "\n".join(_format_chain_plan_output(_make_chain_plan(), "s", 0.1, []))
        self.assertIn("↳ skip_if:", out)
        self.assertIn('{"==": [{"var": "choice"}, "opt_no"]}', out)

    def test_no_skip_if_on_any_step_skips_section(self):
        plan = _make_chain_plan()
        plan["steps"][0].pop("skip_if", None)
        out = "\n".join(_format_chain_plan_output(plan, "s", 0.1, []))
        self.assertNotIn("↳ skip_if:", out)

    def test_cost_upper_bound_note_in_confirmation(self):
        out = "\n".join(_format_chain_plan_output(_make_chain_plan(), "s", 0.1, []))
        self.assertIn("upper bound", out)
        self.assertIn("$0.10", out)

    def test_chain_warnings_passthrough(self):
        out = "\n".join(
            _format_chain_plan_output(
                _make_chain_plan(),
                "s",
                0.1,
                ["sample size may be small for the screening step"],
            )
        )
        self.assertIn("sample size may be small for the screening step", out)

    def test_response_options_inline_with_question(self):
        out = "\n".join(_format_chain_plan_output(_make_chain_plan(), "s", 0.1, []))
        self.assertIn("options: {'mode': 'single'}", out)
        self.assertIn("options: {'scale': [1, 2, 3, 4, 5]}", out)


class SkipIfFormatterTests(unittest.TestCase):
    def test_when_answer_in(self):
        self.assertEqual(
            _format_skip_if({"when_answer_in": ["opt_no", "opt_maybe"]}),
            "answer in ['opt_no', 'opt_maybe']",
        )

    def test_when_answer_equals(self):
        self.assertEqual(
            _format_skip_if({"when_answer_equals": "opt_no"}),
            "answer == 'opt_no'",
        )

    def test_predicate(self):
        out = _format_skip_if({"predicate": {"<": [{"var": "rating"}, "3"]}})
        self.assertIn("predicate", out)
        self.assertIn('"<"', out)


class AudienceTargetingFormatterTests(unittest.TestCase):
    def test_no_targeting_fields_returns_empty(self):
        self.assertEqual(_format_audience_targeting({}), [])
        self.assertEqual(_format_audience_targeting({"annotator_filter": None}), [])
        self.assertEqual(_format_audience_targeting({"annotator_distribution": []}), [])

    def test_filter_only(self):
        out = _format_audience_targeting({"annotator_filter": {"country": ["US", "CA"]}})
        self.assertEqual(out, ["Targeting: country in [US, CA]"])

    def test_filter_with_multiple_columns_joined_with_semicolons(self):
        out = _format_audience_targeting(
            {"annotator_filter": {"country": ["US"], "privacy_tor": [False]}}
        )
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("Targeting:"))
        self.assertIn("country in [US]", out[0])
        self.assertIn("privacy_tor in [false]", out[0])
        self.assertIn(";", out[0])

    def test_distribution_only(self):
        out = _format_audience_targeting({"annotator_distribution": ["country", "is_eu"]})
        self.assertEqual(out, ["Balanced by: country, is_eu"])

    def test_filter_and_distribution_both_rendered(self):
        out = _format_audience_targeting(
            {
                "annotator_filter": {"is_eu": [True]},
                "annotator_distribution": ["country"],
            }
        )
        self.assertEqual(len(out), 2)
        self.assertIn("Targeting:", out[0])
        self.assertIn("Balanced by:", out[1])

    def test_unknown_column_passes_through_without_validation(self):
        """Renderer must stay generic — the planner enforces the column allow-list,
        not the MCP. Adding columns server-side should not need a client release."""
        out = _format_audience_targeting({"annotator_filter": {"future_column_xyz": ["v"]}})
        self.assertEqual(out, ["Targeting: future_column_xyz in [v]"])


class StandalonePlanWithTargetingTests(unittest.TestCase):
    def test_standalone_renders_targeting_when_present(self):
        plan = {
            "task_type": "rating",
            "datapoints": [{}],
            "max_responses_per_datapoint": 10,
            "annotator_filter": {"country": ["US"]},
            "annotator_distribution": ["country"],
        }
        out = "\n".join(_format_standalone_plan_output(plan, "s", 0.03, []))
        self.assertIn("Targeting: country in [US]", out)
        self.assertIn("Balanced by: country", out)

    def test_standalone_omits_targeting_when_absent(self):
        plan = {"task_type": "rating", "datapoints": [{}], "max_responses_per_datapoint": 10}
        out = "\n".join(_format_standalone_plan_output(plan, "s", 0.03, []))
        self.assertNotIn("Targeting:", out)
        self.assertNotIn("Balanced by:", out)


class ChainPlanWithTargetingTests(unittest.TestCase):
    def test_chain_renders_targeting_above_chain_structure(self):
        plan = _make_chain_plan(annotator_filter={"is_eu": [True]})
        out = "\n".join(_format_chain_plan_output(plan, "s", 0.03, []))
        targeting_pos = out.index("Targeting:")
        structure_pos = out.index("Chain structure:")
        self.assertLess(targeting_pos, structure_pos)

    def test_chain_omits_targeting_when_absent(self):
        out = "\n".join(_format_chain_plan_output(_make_chain_plan(), "s", 0.03, []))
        self.assertNotIn("Targeting:", out)
        self.assertNotIn("Balanced by:", out)


if __name__ == "__main__":
    unittest.main()
