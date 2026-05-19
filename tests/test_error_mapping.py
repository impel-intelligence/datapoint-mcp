"""Tests for the user-friendly error rendering in upload_media and create_survey,
and for the optional pricing line in check_balance.

stdlib unittest only — patches the MCP server's lazy `_get_client` so the
DatapointClient is replaced with a Mock that raises specific DatapointAPIErrors.
"""

from __future__ import annotations

import unittest
from unittest import mock

from mcp_server.client import DatapointAPIError
from mcp_server.server import (
    _describe_upload_error,
    add_credits,
    cancel_survey,
    check_balance,
    check_subscription,
    check_survey,
    create_survey,
    manage_billing,
    retry_failed_datapoints,
    upload_media,
)


class DescribeUploadErrorTests(unittest.TestCase):
    def test_413_media_too_large_renders_human_cap(self):
        err = DatapointAPIError(413, {"code": "media_too_large", "max_bytes": 20 * 1024 * 1024})
        self.assertEqual(
            _describe_upload_error(err),
            "file exceeds the upload cap (20 MB max)",
        )

    def test_413_without_max_bytes_falls_back(self):
        err = DatapointAPIError(413, {"code": "media_too_large"})
        self.assertEqual(_describe_upload_error(err), "file exceeds the upload cap")

    def test_other_error_falls_through_to_detail_string(self):
        err = DatapointAPIError(500, "internal error")
        self.assertEqual(_describe_upload_error(err), "internal error")

    def test_413_without_dict_detail_falls_through(self):
        err = DatapointAPIError(413, "Payload Too Large")
        self.assertEqual(_describe_upload_error(err), "Payload Too Large")


class UploadMediaErrorTests(unittest.TestCase):
    def test_413_renders_friendly_message_in_failed_block(self):
        client = mock.Mock()
        client.upload_media.side_effect = DatapointAPIError(
            413, {"code": "media_too_large", "max_bytes": 20 * 1024 * 1024}
        )
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = upload_media(["/tmp/big.mp4"])
        self.assertIn("file exceeds the upload cap (20 MB max)", out)
        self.assertNotIn("media_too_large", out)
        self.assertNotIn("max_bytes", out)


class UploadMediaSummaryTests(unittest.TestCase):
    def _ok_response(self, name: str) -> dict:
        return {
            "media": [
                {"filename": name, "media_ref": f"dp://media/{name}", "type": "image", "size_bytes": 1024}
            ]
        }

    def test_all_success_summary(self):
        client = mock.Mock()
        client.upload_media.side_effect = [self._ok_response("a.png"), self._ok_response("b.png")]
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = upload_media(["/tmp/a.png", "/tmp/b.png"])
        self.assertIn("Uploaded 2 files.", out)
        self.assertIn("dp://media/a.png", out)
        self.assertIn("dp://media/b.png", out)

    def test_partial_failure_summary(self):
        client = mock.Mock()
        client.upload_media.side_effect = [
            self._ok_response("a.png"),
            DatapointAPIError(413, {"code": "media_too_large", "max_bytes": 20 * 1024 * 1024}),
        ]
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = upload_media(["/tmp/a.png", "/tmp/big.mp4"])
        self.assertIn("Uploaded 1 of 2 files; 1 failed.", out)
        self.assertIn("dp://media/a.png", out)
        self.assertIn("/tmp/big.mp4: file exceeds the upload cap", out)

    def test_all_failure_summary(self):
        client = mock.Mock()
        client.upload_media.side_effect = [
            DatapointAPIError(500, "boom"),
            DatapointAPIError(500, "boom"),
        ]
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = upload_media(["/tmp/a.png", "/tmp/b.png"])
        self.assertIn("All 2 files failed to upload.", out)

    def test_no_files_returns_explanation(self):
        client = mock.Mock()
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = upload_media([])
        self.assertEqual(out, "No files provided.")
        client.upload_media.assert_not_called()


