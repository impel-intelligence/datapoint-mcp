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
    check_balance,
    create_survey,
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
