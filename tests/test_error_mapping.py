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
    cancel_survey,
    check_balance,
    check_survey,
    create_survey,
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
            "cost_usd": 2.50,
        }
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = cancel_survey("job_x")
        client.cancel_job.assert_called_once_with("job_x")
        self.assertIn("Cancelled survey job_x", out)
        self.assertIn("Status: cancelled", out)
        self.assertIn("is_paused: true", out)
        self.assertIn("Settled cost: $2.50.", out)

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
            "cost_usd": 0.50,
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

    def test_402_insufficient_balance_unchanged(self):
        err = DatapointAPIError(402, {"needed_usd": 5.0, "available_usd": 1.5})
        client = self._client_raising(err)
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = create_survey({"datapoints": [], "task_type": "comparison"})
        self.assertIn("Insufficient balance", out)
        self.assertIn("$5.00", out)
        self.assertIn("$1.50", out)


class CheckBalanceTests(unittest.TestCase):
    def _balance_dict(self) -> dict:
        return {"available_usd": 12.50, "reserved_usd": 1.25, "total_purchased_usd": 50.0}

    def test_renders_per_response_rate_when_pricing_succeeds(self):
        client = mock.Mock()
        client.get_balance.return_value = self._balance_dict()
        client.get_pricing.return_value = {"per_response_usd": 0.0500}
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_balance()
        self.assertIn("Available: $12.50", out)
        self.assertIn("Per-response rate: $0.0500", out)

    def test_omits_rate_line_when_pricing_404s(self):
        client = mock.Mock()
        client.get_balance.return_value = self._balance_dict()
        client.get_pricing.side_effect = DatapointAPIError(404, "Not Found")
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_balance()
        self.assertIn("Available: $12.50", out)
        self.assertNotIn("Per-response rate", out)

    def test_omits_rate_line_when_pricing_response_missing_field(self):
        client = mock.Mock()
        client.get_balance.return_value = self._balance_dict()
        client.get_pricing.return_value = {}
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_balance()
        self.assertNotIn("Per-response rate", out)

    def test_omits_rate_line_when_pricing_per_response_usd_null(self):
        client = mock.Mock()
        client.get_balance.return_value = self._balance_dict()
        client.get_pricing.return_value = {"per_response_usd": None}
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_balance()
        self.assertNotIn("Per-response rate", out)

    def test_omits_rate_line_on_non_404_pricing_error(self):
        client = mock.Mock()
        client.get_balance.return_value = self._balance_dict()
        client.get_pricing.side_effect = DatapointAPIError(500, "internal error")
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_balance()
        self.assertIn("Available: $12.50", out)
        self.assertNotIn("Per-response rate", out)
        self.assertNotIn("internal error", out)

    def test_balance_failure_still_short_circuits(self):
        client = mock.Mock()
        client.get_balance.side_effect = DatapointAPIError(401, "unauthorized")
        with mock.patch("mcp_server.server._get_client", return_value=client):
            out = check_balance()
        self.assertIn("Error", out)
        client.get_pricing.assert_not_called()


if __name__ == "__main__":
    unittest.main()