class RetryFailedDatapointsTests(unittest.TestCase):
    def test_retry_all_failed_datapoints(self):
        client = mock.Mock()
        client.retry_job.return_value = {
            "job_id": "job_x",
            "retried": 3,
            "datapoint_indices": [0, 4, 7],
        }
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = retry_failed_datapoints("job_x")
        client.retry_job.assert_called_once_with("job_x", datapoint_indices=None)
        self.assertIn("Re-queued 3 datapoints on survey job_x", out)
        self.assertIn("[0, 4, 7]", out)

    def test_retry_specific_indices_propagates(self):
        client = mock.Mock()
        client.retry_job.return_value = {
            "job_id": "job_x",
            "retried": 1,
            "datapoint_indices": [4],
        }
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = retry_failed_datapoints("job_x", datapoint_indices=[4])
        client.retry_job.assert_called_once_with("job_x", datapoint_indices=[4])
        self.assertIn("Re-queued 1 datapoint", out)

    def test_retry_when_nothing_failed(self):
        client = mock.Mock()
        client.retry_job.return_value = {
            "job_id": "job_x",
            "retried": 0,
            "datapoint_indices": [],
        }
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = retry_failed_datapoints("job_x")
        self.assertIn("No failed datapoints to retry", out)

    def test_retry_404_renders_not_found(self):
        client = mock.Mock()
        client.retry_job.side_effect = DatapointAPIError(404, "Job not found")
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = retry_failed_datapoints("job_x")
        self.assertIn("Survey not found: job_x", out)

    def test_retry_400_surfaces_backend_reason(self):
        client = mock.Mock()
        client.retry_job.side_effect = DatapointAPIError(400, "Job is not in a retriable state")
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = retry_failed_datapoints("job_x")
        self.assertIn("Cannot retry: Job is not in a retriable state", out)


class CancelSurveyTests(unittest.TestCase):
    def test_cancel_success_renders_settled_cost(self):
        client = mock.Mock()
        client.cancel_job.return_value = {
            "job_id": "job_x",
            "status": "cancelled",
            "is_paused": True,
            "cost_credits": 250,
        }
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = cancel_survey("job_x")
        client.cancel_job.assert_called_once_with("job_x")
        self.assertIn("Cancelled survey job_x", out)
        self.assertIn("Status: cancelled", out)
        self.assertIn("is_paused: true", out)
        self.assertIn("Settled cost: 250 credits.", out)

    def test_cancel_404_renders_not_found(self):
        client = mock.Mock()
        client.cancel_job.side_effect = DatapointAPIError(404, "Job not found")
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = cancel_survey("job_x")
        self.assertEqual(out, "Survey not found: job_x")

    def test_cancel_400_already_terminal_surfaces_backend_reason(self):
        client = mock.Mock()
        client.cancel_job.side_effect = DatapointAPIError(
            400, "Cannot cancel a job with status 'completed'."
        )
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = cancel_survey("job_x")
        self.assertIn("Cannot cancel:", out)
        self.assertIn("status 'completed'", out)

    def test_cancel_500_surfaces_detail(self):
        client = mock.Mock()
        client.cancel_job.side_effect = DatapointAPIError(500, "internal error")
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = cancel_survey("job_x")
        self.assertIn("Error: internal error", out)


class CheckSurveyAudienceTargetingTests(unittest.TestCase):
    def _status(self, **overrides) -> dict:
        base = {
            "job_id": "job_x",
            "name": "test-survey",
            "status": "active",
            "task_type": "comparison",
            "total_datapoints": 5,
            "processing_datapoints": 0,
            "ready_datapoints": 5,
            "completed_datapoints": 5,
            "failed_datapoints": 0,
            "total_responses": 10,
            "max_responses_per_datapoint": 2,
            "cost_credits": 50,
            "errors": [],
            "is_paused": False,
        }
        base.update(overrides)
        return base

    def test_renders_targeting_when_filter_present(self):
        client = mock.Mock()
        client.get_job_status.return_value = self._status(
            annotator_filter={"country": ["US"]},
        )
        client.get_job_results.return_value = {"results": [], "task_type": "comparison"}
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_survey("job_x")
        self.assertIn("Targeting: country in [US]", out)

    def test_renders_distribution_when_present(self):
        client = mock.Mock()
        client.get_job_status.return_value = self._status(
            annotator_distribution=["country", "is_eu"],
        )
        client.get_job_results.return_value = {"results": [], "task_type": "comparison"}
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_survey("job_x")
        self.assertIn("Balanced by: country, is_eu", out)

    def test_renders_response_options_when_present(self):
        client = mock.Mock()
        client.get_job_status.return_value = self._status(
            response_options={"options": ["yes", "no"]},
        )
        client.get_job_results.return_value = {"results": [], "task_type": "comparison"}
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_survey("job_x")
        self.assertIn("Response options:", out)
        self.assertIn("yes", out)

    def test_no_targeting_fields_omits_lines(self):
        client = mock.Mock()
        client.get_job_status.return_value = self._status()
        client.get_job_results.return_value = {"results": [], "task_type": "comparison"}
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_survey("job_x")
        self.assertNotIn("Targeting:", out)
        self.assertNotIn("Balanced by:", out)
        self.assertNotIn("Response options:", out)


