"""Tests for the DatapointClient HTTP wrapper.

stdlib unittest only — uses unittest.mock to capture _request calls without
hitting the network.
"""

from __future__ import annotations

import unittest
from unittest import mock

from mcp_server.client import DatapointClient


def _make_client() -> DatapointClient:
    return DatapointClient(api_key="dp_live_test", base_url="https://example.test/v1")


class GetJobResponsesParamsTests(unittest.TestCase):
    def test_default_call_omits_include_flags(self):
        client = _make_client()
        with mock.patch.object(client, "_request", return_value={}) as req:
            client.get_job_responses("job_x", page=2, per_page=50)
        req.assert_called_once_with(
            "GET", "/jobs/job_x/responses", params={"page": 2, "per_page": 50}
        )

    def test_include_abandoned_propagates_as_query_param(self):
        client = _make_client()
        with mock.patch.object(client, "_request", return_value={}) as req:
            client.get_job_responses("job_x", include_abandoned=True)
        params = req.call_args.kwargs["params"]
        self.assertTrue(params.get("include_abandoned"))
        self.assertNotIn("include_in_progress", params)

    def test_include_in_progress_propagates_as_query_param(self):
        client = _make_client()
        with mock.patch.object(client, "_request", return_value={}) as req:
            client.get_job_responses("job_x", include_in_progress=True)
        params = req.call_args.kwargs["params"]
        self.assertTrue(params.get("include_in_progress"))
        self.assertNotIn("include_abandoned", params)

    def test_both_flags_propagate(self):
        client = _make_client()
        with mock.patch.object(client, "_request", return_value={}) as req:
            client.get_job_responses(
                "job_x", include_abandoned=True, include_in_progress=True
            )
        params = req.call_args.kwargs["params"]
        self.assertTrue(params.get("include_abandoned"))
        self.assertTrue(params.get("include_in_progress"))


class CancelJobTests(unittest.TestCase):
    def test_cancel_job_posts_to_cancel_path(self):
        client = _make_client()
        with mock.patch.object(client, "_request", return_value={}) as req:
            client.cancel_job("job_x")
        req.assert_called_once_with("POST", "/jobs/job_x/cancel")

    def test_cancel_job_returns_request_payload(self):
        client = _make_client()
        payload = {"job_id": "job_x", "status": "cancelled", "is_paused": True, "cost_credits": 123}
        with mock.patch.object(client, "_request", return_value=payload):
            result = client.cancel_job("job_x")
        self.assertEqual(result, payload)


if __name__ == "__main__":
    unittest.main()
