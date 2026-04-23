"""HTTP client wrapper for the Datapoint AI REST API.

Handles authentication, request formatting, and error handling.
The API key is never logged or included in error messages.
"""

import httpx

from mcp_server.config import get_api_key, get_base_url

REQUEST_TIMEOUT = 30.0
UPLOAD_TIMEOUT = 60.0
PLAN_TIMEOUT = 60.0


class DatapointAPIError(Exception):
    """Raised when the Datapoint API returns an error.

    ``detail`` is whatever the server put in its error body — a string for simple
    cases, a dict for structured errors like the survey planner's 422 response
    (``{"message": ..., "warnings": [...]}``). Callers that want to render
    structured errors nicely should check ``isinstance(e.detail, dict)``.
    """

    def __init__(self, status_code: int, detail):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API error {status_code}: {detail}")


class DatapointClient:
    """Synchronous HTTP client for the Datapoint AI API."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or get_api_key()
        self.base_url = (base_url or get_base_url()).rstrip("/")
        self._http = httpx.Client(timeout=REQUEST_TIMEOUT)

    def close(self):
        self._http.close()

    @property
    def is_authenticated(self) -> bool:
        return bool(self.api_key)

    def _headers(self, include_api_key: bool = True) -> dict:
        headers = {"Content-Type": "application/json"}
        if include_api_key and self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _request(self, method: str, path: str, auth: bool = True, **kwargs) -> dict:
        """Make an HTTP request and return the JSON response."""
        url = f"{self.base_url}{path}"
        resp = self._http.request(method, url, headers=self._headers(include_api_key=auth), **kwargs)

        if resp.status_code >= 400:
            try:
                body = resp.json()
                detail = body.get("detail", body.get("message", resp.text))
            except Exception:
                detail = resp.text
            raise DatapointAPIError(resp.status_code, detail)

        return resp.json()

    # ----- Billing -----

    def get_balance(self) -> dict:
        return self._request("GET", "/billing/balance")

    def create_checkout(self, product_id: str | None = None) -> dict:
        body = {}
        if product_id:
            body["product_id"] = product_id
        return self._request("POST", "/billing/checkout", json=body)

    # ----- Jobs / Surveys -----

    def create_job(self, payload: dict) -> dict:
        return self._request("POST", "/jobs", json=payload)

    def get_job_status(self, job_id: str) -> dict:
        return self._request("GET", f"/jobs/{job_id}")

    def get_job_results(self, job_id: str, page: int = 1, per_page: int = 100) -> dict:
        return self._request("GET", f"/jobs/{job_id}/results", params={"page": page, "per_page": per_page})

    def get_job_responses(self, job_id: str, page: int = 1, per_page: int = 100) -> dict:
        return self._request("GET", f"/jobs/{job_id}/responses", params={"page": page, "per_page": per_page})

    def list_jobs(self) -> dict:
        return self._request("GET", "/jobs")

    def plan_survey(self, description: str, preferences: dict | None = None) -> dict:
        body: dict = {"description": description}
        if preferences:
            body["preferences"] = preferences
        return self._request("POST", "/surveys/plan", json=body, timeout=PLAN_TIMEOUT)

    # ----- Media -----

    def upload_media(self, file_path: str) -> dict:
        import mimetypes
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        mime_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        with open(path, "rb") as f:
            resp = self._http.post(
                f"{self.base_url}/media",
                headers=headers,
                files={"files": (path.name, f, mime_type)},
                timeout=UPLOAD_TIMEOUT,
            )

        if resp.status_code >= 400:
            raise DatapointAPIError(resp.status_code, resp.text)

        return resp.json()

    # ----- Device Auth -----

    def device_auth_start(self) -> dict:
        return self._request("POST", "/auth/device/start", auth=False, json={})

    def device_auth_poll(self, device_code: str) -> dict:
        return self._request("POST", "/auth/device/poll", auth=False, json={"device_code": device_code})