class CreateSurveyErrorTests(unittest.TestCase):
    def _client_raising(self, exc: Exception) -> mock.Mock:
        client = mock.Mock()
        client.create_job.side_effect = exc
        return client

    def test_422_content_blocked_renders_reason_without_labels(self):
        err = DatapointAPIError(
            422,
            {
                "code": "content_blocked",
                "reason": "Promotes self-harm.",
                "labels": ["self_harm", "violence"],
            },
        )
        client = self._client_raising(err)
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = create_survey({"datapoints": [], "task_type": "comparison"})
        self.assertIn("Content review rejected this survey: Promotes self-harm.", out)
        self.assertNotIn("self_harm", out)
        self.assertNotIn("violence", out)
        self.assertNotIn("labels", out)

    def test_422_content_blocked_includes_field_when_present(self):
        err = DatapointAPIError(
            422,
            {"code": "content_blocked", "reason": "Disallowed.", "field": "instruction"},
        )
        client = self._client_raising(err)
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = create_survey({"datapoints": [], "task_type": "comparison"})
        self.assertIn("(in instruction)", out)

    def test_503_passes_through_backend_detail(self):
        err = DatapointAPIError(503, "Content moderation provider unavailable. Please retry.")
        client = self._client_raising(err)
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = create_survey({"datapoints": [], "task_type": "comparison"})
        self.assertIn("Service temporarily unavailable", out)
        self.assertIn("Please retry", out)

    def test_503_queue_conflict_detail_preserved(self):
        err = DatapointAPIError(503, "Failed to queue tasks. Please retry with a new name.")
        client = self._client_raising(err)
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = create_survey({"datapoints": [], "task_type": "comparison"})
        self.assertIn("Service temporarily unavailable", out)
        self.assertIn("retry with a new name", out)

    def test_402_insufficient_balance_renders_credit_amounts(self):
        err = DatapointAPIError(402, {"needed_credits": 500, "available_credits": 150})
        client = self._client_raising(err)
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = create_survey({"datapoints": [], "task_type": "comparison"})
        self.assertIn("Insufficient balance", out)
        self.assertIn("Need 500 credits", out)
        self.assertIn("have 150 credits", out)


class CheckBalanceTests(unittest.TestCase):
    def _balance_dict(self) -> dict:
        return {"available_credits": 1250, "reserved_credits": 125, "total_purchased_credits": 5000}

    def test_renders_per_response_rate_when_pricing_succeeds(self):
        client = mock.Mock()
        client.get_balance.return_value = self._balance_dict()
        client.get_pricing.return_value = {"credits_per_response": 5}
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_balance()
        self.assertIn("Available: 1250 credits", out)
        self.assertIn("Per-response rate: 5 credits", out)

    def test_omits_rate_line_when_pricing_404s(self):
        client = mock.Mock()
        client.get_balance.return_value = self._balance_dict()
        client.get_pricing.side_effect = DatapointAPIError(404, "Not Found")
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_balance()
        self.assertIn("Available: 1250 credits", out)
        self.assertNotIn("Per-response rate", out)

    def test_omits_rate_line_when_pricing_response_missing_field(self):
        client = mock.Mock()
        client.get_balance.return_value = self._balance_dict()
        client.get_pricing.return_value = {}
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_balance()
        self.assertNotIn("Per-response rate", out)

    def test_omits_rate_line_when_pricing_credits_per_response_null(self):
        client = mock.Mock()
        client.get_balance.return_value = self._balance_dict()
        client.get_pricing.return_value = {"credits_per_response": None}
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_balance()
        self.assertNotIn("Per-response rate", out)

    def test_omits_rate_line_on_non_404_pricing_error(self):
        client = mock.Mock()
        client.get_balance.return_value = self._balance_dict()
        client.get_pricing.side_effect = DatapointAPIError(500, "internal error")
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_balance()
        self.assertIn("Available: 1250 credits", out)
        self.assertNotIn("Per-response rate", out)
        self.assertNotIn("internal error", out)

    def test_balance_failure_still_short_circuits(self):
        client = mock.Mock()
        client.get_balance.side_effect = DatapointAPIError(401, "unauthorized")
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_balance()
        self.assertIn("Error", out)
        client.get_pricing.assert_not_called()


class AddCreditsSubscriptionGateTests(unittest.TestCase):
    def test_403_subscription_required_renders_message_and_tiers(self):
        client = mock.Mock()
        client.create_checkout.side_effect = DatapointAPIError(
            403,
            {
                "code": "subscription_required",
                "message": "Credit pack purchases require an active subscription.",
                "eligible_tiers": ["basic", "pro", "enterprise"],
            },
        )
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = add_credits(product_id="some_credit_pack")
        self.assertIn("Credit pack purchases require an active subscription.", out)
        self.assertIn("Available tiers: Basic, Pro, Enterprise.", out)
        self.assertIn("Call add_credits without a product_id", out)

    def test_403_without_tiers_still_renders(self):
        client = mock.Mock()
        client.create_checkout.side_effect = DatapointAPIError(
            403, {"code": "subscription_required", "message": "Subscription required."}
        )
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = add_credits(product_id="some_credit_pack")
        self.assertIn("Subscription required.", out)
        self.assertNotIn("Available tiers:", out)
        self.assertIn("Call add_credits without a product_id", out)

    def test_other_error_falls_through_unchanged(self):
        client = mock.Mock()
        client.create_checkout.side_effect = DatapointAPIError(500, "internal error")
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = add_credits()
        self.assertIn("Error creating checkout: internal error", out)

    def test_success_renders_checkout_url(self):
        client = mock.Mock()
        client.create_checkout.return_value = {"checkout_url": "https://pay.example.test/abc"}
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = add_credits()
        self.assertIn("https://pay.example.test/abc", out)
        self.assertIn("check_balance or check_subscription", out)


class ManageBillingTests(unittest.TestCase):
    def test_success_renders_portal_url(self):
        client = mock.Mock()
        client.create_portal_session.return_value = {
            "portal_url": "https://portal.example.test/sess_abc",
            "expires_at": "2026-05-20T00:00:00+00:00",
        }
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = manage_billing()
        self.assertIn("https://portal.example.test/sess_abc", out)
        # Internal-only fields must not leak.
        self.assertNotIn("expires_at", out)
        self.assertNotIn("2026-05-20", out)

    def test_404_no_billing_customer_renders_setup_hint(self):
        client = mock.Mock()
        client.create_portal_session.side_effect = DatapointAPIError(
            404,
            {"code": "no_billing_customer", "message": "Complete a checkout to set up billing first."},
        )
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = manage_billing()
        self.assertIn("No billing account yet", out)
        self.assertIn("Use add_credits to complete a checkout first", out)

    def test_500_renders_error_detail(self):
        client = mock.Mock()
        client.create_portal_session.side_effect = DatapointAPIError(500, "internal error")
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = manage_billing()
        self.assertIn("Error opening billing portal: internal error", out)


class CheckSubscriptionTests(unittest.TestCase):
    def _active_pro(self, **overrides) -> dict:
        base = {
            "tier": "pro",
            "status": "active",
            "current_period_start": "2026-05-15 00:00:00+00:00",
            "current_period_end": "2026-06-15 00:00:00+00:00",
            "cancel_at_period_end": False,
            "monthly_credits": 5000,
            "monthly_planner_allowance": 1000,
            "planner_allowance_remaining": 957,
            "credits_per_response_override": None,
            "rate_limit_rpm_override": None,
            "pending_tier_change": None,
            "pending_tier_effective_at": None,
        }
        base.update(overrides)
        return base

    def test_null_response_renders_no_subscription_hint(self):
        client = mock.Mock()
        client.get_subscription.return_value = None
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_subscription()
        self.assertIn("No active subscription", out)
        self.assertIn("Use add_credits", out)

    def test_active_pro_subscription_renders_tier_status_credits_renewal(self):
        client = mock.Mock()
        client.get_subscription.return_value = self._active_pro()
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_subscription()
        self.assertIn("Active subscription: Pro", out)
        self.assertIn("Status: Active", out)
        self.assertIn("Monthly credits: 5000", out)
        self.assertIn("Renews: 2026-06-15", out)
        self.assertIn("Use manage_billing", out)

    def test_canceling_subscription_renders_active_until(self):
        client = mock.Mock()
        client.get_subscription.return_value = self._active_pro(
            status="canceled_pending", cancel_at_period_end=True
        )
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_subscription()
        self.assertIn("Status: Canceling at end of period", out)
        self.assertIn("Active until: 2026-06-15", out)
        self.assertNotIn("Renews:", out)

    def test_past_due_renders_payment_past_due(self):
        client = mock.Mock()
        client.get_subscription.return_value = self._active_pro(status="past_due")
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_subscription()
        self.assertIn("Status: Payment past due", out)

    def test_business_logic_fields_are_hidden(self):
        client = mock.Mock()
        client.get_subscription.return_value = self._active_pro(
            credits_per_response_override=3,
            rate_limit_rpm_override=600,
            planner_allowance_remaining=42,
            monthly_planner_allowance=1000,
            pending_tier_change="basic",
            pending_tier_effective_at="2026-07-01 00:00:00+00:00",
        )
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_subscription()
        self.assertNotIn("override", out.lower())
        self.assertNotIn("planner", out.lower())
        self.assertNotIn("rate_limit", out.lower())
        self.assertNotIn("pending_tier", out.lower())
        self.assertNotIn("allowance", out.lower())

    def test_500_renders_error_detail(self):
        client = mock.Mock()
        client.get_subscription.side_effect = DatapointAPIError(500, "internal error")
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_subscription()
        self.assertIn("Error: internal error", out)


if __name__ == "__main__":
    unittest.main()
